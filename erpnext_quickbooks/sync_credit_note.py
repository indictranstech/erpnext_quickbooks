from __future__ import unicode_literals
import frappe
from frappe import _
import json
from frappe.utils import flt, cstr, nowdate
import requests.exceptions
from .utils import make_quickbooks_log, pagination
from pyqb.quickbooks.batch import batch_create, batch_delete

"""Sync all the Credit Note from Quickbooks to ERPNEXT"""
def sync_credit_notes(quickbooks_obj): 
	"""Fetch invoice data from QuickBooks"""
	quickbooks_credit_notes_list = [] 
	business_objects = "CreditMemo"
	get_qb_credit_notes =  pagination(quickbooks_obj, business_objects)
	if get_qb_credit_notes:
		sync_qb_credit_notes(get_qb_credit_notes, quickbooks_credit_notes_list)
		sync_qb_journal_entry_against_si(get_qb_credit_notes)

def sync_qb_credit_notes(get_qb_credit_notes, quickbooks_credit_notes_list):
	company_name = frappe.defaults.get_defaults().get("company")
	default_currency = frappe.db.get_value("Company" ,{"name":company_name},"default_currency")
	for qb_credit_note in get_qb_credit_notes:
		if valid_customer_and_product(qb_credit_note):
			try:
				create_note(qb_credit_note, quickbooks_credit_notes_list, default_currency)
			except Exception, e:
				make_quickbooks_log(title=e.message, status="Error", method="sync_qb_credit_notes", message=frappe.get_traceback(),
						request_data=qb_credit_note, exception=True)

def valid_customer_and_product(qb_credit_note):
	""" Fetch valid_customer data from ERPNEXT and store in ERPNEXT """ 
	from .sync_customers import create_customer
	customer_id = qb_credit_note['CustomerRef'].get('value') 
	if customer_id:
		if not frappe.db.get_value("Customer", {"quickbooks_cust_id": customer_id}, "name"):
			create_customer(qb_credit_note['CustomerRef'], quickbooks_customer_list = [])
	else:
		raise _("Customer is mandatory to create order")
	return True

def create_note(qb_credit_note, quickbooks_credit_notes_list, default_currency):
	""" Create credit Note in ERPNEXT """
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	create_stock_entry(qb_credit_note, quickbooks_settings, quickbooks_credit_notes_list, default_currency)

def create_stock_entry(qb_credit_note, quickbooks_settings, quickbooks_credit_notes_list, default_currency):
	""" 
	In ERPNext Sales return is created against SI.
	But 
	In Quickbooks Credit Note/Sales return is created against Customer not against any SI/Invoice,
	So, to maintain stock in ERPNext, it is necessary to create +ve Stock Entry as stock is again going 
	to increase as customer is returning the product.
	Than, after that Journal Entry is created with voucher type as Credit Note against Customer as advance payment. 
	"""
	stock_entry = frappe.db.get_value("Stock Entry", {"quickbooks_credit_memo_id": str(qb_credit_note.get("Id"))+"-"+"CN"}, "name")
	if not stock_entry:
		items = get_item_stock(qb_credit_note['Line'], quickbooks_settings)
		if items:
			stock_entry = frappe.get_doc({
				"doctype": "Stock Entry",
				"naming_series" : "CN-SE-QB-",
				"quickbooks_credit_memo_id" : str(qb_credit_note.get("Id"))+"-"+"CN",
				"posting_date" : qb_credit_note.get('TxnDate'),
				"purpose": "Material Receipt",
				"to_warehouse" : quickbooks_settings.warehouse,
				"quickbooks_customer_reference" : frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_credit_note['CustomerRef'].get('value')},"name"),
				"quickbooks_credit_memo_reference" : qb_credit_note.get("DocNumber"),
				"items" : items
				})
			stock_entry.flags.ignore_mandatory = True
			stock_entry.save(ignore_permissions=True)
			stock_entry.submit()

