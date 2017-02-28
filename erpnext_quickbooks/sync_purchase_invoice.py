from __future__ import unicode_literals
import frappe
from frappe import _
import json
import ast
from frappe.utils import flt, nowdate, cstr
import requests.exceptions
from .utils import make_quickbooks_log


"""Sync all the Purchase Invoice from Quickbooks to ERPNEXT"""

def sync_pi_orders(quickbooks_obj):
	quickbooks_purchase_invoice_list =[] 
	purchase_invoice_query = """SELECT * FROM Bill""" 
	qb_purchase_invoice = quickbooks_obj.query(purchase_invoice_query)
	if qb_purchase_invoice['QueryResponse']:
		get_qb_purchase_invoice =  qb_purchase_invoice['QueryResponse']
		# print get_qb_purchase_invoice,"lllllll"
		# get_qb_purchase_invoice =  {u'startPosition': 1, u'totalCount': 7, u'Bill': [{u'SyncToken': u'1', u'domain': u'QBO', u'APAccountRef': {u'name': u'Accounts Payable (Creditors)', u'value': u'56'}, u'VendorRef': {u'name': u'kala joshi', u'value': u'10'}, u'GlobalTaxCalculation': u'TaxExcluded', u'TxnDate': u'2017-02-24', u'TotalAmt': 2652.5, u'ExchangeRate': 1, u'CurrencyRef': {u'name': u'Indian Rupee', u'value': u'INR'}, u'HomeBalance': 2652.5, u'Id': u'23', u'sparse': False, u'Line': [{u'DetailType': u'ItemBasedExpenseLineDetail', u'Amount': 2000.0, u'Id': u'1', u'ItemBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'Qty': 1, u'BillableStatus': u'NotBillable', u'UnitPrice': 2000, u'ItemRef': {u'name': u'laptop', u'value': u'3'}}, u'Description': u'description'}, {u'DetailType': u'ItemBasedExpenseLineDetail', u'Amount': 50.0, u'Id': u'4', u'ItemBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'10'}, u'Qty': 1, u'BillableStatus': u'NotBillable', u'UnitPrice': 50, u'ItemRef': {u'name': u'mug', u'value': u'5'}}}, {u'DetailType': u'AccountBasedExpenseLineDetail', u'Amount': 500.0, u'Id': u'2', u'AccountBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'AccountRef': {u'name': u'Purchases', u'value': u'43'}, u'BillableStatus': u'NotBillable'}, u'Description': u'description'}], u'Balance': 2652.5, u'DueDate': u'2017-02-24', u'TxnTaxDetail': {u'TotalTax': 102.5, u'TaxLine': [{u'DetailType': u'TaxLineDetail', u'Amount': 100.0, u'TaxLineDetail': {u'NetAmountTaxable': 2500.0, u'TaxPercent': 4, u'TaxRateRef': {u'value': u'11'}, u'PercentBased': True}}, {u'DetailType': u'TaxLineDetail', u'Amount': 2.5, u'TaxLineDetail': {u'NetAmountTaxable': 50.0, u'TaxPercent': 5, u'TaxRateRef': {u'value': u'15'}, u'PercentBased': True}}]}, u'MetaData': {u'CreateTime': u'2017-02-24T01:59:54-08:00', u'LastUpdatedTime': u'2017-02-24T05:40:11-08:00'}}, {u'SyncToken': u'2', u'domain': u'QBO', u'APAccountRef': {u'name': u'Accounts Payable (Creditors)', u'value': u'56'}, u'VendorRef': {u'name': u'kala joshi', u'value': u'10'}, u'GlobalTaxCalculation': u'TaxExcluded', u'TxnDate': u'2017-02-23', u'TotalAmt': 2080.0, u'ExchangeRate': 1, u'CurrencyRef': {u'name': u'Indian Rupee', u'value': u'INR'}, u'HomeBalance': 2080.0, u'Id': u'21', u'sparse': False, u'Line': [{u'DetailType': u'ItemBasedExpenseLineDetail', u'Amount': 2000.0, u'Id': u'1', u'ItemBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'Qty': 1, u'BillableStatus': u'NotBillable', u'UnitPrice': 2000, u'ItemRef': {u'name': u'laptop', u'value': u'3'}}, u'Description': u'description'}], u'Balance': 2080.0, u'DueDate': u'2017-02-23', u'TxnTaxDetail': {u'TotalTax': 80.0, u'TaxLine': [{u'DetailType': u'TaxLineDetail', u'Amount': 80.0, u'TaxLineDetail': {u'NetAmountTaxable': 2000.0, u'TaxPercent': 4, u'TaxRateRef': {u'value': u'11'}, u'PercentBased': True}}]}, u'MetaData': {u'CreateTime': u'2017-02-23T02:43:13-08:00', u'LastUpdatedTime': u'2017-02-23T03:12:22-08:00'}}, {u'SyncToken': u'0', u'domain': u'QBO', u'APAccountRef': {u'name': u'Accounts Payable (Creditors)', u'value': u'56'}, u'VendorRef': {u'name': u'jaishree joshi', u'value': u'8'}, u'GlobalTaxCalculation': u'TaxExcluded', u'TxnDate': u'2017-02-23', u'TotalAmt': 1283.36, u'ExchangeRate': 1, u'CurrencyRef': {u'name': u'Indian Rupee', u'value': u'INR'}, u'HomeBalance': 1283.36, u'Id': u'18', u'sparse': False, u'Line': [{u'DetailType': u'ItemBasedExpenseLineDetail', u'Amount': 1234.0, u'Id': u'1', u'ItemBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'Qty': 1, u'BillableStatus': u'NotBillable', u'UnitPrice': 1234, u'ItemRef': {u'name': u'laptop', u'value': u'3'}}, u'Description': u'1234'}], u'Balance': 1283.36, u'DueDate': u'2017-02-23', u'TxnTaxDetail': {u'TotalTax': 49.36, u'TaxLine': [{u'DetailType': u'TaxLineDetail', u'Amount': 49.36, u'TaxLineDetail': {u'NetAmountTaxable': 1234.0, u'TaxPercent': 4, u'TaxRateRef': {u'value': u'11'}, u'PercentBased': True}}]}, u'MetaData': {u'CreateTime': u'2017-02-23T01:40:43-08:00', u'LastUpdatedTime': u'2017-02-23T01:40:43-08:00'}}, {u'SyncToken': u'2', u'domain': u'QBO', u'Id': u'15', u'VendorRef': {u'name': u'Pannu jain', u'value': u'5'}, u'GlobalTaxCalculation': u'TaxExcluded', u'TxnDate': u'2017-02-23', u'APAccountRef': {u'name': u'Accounts Payable (Creditors) - USD', u'value': u'51'}, u'ExchangeRate': 66.845367, u'CurrencyRef': {u'name': u'United States Dollar', u'value': u'USD'}, u'HomeBalance': 0, u'LinkedTxn': [{u'TxnId': u'16', u'TxnType': u'BillPaymentCheck'}, {u'TxnId': u'17', u'TxnType': u'BillPaymentCheck'}], u'DueDate': u'2017-04-24', u'TotalAmt': 1283.36, u'sparse': False, u'Line': [{u'DetailType': u'AccountBasedExpenseLineDetail', u'Amount': 1234.0, u'Id': u'1', u'AccountBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'AccountRef': {u'name': u'Sales of Product Income', u'value': u'44'}, u'BillableStatus': u'NotBillable'}, u'Description': u'descp 2'}], u'Balance': 0, u'SalesTermRef': {u'value': u'4'}, u'TxnTaxDetail': {u'TotalTax': 49.36, u'TaxLine': [{u'DetailType': u'TaxLineDetail', u'Amount': 49.36, u'TaxLineDetail': {u'NetAmountTaxable': 1234.0, u'TaxPercent': 4, u'TaxRateRef': {u'value': u'11'}, u'PercentBased': True}}]}, u'MetaData': {u'CreateTime': u'2017-02-23T01:08:29-08:00', u'LastUpdatedTime': u'2017-02-23T01:12:31-08:00'}}, {u'SyncToken': u'3', u'domain': u'QBO', u'APAccountRef': {u'name': u'Accounts Payable (Creditors) - USD', u'value': u'51'}, u'VendorRef': {u'name': u'Pannu jain', u'value': u'5'}, u'GlobalTaxCalculation': u'TaxExcluded', u'TxnDate': u'2017-02-22', u'TotalAmt': 127.92, u'ExchangeRate': 66.94247, u'CurrencyRef': {u'name': u'United States Dollar', u'value': u'USD'}, u'HomeBalance': 0, u'LinkedTxn': [{u'TxnId': u'9', u'TxnType': u'BillPaymentCheck'}, {u'TxnId': u'10', u'TxnType': u'BillPaymentCheck'}], u'Id': u'7', u'sparse': False, u'Line': [{u'DetailType': u'ItemBasedExpenseLineDetail', u'Amount': 123.0, u'Id': u'1', u'ItemBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'Qty': 1, u'BillableStatus': u'NotBillable', u'UnitPrice': 123, u'ItemRef': {u'name': u'laptop', u'value': u'3'}}, u'Description': u'laptop'}], u'Balance': 0, u'DueDate': u'2017-02-22', u'TxnTaxDetail': {u'TotalTax': 4.92, u'TaxLine': [{u'DetailType': u'TaxLineDetail', u'Amount': 4.92, u'TaxLineDetail': {u'NetAmountTaxable': 123.0, u'TaxPercent': 4, u'TaxRateRef': {u'value': u'11'}, u'PercentBased': True}}]}, u'MetaData': {u'CreateTime': u'2017-02-21T23:31:19-08:00', u'LastUpdatedTime': u'2017-02-21T23:35:46-08:00'}}, {u'SyncToken': u'0', u'domain': u'QBO', u'APAccountRef': {u'name': u'Accounts Payable (Creditors) - USD', u'value': u'51'}, u'VendorRef': {u'name': u'Pannu jain', u'value': u'5'}, u'GlobalTaxCalculation': u'TaxExcluded', u'TxnDate': u'2017-02-22', u'TotalAmt': 1283.36, u'ExchangeRate': 66.94247, u'CurrencyRef': {u'name': u'United States Dollar', u'value': u'USD'}, u'HomeBalance': 85911.29, u'Id': u'8', u'sparse': False, u'Line': [{u'DetailType': u'AccountBasedExpenseLineDetail', u'Amount': 1234.0, u'Id': u'1', u'AccountBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'AccountRef': {u'name': u'Sales of Product Income', u'value': u'44'}, u'BillableStatus': u'NotBillable'}, u'Description': u'descp 2'}], u'Balance': 1283.36, u'DueDate': u'2017-02-22', u'TxnTaxDetail': {u'TotalTax': 49.36, u'TaxLine': [{u'DetailType': u'TaxLineDetail', u'Amount': 49.36, u'TaxLineDetail': {u'NetAmountTaxable': 1234.0, u'TaxPercent': 4, u'TaxRateRef': {u'value': u'11'}, u'PercentBased': True}}]}, u'MetaData': {u'CreateTime': u'2017-02-21T23:32:23-08:00', u'LastUpdatedTime': u'2017-02-21T23:32:23-08:00'}}, {u'SyncToken': u'0', u'domain': u'QBO', u'APAccountRef': {u'name': u'Accounts Payable (Creditors) - USD', u'value': u'51'}, u'VendorRef': {u'name': u'Pannu jain', u'value': u'5'}, u'GlobalTaxCalculation': u'TaxExcluded', u'TxnDate': u'2017-02-22', u'TotalAmt': 255.84, u'ExchangeRate': 66.94247, u'CurrencyRef': {u'name': u'United States Dollar', u'value': u'USD'}, u'HomeBalance': 17126.56, u'Id': u'6', u'sparse': False, u'Line': [{u'DetailType': u'ItemBasedExpenseLineDetail', u'Amount': 123.0, u'Id': u'1', u'ItemBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'Qty': 1, u'BillableStatus': u'NotBillable', u'UnitPrice': 123, u'ItemRef': {u'name': u'laptop', u'value': u'3'}}, u'Description': u'laptop'}, {u'DetailType': u'AccountBasedExpenseLineDetail', u'Amount': 123.0, u'Id': u'2', u'AccountBasedExpenseLineDetail': {u'TaxCodeRef': {u'value': u'3'}, u'AccountRef': {u'name': u'Deferred Krishi Kalyan Cess Input Credit', u'value': u'35'}, u'BillableStatus': u'NotBillable'}, u'Description': u'description 1'}], u'Balance': 255.84, u'DueDate': u'2017-02-23', u'TxnTaxDetail': {u'TotalTax': 9.84, u'TaxLine': [{u'DetailType': u'TaxLineDetail', u'Amount': 9.84, u'TaxLineDetail': {u'NetAmountTaxable': 246.0, u'TaxPercent': 4, u'TaxRateRef': {u'value': u'11'}, u'PercentBased': True}}]}, u'MetaData': {u'CreateTime': u'2017-02-21T23:30:06-08:00', u'LastUpdatedTime': u'2017-02-21T23:30:06-08:00'}}], u'maxResults': 7}
		sync_qb_pi_orders(get_qb_purchase_invoice, quickbooks_purchase_invoice_list)

