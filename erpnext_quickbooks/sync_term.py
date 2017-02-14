from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log, pagination

def sync_terms(quickbooks_obj):
	"""Fetch Term data from QuickBooks"""
	quickbooks_term_list = []
	business_objects = "Term"
	get_qb_term = pagination(quickbooks_obj, business_objects)
	if get_qb_term:
		sync_qb_term(get_qb_term, quickbooks_term_list)
	
def sync_qb_term(get_qb_term, quickbooks_term_list):
	for qb_term in get_qb_term:
		if not frappe.db.get_value("Terms and Conditions", {"quickbooks_term_id": qb_term.get('Id')}, "name"):
			create_term(qb_term, quickbooks_term_list)


def create_term(qb_term, quickbooks_term_list):
	""" store Term data in ERPNEXT """ 
	term = None
	try:	
		term = frappe.get_doc({
			"doctype": "Terms and Conditions",
			"quickbooks_term_id": qb_term.get('Id'),
			"title" : qb_term.get('Name'),
			"terms" : str(qb_term.get('DueDays')) + _(" Due Days")
		})
		term.flags.ignore_mandatory = True
		term.insert()

		frappe.db.commit()
		quickbooks_term_list.append(term.quickbooks_cust_id)

	except Exception, e:
		make_quickbooks_log(title=e.message, status="Error", method="create_term", message=frappe.get_traceback(),
				request_data=qb_term, exception=True)
	
	return quickbooks_term_list