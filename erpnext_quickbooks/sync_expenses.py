from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from frappe.utils import flt, cstr, nowdate
from .utils import make_quickbooks_log, pagination
import csv
# from pyqb.quickbooks.batch import batch_create, batch_delete
# from pyqb.quickbooks.objects.customer import Customer 

def sync_expenses(quickbooks_obj):
	"""Fetch Expenses data from QuickBooks"""
	quickbooks_expense_list = []
	business_objects = "Purchase"
	get_qb_expenses = pagination(quickbooks_obj, business_objects)
	if get_qb_expenses:
		sync_qb_expenses(get_qb_expenses)

# def create_csv(l):
# 	with open('expense','w') as fp:
# 		a = csv.writer(fp)
# 		data =[l]
# 		a.writerows(data)


def sync_qb_expenses(get_qb_expenses):
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	for expenses in get_qb_expenses:
 		try:
 			if not frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": cstr(expenses.get('Id'))+'-'+'EXP'}, "name"):
				create_expenses(expenses, quickbooks_settings)
 		except Exception, e:
 			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_expenses", message=frappe.get_traceback(),
						request_data=expenses, exception=True)


def create_expenses(expenses, quickbooks_settings):
	exp = frappe.get_doc({
		"doctype": "Journal Entry",
		"naming_series" : "EXP-JV-Quickbooks-",
		"quickbooks_journal_entry_id" : expenses.get('Id')+"-"+"EXP",
		"voucher_type" : _("Journal Entry"),
		"posting_date" : expenses.get('TxnDate'),
		"multi_currency": 1
	})
	exp_cur = validate(expenses)
	print expenses
	print "\n\n"
	print exp_cur, "111", expenses.get('EntityRef') , expenses.get('CurrencyRef') , expenses.get('AccountRef'), expenses.get('ExchangeRate')
	get_journal_entry_account(exp, expenses, quickbooks_settings, exp_cur)
	data = exp.accounts
	for i in data:
		print i.__dict__
	print "\n\n"		
	print "\n"
	exp.save()
	exp.submit()
	frappe.db.commit()


def party_credit_debit_entry(exp, expenses, quickbooks_settings, exp_cur):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")
	party_ref = get_party_type(expenses)
	if party_ref:
		party_debit(exp, expenses, party_ref, quickbooks_settings, company_currency)
		party_credit(exp, expenses, party_ref, quickbooks_settings, company_currency)

def append_row_party_detail(exp= None, party_ref=None, quickbooks_settings= None, debit_in_account_currency=None, credit_in_account_currency=None, exchange_rate = None, is_advance= None):
	account = exp.append("accounts", {})
	account.party_type =  party_ref.get('party_type')
	account.party = party_ref.get('name')
	account.is_advance = is_advance
	account.exchange_rate = exchange_rate
	get_creditors_debtors_account(account, party_ref, quickbooks_settings)
	if debit_in_account_currency!= None and debit_in_account_currency != 0:
		account.debit_in_account_currency = flt(debit_in_account_currency , account.precision("debit_in_account_currency"))
		
	if credit_in_account_currency != None and credit_in_account_currency != 0:
		account.credit_in_account_currency = flt(credit_in_account_currency , account.precision("credit_in_account_currency"))

def get_creditors_debtors_account(account, party_ref, quickbooks_settings):
	if party_ref.get('party_type') == 'Supplier':
		debtors_account =frappe.db.get_value("Account", {"account_currency": party_ref.get('default_currency'), 'account_type': 'Payable', "root_type": "Liability"}, "name")
		account.account = debtors_account if debtors_account else frappe.db.get_value("Company", {"name": quickbooks_settings.select_company}, "default_payable_account")
		account.account_currency = party_ref.get('default_currency')
		print account.account, "--------------------",account.account_currency
	elif party_ref.get('party_type') == 'Customer':
		creditors_account =frappe.db.get_value("Account", {"account_currency": party_ref.get('default_currency'), 'account_type': 'Receivable', "root_type": "Asset"}, "name")
		account.account = creditors_account if creditors_account else frappe.db.get_value("Company", {"name": quickbooks_settings.select_company}, "default_receivable_account")
		account.account_currency = party_ref.get('default_currency')