def sync_qb_pi_orders(get_qb_purchase_invoice, quickbooks_purchase_invoice_list):
	company_name = frappe.defaults.get_defaults().get("company")
	default_currency = frappe.db.get_value("Company" ,{"name":company_name},"default_currency")
	for qb_orders in get_qb_purchase_invoice['Bill']:
		if valid_supplier_and_product(qb_orders):
			try:
				create_purchase_invoice_order(qb_orders, quickbooks_purchase_invoice_list, default_currency)
			except Exception, e:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				else:
					make_quickbooks_log(title=e.message, status="Error", method="sync_qb_pi_orders", message=frappe.get_traceback(),
						request_data=qb_orders, exception=True)

def valid_supplier_and_product(qb_orders):
	"""  valid_supplier data from ERPNEXT and store in ERPNEXT """ 
	from .sync_suppliers import create_Supplier
	supplier_id = qb_orders['VendorRef']['value'] 
	if supplier_id:
		if not frappe.db.get_value("Supplier", {"quickbooks_supp_id": supplier_id}, "name"):
			# json_data = json.dumps(qb_orders['VendorRef'])
			create_Supplier(qb_orders['VendorRef'], quickbooks_supplier_list = [])		
	else:
		raise _("supplier is mandatory to create order")
	
	return True

