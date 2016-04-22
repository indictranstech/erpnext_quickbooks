from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions


def sync_customers(quickbooks_obj):
	"""Fetch Customer data from QuickBooks"""
	quickbooks_customer_list = []
	customer_query = """SELECT DisplayName, Id FROM  Customer""" 
	fetch_customer_qb = quickbooks_obj.query(customer_query)
	get_qb_customer =  fetch_customer_qb['QueryResponse']['Customer']
	sync_qb_customers(get_qb_customer,quickbooks_customer_list)
	
def sync_qb_customers(get_qb_customer,quickbooks_customer_list):
	for qb_customer in get_qb_customer:
		if not frappe.db.get_value("Customer", {"quickbooks_cust_id": qb_customer.get('id')}, "name"):
			create_customer(qb_customer, quickbooks_customer_list)


def create_customer(qb_customer,quickbooks_customer_list):
	""" store in ERPNEXT """ 
	
	customer = None
	try:	
		customer = frappe.new_doc("Customer")
		customer.quickbooks_cust_id = str(qb_customer.get('Id')) if not str(qb_customer.get('Id'))  else str(qb_customer.get('value'))
		customer.customer_name = str(qb_customer.get('DisplayName')) if not str(qb_customer.get('DisplayName'))  else str(qb_customer.get('name'))
		customer.customer_type = "Company"
		customer.customer_group ="Commercial"
		customer.territory = "All Territories"
		customer.insert()
		quickbooks_customer_list.append(customer.quickbooks_cust_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e

	print "qb customer list ",quickbooks_customer_list	
	return quickbooks_customer_list
