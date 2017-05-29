from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log, pagination


def sync_taxagency(quickbooks_obj):
	"""Fetch TaxAgency data from QuickBooks"""
	quickbooks_taxagency_list = []
	business_objects = "TaxAgency"
	get_qb_taxagency = pagination(quickbooks_obj, business_objects)
	if get_qb_taxagency:
		sync_qb_taxagency(get_qb_taxagency, quickbooks_taxagency_list)

def sync_qb_taxagency(get_qb_taxagency, quickbooks_taxagency_list):
	for qb_taxagency in get_qb_taxagency:
		if not frappe.db.get_value("QuickBooks TaxAgency", {"quickbooks_tax_agency_id": qb_taxagency.get('Id')}, "name"):
			create_taxagency(qb_taxagency, quickbooks_taxagency_list)

def create_taxagency(qb_taxagency, quickbooks_taxagency_list):
	""" store TaxAgency data in ERPNEXT """ 
	taxagency = None
	try:	
		taxagency = frappe.get_doc({
			"doctype": "QuickBooks TaxAgency",
			"tax_registration_number": qb_taxagency.get('TaxRegistrationNumber'),
			"quickbooks_tax_agency_id": qb_taxagency.get('Id'),
			"display_name" : qb_taxagency.get('DisplayName')
		}).insert()
		
		frappe.db.commit()
		quickbooks_taxagency_list.append(taxagency.quickbooks_tax_agency_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_quickbooks_log(title=e.message, status="Error", method="create_taxagency", message=frappe.get_traceback(),
				request_data=qb_taxagency, exception=True)
	
	return quickbooks_taxagency_list