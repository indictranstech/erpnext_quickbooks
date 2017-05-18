

from __future__ import unicode_literals
import frappe
from frappe import _
import json
import ast
from frappe.utils import flt, nowdate, cstr
import requests.exceptions
from .utils import make_quickbooks_log, pagination

"""Sync all the Purchase Invoice from Quickbooks to ERPNEXT"""
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
	""" Store Sales Invoice in ERPNEXT """
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	create_supplier_credit(qb_supplier_credit, quickbooks_settings, quickbooks_supplier_credits_list, default_currency=None)

def create_supplier_credit(qb_supplier_credit, quickbooks_settings, quickbooks_supplier_credits_list, default_currency=None):
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
	# accounts_entry(stock_entry, doctype, qb_supplier_credits, ref_doc, quickbooks_settings)


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



# from __future__ import unicode_literals
# import frappe
# from frappe import _
# import json
# import ast
# from frappe.utils import flt, nowdate, cstr
# import requests.exceptions
# from .utils import make_quickbooks_log, pagination

# """Sync all the Purchase Invoice from Quickbooks to ERPNEXT"""
# def sync_supplier_credits(quickbooks_obj):
# 	quickbooks_supplier_credits_list =[] 
# 	business_objects = "VendorCredit"
# 	get_qb_supplier_credits =  pagination(quickbooks_obj, business_objects)
# 	if get_qb_supplier_credits:
# 		sync_qb_supplier_credits(get_qb_supplier_credits, quickbooks_supplier_credits_list)

# def sync_qb_supplier_credits(get_qb_supplier_credits, quickbooks_supplier_credits_list):
# 	company_name = frappe.defaults.get_defaults().get("company")
# 	default_currency = frappe.db.get_value("Company" ,{"name":company_name},"default_currency")
# 	for qb_supplier_credit in get_qb_supplier_credits:
# 		if valid_supplier_and_product(qb_supplier_credit):
# 			try:
# 				create_credit(qb_supplier_credit, quickbooks_supplier_credits_list, default_currency)
# 			except Exception, e:
# 				make_quickbooks_log(title=e.message, status="Error", method="sync_qb_supplier_credits", message=frappe.get_traceback(),
# 						request_data=qb_supplier_credit, exception=True)

# def valid_supplier_and_product(qb_supplier_credit):
# 	"""  valid_supplier data from ERPNEXT and store in ERPNEXT """ 
# 	from .sync_suppliers import create_Supplier
# 	supplier_id = qb_supplier_credit['VendorRef']['value'] 
# 	if supplier_id:
# 		if not frappe.db.get_value("Supplier", {"quickbooks_supp_id": supplier_id}, "name"):
# 			create_Supplier(qb_supplier_credit['VendorRef'], quickbooks_supplier_list = [])		
# 	else:
# 		raise _("supplier is mandatory to create order")
	
# 	return True

# def create_credit(qb_supplier_credit, quickbooks_supplier_credits_list, default_currency=None):
# 	""" Store Sales Invoice in ERPNEXT """
# 	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
# 	create_supplier_credit(qb_supplier_credit, quickbooks_settings, quickbooks_supplier_credits_list, default_currency=None)

