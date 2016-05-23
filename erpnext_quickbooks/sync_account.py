from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.defaults
import requests.exceptions
from .utils import make_quickbooks_log

"""Code to fetch all the Account from Quickbooks And store it in ERPNEXT"""
def sync_Account(quickbooks_obj):
	"""Fetch Account data from QuickBooks"""
	quickbooks_account_list = []
	account_query = """SELECT Name, Active, Classification, AccountType, AccountSubType, CurrencyRef, Id FROM Account order Id Desc""" 
	qb_account = quickbooks_obj.query(account_query)
	get_qb_account =  qb_account['QueryResponse']['Account']
	sync_qb_accounts(get_qb_account,quickbooks_account_list)
	
def sync_qb_accounts(get_qb_account, quickbooks_account_list):
	for qb_account in get_qb_account:
		if not frappe.db.get_value("Account", {"quickbooks_account_id": qb_account.get('id')}, "name"):
			create_account(qb_account, quickbooks_account_list)

# def sync_qb_accounts(data):
# 	for qb_account in data:
# 		if not frappe.db.get_value("Account", {"quickbooks_account_id": qb_account.get('Id')}, "name"):
# 			create_account(qb_account, quickbooks_account_list =[])

def create_account(qb_account, quickbooks_account_list):
	""" store Account data in ERPNEXT """ 
	account = None
	account_type = None
	root_type = None
	parent_account = None
	Default_company = frappe.defaults.get_defaults().get("company")
	Company_abbr = frappe.db.get_value("Company",{"name":Default_company},"abbr")
	
	if qb_account.get('Classification') == "Asset":
		parent_account = _("Accounts Receivable") + " - " + Company_abbr
		root_type = "Asset"
	elif qb_account.get('Classification') == "Liability":
		parent_account = _("Accounts Payable") + " - " + Company_abbr
		root_type = "Liability"
	else:
		parent_account = _("Direct Expenses") + " - " + Company_abbr
		root_type = "Expense"
		
	try:	
		account = frappe.new_doc("Account")
		account.quickbooks_account_id = str(qb_account.get('Id'))
		account.account_name = str(qb_account.get('Name'))
		account.is_group = False
		account.parent_account = parent_account
		account.root_type = root_type
		account.account_currency = qb_account.get('CurrencyRef').get('value')
		account.flags.ignore_mandatory = True
		account.insert()

		frappe.db.commit()
		quickbooks_account_list.append(account.quickbooks_account_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_quickbooks_log(title=e.message, status="Error", method="create_account", message=frappe.get_traceback(),
				request_data=qb_account, exception=True)
	
	return quickbooks_account_list