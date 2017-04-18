from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cstr, nowdate
import requests.exceptions
from .utils import make_quickbooks_log, pagination
from erpnext.accounts.doctype.journal_entry.journal_entry import get_payment_entry_against_invoice

"""Important code to fetch payment done againt invoice and create journal Entry""" 

def sync_si_payment(quickbooks_obj):
	"""Fetch payment_invoice data from QuickBooks"""
	business_objects = "Payment"
	get_qb_payment = pagination(quickbooks_obj, business_objects)
	if get_qb_payment: 
		get_payment_received= validate_si_payment(get_qb_payment)
		if get_payment_received:
			sync_qb_journal_entry_against_si(get_payment_received)

def validate_si_payment(get_qb_payment):
	recived_payment = [] 
	for entries in get_qb_payment:
		if entries.get('DepositToAccountRef'):
			for line in entries['Line']:
				recived_payment.append({
					'Id': entries.get('Id')+"-"+'SI'+"-"+line.get('LinkedTxn')[0].get('TxnId'),
					'Type':	line.get('LinkedTxn')[0].get('TxnType'),
					'ExchangeRate': entries.get('ExchangeRate'),
					'Amount': line.get('Amount')*entries.get('ExchangeRate'),
					'TxnDate': entries.get('TxnDate'),
					'qb_account_id': entries.get('DepositToAccountRef').get('value'),
					'qb_si_id':line.get('LinkedTxn')[0].get('TxnId'),
					'paid_amount': line.get('Amount')
					})
	return recived_payment

def sync_qb_journal_entry_against_si(get_payment_received):
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	for recived_payment in get_payment_received:
 		try:
 			if not frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": recived_payment.get('Id')}, "name"):
 				create_journal_entry_against_si(recived_payment, quickbooks_settings)
 		except Exception, e:
 			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_si", message=frappe.get_traceback(),
						request_data=recived_payment, exception=True)


def create_journal_entry_against_si(recived_payment, quickbooks_settings):
	invoice_name =frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": recived_payment.get('qb_si_id')}, "name")
	if invoice_name:
		ref_doc = frappe.get_doc("Sales Invoice", invoice_name)
		si_je = frappe.get_doc({
			"doctype": "Journal Entry",
			"naming_series" : "SI-JV-Quickbooks-",
			"quickbooks_journal_entry_id" : recived_payment.get('Id'),
			"voucher_type" : _("Journal Entry"),
			"posting_date" : recived_payment.get('TxnDate'),
			"multi_currency": 1
		})
		get_journal_entry_account(si_je, "Sales Invoice", recived_payment, ref_doc, quickbooks_settings)
		# print si_je, "---------------"
		# data = si_je.accounts
		# for i in data:
		# 	print i.__dict__
		# print "\n\n"		
		# print "\n"
		si_je.save()
		si_je.submit()
		frappe.db.commit()

def get_journal_entry_account(si_je, doctype , recived_payment, ref_doc, quickbooks_settings):
	accounts_entry(si_je, doctype, recived_payment, ref_doc, quickbooks_settings)


def accounts_entry(si_je, doctype, recived_payment, ref_doc, quickbooks_settings):
	append_row_credit_detail(si_je= si_je, doctype= doctype, recived_payment= recived_payment, ref_doc=ref_doc, quickbooks_settings= quickbooks_settings)
	append_row_debit_detail(si_je= si_je, recived_payment = recived_payment, ref_doc=ref_doc, quickbooks_settings= quickbooks_settings)

def append_row_credit_detail(si_je= None, doctype= None, recived_payment = None, ref_doc=None, quickbooks_settings= None):
	# print recived_payment.get('ExchangeRate'), "00000000000000000000000000000000000000000000000000000000000000000000000000000"
	account = si_je.append("accounts", {})
	account.account = ref_doc.debit_to
	account.party_type =  "Customer"
	account.party = ref_doc.customer_name
	account.is_advance = "No"
	account.exchange_rate = recived_payment.get('ExchangeRate')
	account.credit = flt(recived_payment.get("Amount") , account.precision("credit"))
	account.credit_in_account_currency = flt(recived_payment.get("paid_amount") , account.precision("credit_in_account_currency"))
	account.reference_type = doctype
	account.reference_name = ref_doc.name


def append_row_debit_detail(si_je= None, recived_payment = None, ref_doc=None, quickbooks_settings= None):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")

	account = si_je.append("accounts", {})
	account_ref = get_account_detail(recived_payment.get('qb_account_id'))
	account.account = account_ref.get('name')
	if account_ref.get('account_currency') == company_currency:
		account.exchange_rate = 1
		account.debit_in_account_currency = flt(recived_payment.get("paid_amount") * recived_payment.get('ExchangeRate') , account.precision("debit_in_account_currency"))
	else:
		account.exchange_rate = recived_payment.get('ExchangeRate')
		account.debit_in_account_currency = flt(recived_payment.get("paid_amount") , account.precision("debit_in_account_currency"))

	account.is_advance = "No"


"""Important code to fetch payment done againt purchase invoice and create journal Entry against that PI""" 

