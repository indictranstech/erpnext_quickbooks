# -*- coding: utf-8 -*-
# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt



from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _,msgprint
import httplib
import urllib3
from urlparse import parse_qsl
import json
from rauth import OAuth1Session, OAuth1Service
from erpnext_quickbooks.pyqb.quickbooks import QuickBooks
from erpnext_quickbooks.exceptions import QuickbooksError
from time import strftime


class QuickbooksSettings(Document):
	pass

QUICKBOOKS_CLIENT_KEY = ""
QUICKBOOKS_CLIENT_SECRET = ""
authorize_url = ""
request_token = ""
request_token_secret = ""
access_token = ""
access_token_secret = ""
realm_id = ""
callback_url=""


@frappe.whitelist(allow_guest=True)
def First_callback(realmId,oauth_verifier):
	login_via_oauth2(realmId,oauth_verifier)

def login_via_oauth2(realmId,oauth_verifier):
	""" Store necessary token's to Setup service """
	global realm_id
	global access_token
	global access_token_secret
	quickbooks = QuickBooks(
       sandbox=True,
       consumer_key = QUICKBOOKS_CLIENT_KEY,
       consumer_secret = QUICKBOOKS_CLIENT_SECRET,
       minorversion=4
     )
	quickbooks.authorize_url = authorize_url
	quickbooks.request_token = request_token
	quickbooks.request_token_secret = request_token_secret
	quickbooks.company_id = realmId
	quickbooks.set_up_service()
 	quickbooks.get_access_tokens(oauth_verifier)
	realm_id = realmId
	access_token = quickbooks.access_token
	access_token_secret = quickbooks.access_token_secret 
	
	 
	select = """SELECT displayname FROM  Customer""" 
	data12 = quickbooks.query(select)
	msgprint(_(data12['QueryResponse']))
	return data12
 
@frappe.whitelist(allow_guest=True)
def quickbooks_authentication_popup(consumer_key,consumer_secret):
	""" Open new popup window to Connect Quickbooks App to Quickbooks sandbox Account """

	global authorize_url
	global request_token
	global request_token_secret
	global QUICKBOOKS_CLIENT_KEY
	global QUICKBOOKS_CLIENT_SECRET

	QUICKBOOKS_CLIENT_KEY = consumer_key
	QUICKBOOKS_CLIENT_SECRET = consumer_secret
	quickbooks = QuickBooks(
           sandbox=True,
           consumer_key = consumer_key,
           consumer_secret = consumer_secret,
           callback_url = 'http://'+ frappe.request.host + '/api/method/erpnext_quickbooks.erpnext_quickbooks.doctype.quickbooks_settings.quickbooks_settings.First_callback'
    )

	authorize_url = quickbooks.get_authorize_url()
	request_token = quickbooks.request_token
	request_token_secret = quickbooks.request_token_secret
	return authorize_url
	 
 
@frappe.whitelist()
def sync_quickbooks_data_erp():
	quickbooks_obj = QuickBooks(
        sandbox=True,
        consumer_key=QUICKBOOKS_CLIENT_KEY,
        consumer_secret=QUICKBOOKS_CLIENT_SECRET,
        access_token=access_token,
        access_token_secret=access_token_secret,
        company_id=realm_id,
        minorversion=4
    )

	customer_data = create_customer(quickbooks_obj)
	supplier_data = create_Supplier(quickbooks_obj)
	Employee_data = create_Employee(quickbooks_obj)
	if customer_data and supplier_data and Employee_data:
		return "Success"
	else:
		return "failed to update"


def create_customer(quickbooks_obj):
	""" Fetch Customer data from QuickBooks and store in ERPNEXT """ 

	customer = None
	customer_query = """SELECT DisplayName, Id FROM  Customer""" 
	fetch_customer_qb = quickbooks_obj.query(customer_query)
	qb_customer =  fetch_customer_qb['QueryResponse']
		
	customer = frappe.new_doc("Customer")
	if qb_customer:
		for fields in qb_customer['Customer']:
			customer.customer_name = fields.get('DisplayName')
			customer.customer_type = "Company"
			customer.customer_group ="Commercial"
			customer.territory = "All Territories"
			customer.quickbooksid = str(fields.get('Id'))
			customer.insert()
	return customer



def create_Supplier(quickbooks_obj):
	""" Fetch Supplier data from QuickBooks and store in ERPNEXT """ 

	supplier = None
	supplier_query = """SELECT  DisplayName, CurrencyRef, Id FROM  Vendor""" 
	fetch_vendor_qb = quickbooks_obj.query(supplier_query)
	qb_supplier =  fetch_vendor_qb['QueryResponse']
		
	supplier = frappe.new_doc("Supplier")
	if qb_supplier:
		for fields in qb_supplier['Vendor']:
			supplier.supplier_name = fields.get('DisplayName')
			supplier.supplier_type = "Distributor"
			supplier.default_currency =fields['CurrencyRef'].get('value','') if fields.get('CurrencyRef') else ''
			supplier.quickbooks_id = str(fields.get('Id'))
			supplier.insert()
	return supplier

def create_Employee(quickbooks_obj):
	""" Fetch Employee data from QuickBooks and store in ERPNEXT """ 

	employee = None
	employee_query = """SELECT Id, DisplayName, PrimaryPhone, Gender, PrimaryEmailAddr, BirthDate, HiredDate, ReleasedDate FROM Employee""" 
	fetch_employee_qb = quickbooks_obj.query(employee_query)
	qb_employee =  fetch_employee_qb['QueryResponse']
		
	employee = frappe.new_doc("Employee")
	if qb_employee:
		for fields in qb_employee['Employee']:
			employee.employee_name = fields.get('DisplayName')
			#employee.quickbooks_emp_id = str(fields.get('Id'))
			employee.date_of_joining = fields.get('HiredDate') if fields.get('HiredDate') else strftime("%Y-%m-%d")
			employee.date_of_birth = fields.get('BirthDate') if fields.get('BirthDate') else "2016-04-01"
			employee.gender = fields.get('Gender') if fields.get('Gender') else "Male"
			employee.cell_number =fields['Mobile'].get('FreeFormNumber','') if fields.get('Mobile') else ''
			employee.personal_email =fields['PrimaryEmailAddr'].get('Address','') if fields.get('PrimaryEmailAddr') else ''
			employee.insert()
	return employee
