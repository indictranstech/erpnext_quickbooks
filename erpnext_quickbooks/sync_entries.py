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
					'qb_si_id':line.get('LinkedTxn')[0].get('TxnId')
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
	if frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": recived_payment.get('qb_si_id')}, "name"):
		row = validate_oustanding_amount_si(recived_payment)
		qb_account_name = frappe.db.get_value("Account", {"quickbooks_account_id": recived_payment.get('qb_account_id')}, "name")
		if row.get('name'):
			si_je = get_payment_entry_against_invoice("Sales Invoice", row.get('name'), amount=row.get('amount'), debit_in_account_currency=row.get('debit_in_account_currency'), journal_entry=False, bank_account=qb_account_name)
			si_je = frappe.get_doc(si_je)
			si_je.quickbooks_journal_entry_id = recived_payment.get('Id')
			si_je.naming_series = "SI-JV-Quickbooks-"
			si_je.voucher_type = _("Journal Entry")
			si_je.posting_date = recived_payment.get('TxnDate')
			if not si_je.difference ==0.0:
				create_diff_entry(si_je, quickbooks_settings)
			si_je.save()
			si_je.submit()
			frappe.db.commit()

def validate_oustanding_amount_si(recived_payment):
	"""validate outstanding amount"""
	accounts_details = {}
	accounts_details['amount'] = recived_payment.get('Amount')
	accounts_details['debit_in_account_currency'] = recived_payment.get('Amount')
	si = frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": recived_payment.get('qb_si_id')}, ["name","outstanding_amount"],as_dict=1)
	if recived_payment.get('Amount') > si.get('outstanding_amount'):
		accounts_details['amount'] = si.get('outstanding_amount')
	accounts_details['name'] = si.get('name')
	return accounts_details




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
					"qb_pi_id": linked_txn.get('LinkedTxn')[0].get('TxnId')
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
	if frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": bill_payment.get('qb_pi_id')}, "name"):
		row = validate_oustanding_amount(bill_payment)
		qb_account_name = frappe.db.get_value("Account", {"quickbooks_account_id": bill_payment.get('qb_account_id')}, "name")
		if bill_payment['PayType'] == "Check" and row.get('name'):
			pi_je = get_payment_entry_against_invoice("Purchase Invoice", row.get('name'), amount=row.get('amount'), debit_in_account_currency=row.get('debit_in_account_currency'), journal_entry=False, bank_account=qb_account_name)
			pi_je = frappe.get_doc(pi_je)
			pi_je.quickbooks_journal_entry_id = bill_payment.get('Id')
			pi_je.naming_series = "PI-JV-Quickbooks-"
			pi_je.voucher_type = _("Journal Entry")
			pi_je.posting_date = bill_payment.get('TxnDate')
			if not pi_je.difference ==0.0:
				create_diff_entry(pi_je, quickbooks_settings)
			pi_je.save()
			pi_je.submit()
			frappe.db.commit()

def validate_oustanding_amount(bill_payment):
	"""validate outstanding amount"""
	accounts_details = {}
	accounts_details['amount'] = bill_payment.get('Amount')
	accounts_details['debit_in_account_currency'] = bill_payment.get('Amount')
	pi = frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": bill_payment.get('qb_pi_id')}, ["name","outstanding_amount"],as_dict=1)
	if bill_payment.get('Amount') > pi.get('outstanding_amount'):
		accounts_details['amount'] = pi.get('outstanding_amount')
	accounts_details['name'] = pi.get('name')
	return accounts_details


def create_diff_entry(pi_je, quickbooks_settings):
	debit = abs(pi_je.difference) if pi_je.difference < 0  else ''
	credit = abs(pi_je.difference) if pi_je.difference > 0  else ''
	account = pi_je.append("accounts", {})
	account.account = quickbooks_settings.profit_loss_account
	account.debit_in_account_currency = debit
	account.credit_in_account_currency = credit