# def create_supplier_credit(qb_supplier_credit, quickbooks_settings, quickbooks_supplier_credits_list, default_currency=None):
# 	pi = frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": str(qb_supplier_credit.get("Id"))+"-"+"SC"}, "name") 
# 	term_id = qb_supplier_credit.get('SalesTermRef').get('value') if qb_supplier_credit.get('SalesTermRef') else ""
# 	term = ""
# 	if term_id:
# 		term = frappe.db.get_value("Terms and Conditions", {"quickbooks_term_id": term_id}, ["name","terms"],as_dict=1)
# 	if not pi:
# 		stock_item = update_stock(qb_supplier_credit['Line'], quickbooks_settings)
# 		# print stock_item, "updata update"
# 		pi = frappe.get_doc({
# 			"doctype": "Purchase Invoice",
# 			"quickbooks_purchase_invoice_id" : str(qb_supplier_credit.get("Id"))+"-"+"SC",
# 			"naming_series": "SUPP-CREDIT-",
# 			"quickbooks_bill_no": qb_supplier_credit.get("DocNumber"),
# 			"title" : frappe.db.get_value("Supplier",{"quickbooks_supp_id":qb_supplier_credit['VendorRef'].get('value')},"name"),
# 			"supplier": frappe.db.get_value("Supplier",{"quickbooks_supp_id":qb_supplier_credit['VendorRef'].get('value')},"name"),
# 			"currency" : qb_supplier_credit.get("CurrencyRef").get('value') if qb_supplier_credit.get("CurrencyRef") else default_currency,
# 			"conversion_rate" : qb_supplier_credit.get("ExchangeRate") if qb_supplier_credit.get("CurrencyRef") else 1,
# 			"posting_date": qb_supplier_credit.get('TxnDate'),
# 			"due_date": qb_supplier_credit.get('DueDate'),
# 			"update_stock": 0 if stock_item == False else 1,
# 			"buying_price_list": quickbooks_settings.buying_price_list,
# 			"ignore_pricing_rule": 1,
# 			"apply_discount_on": "Net Total",
# 			"items": get_order_items(qb_supplier_credit, qb_supplier_credit['Line'], quickbooks_settings, stock_item),
# 			"taxes": get_individual_item_tax(qb_supplier_credit, qb_supplier_credit['Line'], quickbooks_settings, stock_item) if stock_item == True 
# 			else get_individual_count_based_expense_line(qb_supplier_credit, qb_supplier_credit['Line'], quickbooks_settings, stock_item),
# 			"tc_name": term.get('name') if term else "",
# 			"terms": term.get('terms')if term else ""
# 		})
# 		pi.flags.ignore_mandatory = True
# 		pi.save(ignore_permissions=True)
# 		pi.submit()
# 		quickbooks_supplier_credits_list.append(qb_supplier_credit.get("Id"))

# 		from erpnext.controllers.sales_and_purchase_return import make_return_doc
# 		dn = make_return_doc("Purchase Invoice", pi.name, target_doc=None)
# 		dn.naming_series = "PINV-RET-"
# 		dn.flags.ignore_mandatory = True
# 		dn.save(ignore_permissions=True)
# 		dn.submit()

# 		frappe.db.commit()	
# 	return quickbooks_supplier_credits_list

# def update_stock(line, quickbooks_settings):
# 	"""
# 	Check item is stock item or not
# 	Quickbooks Bill has two table
# 		1. Accounts details : This table is used for Accounts Entry, example freight and Forwarding charges for purchasing that item 
# 		2. Item details : This table is used for Item need to Purchase
# 	"""
# 	is_stock_item = True
# 	Item_Detail, Account_Detail = 0,0
# 	for i in line:
# 		if i['DetailType'] =='ItemBasedExpenseLineDetail':
# 			Item_Detail += 1
# 		elif i['DetailType'] =='AccountBasedExpenseLineDetail':
# 			Account_Detail +=1
# 	if Account_Detail > 0 and Item_Detail ==0:
# 		is_stock_item = False
# 	return is_stock_item

# def get_individual_count_based_expense_line(qb_supplier_credit, order_items, quickbooks_settings, stock_item):
# 	taxes = []

# 	if not qb_supplier_credit.get('GlobalTaxCalculation') == 'NotApplicable':
# 		if stock_item == False:
# 			taxes_rate_list = {}
# 			account_head_list = []
# 			for i in get_order_items(qb_supplier_credit, order_items, quickbooks_settings, stock_item):
# 				account_head =json.loads(i['item_tax_rate']).keys()[0] if json.loads(i['item_tax_rate']).keys() else ''
# 				if account_head in set(account_head_list) and float(i['quickbooks__tax_code_value']) != 0.0:
# 					taxes_rate_list[account_head] += float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
# 				elif i['quickbooks__tax_code_value'] != 0:
# 					taxes_rate_list[account_head] = float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
# 					account_head_list.append(account_head)

