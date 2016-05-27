# -*- coding: utf-8 -*-
# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt



from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _,msgprint
from frappe.utils import cstr, flt, cint, get_files_path
import httplib
import urllib3
from urlparse import parse_qsl
import json
import ast
from rauth import OAuth1Session, OAuth1Service
from erpnext_quickbooks.pyqb.quickbooks import QuickBooks
from erpnext_quickbooks.exceptions import QuickbooksError
from time import strftime
from frappe.utils import flt, nowdate
from erpnext_quickbooks.sync_customers import *
from erpnext_quickbooks.sync_suppliers import *
from erpnext_quickbooks.sync_products import *
from erpnext_quickbooks.sync_employee import *
from erpnext_quickbooks.sync_orders import *
from erpnext_quickbooks.sync_purchase_invoice import *
from erpnext_quickbooks.sync_journal_vouchers import sync_entry
from erpnext_quickbooks.sync_entries import *
from erpnext_quickbooks.sync_account import sync_Account




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
def First_callback(realmId, oauth_verifier):
	login_via_oauth2(realmId, oauth_verifier)


def login_via_oauth2(realmId, oauth_verifier):
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
	
		 
@frappe.whitelist(allow_guest=True)
def quickbooks_authentication_popup(consumer_key, consumer_secret):
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
 
 	customer_data = sync_customers(quickbooks_obj)
	supplier_data = sync_suppliers(quickbooks_obj)
	Employee_data = create_Employee(quickbooks_obj)
	Item_data = create_Item(quickbooks_obj)
	sync_Account(quickbooks_obj)
	invoice_data = sync_si_orders(quickbooks_obj)
 	sync_pi_orders(quickbooks_obj)
	sync_entry(quickbooks_obj)
	payment_invoice(quickbooks_obj)
	
	if customer_data and supplier_data and Employee_data and Item_data:
		return "Success"
	else:
		return "failed to update"

	# Sync_erp_customer(quickbooks_obj)

	# sync_qb_journal_entry(payment1)
	#sync_qb_journal_entry(payment1)
	# sync_entries(journal_entry1)
	#payment_invoice(quickbooks_obj)
	# sync_orders(quickbooks_obj)
	