def sync_pi_payment(quickbooks_obj):
	"""Fetch BillPayment data from QuickBooks"""
	business_objects = "BillPayment"
	get_qb_billpayment = pagination(quickbooks_obj, business_objects)
	if get_qb_billpayment:  
		get_bill_pi= validate_pi_payment(get_qb_billpayment)
		if get_bill_pi:
			sync_qb_journal_entry_against_pi(get_bill_pi)

def validate_pi_payment(get_qb_billpayment):
	paid_pi = []
	for entries in get_qb_billpayment:
		for linked_txn in entries['Line']:
			has_bank_ref = entries.get('CheckPayment').get('BankAccountRef') if entries.get('CheckPayment').get('BankAccountRef') else ''
			if has_bank_ref:
				paid_pi.append({
					"Id": entries.get('Id') + "-" +'PI'+"-"+ linked_txn.get('LinkedTxn')[0].get('TxnId'),
					"Type" : linked_txn.get('LinkedTxn')[0].get('TxnType'),
					"ExchangeRate" :entries.get('ExchangeRate'),
					"Amount": linked_txn.get('Amount')*entries.get('ExchangeRate'),
					"TxnDate" : entries.get('TxnDate'),
					"PayType" :entries.get('PayType'),
					"qb_account_id": entries.get('CheckPayment').get('BankAccountRef').get('value'),
					"qb_pi_id": linked_txn.get('LinkedTxn')[0].get('TxnId'),
					'paid_amount': linked_txn.get('Amount')
					})
	return paid_pi

def sync_qb_journal_entry_against_pi(get_bill_pi):
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	for bill_payment in get_bill_pi:
		try:
			if not frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": bill_payment.get('Id')}, "name"):
				create_journal_entry_against_pi(bill_payment, quickbooks_settings)
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_pi", message=frappe.get_traceback(),
						request_data=bill_payment, exception=True)


def create_journal_entry_against_pi(bill_payment, quickbooks_settings):
	invoice_name =frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": bill_payment.get('qb_pi_id')}, "name")
	if invoice_name:
		ref_doc = frappe.get_doc("Purchase Invoice", invoice_name)
		pi_je = frappe.get_doc({
			"doctype": "Journal Entry",
			"naming_series" : "PI-JV-Quickbooks-",
			"quickbooks_journal_entry_id" : bill_payment.get('Id'),
			"voucher_type" : _("Journal Entry"),
			"posting_date" : bill_payment.get('TxnDate'),
			"multi_currency": 1
		})
		get_journal_entry_account_pi(pi_je, "Purchase Invoice", bill_payment, ref_doc, quickbooks_settings)
		pi_je.save()
		pi_je.submit()
		frappe.db.commit()




def get_journal_entry_account_pi(pi_je, doctype , bill_payment, ref_doc, quickbooks_settings):
	accounts_entry_pi(pi_je, doctype, bill_payment, ref_doc, quickbooks_settings)


def accounts_entry_pi(pi_je, doctype, bill_payment, ref_doc, quickbooks_settings):
	append_row_debit_detail_pi(pi_je= pi_je, doctype= doctype, bill_payment= bill_payment, ref_doc=ref_doc, quickbooks_settings= quickbooks_settings)
	append_row_credit_detail_pi(pi_je= pi_je, bill_payment = bill_payment, ref_doc=ref_doc, quickbooks_settings= quickbooks_settings)

def append_row_debit_detail_pi(pi_je= None, doctype= None, bill_payment = None, ref_doc=None, quickbooks_settings= None):
	account = pi_je.append("accounts", {})
	account.account = ref_doc.credit_to
	account.party_type =  "Supplier"
	account.party = ref_doc.supplier_name
	account.is_advance = "No"
	account.exchange_rate = bill_payment.get('ExchangeRate')
	account.debit = flt(bill_payment.get("Amount") , account.precision("debit"))
	account.debit_in_account_currency = flt(bill_payment.get("paid_amount") , account.precision("debit_in_account_currency"))
	account.reference_type = doctype
	account.reference_name = ref_doc.name

def get_account_detail(quickbooks_account_id):
	return frappe.db.get_value("Account", {"quickbooks_account_id": quickbooks_account_id}, ["name", "account_currency"], as_dict=1)

def append_row_credit_detail_pi(pi_je= None, bill_payment = None, ref_doc=None, quickbooks_settings= None):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")

	account = pi_je.append("accounts", {})
	account_ref = get_account_detail(bill_payment.get('qb_account_id'))
	if account_ref.get('account_currency') == company_currency:
		account.exchange_rate = 1
		account.credit_in_account_currency = flt(bill_payment.get("paid_amount") * bill_payment.get('ExchangeRate'), account.precision("credit_in_account_currency"))
	else:
		account.exchange_rate = bill_payment.get('ExchangeRate')
		account.credit_in_account_currency = flt(bill_payment.get("paid_amount") , account.precision("credit_in_account_currency"))

	account.account = account_ref.get('name')
	account.is_advance = "No"
	