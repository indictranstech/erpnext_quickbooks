from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log
from erpnext.accounts.doctype.journal_entry.journal_entry import get_payment_entry_against_invoice

"""Important code to fetch payment done againt invoice and create journal Entry""" 

def payment_invoice(quickbooks_obj):
	"""Fetch payment_invoice data from QuickBooks"""
	payment = """SELECT * from Payment""" 
	qb_payment = quickbooks_obj.query(payment)
	get_qb_payment =  qb_payment['QueryResponse']['Payment']
	sync_qb_journal_entry(get_qb_payment)
	
def sync_qb_journal_entry(get_qb_payment):
	for recived_payment in get_qb_payment:
		create_journal_entry(recived_payment)


# def sync_qb_journal_entry(payment1):
# 	for recived_payment in payment1:
# 		create_journal_entry(recived_payment)

	
def create_journal_entry(recived_payment):
	item = []
	for i in recived_payment['Line'][0]['LineEx']['any']:
		item.append(i.get('value'))
	
 	LineEx = item
 	Payment_Id = recived_payment['Id']
 	TotalAmt = recived_payment['TotalAmt']
 	Transaction_date=recived_payment['TxnDate']
 	Amount = recived_payment['Line'][0]['Amount']
 	Customer_reference = recived_payment['CustomerRef']
 	Type = recived_payment['Line'][0]['LinkedTxn'][0]['TxnType']
 	Deposit_To_AccountRef = recived_payment['DepositToAccountRef']
	reference_quickbooks_invoce_id = recived_payment['Line'][0]['LinkedTxn'][0]['TxnId']

	qb_journal_entry_id = ''
	if Payment_Id:
		qb_journal_entry_id = "SI" + Payment_Id
	sales_invoice_name = frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": reference_quickbooks_invoce_id}, "name")
	try:	
		if not 	frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": qb_journal_entry_id}, "name"): 	
			if Type == "Invoice" and sales_invoice_name:
				si_je = get_payment_entry_against_invoice("Sales Invoice", sales_invoice_name, amount=None, debit_in_account_currency=None, journal_entry=False, bank_account=None)
				si_je = frappe.get_doc(si_je)
				si_je.quickbooks_journal_entry_id = qb_journal_entry_id
				si_je.naming_series = "SI-JV-Quickbooks-"
				si_je.cheque_no ="dummy check"
				si_je.cheque_date =Transaction_date
				si_je.posting_date = Transaction_date
				si_je.save()
				si_je.submit()
				frappe.db.commit()
			else:
				raise _("No Sales Invoice present with this ")
	except Exception, e:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				else:
					make_quickbooks_log(title=e.message, status="Error", method="create_journal_entry", message=frappe.get_traceback(),
						request_data=recived_payment, exception=True)

