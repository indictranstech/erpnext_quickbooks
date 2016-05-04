from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log



def sync_suppliers(quickbooks_obj):
	""" Fetch Supplier data from QuickBooks"""
	quickbooks_supplier_list = []
	supplier_query = """SELECT  DisplayName, CurrencyRef, Id, BillAddr FROM  Vendor""" 
	qb_supplier = quickbooks_obj.query(supplier_query)
	get_qb_supplier =  qb_supplier['QueryResponse']['Vendor']
	sync_qb_suppliers(get_qb_supplier,quickbooks_supplier_list)

	
def sync_qb_suppliers(get_qb_supplier, quickbooks_supplier_list):
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
		supplier.supplier_type = _("Distributor")
		supplier.default_currency =qb_supplier['CurrencyRef'].get('value','') if qb_supplier.get('CurrencyRef') else ''
		supplier.insert()
		

		if supplier and qb_supplier.get('BillAddr'):
			create_supplier_address(supplier, qb_supplier.get("BillAddr"))
		frappe.db.commit()
		quickbooks_supplier_list.append(supplier.quickbooks_supp_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_quickbooks_log(title=e.message, status="Error", method="create_Supplier", message=frappe.get_traceback(),
				request_data=qb_supplier, exception=True)

	print "qb supplier list ",quickbooks_supplier_list
	return quickbooks_supplier_list

def create_supplier_address(supplier, address):
	address_title, address_type = get_address_title_and_type(supplier.supplier_name)
	try :
		frappe.get_doc({
			"doctype": "Address",
			"quickbooks_address_id": address.get("Id"),
			"address_title": address_title,
			"address_type": address_type,
			"address_line1": address.get("Line1"),
			"city": address.get("City"),
			"state": address.get("CountrySubDivisionCode"),
			"pincode": address.get("PostalCode"),
			"country": frappe.db.get_value("Country",{"code":address.get("CountrySubDivisionCode")},"name"),
			"email_id": address.get("PrimaryEmailAddr"),
			"supplier": supplier.name,
			"supplier_name":  supplier.supplier_name
		}).insert()
			
	except Exception, e:
		make_quickbooks_log(title=e.message, status="Error", method="create_supplier_address", message=frappe.get_traceback(),
				request_data=address, exception=True)
		raise e
	
def get_address_title_and_type(supplier_name):
	address_type = _("Billing")
	address_title = supplier_name
	if frappe.db.get_value("Address", "{0}-{1}".format(supplier_name.strip(), address_type)):
		address_title = "{0}".format(supplier_name.strip())
		
	return address_title, address_type 








	





