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



def pagination(quickbooks_obj, business_objects):
	condition = ""
	group_by = ""
	quickbooks_result_set = []
	if business_objects in ["Customer", "Vendor", "Item", "Employee"]:
		condition = " Where Active IN (true, false)"
		
	record_count = quickbooks_obj.query("""SELECT count(*) from {0} {1} """.format(business_objects, condition))
	total_record = record_count['QueryResponse']['totalCount']
	limit_count = 90
	total_page = total_record / limit_count if total_record % limit_count == 0 else total_record / limit_count + 1
	startposition , maxresults = 0, 0  
	for i in range(total_page):
		maxresults = startposition + limit_count
		if business_objects in ["Customer", "Vendor", "Item", "Employee"]:
			group_by = condition + " ORDER BY Id ASC STARTPOSITION {1} MAXRESULTS {2}".format(business_objects, startposition, maxresults)
		else:
			group_by = " ORDER BY Id ASC STARTPOSITION {1} MAXRESULTS {2}".format(business_objects, startposition, maxresults)
		query_result = """SELECT * FROM {0} {1}""".format(business_objects, group_by)
		qb_data = quickbooks_obj.query(query_result)
		qb_result =  qb_data['QueryResponse']
		if qb_result:
			quickbooks_result_set.extend(qb_result[business_objects])
		startposition = startposition + limit_count
	return quickbooks_result_set

# def pagination(quickbooks_obj, business_objects):
# 	quickbooks_result_set = []

# 	record_count = quickbooks_obj.query("""SELECT count(*) from {0} """.format(business_objects))
# 	total_record = record_count['QueryResponse']['totalCount']
# 	limit_count = 90
# 	total_page = total_record / limit_count
# 	startposition , maxresults = 0, 0  
# 	for i in range(total_page + 1):
# 		maxresults = startposition + limit_count
# 		query_result = """SELECT * FROM {0} ORDER BY Id Desc STARTPOSITION {1} MAXRESULTS {2}""".format(business_objects, startposition, maxresults)
# 		qb_data = quickbooks_obj.query(query_result)
# 		qb_result =  qb_data['QueryResponse']
# 		if qb_result:
# 			quickbooks_result_set.extend(qb_result[business_objects])
# 		startposition = startposition + limit_count
# 	return quickbooks_result_set