def create_purchase_invoice_order(qb_orders, quickbooks_purchase_invoice_list, default_currency=None):
	""" Store Sales Invoice in ERPNEXT """
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	create_purchase_invoice(qb_orders, quickbooks_settings, quickbooks_purchase_invoice_list, default_currency=None)

def create_purchase_invoice(qb_orders, quickbooks_settings, quickbooks_purchase_invoice_list, default_currency=None):
	pi = frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": qb_orders.get("Id")}, "name") 
	term_id = qb_orders.get('SalesTermRef').get('value') if qb_orders.get('SalesTermRef') else ""
	term = ""
	if term_id:
		term = frappe.db.get_value("Terms and Conditions", {"quickbooks_term_id": term_id}, ["name","terms"],as_dict=1)
	if not pi:
		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"quickbooks_purchase_invoice_id" : qb_orders.get("Id"),
			"naming_series": "PINV-",
			"quickbooks_bill_no": qb_orders.get("DocNumber"),
			"title" : frappe.db.get_value("Supplier",{"quickbooks_supp_id":qb_orders['VendorRef'].get('value')},"name"),
			"supplier": frappe.db.get_value("Supplier",{"quickbooks_supp_id":qb_orders['VendorRef'].get('value')},"name"),
			"currency" : qb_orders.get("CurrencyRef").get('value') if qb_orders.get("CurrencyRef") else default_currency,
			"conversion_rate" : qb_orders.get("ExchangeRate") if qb_orders.get("CurrencyRef") else 1,
			"posting_date": qb_orders.get('TxnDate'),
			"due_date": qb_orders.get('DueDate'),
			"update_stock": 1,
			"buying_price_list": quickbooks_settings.buying_price_list,
			"ignore_pricing_rule": 1,
			"apply_discount_on": "Net Total",
			"items": get_order_items(qb_orders['Line'], quickbooks_settings),
			"taxes": get_individual_item_tax(qb_orders['Line'], quickbooks_settings),
			"tc_name": term.get('name') if term else "",
			"terms": term.get('terms')if term else ""
		})
		
		pi.flags.ignore_mandatory = True
		pi.save(ignore_permissions=True)
		pi.submit()
		quickbooks_purchase_invoice_list.append(qb_orders.get("Id"))
		frappe.db.commit()	
	return quickbooks_purchase_invoice_list


