from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cstr, nowdate
import requests.exceptions
from .utils import make_quickbooks_log, pagination
from erpnext.accounts.doctype.journal_entry.journal_entry import get_payment_entry_against_invoice

""" Create Payment entry against Sales Invoices"""
def sync_si_payment(quickbooks_obj):
	"""Get all Payment(Payment Entry) from QuickBooks for all the Received Payment"""
	business_objects = "Payment"
	get_qb_payment = pagination(quickbooks_obj, business_objects)
	if get_qb_payment: 
		get_payment_received= get_payment_dict(get_qb_payment)
		if get_payment_received:
			sync_qb_journal_entry_against_si(get_payment_received)
		get_payments_against_credit_entries(get_qb_payment)

def get_payment_dict(get_qb_payment):
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
					'paid_amount': line.get('Amount'),
					"doc_no": entries.get("DocNumber")
					})
	return recived_payment


def get_payments_against_credit_entries(get_qb_payment):
	"""Get payment entries against credit note"""
	try:
		payment_against_credit_note = []
		for entries in get_qb_payment:
			if not entries.get('DepositToAccountRef'):
				payment_against_credit_note.append(entries);
		if payment_against_credit_note:
			adjust_entries(payment_against_credit_note)
	except Exception, e:
 			make_quickbooks_log(title=e.message, status="Error", method="get_payments_against_credit_entries", message=frappe.get_traceback(),
						request_data=get_qb_payment, exception=True)

def adjust_entries(payment_against_credit_note):
	for entries in payment_against_credit_note:
		payments, credit_notes = {}, [] 
		for line in entries['Line']:
			payment_dict = get_credit_note_dict(entries, line)
			if line.get('LinkedTxn')[0].get('TxnType') == "Invoice":
				payments[payment_dict.get("qb_si_id")] = payment_dict
				payments[payment_dict.get("qb_si_id")]["credit_notes"] = []
			else:
				credit_notes.append(payment_dict)
		
		for row in payments:
			payments[row]["credit_notes"].extend(credit_notes)
		
		if payments:
			adjust_je_against_cn(payments)

def get_credit_note_dict(entries, line):
	return {
		'Id': entries.get('Id')+"-"+'SI'+"-"+line.get('LinkedTxn')[0].get('TxnId'),
		'Type':	line.get('LinkedTxn')[0].get('TxnType'),
		'ExchangeRate': entries.get('ExchangeRate'),
		'Amount': flt(line.get('Amount')*entries.get('ExchangeRate'),2),
		'TxnDate': entries.get('TxnDate'),
		'qb_si_id': line.get('LinkedTxn')[0].get('TxnId') if line.get('LinkedTxn')[0].get('TxnType') == "Invoice" else None,
		'paid_amount': flt(line.get('Amount')),
		"doc_no": entries.get("DocNumber"),
		"credit_note_id" : line.get('LinkedTxn')[0].get('TxnId')+"CE" if line.get('LinkedTxn')[0].get('TxnType') == "CreditMemo" else None,
		"customer_name" : frappe.db.get_value("Customer",{"quickbooks_cust_id":entries['CustomerRef'].get('value')},"name")
	}

def adjust_je_against_cn(payments):
	""" Adjust Journal Entries against Credit Note """
	for si, value in payments.iteritems():
		if len(value['credit_notes']) == 1:
			for cn in value['credit_notes']:
				lst = []
				quickbooks_journal_entry_id = cn.get('credit_note_id')
				args = get_jv_voucher_detail_no(quickbooks_journal_entry_id)
				si_name =frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": value.get('qb_si_id'),
				"outstanding_amount":['!=',0] }, "name")
				if args.get('voucher_detail_no') and args.get('unadjusted_amount') and si_name:
					invoice = frappe.get_doc("Sales Invoice", si_name)
					lst.append(frappe._dict(reconcile_entry(args, "Sales Invoice", si_name,
						invoice, paid_amt=value.get('paid_amount'))))
				if lst:
					from erpnext.accounts.utils import reconcile_against_document
					reconcile_against_document(lst)
					frappe.db.commit()
		elif len(value['credit_notes']) > 1:
			for cn in value['credit_notes']:
				lst1 = []
				quickbooks_journal_entry_id = cn.get('credit_note_id')
				args = get_jv_voucher_detail_no(quickbooks_journal_entry_id)
				si_name =frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": value.get('qb_si_id'),
				"outstanding_amount":['!=',0] }, "name")
				if args.get('voucher_detail_no') and args.get('unadjusted_amount') and si_name:
					invoice = frappe.get_doc("Sales Invoice", si_name)
					lst1.append(frappe._dict(reconcile_entry(args, "Sales Invoice", si_name,
						invoice, paid_amt=cn.get('paid_amount'))))
				if lst1:
					from erpnext.accounts.utils import reconcile_against_document
					reconcile_against_document(lst1)
					frappe.db.commit()