def get_item_stock(order_items, quickbooks_settings):
 	items = []
 	for qb_item in order_items:
 		shipp_item = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else 1
		if qb_item.get('SalesItemLineDetail') and shipp_item !="SHIPPING_ITEM_ID":
		 	item_code = get_item_code(qb_item)
		 	if item_code:
		 		items.append({
					"item_code": item_code,
					"rate": qb_item.get('SalesItemLineDetail').get('UnitPrice') if qb_item.get('SalesItemLineDetail').get('UnitPrice') else qb_item.get('Amount'),
					"qty": qb_item.get('SalesItemLineDetail').get('Qty') if qb_item.get('SalesItemLineDetail').get('Qty') else 1,
					"t_warehouse" : quickbooks_settings.warehouse,
					"warehouse": quickbooks_settings.warehouse,
					"uom": _("Nos")
					})
	return items

def get_item_code(qb_item):
	quickbooks_item_id = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else None
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id, "is_stock_item":1}, "item_code")
	return item_code

def sync_qb_journal_entry_against_si(get_qb_payment):
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	for recived_payment in get_qb_payment:
 		try:
 			if not frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": recived_payment.get('Id')+"CE"}, "name"):
 				create_journal_entry_against_si(recived_payment, quickbooks_settings)
 		except Exception, e:
 			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_si", message=frappe.get_traceback(),
						request_data=recived_payment, exception=True)

def create_journal_entry_against_si(recived_payment, quickbooks_settings):
	si_je = frappe.get_doc({
		"doctype": "Journal Entry",
		"naming_series" : "CN-JV-Qb-",
		"quickbooks_journal_entry_id" : recived_payment.get('Id')+"CE",
		"voucher_type" : _("Credit Note"),
		"posting_date" : recived_payment.get('TxnDate'),
		"multi_currency": 1
	})
	get_journal_entry_account(si_je, recived_payment, quickbooks_settings)
	si_je.save()
	si_je.submit()
	frappe.db.commit()

def get_journal_entry_account(si_je, recived_payment, quickbooks_settings):
	accounts_entry(si_je, recived_payment, quickbooks_settings)

def accounts_entry(si_je, recived_payment, quickbooks_settings):
	append_row_credit_detail(si_je= si_je, recived_payment= recived_payment, quickbooks_settings= quickbooks_settings)
	append_row_debit_detail(si_je= si_je, recived_payment = recived_payment, quickbooks_settings= quickbooks_settings)

def append_row_credit_detail(si_je= None, recived_payment = None, quickbooks_settings= None):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")

	account = si_je.append("accounts", {})
	account.account = set_debit_to(si_je, recived_payment, quickbooks_settings, company_currency)
	account.party_type =  "Customer"
	account.party = frappe.db.get_value("Customer",{"quickbooks_cust_id":recived_payment['CustomerRef'].get('value')},"name")
	account.is_advance = "Yes"
	account.exchange_rate = recived_payment.get('ExchangeRate')
	account.credit = flt(recived_payment.get("TotalAmt") * recived_payment.get('ExchangeRate'), account.precision("credit"))
	account.credit_in_account_currency = flt(recived_payment.get("TotalAmt") , account.precision("credit_in_account_currency"))

def set_debit_to(si_je, recived_payment, quickbooks_settings, company_currency):
	"Set debit account"
	party_currency = recived_payment.get("CurrencyRef").get('value') if recived_payment.get("CurrencyRef") else company_currency
	if party_currency:
		debtors_account = frappe.db.get_value("Account", {"account_currency": party_currency, "quickbooks_account_id": ["!=",""], 'account_type': 'Receivable',\
			"company": quickbooks_settings.select_company, "root_type": "Asset", "is_group": "0"}, "name")
		return debtors_account

def append_row_debit_detail(si_je= None, recived_payment = None, quickbooks_settings= None):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")

	account = si_je.append("accounts", {})
	account_ref1 = quickbooks_settings.bank_account
	account_ref = get_account_detail(account_ref1)
	account.account = account_ref.get('name')
	if account_ref.get('account_currency') == company_currency:
		account.exchange_rate = 1
		account.debit_in_account_currency = flt(recived_payment.get("TotalAmt") * recived_payment.get('ExchangeRate') , account.precision("debit_in_account_currency"))
	else:
		account.exchange_rate = recived_payment.get('ExchangeRate')
		account.debit_in_account_currency = flt(recived_payment.get("TotalAmt") , account.precision("debit_in_account_currency"))

	account.is_advance = "No"

def get_account_detail(account_ref):
	return frappe.db.get_value("Account", {"name": account_ref}, ["name", "account_currency"], as_dict=1)