def get_individual_item_tax(order_items, quickbooks_settings):
	"""tax break for individual item from QuickBooks"""
	taxes = []
	taxes_rate_list = {}
	account_head_list = []

	for i in get_order_items(order_items, quickbooks_settings):
		account_head =json.loads(i['item_tax_rate']).keys()[0]
		if account_head in set(account_head_list):
			taxes_rate_list[account_head] += float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
		else:
			taxes_rate_list[account_head] = float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
			account_head_list.append(account_head)

	for key, value in taxes_rate_list.iteritems():
		taxes.append({
			"charge_type": _("On Net Total"),
			"account_head": key,
			"description": _("Total Tax added from invoice"),
			"rate": 0,
			"tax_amount": value
			})

	account_expenses = []
	account_details = account_based_expense_line_detail(order_items, quickbooks_settings)
	for index,i in enumerate(account_details):
		account_heads =json.loads(i['item_tax_rate']).keys()[0]
		if i['expense_account']:
			account_expenses.append({
					"charge_type": "Actual",
					"account_head": i['expense_account'],
					"description": i['expense_account'],
					"rate": 0,
					"tax_amount": i["rate"]
					})
		if i['quickbooks_tax_code_ref']:
			account_expenses.append({"charge_type": "On Previous Row Amount",
					"account_head": account_heads,
					"description": i['quickbooks_tax_code_ref'],
					"rate": i['quickbooks__tax_code_value'],
					"row_id": len(taxes) + 2 *(index +1) -1
					})
	taxes.extend(account_expenses) if account_expenses else ''
	return taxes