def party_debit(exp, expenses, party_ref, quickbooks_settings, company_currency):
	total_tax = expenses.get('TxnTaxDetail').get('TotalTax') if expenses.get('TxnTaxDetail') else 0
	if party_ref.get('default_currency') == company_currency:
		print "if",party_ref.get('default_currency')
		exchange_rate = 1
		debit_amount = flt(expenses.get('TotalAmt') - total_tax)* expenses.get('ExchangeRate')
	else:
		print "elseif",party_ref.get('default_currency'), expenses.get('ExchangeRate')
		exchange_rate = expenses.get('ExchangeRate')
		debit_amount = flt(expenses.get('TotalAmt') - total_tax)
		print debit_amount, "ddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
	if party_ref:
		append_row_party_detail(exp = exp, party_ref= party_ref, quickbooks_settings = quickbooks_settings, debit_in_account_currency=debit_amount , credit_in_account_currency = None, exchange_rate = exchange_rate, is_advance= "Yes")

def party_credit(exp, expenses, party_ref, quickbooks_settings, company_currency):
	total_tax = expenses.get('TxnTaxDetail').get('TotalTax') if expenses.get('TxnTaxDetail') else 0
	if party_ref.get('default_currency') == company_currency:
		print "if",party_ref.get('default_currency')
		exchange_rate = 1
		credit_amount = flt(expenses.get('TotalAmt') - total_tax) * expenses.get('ExchangeRate')
	else:
		print "esle if",party_ref.get('default_currency')
		exchange_rate = expenses.get('ExchangeRate')
		credit_amount = flt(expenses.get('TotalAmt') - total_tax)
		print credit_amount, "credddddddddddddddddddddddddddddddddd"

	if party_ref:
		append_row_party_detail(exp = exp, party_ref= party_ref, quickbooks_settings= quickbooks_settings, debit_in_account_currency=None , credit_in_account_currency = credit_amount, exchange_rate = exchange_rate, is_advance= "No")

def get_party_type(expenses):
	# u'EntityRef': {u'type': u'Vendor', u'name': u'Supplier 4', u'value': u'9'}
	entity_ref = expenses.get('EntityRef')
	if entity_ref:
		quickbooks_party_type = 'Supplier' if entity_ref.get('type') == "Vendor" else 'Customer'
		if quickbooks_party_type == "Customer":
			return frappe.db.get_value("Customer", {"quickbooks_cust_id": entity_ref.get('value')}, ["name","default_currency"],as_dict=1).update({"party_type":"Customer"})
		elif quickbooks_party_type == "Supplier":
			return frappe.db.get_value("Supplier", {"quickbooks_supp_id": entity_ref.get('value')}, ["name","default_currency"],as_dict=1).update({"party_type":"Supplier"})
	else:
		return {}


	
def get_journal_entry_account(exp, expenses, quickbooks_settings, exp_cur):
	create_credit_entry(exp, expenses, quickbooks_settings, exp_cur)
	create_debit_entry(exp, expenses, quickbooks_settings, exp_cur)
	party_credit_debit_entry(exp, expenses, quickbooks_settings, exp_cur)


def get_account_detail(quickbooks_account_id):
	return frappe.db.get_value("Account", {"quickbooks_account_id": quickbooks_account_id}, ["name", "account_currency"], as_dict=1)

def append_row(exp= None, qb_account=None, debit_in_account_currency=None, credit_in_account_currency=None, exchange_rate = None):
	account = exp.append("accounts", {})
	account.account = qb_account
	if debit_in_account_currency!= None and debit_in_account_currency != 0:
		account.debit_in_account_currency = flt(debit_in_account_currency , account.precision("debit_in_account_currency"))
		
	if credit_in_account_currency != None and credit_in_account_currency != 0:
		account.credit_in_account_currency = flt(credit_in_account_currency , account.precision("credit_in_account_currency"))
	account.exchange_rate = exchange_rate


def create_credit_entry(exp, expenses, quickbooks_settings, exp_cur):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")
	quickbooks_account_id = expenses.get('AccountRef').get('value') if expenses.get('AccountRef') else ''
	account_ref = get_account_detail(quickbooks_account_id)

	if account_ref.get('account_currency') == company_currency:
		exchange_rate = 1
		credit_amount = expenses.get('TotalAmt') * expenses.get('ExchangeRate')
	else:
		exchange_rate = expenses.get('ExchangeRate')
		credit_amount = expenses.get('TotalAmt')

	if account_ref:
		append_row(exp = exp, qb_account= account_ref.get('name'), debit_in_account_currency=None , credit_in_account_currency = credit_amount, exchange_rate = exchange_rate)

