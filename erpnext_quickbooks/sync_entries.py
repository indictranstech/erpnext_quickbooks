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
		sync_qb_journal_entry_against_si(get_qb_payment)
	
def sync_qb_journal_entry_against_si(get_qb_payment):
	for recived_payment in get_qb_payment:
 		try:
 			if not frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": "SI" + recived_payment.get('Id')}, "name"):
 				create_journal_entry_against_si(recived_payment)
 		except Exception, e:
 			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_si", message=frappe.get_traceback(),
						request_data=recived_payment, exception=True)

def create_journal_entry_against_si(recived_payment):
 	exchange_rate = recived_payment['ExchangeRate']
  	transaction_date=recived_payment['TxnDate']
 	amount = recived_payment['Line'][0]['Amount'] * exchange_rate
  	Type = recived_payment['Line'][0]['LinkedTxn'][0]['TxnType']
	reference_quickbooks_invoce_id = recived_payment['Line'][0]['LinkedTxn'][0]['TxnId']
 	reference_qb_bank_account_id = recived_payment['DepositToAccountRef']['value'] if recived_payment.get('DepositToAccountRef') else ''
	if reference_qb_bank_account_id:
		sales_invoice_name = frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": reference_quickbooks_invoce_id}, "name")
		qb_account_name = frappe.db.get_value("Account", {"quickbooks_account_id": reference_qb_bank_account_id}, "name")
		if Type == "Invoice" and sales_invoice_name:
			si_je = get_payment_entry_against_invoice("Sales Invoice", sales_invoice_name, amount=amount, debit_in_account_currency=amount, journal_entry=False, bank_account=qb_account_name)
			si_je = frappe.get_doc(si_je)
			si_je.quickbooks_journal_entry_id = "SI" + recived_payment.get('Id')
			si_je.naming_series = "SI-JV-Quickbooks-"
			si_je.voucher_type = _("Journal Entry")
			si_je.posting_date = transaction_date
			si_je.save()
			si_je.submit()
			frappe.db.commit()



"""Important code to fetch payment done againt purchase invoice and create journal Entry against that PI""" 

def sync_pi_payment(quickbooks_obj):
	"""Fetch BillPayment data from QuickBooks"""
	business_objects = "BillPayment"
	get_qb_billpayment = pagination(quickbooks_obj, business_objects)
	if get_qb_billpayment:  
		sync_qb_journal_entry_against_pi(get_qb_billpayment)
	
def sync_qb_journal_entry_against_pi(get_qb_billpayment):
	for bill_payment in get_qb_billpayment:
		try:
			if not frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": "PI" + bill_payment.get('Id')}, "name"):
				create_journal_entry_against_pi(bill_payment)
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_pi", message=frappe.get_traceback(),
						request_data=bill_payment, exception=True)

	
def create_journal_entry_against_pi(bill_payment):
	transaction_date = bill_payment['TxnDate']
	currency_ref = bill_payment['CurrencyRef']
	exchange_rate = bill_payment['ExchangeRate']
	Type = bill_payment.get('PayType')
	amount = flt(bill_payment.get('Line')[0]['Amount']) * exchange_rate
	reference_quickbooks_pi_id = bill_payment.get('Line')[0]['LinkedTxn'][0]['TxnId'] if bill_payment['Line'] else ''
	reference_qb_bank_account_id = bill_payment.get('CheckPayment').get('BankAccountRef').get('value') if bill_payment.get('CheckPayment').get('BankAccountRef') else ''
	if reference_qb_bank_account_id:
		purchase_invoice_name = frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": reference_quickbooks_pi_id}, ["name", "conversion_rate"], as_dict=1)
		qb_account_name = frappe.db.get_value("Account", {"quickbooks_account_id": reference_qb_bank_account_id}, "name")
		if Type == "Check" and purchase_invoice_name['name']:
			pi_je = get_payment_entry_against_invoice("Purchase Invoice", purchase_invoice_name['name'], amount=amount, debit_in_account_currency=amount, journal_entry=False, bank_account=qb_account_name)
			pi_je = frappe.get_doc(pi_je)
			pi_je.quickbooks_journal_entry_id = "PI" + bill_payment.get('Id')
			pi_je.naming_series = "PI-JV-Quickbooks-"
			pi_je.voucher_type = _("Journal Entry")
			pi_je.posting_date = transaction_date
			pi_je.save()
			pi_je.submit()
			frappe.db.commit()