def get_order_items(order_items, quickbooks_settings):
	"""Get all the 'Items details' && 'Account details' from the Purachase Invoice(Bill) from the quickbooks"""
  	items = []
 	for qb_item in order_items:
 		"""Get all the Items details from PI(bill)"""
 		if qb_item.get('DetailType') == "ItemBasedExpenseLineDetail":
			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = item_based_expense_line_detail_tax_code_ref(qb_item)
			item_code = get_item_code(qb_item)
			items.append({
				"item_code": item_code if item_code else '',
				"item_name": item_code if item_code else qb_item.get('Description')[:35],
				"description":qb_item.get('Description') if qb_item.get('Description') else '',
				"rate": qb_item.get('ItemBasedExpenseLineDetail').get('UnitPrice'),
				"qty": qb_item.get('ItemBasedExpenseLineDetail').get('Qty'),
				"expense_account": quickbooks_settings.expense_account,
				"stock_uom": _("Nos"),
				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
				"quickbooks__tax_code_value": quickbooks__tax_code_value			
			})
	return items

def item_based_expense_line_detail_tax_code_ref(qb_item):
	item_wise_tax ={}
	individual_item_tax = ''
	if qb_item.get('ItemBasedExpenseLineDetail').get('TaxCodeRef'):
		tax_code_id1 = qb_item.get('ItemBasedExpenseLineDetail').get('TaxCodeRef').get('value') if qb_item.get('ItemBasedExpenseLineDetail') else ''
		individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
						from 
							`tabQuickBooks TaxRate` as qbr,
							(select * from `tabQuickBooks PurchaseTaxRateList` where parent = {0}) as qbs 
						where 
							qbr.tax_rate_id = qbs.tax_rate_id """.format(tax_code_id1),as_dict=1)
		item_tax_rate = get_tax_head_mapped_to_particular_account(individual_item_tax[0]['tax_head'])
		item_wise_tax[cstr(item_tax_rate)] = flt(individual_item_tax[0]['tax_percent'])
	return item_wise_tax, cstr(individual_item_tax[0]['tax_head']) if individual_item_tax else '', flt(individual_item_tax[0]['tax_percent']) if individual_item_tax else 0

def account_based_expense_line_detail(order_items, quickbooks_settings):
	Expense = []
 	for qb_item in order_items:
		"""Get all Account details from PI(bill)"""
 		if qb_item.get('DetailType') == "AccountBasedExpenseLineDetail":
			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = account_based_expense_line_detail_tax_code_ref(qb_item)
		 	quickbooks_account_reference = qb_item.get('AccountBasedExpenseLineDetail').get('AccountRef').get('value')
		 	quickbooks_account = frappe.db.get_value("Account", {"quickbooks_account_id" : quickbooks_account_reference}, "name")
		 	Expense.append({
				"item_name": quickbooks_account,
				"description":qb_item.get('Description') + _(" Service Item") if qb_item.get('Description') else quickbooks_account,
				"rate": qb_item.get('Amount'),
				"expense_account": quickbooks_account,
				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
				"quickbooks__tax_code_value": quickbooks__tax_code_value
			})
	return Expense


def account_based_expense_line_detail_tax_code_ref(qb_item):
	item_wise_tax ={}
	individual_item_tax = ''
	if qb_item.get('AccountBasedExpenseLineDetail').get('TaxCodeRef'):
		tax_code_id1 = qb_item.get('AccountBasedExpenseLineDetail').get('TaxCodeRef').get('value') if qb_item.get('AccountBasedExpenseLineDetail') else ''
		individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
						from 
							`tabQuickBooks TaxRate` as qbr,
							(select * from `tabQuickBooks PurchaseTaxRateList` where parent = {0}) as qbs 
						where 
							qbr.tax_rate_id = qbs.tax_rate_id """.format(tax_code_id1),as_dict=1)
		item_tax_rate = get_tax_head_mapped_to_particular_account(individual_item_tax[0]['tax_head'])
		item_wise_tax[cstr(item_tax_rate)] = flt(individual_item_tax[0]['tax_percent'])
	return item_wise_tax, cstr(individual_item_tax[0]['tax_head']) if individual_item_tax else '', flt(individual_item_tax[0]['tax_percent']) if individual_item_tax else 0


