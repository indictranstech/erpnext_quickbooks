

from __future__ import unicode_literals
import frappe
from frappe import _
import json
import ast
from frappe.utils import flt, nowdate, cstr
import requests.exceptions
from .utils import make_quickbooks_log, pagination

"""Sync all the Supplier Credit [VendorCredit] from Quickbooks to ERPNEXT"""
def sync_supplier_credits(quickbooks_obj):
	quickbooks_supplier_credits_list =[] 
	business_objects = "VendorCredit"
	get_qb_supplier_credits =  pagination(quickbooks_obj, business_objects)
	if get_qb_supplier_credits:
		sync_qb_supplier_credits(get_qb_supplier_credits, quickbooks_supplier_credits_list)
		sync_qb_journal_entry_against_supplier_credit(get_qb_supplier_credits)

def sync_qb_supplier_credits(get_qb_supplier_credits, quickbooks_supplier_credits_list):
	company_name = frappe.defaults.get_defaults().get("company")
	default_currency = frappe.db.get_value("Company" ,{"name":company_name},"default_currency")
	for qb_supplier_credit in get_qb_supplier_credits:
		if valid_supplier_and_product(qb_supplier_credit):
			try:
				create_credit(qb_supplier_credit, quickbooks_supplier_credits_list, default_currency)
			except Exception, e:
				make_quickbooks_log(title=e.message, status="Error", method="sync_qb_supplier_credits", message=frappe.get_traceback(),
						request_data=qb_supplier_credit, exception=True)

def valid_supplier_and_product(qb_supplier_credit):
	"""  valid_supplier data from ERPNEXT and store in ERPNEXT """ 
	from .sync_suppliers import create_Supplier
	supplier_id = qb_supplier_credit['VendorRef']['value'] 
	if supplier_id:
		if not frappe.db.get_value("Supplier", {"quickbooks_supp_id": supplier_id}, "name"):
			create_Supplier(qb_supplier_credit['VendorRef'], quickbooks_supplier_list = [])		
	else:
		raise _("supplier is mandatory to create order")
	
	return True

def create_credit(qb_supplier_credit, quickbooks_supplier_credits_list, default_currency=None):
	""" Create (Supplier/ Vendor)credit in ERPNEXT """
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	create_supplier_credit(qb_supplier_credit, quickbooks_settings, quickbooks_supplier_credits_list, default_currency=None)

def create_supplier_credit(qb_supplier_credit, quickbooks_settings, quickbooks_supplier_credits_list, default_currency=None):
	""" 
	In ERPNext Purcahse return is created against PI.
	But 
	In Quickbooks Supplier Credit/Purchase return is created against Supplier/Vendor not against any PI/Bill,
	So, to maintain stock in ERPNext, it is necessary to create -ve Stock Entry as stock is again going 
	to decrease as Supplier is returning the product..
	Than, after that Journal Entry is created with voucher type as Debit Note against Supplier as advance Payment. 
	"""
	stock_entry = frappe.db.get_value("Stock Entry", {"quickbooks_credit_memo_id": str(qb_supplier_credit.get("Id"))+"-"+"DN"}, "name")
	if not stock_entry:
		stock_entry = frappe.get_doc({
			"doctype": "Stock Entry",
			"quickbooks_credit_memo_id" : str(qb_supplier_credit.get("Id"))+"-"+"DN",
			"posting_date" : qb_supplier_credit.get('TxnDate'),
			"purpose": "Material Receipt",
			"to_warehouse" : quickbooks_settings.warehouse,
			"quickbooks_customer_reference" : frappe.db.get_value("Supplier",{"quickbooks_supp_id":qb_supplier_credit['VendorRef'].get('value')},"name"),
			"quickbooks_credit_memo_reference" : qb_supplier_credit.get("DocNumber")
			})
		stock_item = update_stock(qb_supplier_credit['Line'], quickbooks_settings)
		if stock_item == True:
			items = get_item_stock(qb_supplier_credit['Line'], quickbooks_settings, stock_item)
			stock_entry.update({"items":items})

		stock_entry
		stock_entry.flags.ignore_mandatory = True
		stock_entry.save(ignore_permissions=True)
		stock_entry.submit()

def get_item_stock(order_items, quickbooks_settings, stock_item):
  	items = []
 	for qb_item in order_items:
  		if qb_item.get('DetailType') == "ItemBasedExpenseLineDetail" and stock_item == True:
			item_code = get_item_code(qb_item)
			items.append({
				"item_code": item_code if item_code else '',
				"rate": qb_item.get('ItemBasedExpenseLineDetail').get('UnitPrice'),
				"qty": -(qb_item.get('ItemBasedExpenseLineDetail').get('Qty')),
				"t_warehouse" : quickbooks_settings.warehouse,
				"warehouse": quickbooks_settings.warehouse,
				"uom": _("Nos")
			})
	return items

def update_stock(line, quickbooks_settings):
	"""
	Check item is stock item or not
	Quickbooks Bill has two table
		1. Accounts details : This table is used for Accounts Entry, example freight and Forwarding charges for purchasing that item 
		2. Item details : This table is used for Item need to Purchase
	"""
	is_stock_item = True
	Item_Detail, Account_Detail = 0,0
	for i in line:
		if i['DetailType'] =='ItemBasedExpenseLineDetail':
			Item_Detail += 1
		elif i['DetailType'] =='AccountBasedExpenseLineDetail':
			Account_Detail +=1
	if Account_Detail > 0 and Item_Detail ==0:
		is_stock_item = False
	return is_stock_item

