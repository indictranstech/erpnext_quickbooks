# -*- coding: utf-8 -*-
# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _, msgprint
from frappe.utils import cstr, flt, cint, get_files_path
import httplib
import urllib3
from urlparse import parse_qsl
import json
import ast
from rauth import OAuth1Session, OAuth1Service
from erpnext_quickbooks.pyqb.quickbooks import QuickBooks
from erpnext_quickbooks.exceptions import QuickbooksError
from time import strftime
from frappe.utils import flt, nowdate

class QuickbooksSettings(Document):
	pass

 

@frappe.whitelist(allow_guest=True)
def First_callback(realmId, oauth_verifier):
	login_via_oauth2(realmId, oauth_verifier)
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/desk#Form/Quickbooks Settings"

def login_via_oauth2(realmId, oauth_verifier):
	""" Store necessary token's to Setup service """
	
	quickbooks_settings = frappe.get_doc("Quickbooks Settings")
	 
	quickbooks = QuickBooks(
       sandbox=True,
       consumer_key = quickbooks_settings.consumer_key,
       consumer_secret = quickbooks_settings.consumer_secret,
       minorversion=4
     )

	quickbooks.authorize_url = quickbooks_settings.authorize_url
	quickbooks.request_token = quickbooks_settings.request_token
	quickbooks.request_token_secret = quickbooks_settings.request_token_secret
	quickbooks.set_up_service()

 	quickbooks.get_access_tokens(oauth_verifier)

	quickbooks.company_id = realmId

	quickbooks_settings.realm_id = realmId
	quickbooks_settings.access_token = quickbooks.access_token
	quickbooks_settings.access_token_secret = quickbooks.access_token_secret 
	quickbooks_settings.save()
	frappe.db.commit()
	
		 
@frappe.whitelist(allow_guest=True)
def quickbooks_authentication_popup(consumer_key, consumer_secret):
	""" Open new popup window to Connect Quickbooks App to Quickbooks sandbox Account """

	quickbooks_settings = frappe.get_doc("Quickbooks Settings")

	quickbooks = QuickBooks(
           sandbox = False,
           consumer_key = quickbooks_settings.consumer_key,
           consumer_secret = quickbooks_settings.consumer_secret,
           callback_url = 'http://'+ frappe.request.host + '/api/method/erpnext_quickbooks.erpnext_quickbooks.doctype.quickbooks_settings.quickbooks_settings.First_callback'
    )
	try:
		quickbooks_settings.authorize_url = quickbooks.get_authorize_url()
		quickbooks_settings.request_token = quickbooks.request_token
		quickbooks_settings.request_token_secret = quickbooks.request_token_secret
		quickbooks_settings.save()
		frappe.db.commit()
	except Exception, e:
		frappe.throw(_("HTTPSConnection Error Please Connect to Internet"))
	return quickbooks_settings.authorize_url

@frappe.whitelist()
def quickbooks_tax_head():
	display_names = frappe.get_all('QuickBooks TaxRate', fields =["display_name"], as_list=1)
	for tax_head_quickbooks in display_names:
		create_tax_head_mapper(tax_head_quickbooks)
	return True

def create_tax_head_mapper(tax_head_quickbooks):
	tax_head_mapper = frappe.new_doc("Tax Head Mapper")
	tax_head_mapper.parent ="Quickbooks Settings"
	tax_head_mapper.parenttype = "Quickbooks Settings"
	tax_head_mapper.parentfield ="tax_head_mapper"
	tax_head_mapper.tax_head_quickbooks = tax_head_quickbooks[0]
	tax_head_mapper.flags.ignore_mandatory = True
	tax_head_mapper.flags.ignore_permissions = 1
	tax_head_mapper.insert()
	frappe.db.commit()
	# return tax_head_mapper.name

@frappe.whitelist()
def detail_comparison_erp_qb_accounts(company_name):
	erpnext = frappe.db.sql("""SELECT name, root_type, quickbooks_account_id, company from `tabAccount` 
				where is_group=0 
				and company = '{}' 
				and quickbooks_account_id is NULL 
				order by root_type""".format(company_name), as_list=1)
	quickbooks = frappe.db.sql("""SELECT name, root_type, quickbooks_account_id, company from `tabAccount` 
				where is_group=0 
				and company = '{}' 
				and quickbooks_account_id is not NULL 
				order by root_type""".format(company_name), as_list=1)
	from collections import defaultdict
	d = defaultdict(dict)
	for row in quickbooks:
		if "QBK" not in d[row[1]]:
			d[row[1]]["QBK"] = [row[0]]
		else:
			d[row[1]]["QBK"].append(row[0])
	for row in erpnext:
		if "ERP" not in d[row[1]]:
			d[row[1]]["ERP"] = [row[0]]
		else:
			d[row[1]]["ERP"].append(row[0])
	return d