def get_tax_head_mapped_to_particular_account(tax_head):
	""" fetch respective tax head from Tax Head Mappe table """
	account_head_erpnext =frappe.db.get_value("Tax Head Mapper", {"tax_head_quickbooks": tax_head, \
			"parent": "Quickbooks Settings"}, "account_head_erpnext")
	if not account_head_erpnext:
		Default_company = frappe.defaults.get_defaults().get("company")
		Company_abbr = frappe.db.get_value("Company",{"name":Default_company},"abbr")
		account_head_erpnext = "Miscellaneous Expenses" +" - "+ Company_abbr
	return account_head_erpnext

def get_item_code(qb_item):
	quickbooks_item_id = qb_item.get('ItemBasedExpenseLineDetail').get('ItemRef').get('value') if qb_item.get('ItemBasedExpenseLineDetail') else ''
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id}, "item_code")
	return item_code


# def get_order_taxes(qb_orders):
# 	taxes = []
# 	Default_company = frappe.defaults.get_defaults().get("company")
# 	Company_abbr = frappe.db.get_value("Company",{"name":Default_company},"abbr")
	
# 	if not qb_orders.get('GlobalTaxCalculation') == 'NotApplicable':
# 		if qb_orders.get('GlobalTaxCalculation') == 'TaxExcluded' and qb_orders.get('TxnTaxDetail').get('TaxLine'):
# 			taxes.append({
# 				"category" : _("Total"),
# 				"charge_type": _("Actual"),
# 				"account_head": get_tax_account_head(),
# 				"description": "Total Tax added from invoice",
# 				"tax_amount": qb_orders.get('TxnTaxDetail').get('TotalTax') 
# 				#"included_in_print_rate": set_included_in_print_rate(shopify_order)
# 			})
# 		# else:
# 		# 	for tax in qb_orders['TxnTaxDetail']['TaxLine']:
# 		# 			taxes.append({
# 		# 				"charge_type": _("On Net Total"),
# 		# 				"account_head": "Commission on Sales - ES",#get_tax_account_head(tax),
# 		# 				"description": "{0} - {1}%".format(tax.get("title"), tax.get("rate") * 100.0),
# 		# 				"rate": tax.get("rate") * 100.00
# 		# 				#"included_in_print_rate": set_included_in_print_rate(shopify_order)
# 		# 			})
# 			#taxes = update_taxes_with_shipping_lines(taxes, shopify_order.get("shipping_lines"))
# 	return taxes