def reconcile_entry(args, invoice_type , invoice_name, invoice, paid_amt=None):
	if invoice_type == "Purchase Invoice":
		dr_or_cr = "debit_in_account_currency"
		party_type = "Supplier"
		party = invoice.get('supplier_name')
		account = invoice.get("credit_to")
	elif invoice_type == "Sales Invoice":
		dr_or_cr = "credit_in_account_currency"
		party_type = "Customer"
		party = invoice.get('customer_name')
		account = invoice.get('debit_to')
	return {
		'voucher_type' : 'Journal Entry',
		'voucher_no' : args.get('voucher_no'),
		'voucher_detail_no' : args.get('voucher_detail_no'),
		'against_voucher_type' : invoice_type,
		'against_voucher'  : invoice_name,
		'account' : account,
		'party_type': party_type,
		'party': party,
		'is_advance' : "Yes",
		'dr_or_cr' : dr_or_cr,
		'unadjusted_amount' : round(args.get('unadjusted_amount'),2),
		'allocated_amount' : round(paid_amt,2)
	}


def get_jv_voucher_detail_no(quickbooks_journal_entry_id):
	account_dict ={}
	jv_name = frappe.db.get_value("Journal Entry",
		{"quickbooks_journal_entry_id": quickbooks_journal_entry_id}, "name")
	jv = frappe.get_doc("Journal Entry", jv_name)

	if jv.get('voucher_type') == 'Credit Note':
		for row in jv.accounts:
			if row.get('credit_in_account_currency') and not row.get('reference_name'):
				account_dict['voucher_detail_no'] = row.get('name')
				account_dict['unadjusted_amount'] = row.get('credit_in_account_currency')
		account_dict['voucher_no'] = jv_name
	elif jv.get('voucher_type') == 'Debit Note':
		for row in jv.accounts:
			if row.get('debit_in_account_currency') and not row.get('reference_name'):
				account_dict['voucher_detail_no'] = row.get('name')
				account_dict['unadjusted_amount'] = row.get('debit_in_account_currency')
		account_dict['voucher_no'] = jv_name
	return frappe._dict(account_dict)

	
def sync_qb_journal_entry_against_si(get_payment_received):
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	for recived_payment in get_payment_received:
 		try:
 			if not frappe.db.get_value("Payment Entry", {"quickbooks_payment_id": recived_payment.get('Id')}, "name"):
 				create_payment_entry_si(recived_payment, quickbooks_settings)
 		except Exception, e:
 			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_si", message=frappe.get_traceback(),
						request_data=recived_payment, exception=True)

def create_payment_entry_si(recived_payment, quickbooks_settings):
	""" create payment entry against sales Invoice """
	invoice_name =frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": recived_payment.get('qb_si_id')}, "name")
	account_ref = get_account_detail(recived_payment.get('qb_account_id'))
	if invoice_name:
		ref_doc = frappe.get_doc("Sales Invoice", invoice_name)
		si_pe = frappe.new_doc("Payment Entry")
		si_pe.naming_series = "SI-PE-QB-"
		si_pe.quickbooks_invoice_reference_no = ref_doc.get('quickbooks_invoice_no')
		si_pe.quickbooks_payment_reference_no = recived_payment.get('doc_no')
		si_pe.posting_date = recived_payment.get('TxnDate')
		si_pe.quickbooks_payment_id = recived_payment.get('Id')
		si_pe.payment_type = "Receive"
		si_pe.party_type = "Customer"
		si_pe.party = ref_doc.customer_name
		si_pe.paid_from = ref_doc.get("debit_to")
		# si_pe.paid_to = account_ref.get('name')
		si_pe.paid_amount= flt(recived_payment.get('paid_amount'), si_pe.precision('paid_amount'))
		si_pe.source_exchange_rate = recived_payment.get('ExchangeRate')
		si_pe.base_paid_amount = flt(recived_payment.get('paid_amount') * recived_payment.get('ExchangeRate'), si_pe.precision('base_paid_amount'))
		si_pe.base_received_amount = flt(recived_payment.get('paid_amount') * recived_payment.get('ExchangeRate'), si_pe.precision('base_received_amount'))
		si_pe.allocate_payment_amount = 1
		si_pe.reference_no = recived_payment.get('Type')
		si_pe.reference_date = recived_payment.get('TxnDate')

		get_accounts(si_pe, ref_doc, recived_payment, quickbooks_settings)
		get_reference(dt= "Sales Invoice", pay_entry_obj= si_pe, ref_doc= ref_doc, ref_pay= recived_payment, quickbooks_settings= quickbooks_settings)
		get_deduction(dt= "Sales Invoice", pay_entry_obj= si_pe, ref_doc= ref_doc, ref_pay= recived_payment, quickbooks_settings= quickbooks_settings)
		
		si_pe.flags.ignore_mandatory = True
		si_pe.save(ignore_permissions=True)
		si_pe.submit()
		frappe.db.commit()

