# -*- coding: utf-8 -*-
# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from .exceptions import QuickbooksSetupError

def disable_quickbooks_sync_on_exception():
	frappe.db.rollback()
	frappe.db.set_value("Quickbooks Settings", None, "enable_quickbooks_online", 0)
	frappe.db.commit()

	
def make_quickbooks_log(title="Sync Log", status="Queued", method="sync_quickbooks", message=None, exception=False, 
name=None, request_data={}):	
	if not name:
		name = frappe.db.get_value("Quickbooks Log", {"status": "Queued"})
		
		if name:
			""" if name not provided by log calling method then fetch existing queued state log"""
			log = frappe.get_doc("Quickbooks Log", name)
		
		else:
			""" if queued job is not found create a new one."""
			log = frappe.get_doc({"doctype":"Quickbooks Log"}).insert(ignore_permissions=True)
		
		if exception:
			frappe.db.rollback()
			log = frappe.get_doc({"doctype":"Quickbooks Log"}).insert(ignore_permissions=True)
			
		log.message = message if message else frappe.get_traceback()
		log.title = title[0:140]
		log.method = method
		log.status = status
		log.request_data= json.dumps(request_data)
		
		log.save(ignore_permissions=True)
		frappe.db.commit()