def get_tax_account_head():
	tax_account =  frappe.db.get_value("Quickbooks Tax Account", \
		{"parent": "Quickbooks Settings"}, "tax_account")

	if not tax_account:
		frappe.throw("Tax Account not specified for Shopify Tax ")

	return tax_account

from pyqb.quickbooks.batch import batch_create, batch_delete
from pyqb.quickbooks.objects.base import Ref
from pyqb.quickbooks.objects.bill import Bill, BillLine, AccountBasedExpenseLineDetail, ItemBasedExpenseLineDetail

"""	Sync Purchase Invoices Records From ERPNext to QuickBooks """
def sync_erp_purchase_invoices():
	"""Receive Response From Quickbooks and Update quickbooks_purchase_invoice_id in Purchase Invoices"""
	response_from_quickbooks = sync_erp_purchase_invoices_to_quickbooks()
	if response_from_quickbooks:
		try:
			for response_obj in response_from_quickbooks.successes:
				if response_obj:
					frappe.db.sql("""UPDATE `tabPurchase Invoice` SET quickbooks_purchase_invoice_id = %s WHERE name ='%s'""" %(response_obj.Id, response_obj.DocNumber))
				else:
					raise _("Does not get any response from quickbooks")	
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_erp_purchase_invoices", message=frappe.get_traceback(),
				request_data=response_obj, exception=True)

def sync_erp_purchase_invoices_to_quickbooks():
	"""Sync ERPNext Purchase Invoice to QuickBooks"""
	Purchase_invoice_list = []
	for erp_purchase_invoice in erp_purchase_invoice_data():
		try:
			if erp_purchase_invoice: 
				create_erp_purchase_invoice_to_quickbooks(erp_purchase_invoice, Purchase_invoice_list)
			else:
				raise _("Purchase invoice does not exist in ERPNext")
		except Exception, e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_quickbooks_log(title=e.message, status="Error", method="sync_erp_purchase_invoices_to_quickbooks", message=frappe.get_traceback(),
					request_data=erp_purchase_invoice, exception=True)
	results = batch_create(Purchase_invoice_list)
	return results

