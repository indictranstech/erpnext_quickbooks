from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log, pagination


def sync_tax_code(quickbooks_obj):
	"""Fetch TaxCode data from QuickBooks"""
	quickbooks_tax_code_list = []
	business_objects = "TaxCode"
	get_qb_tax_code = pagination(quickbooks_obj, business_objects)
	if get_qb_tax_code:
		sync_qb_tax_code(get_qb_tax_code, quickbooks_tax_code_list)


def sync_qb_tax_code(get_qb_tax_code, quickbooks_tax_code_list):
	for qb_tax_code in get_qb_tax_code:
		if not frappe.db.get_value("QuickBooks TaxCode", {"tax_code_id": qb_tax_code.get('Id')}, "display_name"):
			create_tax_code(qb_tax_code, quickbooks_tax_code_list)


def create_tax_code(qb_tax_code, quickbooks_tax_code_list):
	""" store TaxCode data in ERPNEXT """ 
	tax_code = None
	try:	
		tax_code = frappe.get_doc({
			"doctype": "QuickBooks TaxCode",
			"display_name": qb_tax_code.get('Name'),
			"tax_code_id": qb_tax_code.get('Id'),
			"active" : qb_tax_code.get('Active'),
			"quickbooks_sales_tax_rate_list" : get_quickbooks_sales_tax_rate_list(qb_tax_code),
			"quickbooks_purchase_tax_rate_list" : get_quickbooks_purchase_tax_rate_list(qb_tax_code)
		}).insert()
		
		frappe.db.commit()
		quickbooks_tax_code_list.append(tax_code.tax_code_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_quickbooks_log(title=e.message, status="Error", method="create_tax_code", message=frappe.get_traceback(),
				request_data=qb_tax_code, exception=True)
	
	return quickbooks_tax_code_list

def get_quickbooks_sales_tax_rate_list(qb_tax_code):
	quickbooks_sales_tax_rate_list =[]
	if qb_tax_code.get('SalesTaxRateList').get('TaxRateDetail'):
		quickbooks_sales_tax_rate_list.append({
			"tax_type_applicable" : qb_tax_code.get('SalesTaxRateList').get('TaxRateDetail')[0].get('TaxTypeApplicable'),
			"tax_rate_ref": str(qb_tax_code.get('SalesTaxRateList').get('TaxRateDetail')[0].get('TaxRateRef')),
			"tax_rate_name": qb_tax_code.get('SalesTaxRateList').get('TaxRateDetail')[0].get('TaxRateRef').get('name'),
			"tax_rate_id": qb_tax_code.get('SalesTaxRateList').get('TaxRateDetail')[0].get('TaxRateRef').get('value'),
			"tax_order": qb_tax_code.get('SalesTaxRateList').get('TaxRateDetail')[0].get('TaxOrder')
			})

	return quickbooks_sales_tax_rate_list

def get_quickbooks_purchase_tax_rate_list(qb_tax_code):
	quickbooks_purchase_tax_rate_list =[]
	if qb_tax_code.get('PurchaseTaxRateList').get('TaxRateDetail'):
		quickbooks_purchase_tax_rate_list.append({
			"tax_type_applicable" : qb_tax_code.get('PurchaseTaxRateList').get('TaxRateDetail')[0].get('TaxTypeApplicable'),
			"tax_rate_ref": str(qb_tax_code.get('PurchaseTaxRateList').get('TaxRateDetail')[0].get('TaxRateRef')),
			"tax_rate_name": qb_tax_code.get('PurchaseTaxRateList').get('TaxRateDetail')[0].get('TaxRateRef').get('name'),
			"tax_rate_id": qb_tax_code.get('PurchaseTaxRateList').get('TaxRateDetail')[0].get('TaxRateRef').get('value'),
			"tax_order": qb_tax_code.get('PurchaseTaxRateList').get('TaxRateDetail')[0].get('TaxOrder')
			})

	return quickbooks_purchase_tax_rate_list