def create_debit_entry(exp, expenses, quickbooks_settings, exp_cur):

	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")

	line = expenses.get('Line')
	# print line
	if line:
		for index, row in enumerate(line):
			if row.get('Amount') and row.get('DetailType') == 'AccountBasedExpenseLineDetail':
				quickbook_account_ref = row.get('AccountBasedExpenseLineDetail').get('AccountRef')
				quickbooks_account_id = quickbook_account_ref.get('value') if quickbook_account_ref else ''
				account_ref = get_account_detail(quickbooks_account_id)
				if account_ref.get('account_currency') == company_currency:
					exchange_rate = 1
					debit_amount = row.get('Amount') * expenses.get('ExchangeRate')
				else:
					exchange_rate = expenses.get('ExchangeRate')
					debit_amount = row.get('Amount')
				
				if account_ref:
					append_row(exp = exp, qb_account= account_ref.get('name'), debit_in_account_currency= debit_amount , credit_in_account_currency = None, exchange_rate = exchange_rate)

	tax_detail = expenses.get('TxnTaxDetail')
	if tax_detail:
		for index, row in enumerate(tax_detail.get("TaxLine")):
			tax_rate_ref =row.get('TaxLineDetail').get('TaxRateRef')
			quickbooks_tax_rate_id = tax_rate_ref.get('value') if tax_rate_ref else ''
			account_ref = get_tax_account(expenses, quickbooks_tax_rate_id, quickbooks_settings)
			
			if account_ref.get('account_currency') == company_currency:
				exchange_rate = 1
				amount = row.get('Amount')  * expenses.get('ExchangeRate')
			else:
				exchange_rate = expenses.get('ExchangeRate')
				amount = row.get('Amount') 

			if account_ref:
				append_row(exp = exp, qb_account= account_ref.get('name'), debit_in_account_currency= amount , credit_in_account_currency = None, exchange_rate = exchange_rate)



def get_tax_account(expenses, quickbooks_tax_rate_id, quickbooks_settings):
	if not expenses.get('GlobalTaxCalculation') == 'NotApplicable':
		individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent 
					from  `tabQuickBooks TaxRate` as qbr where qbr.tax_rate_id = {}""".format(quickbooks_tax_rate_id),as_dict=1)
		tax_head = individual_item_tax[0]['tax_head']
		tax_account = get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings)
	return tax_account

def get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings):
	""" fetch respective tax head from Tax Head Mappe table """
	account_head_erpnext =frappe.db.get_value("Tax Head Mapper", {"tax_head_quickbooks": tax_head, \
			"parent": "Quickbooks Settings"}, "account_head_erpnext")
	if not account_head_erpnext:
		account_head_erpnext = quickbooks_settings.undefined_tax_account
	account_head_erpnext = frappe.db.get_value("Account", {"name": account_head_erpnext}, ["name", "account_currency"], as_dict=1)
	return account_head_erpnext

def validate(expenses):
	# {'name': u'Supplier 4', 'default_currency': u'INR'}
	entity = get_party_type(expenses)
	if entity:
		party_curr = entity.get('default_currency') if entity.get('default_currency') else ''
		credit_account_ref = expenses.get('AccountRef').get('value') if expenses.get('AccountRef') else ''
		if credit_account_ref:
			credit_account_curr = frappe.db.get_value("Account", {"quickbooks_account_id": credit_account_ref}, "account_currency")
			if credit_account_curr == party_curr:
				print party_curr, "if"
				return party_curr
			elif party_curr:
				print party_curr, "elsif"
				return party_curr
			else:
				print credit_account_curr ,"else"
				return credit_account_curr
	else:
		credit_account_ref = expenses.get('AccountRef').get('value') if expenses.get('AccountRef') else ''
		if credit_account_ref:
			credit_account_curr = frappe.db.get_value("Account", {"quickbooks_account_id": credit_account_ref}, "account_currency")
			print  credit_account_curr, "if not else"
			return credit_account_curr
