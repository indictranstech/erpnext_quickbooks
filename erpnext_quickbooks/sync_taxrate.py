from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log, pagination


def sync_tax_rate(quickbooks_obj):
	"""Fetch TaxRate data from QuickBooks"""
	quickbooks_tax_rate_list = []
	business_objects = "TaxRate"
	get_qb_tax_rate = pagination(quickbooks_obj, business_objects)
	if get_qb_tax_rate:
		sync_qb_tax_rate(get_qb_tax_rate, quickbooks_tax_rate_list)


def sync_qb_tax_rate(get_qb_tax_rate, quickbooks_tax_rate_list):
	for qb_tax_rate in get_qb_tax_rate:
		if not frappe.db.get_value("QuickBooks TaxRate", {"tax_rate_id": qb_tax_rate.get('Id')}, "display_name"):
			create_tax_rate(qb_tax_rate, quickbooks_tax_rate_list)


def create_tax_rate(qb_tax_rate, quickbooks_tax_rate_list):
	""" store TaxRate data in ERPNEXT """ 
	tax_rate = None
	try:	
		tax_rate = frappe.get_doc({
			"doctype": "QuickBooks TaxRate",
			"display_name": qb_tax_rate.get('Name'),
			"tax_rate_id": qb_tax_rate.get('Id'),
			"active" : qb_tax_rate.get('Active'),
			"description": qb_tax_rate.get('Description'),
			"rate_value": qb_tax_rate.get('RateValue'),
			"agency_ref": str(qb_tax_rate.get('AgencyRef')),
			"tax_return_line_ref": str(qb_tax_rate.get('TaxReturnLineRef'))
		}).insert()
		
		frappe.db.commit()
		quickbooks_tax_rate_list.append(tax_rate.tax_rate_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_quickbooks_log(title=e.message, status="Error", method="create_tax_rate", message=frappe.get_traceback(),
				request_data=qb_tax_rate, exception=True)
	
	return quickbooks_tax_rate_list

 