# 			if taxes_rate_list:
# 				for key, value in taxes_rate_list.iteritems():
# 					taxes.append({
# 						"category" : _("Total"),
# 						"charge_type": _("On Net Total"),
# 						"account_head": key,
# 						"description": _("Total Tax added from invoice"),
# 						"rate": 0,
# 						"tax_amount": value
# 						})
# 	return taxes

# def calculate_tax_amount(qb_supplier_credit, order_items, quickbooks_settings, stock_item):
# 	""" calculate tax amount for all the item and add record in taxes """
# 	totol_tax =[]
# 	taxes_rate_list = {}
# 	account_head_list = set()
# 	for i in get_order_items(qb_supplier_credit, order_items, quickbooks_settings, stock_item):
# 		account_head =json.loads(i['item_tax_rate']).keys()[0] if json.loads(i['item_tax_rate']).keys() else ''
# 		if account_head in account_head_list and float(i['quickbooks__tax_code_value']) != 0.0:
# 			taxes_rate_list[account_head] += float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
# 		elif i['quickbooks__tax_code_value'] != 0:
# 			taxes_rate_list[account_head] = float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
# 			account_head_list.add(account_head)

# 	if taxes_rate_list:
# 		for key, value in taxes_rate_list.iteritems():
# 			totol_tax.append({
# 				"charge_type": _("On Net Total"),
# 				"account_head": key,
# 				"description": _("Total Tax added from invoice"),
# 				"rate": 0,
# 				"tax_amount": value
# 				})
# 	return totol_tax

# def get_individual_item_tax(qb_supplier_credit, order_items, quickbooks_settings, stock_item):
# 	"""tax break for individual item from QuickBooks"""
# 	taxes = []

# 	if stock_item == True:
# 		if not qb_supplier_credit.get('GlobalTaxCalculation') == 'NotApplicable':
# 			taxes.extend(calculate_tax_amount(qb_supplier_credit, order_items, quickbooks_settings, stock_item))

# 		account_expenses = []
# 		account_details = account_based_expense_line_detail(qb_supplier_credit, order_items, quickbooks_settings)
# 		for index,i in enumerate(account_details):
# 			if i['expense_account']:
# 				account_expenses.append({
# 						"charge_type": "Actual",
# 						"account_head": i['expense_account'],
# 						"description": i['expense_account'],
# 						"rate": 0,
# 						"tax_amount": i["rate"]
# 						})
# 		taxes.extend(account_expenses) if account_expenses else ''

# 		if not qb_supplier_credit.get('GlobalTaxCalculation') == 'NotApplicable':
# 			account_expenses_tax = {}
# 			account_head_tax_list = []
# 			account_tax_details = account_based_expense_line_detail(qb_supplier_credit, order_items, quickbooks_settings)

# 			for index,i in enumerate(account_tax_details):
# 				account_heads =json.loads(i['item_tax_rate']).keys()[0] if json.loads(i['item_tax_rate']).keys() else ''

# 				if account_heads in set(account_head_tax_list) and float(i['quickbooks__tax_code_value']) != 0.0:
# 					account_expenses_tax[account_heads] += float(i['quickbooks__tax_code_value']*i['rate']*1/100)
# 				elif i['quickbooks__tax_code_value'] != 0:
# 					account_expenses_tax[account_heads] = float(i['quickbooks__tax_code_value']*i['rate']*1/100)
# 					account_head_tax_list.append(account_heads)

# 			taxes_on_account_details = []
# 			if account_expenses_tax:
# 				for key, value in account_expenses_tax.iteritems():
# 					taxes_on_account_details.append({
# 						"charge_type": _("Actual"),
# 						"account_head": key,
# 						"description": key,
# 						"rate": 0,
# 						"tax_amount": value
# 						})
# 			taxes.extend(taxes_on_account_details) if taxes_on_account_details else ''
# 	return taxes