def get_accounts(si_pe, ref_doc, recived_payment, quickbooks_settings):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")
	account_ref = get_account_detail(recived_payment.get('qb_account_id'))
	si_pe.paid_to = account_ref.get('name')
	if account_ref.get('account_currency') == company_currency:
		si_pe.target_exchange_rate = 1
		si_pe.received_amount = flt(recived_payment.get('paid_amount') * recived_payment.get('ExchangeRate'), si_pe.precision('received_amount'))
	else:
		si_pe.target_exchange_rate = recived_payment.get('ExchangeRate')
		si_pe.received_amount = flt(recived_payment.get('paid_amount') , si_pe.precision('received_amount'))


""" Create Payment entry against Purchase Invoices""" 

def sync_pi_payment(quickbooks_obj):
	"""Get all BillPayment(Payment Entry) from QuickBooks for all the paid Bills"""
	business_objects = "BillPayment"
	get_qb_billpayment = pagination(quickbooks_obj, business_objects)
	if get_qb_billpayment:  
		get_bill_pi = get_bill_payment_dict(get_qb_billpayment)
		if get_bill_pi:
			sync_qb_journal_entry_against_pi(get_bill_pi)
		get_payments_against_debit_entries(get_qb_billpayment)

def get_bill_payment_dict(get_qb_billpayment):
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
					'paid_amount': linked_txn.get('Amount'),
					"doc_no": entries.get("DocNumber")
					})
	return paid_pi


def get_vendor_debit_dict(entries, line):
	return {
		'Id': entries.get('Id')+"-"+'PI'+"-"+line.get('LinkedTxn')[0].get('TxnId'),
		'Type':	line.get('LinkedTxn')[0].get('TxnType'),
		'ExchangeRate': entries.get('ExchangeRate'),
		'Amount': flt(line.get('Amount')*entries.get('ExchangeRate'), 2),
		'TxnDate': entries.get('TxnDate'),
		'qb_pi_id': line.get('LinkedTxn')[0].get('TxnId') if line.get('LinkedTxn')[0].get('TxnType') == "Bill" else None,
		'paid_amount': flt(line.get('Amount')),
		"doc_no": entries.get("DocNumber"),
		"vendor_credit_id" : line.get('LinkedTxn')[0].get('TxnId')+"DE" if line.get('LinkedTxn')[0].get('TxnType') == "VendorCredit" else None,
	}

def adjust_debit_entries(payment_against_debit_note):
	for entries in payment_against_debit_note:
		payments, vendor_credit = {}, [] 
		for line in entries['Line']:
			payment_dict = get_vendor_debit_dict(entries, line)
			if line.get('LinkedTxn')[0].get('TxnType') == "Bill":
				payments[payment_dict.get("qb_pi_id")] = payment_dict
				payments[payment_dict.get("qb_pi_id")]["vendor_credit"] = []
			else:
				vendor_credit.append(payment_dict)
		
		for row in payments:
			payments[row]["vendor_credit"].extend(vendor_credit)
		
		if payments:
			adjust_je_against_dn(payments)