def get_item_code(qb_item):
	quickbooks_item_id = qb_item.get('ItemBasedExpenseLineDetail').get('ItemRef').get('value') if qb_item.get('ItemBasedExpenseLineDetail') else ''
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id}, "item_code")
	return item_code

def sync_qb_journal_entry_against_supplier_credit(get_qb_supplier_credits):
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	for qb_supplier_credits in get_qb_supplier_credits:
 		try:
 			if not frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": qb_supplier_credits.get('Id')+"DE"}, "name"):
 				sync_qb_journal_entry(qb_supplier_credits, quickbooks_settings)
 		except Exception, e:
 			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_supplier_credit", message=frappe.get_traceback(),
						request_data=qb_supplier_credits, exception=True)

def sync_qb_journal_entry(qb_supplier_credits, quickbooks_settings):
	stock_entry =frappe.db.get_value("Stock Entry", {"quickbooks_credit_memo_id": qb_supplier_credits.get('Id')+"-"+"DN"}, "name")
	if stock_entry:
		ref_doc = frappe.get_doc("Stock Entry", stock_entry)
		stock_entry = frappe.get_doc({
			"doctype": "Journal Entry",
			"naming_series" : "DN-JV-Quickbooks-",
			"quickbooks_journal_entry_id" : qb_supplier_credits.get('Id')+"DE",
			"voucher_type" : _("Debit Note"),
			"posting_date" : qb_supplier_credits.get('TxnDate'),
			"multi_currency": 1
		})
		get_journal_entry_account(stock_entry, "Stock Entry", qb_supplier_credits, ref_doc, quickbooks_settings)
		stock_entry.save()
		stock_entry.submit()
		frappe.db.commit()

def get_journal_entry_account(stock_entry, doctype , qb_supplier_credits, ref_doc, quickbooks_settings):
	accounts_entry_pi(stock_entry, doctype, qb_supplier_credits, ref_doc, quickbooks_settings)
	
def accounts_entry_pi(stock_entry, doctype, qb_supplier_credits, ref_doc, quickbooks_settings):
	append_row_debit_detail_pi(stock_entry= stock_entry, doctype= doctype, qb_supplier_credits= qb_supplier_credits, ref_doc=ref_doc, quickbooks_settings= quickbooks_settings)
	append_row_credit_detail_pi(stock_entry= stock_entry, qb_supplier_credits = qb_supplier_credits, ref_doc=ref_doc, quickbooks_settings= quickbooks_settings)

def append_row_debit_detail_pi(stock_entry= None, doctype= None, qb_supplier_credits = None, ref_doc=None, quickbooks_settings= None):
	account = stock_entry.append("accounts", {})
	account.account = set_credit_to(stock_entry, qb_supplier_credits, quickbooks_settings)
	account.party_type =  "Supplier"
	account.party = frappe.db.get_value("Supplier",{"quickbooks_supp_id":qb_supplier_credits['VendorRef'].get('value')},"name")
	account.is_advance = "Yes"
	account.exchange_rate = qb_supplier_credits.get('ExchangeRate')
	account.debit = flt(qb_supplier_credits.get("TotalAmt") * qb_supplier_credits.get('ExchangeRate'), account.precision("debit"))
	account.debit_in_account_currency = flt(qb_supplier_credits.get("TotalAmt") , account.precision("debit_in_account_currency"))

def set_credit_to(stock_entry, qb_supplier_credits, quickbooks_settings):
	"Set credit account"
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")
	party_currency = qb_supplier_credits.get("CurrencyRef").get('value') if qb_supplier_credits.get("VendorRef") else company_currency
	if party_currency:
		creditors_account = frappe.db.get_value("Account", {"account_currency": party_currency, "quickbooks_account_id": ["!=",""], 'account_type': 'Payable',\
			"company": quickbooks_settings.select_company, "root_type": "Liability", "is_group": "0"}, "name")
		return creditors_account

def append_row_credit_detail_pi(stock_entry= None, qb_supplier_credits = None, ref_doc=None, quickbooks_settings= None):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")

	account =stock_entry.append("accounts", {})
	account_ref1 = quickbooks_settings.bank_account
	account_ref = get_account_detail(account_ref1)
	if account_ref.get('account_currency') == company_currency:
		account.exchange_rate = 1
		account.credit_in_account_currency = flt(qb_supplier_credits.get("TotalAmt") * qb_supplier_credits.get('ExchangeRate'), account.precision("credit_in_account_currency"))
	else:
		account.exchange_rate = qb_supplier_credits.get('ExchangeRate')
		account.credit_in_account_currency = flt(qb_supplier_credits.get("TotalAmt") , account.precision("credit_in_account_currency"))

	account.account = quickbooks_settings.bank_account
	account.is_advance = "No"

def get_account_detail(account_ref):
	return frappe.db.get_value("Account", {"name": account_ref}, ["name", "account_currency"], as_dict=1)
