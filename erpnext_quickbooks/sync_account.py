from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.defaults
import requests.exceptions
from .utils import make_quickbooks_log
from pyqb.quickbooks.batch import batch_create, batch_delete
from pyqb.quickbooks.objects.account import Account 


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
		if not frappe.db.get_value("Account", {"quickbooks_account_id": qb_account.get('Id')}, "name"):
			create_account(qb_account, quickbooks_account_list)

def create_account(qb_account, quickbooks_account_list):
	""" store Account data in ERPNEXT """ 
	account = None
	account_type = None
	root_type = None
	parent_account = None
	Default_company = frappe.defaults.get_defaults().get("company")
	Company_abbr = frappe.db.get_value("Company", {"name": Default_company}, "abbr")
	
	
	if qb_account.get('AccountType') == "Fixed Asset":
		parent_account = _("Fixed Assets") + " - " + Company_abbr
		root_type = _("Asset")
	elif qb_account.get('AccountType') == "Other Current Asset":
		parent_account = _("Current Assets") + " - " + Company_abbr
		root_type = _("Asset")
	elif qb_account.get('AccountType') == "Bank":
		parent_account = _("Bank Accounts") + " - " + Company_abbr
		root_type = _("Asset")
	elif qb_account.get('AccountType') == "Other Asset":
		parent_account = _("Loans and Advances (Assets)") + " - " + Company_abbr
		root_type = _("Asset")
	elif qb_account.get('AccountType') == "Accounts Receivable":
		parent_account = _("Accounts Receivable") + " - " + Company_abbr
		root_type = _("Asset")
	elif qb_account.get('AccountType') == "Accounts Payable":
		parent_account = _("Accounts Payable") + " - " + Company_abbr
		root_type = _("Liability")
	elif qb_account.get('AccountType') == 'Other Current Liability':
		parent_account = _("Current Liabilities") + " - " + Company_abbr
		root_type = _("Liability")
	elif qb_account.get('AccountType') == 'Long Term Liability':
		parent_account = _("Loans (Liabilities)") + " - " + Company_abbr
		root_type = _("Liability")
	elif qb_account.get("AccountType") == "Equity":
		parent_account = _("Equity") + " - " + Company_abbr
		root_type = _("Equity")
	elif qb_account.get('AccountType') == 'Income':
		parent_account = _("Direct Income") + " - " + Company_abbr
		root_type = _("Income")
	elif qb_account.get('AccountType') == 'Other Income':
		parent_account = _("Indirect Income") + " - " + Company_abbr
		root_type = _("Income")
	elif qb_account.get('AccountType') == 'Expense':
		parent_account = _("Direct Expenses") + " - " + Company_abbr
		root_type = _("Expense")
	elif qb_account.get('AccountType') == 'Other Expense':
		parent_account = _("Indirect Expenses") + " - " + Company_abbr
		root_type = _("Expense")
	elif qb_account.get('AccountType') == 'Cost of Goods Sold':
		parent_account = _("Indirect Expenses") + " - " + Company_abbr
		root_type = _("Expense")

	try:	
		account = frappe.new_doc("Account")
		account.quickbooks_account_id = str(qb_account.get('Id'))
		account.account_name = str(qb_account.get('Name')) + " - " + "qb"
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


"""Sync ERPNext Account to QuickBooks"""

def sync_erp_accounts():
	"""Recive Response From Quickbooks and Update quickbooks_account_id in Account"""
	response_from_quickbooks = sync_erp_accounts_to_quickbooks()
	if response_from_quickbooks:
		try:
			for response_obj in response_from_quickbooks.successes:
				if response_obj:
					frappe.db.sql("""UPDATE tabAccount SET quickbooks_account_id = %s WHERE name ='%s'""" %(response_obj.Id, response_obj.Name))
				else:
					raise _("Does not get any response from quickbooks")	
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_erp_accounts", message=frappe.get_traceback(),
				request_data=response_obj, exception=True)

def sync_erp_accounts_to_quickbooks():
	Account_list = []
	for erp_account in erp_account_data():
		try:
			if erp_account:
				create_erp_account_to_quickbooks(erp_account, Account_list)
			else:
				raise _("Account does not exist in ERPNext")
		except Exception, e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_quickbooks_log(title=e.message, status="Error", method="sync_erp_accounts_to_quickbooks", message=frappe.get_traceback(),
					request_data=erp_account, exception=True)
	results = batch_create(Account_list)
	return results

def erp_account_data():
	erp_account = frappe.db.sql("""select name, root_type, account_type, quickbooks_account_id from `tabAccount` where is_group =0 && quickbooks_account_id is NULL""" ,as_dict=1)
	return erp_account

def create_erp_account_to_quickbooks(erp_account, Account_list):
	account_obj = Account()
	account_obj.Name = erp_account.name
	account_obj.FullyQualifiedName = erp_account.name
	account_classification_and_account_type(account_obj, erp_account)
	account_obj.save()
	Account_list.append(account_obj)
	return Account_list

def account_classification_and_account_type(account_obj, erp_account):
	if erp_account.root_type == "Asset":
		account_obj.Classification = erp_account.root_type
		account_obj.AccountType = "Other Current Asset"
		account_obj.AccountSubType = "AllowanceForBadDebts"
	elif erp_account.root_type =="Liability":
		account_obj.Classification = erp_account.root_type
		account_obj.AccountType = "Liability"
		account_obj.AccountSubType = "OtherCurrentLiabilities"
	elif erp_account.root_type =="Expense":
		account_obj.Classification = erp_account.root_type
		account_obj.AccountType ="Other Expense"
		account_obj.AccountSubType ="Amortization"
	elif erp_account.root_type == "Income":
		account_obj.Classification = erp_account.root_type
		account_obj.AccountType = "Income"
		account_obj.AccountSubType = "SalesOfProductIncome"
	elif erp_account.root_type == "Equity":
		account_obj.Classification = erp_account.root_type
		account_obj.AccountType = "Equity"
		account_obj.AccountSubType ="RetainedEarnings"
	else:
		account_obj.Classification = None
		account_obj.AccountType = "Cost of Goods Sold"