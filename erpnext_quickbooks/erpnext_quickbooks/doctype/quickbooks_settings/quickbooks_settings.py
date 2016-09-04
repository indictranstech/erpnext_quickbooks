# -*- coding: utf-8 -*-
# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _,msgprint
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
           sandbox=True,
           consumer_key = quickbooks_settings.consumer_key,
           consumer_secret = quickbooks_settings.consumer_secret,
           callback_url = 'http://'+ frappe.request.host + '/api/method/erpnext_quickbooks.erpnext_quickbooks.doctype.quickbooks_settings.quickbooks_settings.First_callback'
    )

	quickbooks_settings.authorize_url = quickbooks.get_authorize_url()
	quickbooks_settings.request_token = quickbooks.request_token
	quickbooks_settings.request_token_secret = quickbooks.request_token_secret
	quickbooks_settings.save()
	frappe.db.commit()
	return quickbooks_settings.authorize_url