def get_payments_against_debit_entries(get_qb_payment):
	"""Get payment entries against credit note"""
	try:
		payment_against_debit_note = []
		for entries in get_qb_payment:
			if not entries.get('CheckPayment').get('BankAccountRef'):
				payment_against_debit_note.append(entries);
		if payment_against_debit_note:
			adjust_debit_entries(payment_against_debit_note)
	except Exception, e:
 			make_quickbooks_log(title=e.message, status= "Error", method="get_payments_against_debit_entries", message=frappe.get_traceback(),
						request_data= get_qb_payment, exception= True)

def adjust_je_against_dn(payments):
	""" Adjust Journal Entries against Debit Note """
	try :
		for pi, value in payments.iteritems():
			if len(value['vendor_credit']) == 1:
				for dn in value['vendor_credit']:
					lst = []
					quickbooks_journal_entry_id = dn.get('vendor_credit_id')
					args = get_jv_voucher_detail_no(quickbooks_journal_entry_id)
					pi_name =frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": value.get('qb_pi_id'),
					"outstanding_amount":['!=',0] }, "name")
					if args.get('voucher_detail_no') and args.get('unadjusted_amount') and pi_name:
						invoice = frappe.get_doc("Purchase Invoice", pi_name)
						lst.append(frappe._dict(reconcile_entry(args, "Purchase Invoice", pi_name,
							invoice, paid_amt=value.get('paid_amount'))))
					if lst:
						from erpnext.accounts.utils import reconcile_against_document
						reconcile_against_document(lst)
						frappe.db.commit()
			elif len(value['vendor_credit']) > 1:
				for dn in value['vendor_credit']:
					lst1 = []
					quickbooks_journal_entry_id = dn.get('vendor_credit_id')
					args = get_jv_voucher_detail_no(quickbooks_journal_entry_id)
					pi_name =frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": value.get('qb_pi_id'),
					"outstanding_amount":['!=',0] }, "name")
					if args.get('voucher_detail_no') and args.get('unadjusted_amount') and pi_name:
						invoice = frappe.get_doc("Purchase Invoice", pi_name)
						lst1.append(frappe._dict(reconcile_entry(args, "Purchase Invoice", pi_name,
							invoice, paid_amt=dn.get('paid_amount'))))
					if lst1:
						from erpnext.accounts.utils import reconcile_against_document
						reconcile_against_document(lst1)
						frappe.db.commit()
	except Exception, e:
		make_quickbooks_log(title=e.message, status="Error", method="adjust_je_against_dn", message=frappe.get_traceback(),
						request_data=payments, exception=True)



def sync_qb_journal_entry_against_pi(get_bill_pi):
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	for bill_payment in get_bill_pi:
		try:
			if not frappe.db.get_value("Payment Entry", {"quickbooks_payment_id": bill_payment.get('Id')}, "name"):
				create_payment_entry_pi(bill_payment, quickbooks_settings)
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_pi", message=frappe.get_traceback(),
						request_data=bill_payment, exception=True)



def create_payment_entry_pi(bill_payment, quickbooks_settings):
	""" create payment entry against Purchase Invoice """

	invoice_name =frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": bill_payment.get('qb_pi_id')}, "name")
	account_ref = get_account_detail(bill_payment.get('qb_account_id'))
	if invoice_name:
		ref_doc = frappe.get_doc("Purchase Invoice", invoice_name)
		pi_pe = frappe.new_doc("Payment Entry")
		pi_pe.naming_series = "PI-PE-QB-"
		pi_pe.quickbooks_invoice_reference_no = ref_doc.get('quickbooks_bill_no')
		pi_pe.quickbooks_payment_reference_no = bill_payment.get('doc_no')
		pi_pe.posting_date = bill_payment.get('TxnDate')
		pi_pe.quickbooks_payment_id = bill_payment.get('Id')
		pi_pe.payment_type = "Pay"
		pi_pe.party_type = "Supplier"
		pi_pe.party = ref_doc.supplier_name
		pi_pe.paid_to = ref_doc.get("credit_to")
		pi_pe.received_amount = flt(bill_payment.get('paid_amount'), pi_pe.precision('received_amount'))
		pi_pe.target_exchange_rate = bill_payment.get('ExchangeRate')
		pi_pe.base_received_amount =  flt(bill_payment.get('paid_amount') * bill_payment.get('ExchangeRate'), pi_pe.precision('base_received_amount'))
		pi_pe.base_paid_amount = flt(bill_payment.get('paid_amount') * bill_payment.get('ExchangeRate'), pi_pe.precision('base_paid_amount'))
		pi_pe.allocate_payment_amount = 1
		pi_pe.reference_no = bill_payment.get('Type')
		pi_pe.reference_date = bill_payment.get('TxnDate')

		get_accounts_pi(pi_pe, ref_doc, bill_payment, quickbooks_settings)
		get_reference(dt= "Purchase Invoice", pay_entry_obj= pi_pe, ref_doc= ref_doc, ref_pay= bill_payment, quickbooks_settings= quickbooks_settings)
		get_deduction(dt= "Purchase Invoice", pay_entry_obj= pi_pe, ref_doc= ref_doc, ref_pay= bill_payment, quickbooks_settings= quickbooks_settings)
		pi_pe.flags.ignore_mandatory = True
		pi_pe.save(ignore_permissions=True)
		pi_pe.submit()
		frappe.db.commit()

