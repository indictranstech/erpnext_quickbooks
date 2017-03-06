from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log, pagination
from pyqb.quickbooks.batch import batch_create, batch_delete
from pyqb.quickbooks.objects.vendor import Vendor

def sync_suppliers(quickbooks_obj):
	""" Fetch Supplier data from QuickBooks"""
	
	quickbooks_supplier_list = []
	business_objects = "Vendor"
	get_qb_supplier =  pagination(quickbooks_obj, business_objects)
	if get_qb_supplier:
		sync_qb_suppliers(get_qb_supplier, quickbooks_supplier_list)

	
def sync_qb_suppliers(get_qb_supplier, quickbooks_supplier_list):
	for qb_supplier in get_qb_supplier:
		if not frappe.db.get_value("Supplier", {"quickbooks_supp_id": qb_supplier.get('Id')}, "name"):
			create_Supplier(qb_supplier, quickbooks_supplier_list)

def create_Supplier(qb_supplier, quickbooks_supplier_list):
	""" Store Supplier Data in ERPNEXT """ 
	supplier = None
	try:	
		supplier = frappe.get_doc({
			"doctype": "Supplier",
			"quickbooks_supp_id": str(qb_supplier.get('Id')) if qb_supplier.get('Id')  else str(qb_supplier.get('value')),
			"supplier_name" : str(qb_supplier.get('DisplayName')) if qb_supplier.get('DisplayName')  else str(qb_supplier.get('name')),
			"supplier_type" :  _("Distributor"),
			"default_currency" : qb_supplier['CurrencyRef'].get('value','') if qb_supplier.get('CurrencyRef') else '',
		})
		supplier.flags.ignore_mandatory = True
		supplier.insert()

		if supplier and qb_supplier.get('BillAddr'):
			create_supplier_address(qb_supplier, supplier, qb_supplier.get("BillAddr"), "Billing", 1)
		
		frappe.db.commit()
		quickbooks_supplier_list.append(supplier.quickbooks_supp_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_quickbooks_log(title=e.message, status="Error", method="create_Supplier", message=frappe.get_traceback(),
				request_data=qb_supplier, exception=True)
	return quickbooks_supplier_list

def create_supplier_address(qb_supplier, supplier, address, type_of_address, index):
	address_title, address_type = get_address_title_and_type(supplier.supplier_name, type_of_address, index)
	qb_id = str(address.get("Id")) + str(address_type)
	try :
		supplier_address = frappe.get_doc({
			"doctype": "Address",
			"quickbooks_address_id": qb_id,
			"address_title": address_title,
			"address_type": address_type,
			"address_line1": address.get("Line1")[:35] if address.get("Line1") else '',
			"address_line2": address.get("Line1")[36:70] if address.get("Line1") else '',
			"city": address.get("City"),
			"state": address.get("CountrySubDivisionCode"),
			"pincode": address.get("PostalCode"),
			"country": address.get("Country"),
			"email_id": qb_supplier.get('PrimaryEmailAddr').get('Address') if qb_supplier.get('PrimaryEmailAddr') else '',
			"phone" : qb_supplier.get('Mobile').get('FreeFormNumber') if qb_supplier.get('Mobile') else '',
			"supplier": supplier.name,
			"supplier_name": supplier.name
		})
		supplier_address.flags.ignore_mandatory = True
		supplier_address.insert()
			
	except Exception, e:
		make_quickbooks_log(title=e.message, status="Error", method="create_supplier_address", message=frappe.get_traceback(),
				request_data=address, exception=True)
		raise e
	
def get_address_title_and_type(supplier_name, type_of_address, index):
	address_type = _(type_of_address)
	address_title = supplier_name
	if frappe.db.get_value("Address", "{0}-{1}".format(supplier_name.strip(), address_type)):
		address_title = "{0}-{1}".format(supplier_name.strip(), index)
		
	return address_title, address_type  


"""Sync Supplier From Erpnext to Quickbooks"""
def sync_erp_suppliers(quickbooks_obj):
	"""Receive Response From Quickbooks and Update quickbooks_supp_id for Supplier"""
	response_from_quickbooks = sync_erp_suppliers_to_quickbooks(quickbooks_obj)
	if response_from_quickbooks:
		try:
			for response_obj in response_from_quickbooks.successes:
				if response_obj:
					frappe.db.sql("""UPDATE tabSupplier SET quickbooks_supp_id = %s WHERE supplier_name ='%s'""" %(response_obj.Id, response_obj.DisplayName))
					frappe.db.commit()
				else:
					raise _("Does not get any response from quickbooks")	
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_erp_suppliers", message=frappe.get_traceback(),
				request_data=response_obj, exception=True)

def sync_erp_suppliers_to_quickbooks(quickbooks_obj):
	Supplier_list = []
	for erp_supplier in erp_supplier_data():
		try:
			if erp_supplier:
				create_erp_suppliers_to_quickbooks(erp_supplier, Supplier_list)
			else:
				raise _("Supplier does not exist in ERPNext")
		except Exception, e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_quickbooks_log(title=e.message, status="Error", method="sync_erp_suppliers", message=frappe.get_traceback(),
					request_data=erp_supplier, exception=True)
	results = batch_create(Supplier_list)
	return results
	
def erp_supplier_data():
	erp_supplier = frappe.db.sql("""select supplier_name from `tabSupplier` WHERE  quickbooks_supp_id IS NULL""" ,as_dict=1)
	return erp_supplier

def create_erp_suppliers_to_quickbooks(erp_supplier, Supplier_list):
	supplier_obj = Vendor()
	supplier_obj.CompanyName = erp_supplier.supplier_name
	supplier_obj.DisplayName = erp_supplier.supplier_name
	supplier_obj.save()
	Supplier_list.append(supplier_obj)
	return Supplier_list

