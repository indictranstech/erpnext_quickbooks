from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log


def sync_entry(quickbooks_obj):
	"""Fetch JournalEntry data from QuickBooks"""
	Entry = """SELECT * from JournalEntry""" 
	qb_Entry = quickbooks_obj.query(Entry)
	get_qb_Entry =  qb_Entry['QueryResponse']['JournalEntry']
	sync_entries(get_qb_Entry)

# def sync_entries(journal_entry1):
# 	for qb_journal_entry in journal_entry1:
# 		create_journal_entry(qb_journal_entry)

def sync_entries(get_qb_Entry):
	for qb_journal_entry in get_qb_Entry:
		create_journal_entry(qb_journal_entry)


def create_journal_entry(qb_journal_entry, quickbooks_journal_entry_list=[]):
	""" store JournalEntry data in ERPNEXT """ 

	journal = None
	qb_journal_entry_id = ''
	if qb_journal_entry.get('Id'):
		qb_journal_entry_id = "JE" + qb_journal_entry.get('Id')
	try:	
		if not 	frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": qb_journal_entry_id}, "name"): 
			journal = frappe.new_doc("Journal Entry")
			journal.quickbooks_journal_entry_id = qb_journal_entry_id
			journal.voucher_type = _("Journal Entry")
			journal.naming_series = "JE-Quickbooks-"
			journal.posting_date = qb_journal_entry.get('TxnDate')
			get_journal_entry_account(journal,qb_journal_entry)
			journal.cheque_no ="dummy check"
			journal.cheque_date =qb_journal_entry.get('TxnDate')
			journal.flags.ignore_mandatory = True
			journal.save()
			journal.submit()

			frappe.db.commit()
			quickbooks_journal_entry_list.append(journal.quickbooks_journal_entry_id)

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_quickbooks_log(title=e.message, status="Error", method="create_journal_entry", message=frappe.get_traceback(),
				request_data=qb_journal_entry, exception=True)
	
	return quickbooks_journal_entry_list


def get_journal_entry_account(journal, qb_journal_entry):
	journal.set("accounts", [])
	for row in qb_journal_entry['Line']:
		account = journal.append("accounts")
		account.account = get_Account(row)
		account.party_type = get_party_type(row)
		account.party = get_party(row)
		account.debit_in_account_currency = get_debit_in_account_currency(row)
		account.credit_in_account_currency = get_credit_in_account_currency(row)
		
def get_Account(row):
	quickbooks_account_reference = row.get('JournalEntryLineDetail')['AccountRef']['value']
	return frappe.db.get_value("Account", {"quickbooks_account_id": quickbooks_account_reference}, "name")
	

def get_party_type(row):
	quickbooks_party_type = row.get('JournalEntryLineDetail').get('Entity').get('Type') if row.get('JournalEntryLineDetail').get('Entity') else ''
	if quickbooks_party_type == "Customer":
		return "Customer"
	elif quickbooks_party_type == "Vendor":
		return "Supplier"
	else:
		return quickbooks_party_type


def get_party(row):
	quickbooks_party_type = row.get('JournalEntryLineDetail').get('Entity').get('Type') if row.get('JournalEntryLineDetail').get('Entity') else ''
	quickbooks_party = row.get('JournalEntryLineDetail').get('Entity').get('EntityRef').get('value') if row.get('JournalEntryLineDetail').get('Entity') else ''
	if quickbooks_party_type == "Customer" and quickbooks_party:
		return frappe.db.get_value("Customer", {"quickbooks_cust_id": quickbooks_party}, "name")
	elif quickbooks_party_type == "Vendor" and quickbooks_party:
		return frappe.db.get_value("Supplier", {"quickbooks_supp_id": quickbooks_party}, "name")
	else:
		return quickbooks_party 

def get_debit_in_account_currency(row):
	quickbooks_debit_in_account_currency = row.get('Amount') if row['JournalEntryLineDetail']['PostingType'] == "Debit" else ''
	return quickbooks_debit_in_account_currency

def get_credit_in_account_currency(row):
	quickbooks_credit_in_account_currency = row.get('Amount') if row['JournalEntryLineDetail']['PostingType'] == "Credit" else ''
	return quickbooks_credit_in_account_currency
