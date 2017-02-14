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
	if qb_payment['QueryResponse']:
		get_qb_payment =  qb_payment['QueryResponse']['Payment']
		sync_qb_journal_entry_against_si(get_qb_payment)
	
def sync_qb_journal_entry_against_si(get_qb_payment):
	for recived_payment in get_qb_payment:
		create_journal_entry_against_si(recived_payment)
	
def create_journal_entry_against_si(recived_payment):
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
 	reference_qb_bank_account_id = recived_payment['DepositToAccountRef']['value'] if recived_payment.get('DepositToAccountRef') else None
	reference_quickbooks_invoce_id = recived_payment['Line'][0]['LinkedTxn'][0]['TxnId']

	qb_journal_entry_id = ''
	if Payment_Id:
		qb_journal_entry_id = "SI" + Payment_Id
	sales_invoice_name = frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": reference_quickbooks_invoce_id}, "name")
	qb_account_name = frappe.db.get_value("Account", {"quickbooks_account_id": reference_qb_bank_account_id}, "name")
	try:	
		if not 	frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": qb_journal_entry_id}, "name"): 	
			if Type == "Invoice" and sales_invoice_name:
				si_je = get_payment_entry_against_invoice("Sales Invoice", sales_invoice_name, amount=None, debit_in_account_currency=None, journal_entry=False, bank_account=qb_account_name)
				si_je = frappe.get_doc(si_je)
				si_je.quickbooks_journal_entry_id = qb_journal_entry_id
				si_je.naming_series = "SI-JV-Quickbooks-"
				si_je.voucher_type = _("Journal Entry")
				# si_je.user_remark = recived_payment.get('PaymentRefNum') if recived_payment.get('PaymentRefNum') else ""
				si_je.posting_date = Transaction_date
				si_je.save()
				si_je.submit()
				frappe.db.commit()
			else:
				raise Exception(" No Sales Invoice present ")
	except Exception, e:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				else:
					make_quickbooks_log(title=e.message, status="Error", method="create_journal_entry_against_si", message=frappe.get_traceback(),
						request_data=recived_payment, exception=True)


"""Important code to fetch payment done againt purchase invoice and create journal Entry against that PI""" 
def bill_payment(quickbooks_obj):
	"""Fetch BillPayment data from QuickBooks"""
	billpayment = """SELECT * FROM BillPayment""" 
	qb_billpayment = quickbooks_obj.query(billpayment)
	if qb_billpayment['QueryResponse']:
		get_qb_billpayment =  qb_billpayment['QueryResponse']['BillPayment']
		sync_qb_journal_entry_against_pi(get_qb_billpayment)
	
def sync_qb_journal_entry_against_pi(get_qb_billpayment):
	for made_payment in get_qb_billpayment:
		create_journal_entry_against_pi(made_payment)
	
def create_journal_entry_against_pi(made_payment):
	Transaction_date = made_payment['TxnDate']
	Supplier_Ref = made_payment['VendorRef']
	CurrencyRef = made_payment['CurrencyRef']
	Deposit_To_AccountRef = made_payment.get('CheckPayment')
	Amount =  made_payment.get('Line')[0]['Amount'] if made_payment['Line'] else made_payment['TotalAmt']
	Type = made_payment['PayType']
	reference_quickbooks_PI_id = made_payment.get('Line')[0]['LinkedTxn'][0]['TxnId'] if made_payment['Line'] else ''
	Bill_Payment_Id = made_payment['Id']
	reference_qb_bank_account_id = made_payment.get('CheckPayment').get('BankAccountRef').get('value') if made_payment.get('CheckPayment') else None

	qb_journal_entry_id = ''
	if Bill_Payment_Id:
		qb_journal_entry_id = "PI" + Bill_Payment_Id

	purchase_invoice_name = frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": reference_quickbooks_PI_id}, "name")
	qb_account_name = frappe.db.get_value("Account", {"quickbooks_account_id": reference_qb_bank_account_id}, "name")
	try:	
		if not 	frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": qb_journal_entry_id}, "name"): 	
			if Type == "Check" and purchase_invoice_name:
				pi_je = get_payment_entry_against_invoice("Purchase Invoice", purchase_invoice_name, amount=None, debit_in_account_currency=None, journal_entry=False, bank_account=qb_account_name)
				pi_je = frappe.get_doc(pi_je)
				pi_je.quickbooks_journal_entry_id = qb_journal_entry_id
				pi_je.naming_series = "PI-JV-Quickbooks-"
				pi_je.voucher_type = _("Journal Entry")
				pi_je.posting_date = Transaction_date
				pi_je.save()
				pi_je.submit()
				frappe.db.commit()
			else:
				raise Exception("No Purchase Invoice present")
	except Exception, e:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				else:
					make_quickbooks_log(title=e.message, status="Error", method="create_journal_entry_against_pi", message=frappe.get_traceback(),
						request_data=made_payment, exception=True)