# def get_order_items(qb_supplier_credit, order_items, quickbooks_settings, stock_item):
# 	"""
# 	Get all the 'Items details' && 'Account details' from the Purachase Invoice(Bill) from the quickbooks
# 	PI (Bill) : During the creation of PI (Bill) in ERPNext from QuickBooks need to handle 3 scenario , 
# 				as Account details, Item details table record from Quickbooks record has to be manage in Item and Tax table in ERPNext
				
# 				So, In Quickbooks PI (Bill) can be created By 3 types:
# 				1. PI (Bill) with Account details record with and without taxes ,So in this case Stock should not get update, 
# 				   So during the creation PI in ERPNext, Account details record is populated in Item table. 
# 				2. PI (Bill) with  Item details record with and without taxes ,So in this case Stock should get updated, 
# 				   So during the creation PI in ERPNext, Item details record is populated in Item table.
# 				3. PI (Bill) with Item details and Account details record with and without taxes ,So in this case Stock should get updated, 
# 				   So during the creation PI in ERPNext, Item details record is populated in Item table and Account details record 
# 				   is populated in Tax table.. 
# 	"""
#   	items = []
#  	for qb_item in order_items:
#  		"""
# 	 		Get all the Items details from PI(bill)
# 	 		It will excecute only in case of 2nd and 3rd scenario as explained above
#  		"""
#  		if qb_item.get('DetailType') == "ItemBasedExpenseLineDetail" and stock_item == True:
# 			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = item_based_expense_line_detail_tax_code_ref(qb_supplier_credit, qb_item, quickbooks_settings)
# 			item_code = get_item_code(qb_item)
# 			items.append({
# 				"item_code": item_code if item_code else '',
# 				"item_name": item_code if item_code else qb_item.get('Description')[:35],
# 				"description":qb_item.get('Description') if qb_item.get('Description') else '',
# 				"rate": qb_item.get('ItemBasedExpenseLineDetail').get('UnitPrice'),
# 				"qty": qb_item.get('ItemBasedExpenseLineDetail').get('Qty'),
# 				"expense_account": quickbooks_settings.expense_account,
# 				"stock_uom": _("Nos"),
# 				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
# 				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
# 				"quickbooks__tax_code_value": quickbooks__tax_code_value			
# 			})
# 		if qb_item.get('DetailType') == "AccountBasedExpenseLineDetail" and stock_item == False:
# 		 	"""
# 		 		Get all Account details from PI(bill)
# 		 		It will excecute only in case of 2st scenario as explained above
# 		 	"""
# 			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = account_based_expense_line_detail_tax_code_ref(qb_supplier_credit, qb_item, quickbooks_settings)
# 		 	quickbooks_account_reference = qb_item.get('AccountBasedExpenseLineDetail').get('AccountRef').get('value')
# 		 	quickbooks_account = frappe.db.get_value("Account", {"quickbooks_account_id" : quickbooks_account_reference}, "name")
# 		 	items.append({
# 				"item_name": quickbooks_account,
# 				"description":qb_item.get('Description') + _(" Service Item") if qb_item.get('Description') else quickbooks_account,
# 				"rate": qb_item.get('Amount'),
# 				"qty": 1,
# 				"stock_uom": _("Nos"),
# 				"expense_account": quickbooks_account,
# 				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
# 				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
# 				"quickbooks__tax_code_value": quickbooks__tax_code_value
# 			})
# 	return items

# def item_based_expense_line_detail_tax_code_ref(qb_supplier_credit,qb_item, quickbooks_settings):
# 	"""
# 	this function tell about Tax Account(in which tax will going to be get booked) and how much tax percent amount will going
# 	to get booked in that particular account for each Entry
# 	"""
# 	item_wise_tax ={}
# 	tax_head = ''
# 	tax_percent = 0.0
# 	if not qb_supplier_credit.get('GlobalTaxCalculation') == 'NotApplicable':
# 		if qb_item.get('ItemBasedExpenseLineDetail').get('TaxCodeRef'):
# 			tax_code_id1 = qb_item.get('ItemBasedExpenseLineDetail').get('TaxCodeRef').get('value') if qb_item.get('ItemBasedExpenseLineDetail') else ''
# 			if not tax_code_id1 == 'NON':
# 				individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
# 								from 
# 									`tabQuickBooks TaxRate` as qbr,
# 									(select * from `tabQuickBooks PurchaseTaxRateList` where parent = {0}) as qbs 
# 								where 
# 									qbr.tax_rate_id = qbs.tax_rate_id """.format(tax_code_id1),as_dict=1)
# 				tax_head = individual_item_tax[0]['tax_head']
# 				tax_percent = flt(individual_item_tax[0]['tax_percent'])
# 				item_tax_rate = get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings)
# 				item_wise_tax[cstr(item_tax_rate)] = tax_percent
# 	return item_wise_tax, tax_head, tax_percent 