def get_accounts_pi(pi_pe, ref_doc, bill_payment, quickbooks_settings):
	""" set exchange rate and payment amount , when payment is done in multi currency, apart from system currency """

	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")
	account_ref = get_account_detail(bill_payment.get('qb_account_id'))
	pi_pe.paid_from = account_ref.get('name')
	if account_ref.get('account_currency') == company_currency:
		pi_pe.source_exchange_rate = 1
		pi_pe.paid_amount = flt(bill_payment.get('paid_amount') * bill_payment.get('ExchangeRate'), pi_pe.precision('paid_amount'))
	else:
		pi_pe.source_exchange_rate = bill_payment.get('ExchangeRate')
		pi_pe.paid_amount = flt(bill_payment.get('paid_amount') , pi_pe.precision('paid_amount'))



def get_reference(dt= None, pay_entry_obj= None, ref_doc= None, ref_pay= None, quickbooks_settings= None):
	""" get reference of Invoices for which payment is done. """

	account = pay_entry_obj.append("references", {})
	account.reference_doctype = dt
	account.reference_name = ref_doc.get('name')
	account.total_amount = flt(ref_doc.get('grand_total'), account.precision('total_amount'))
	account.allocated_amount = flt(ref_pay.get('paid_amount'), account.precision('allocated_amount'))


def get_deduction(dt= None, pay_entry_obj= None, ref_doc= None, ref_pay= None, quickbooks_settings= None):
	"""	calculate deduction for Multi currency gain and loss """
	if dt == "Purchase Invoice":
		total_allocated_amount = flt(ref_pay.get("paid_amount") * ref_doc.get('conversion_rate'))
		recevied_amount = flt(ref_pay.get("paid_amount") * ref_pay.get('ExchangeRate'))
		deduction_amount = recevied_amount - total_allocated_amount
	else:
		total_allocated_amount = flt(flt(ref_pay.get("paid_amount")) * flt(ref_doc.get('conversion_rate')))
		deduction_amount = total_allocated_amount - pay_entry_obj.base_received_amount

	if round(deduction_amount, 2):
		deduction = pay_entry_obj.append("deductions",{})
		deduction.account = quickbooks_settings.profit_loss_account
		deduction.cost_center = frappe.db.get_value("Company",{"name": quickbooks_settings.select_company },"cost_center")
		deduction.amount = deduction_amount

def get_account_detail(quickbooks_account_id):
	""" account for payment """
	return frappe.db.get_value("Account", {"quickbooks_account_id": quickbooks_account_id}, ["name", "account_currency"], as_dict=1)

# def reconcile_entry(args, si_name, invoice, paid_amt=None):
# 	return {
# 		'voucher_type' : 'Journal Entry',
# 		'voucher_no' : args.get('voucher_no'),
# 		'voucher_detail_no' : args.get('voucher_detail_no'),
# 		'against_voucher_type' : 'Sales Invoice',
# 		'against_voucher'  : si_name,
# 		'account' : invoice.get('debit_to'),
# 		'party_type': "Customer",
# 		'party': invoice.get('customer_name'),
# 		'is_advance' : "Yes",
# 		'dr_or_cr' : "credit_in_account_currency",
# 		'unadjusted_amount' : round(args.get('unadjusted_amount'),2),
# 		'allocated_amount' : round(paid_amount,2)
# 	}	