def erp_purchase_invoice_data():
	"""ERPNext Invoices Record"""
	erp_purchase_invoice = frappe.db.sql("""SELECT `name`,`supplier_name`, taxes_and_charges, DATE_FORMAT(due_date,'%d-%m-%Y') as due_date, DATE_FORMAT(posting_date,'%d-%m-%Y') as posting_date from  `tabPurchase Invoice` where `quickbooks_purchase_invoice_id` is NULL and docstatus = 1""" ,as_dict=1)
	return erp_purchase_invoice

def erp_purchase_invoice_item_data(purchase_invoice_name):
	"""ERPNext Invoice Items Record of Particular Invoice"""
	erp_purchase_invoice_item = frappe.db.sql("""SELECT `idx`, `description`, `rate`, `item_code`, `qty` from `tabPurchase Invoice Item` where parent = '%s'""" %(purchase_invoice_name), as_dict=1)
	return erp_purchase_invoice_item

def create_erp_purchase_invoice_to_quickbooks(erp_purchase_invoice, Purchase_invoice_list):
	purchase_invoice_obj = Bill()
	purchase_invoice_obj.DocNumber = erp_purchase_invoice.name
	purchase_invoice_obj.DueDate = erp_purchase_invoice.due_date
	purchase_invoice_obj.TxnDate =  erp_purchase_invoice.posting_date
	Vendor_ref(purchase_invoice_obj, erp_purchase_invoice)
	if erp_purchase_invoice.get('taxes_and_charges'):
		purchase_invoice_obj.GlobalTaxCalculation = "TaxExcluded"
	else:
		purchase_invoice_obj.GlobalTaxCalculation = "NotApplicable"
	purchase_invoice_item(purchase_invoice_obj, erp_purchase_invoice)
  	Vendor_ref(purchase_invoice_obj, erp_purchase_invoice)
	purchase_invoice_obj.save()
	Purchase_invoice_list.append(purchase_invoice_obj)
	return Purchase_invoice_list


def Vendor_ref(purchase_invoice_obj, erp_purchase_invoice):
	vendor_reference = Ref()
	vendor_reference.value = frappe.db.get_value("Supplier", {"name": erp_purchase_invoice.get('supplier_name')}, "quickbooks_supp_id")
	purchase_invoice_obj.VendorRef = vendor_reference

def purchase_invoice_item(purchase_invoice_obj, erp_purchase_invoice):
	purchase_invoice_name = erp_purchase_invoice.name
	for purchase_invoice_item in erp_purchase_invoice_item_data(purchase_invoice_name):
		line = BillLine()
		line.LineNum = purchase_invoice_item.idx
		line.Amount = flt(purchase_invoice_item.rate) * flt(purchase_invoice_item.qty)
		line.Description = purchase_invoice_item.description
		line.DetailType = "ItemBasedExpenseLineDetail"
		line.ItemBasedExpenseLineDetail = ItemBasedExpenseLineDetail()
		line.ItemBasedExpenseLineDetail.ItemRef = purchase_item_ref(purchase_invoice_item)
		line.ItemBasedExpenseLineDetail.BillableStatus = "NotBillable"
		line.ItemBasedExpenseLineDetail.Qty = purchase_invoice_item.qty
		line.ItemBasedExpenseLineDetail.UnitPrice = purchase_invoice_item.rate
		line.ItemBasedExpenseLineDetail.TaxCodeRef = TaxCodeRef(erp_purchase_invoice)
		purchase_invoice_obj.Line.append(line)


def purchase_item_ref(purchase_invoice_item):
	item_reference = Ref()
	item_reference.name = purchase_invoice_item.get('item_code')
	item_reference.value = frappe.db.get_value("Item", {"name": purchase_invoice_item.get('item_code')}, "quickbooks_item_id")
	return item_reference

def TaxCodeRef(erp_purchase_invoice):
	# quickbooks_purchase_tax_id = frappe.db.get_value("Purchase Taxes and Charges Template", {"name": erp_purchase_invoice.get('taxes_and_charges')}, "quickbooks_purchase_tax_id")
	# print quickbooks_purchase_tax_id,""
	# return {"value": quickbooks_purchase_tax_id}
	return {"value": "11"}
