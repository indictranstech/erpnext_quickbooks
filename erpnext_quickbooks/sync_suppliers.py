from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions



def sync_suppliers(quickbooks_obj):
	""" Fetch Supplier data from QuickBooks"""
	quickbooks_supplier_list = []
	supplier_query = """SELECT  DisplayName, CurrencyRef, Id FROM  Vendor""" 
	fetch_supplier_qb = quickbooks_obj.query(supplier_query)
	get_qb_supplier =  fetch_supplier_qb['QueryResponse']['Vendor']
	sync_qb_suppliers(get_qb_supplier,quickbooks_supplier_list)

	
def sync_qb_suppliers(get_qb_supplier,quickbooks_supplier_list):
	for qb_supplier in get_qb_supplier:
		if not frappe.db.get_value("Supplier", {"quickbooks_supp_id": qb_supplier.get('Id')}, "name"):
			create_Supplier(qb_supplier, quickbooks_supplier_list)

def create_Supplier(qb_supplier, quickbooks_supplier_list):
	""" store in ERPNEXT """ 

	supplier = None
	try:	
		supplier = frappe.new_doc("Supplier")
		supplier.quickbooks_supp_id = str(qb_supplier.get('Id')) if qb_supplier.get('Id')  else str(qb_supplier.get('value'))
		supplier.supplier_name = str(qb_supplier.get('DisplayName')) if qb_supplier.get('DisplayName')  else str(qb_supplier.get('name'))
		supplier.supplier_type = "Distributor"
		supplier.default_currency =qb_supplier['CurrencyRef'].get('value','') if qb_supplier.get('CurrencyRef') else ''
		supplier.insert()
		quickbooks_supplier_list.append(supplier.quickbooks_supp_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e

	print "qb supplier list ",quickbooks_supplier_list
	return quickbooks_supplier_list







	