# def account_based_expense_line_detail(qb_supplier_credit, order_items, quickbooks_settings):
# 	Expense = []
#  	for qb_item in order_items:
# 		"""Get all Account details from PI(bill)"""
#  		if qb_item.get('DetailType') == "AccountBasedExpenseLineDetail":
# 			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = account_based_expense_line_detail_tax_code_ref(qb_supplier_credit, qb_item, quickbooks_settings)
# 		 	quickbooks_account_reference = qb_item.get('AccountBasedExpenseLineDetail').get('AccountRef').get('value')
# 		 	quickbooks_account = frappe.db.get_value("Account", {"quickbooks_account_id" : quickbooks_account_reference}, "name")
# 		 	Expense.append({
# 				"item_name": quickbooks_account,
# 				"description":qb_item.get('Description') + _(" Service Item") if qb_item.get('Description') else quickbooks_account,
# 				"rate": qb_item.get('Amount'),
# 				"expense_account": quickbooks_account,
# 				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
# 				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
# 				"quickbooks__tax_code_value": quickbooks__tax_code_value
# 			})
# 	return Expense


# def account_based_expense_line_detail_tax_code_ref(qb_supplier_credit, qb_item, quickbooks_settings):
# 	"""
# 	this function tell about Tax Account(in which tax will going to be get booked) and how much tax percent amount will going
# 	to get booked in that particular account for each Entry
# 	"""
# 	item_wise_tax ={}
# 	tax_head = ''
# 	tax_percent = 0.0
# 	if not qb_supplier_credit.get('GlobalTaxCalculation') == 'NotApplicable':
# 		if qb_item.get('AccountBasedExpenseLineDetail').get('TaxCodeRef'):
# 			tax_code_id1 = qb_item.get('AccountBasedExpenseLineDetail').get('TaxCodeRef').get('value') if qb_item.get('AccountBasedExpenseLineDetail') else ''
# 			if not tax_code_id1 == 'NON':
# 				individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
# 								from 
# 									`tabQuickBooks TaxRate` as qbr,
# 									(select * from `tabQuickBooks PurchaseTaxRateList` where parent = {0}) as qbs 
# 								where 
# 									qbr.tax_rate_id = qbs.tax_rate_id """.format(tax_code_id1),as_dict=1)
# 				tax_head = individual_item_tax[0]['tax_head']
# 				tax_percent = flt(individual_item_tax[0]['tax_percent'])
# 				item_tax_rate = get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings)
# 				item_wise_tax[cstr(item_tax_rate)] = tax_percent
# 	return item_wise_tax, tax_head, tax_percent

# def get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings):
# 	""" fetch respective tax head from Tax Head Mappe table """
# 	account_head_erpnext =frappe.db.get_value("Tax Head Mapper", {"tax_head_quickbooks": tax_head, \
# 			"parent": "Quickbooks Settings"}, "account_head_erpnext")
# 	if not account_head_erpnext:
# 		account_head_erpnext = quickbooks_settings.undefined_tax_account
# 	return account_head_erpnext

# def get_item_code(qb_item):
# 	quickbooks_item_id = qb_item.get('ItemBasedExpenseLineDetail').get('ItemRef').get('value') if qb_item.get('ItemBasedExpenseLineDetail') else ''
# 	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id}, "item_code")
# 	return item_code

############################################################################################
