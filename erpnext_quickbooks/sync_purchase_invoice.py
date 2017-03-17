from __future__ import unicode_literals
import frappe
from frappe import _
import json
import ast
from frappe.utils import flt, nowdate, cstr
import requests.exceptions
from .utils import make_quickbooks_log, pagination

"""Sync all the Purchase Invoice from Quickbooks to ERPNEXT"""
def sync_pi_orders(quickbooks_obj):
	quickbooks_purchase_invoice_list =[] 
	business_objects = "Bill"
	get_qb_purchase_invoice =  pagination(quickbooks_obj, business_objects)
	if get_qb_purchase_invoice:
		sync_qb_pi_orders(get_qb_purchase_invoice, quickbooks_purchase_invoice_list)

def sync_qb_pi_orders(get_qb_purchase_invoice, quickbooks_purchase_invoice_list):
	company_name = frappe.defaults.get_defaults().get("company")
	default_currency = frappe.db.get_value("Company" ,{"name":company_name},"default_currency")
	for qb_orders in get_qb_purchase_invoice:
		if valid_supplier_and_product(qb_orders):
			try:
				create_purchase_invoice_order(qb_orders, quickbooks_purchase_invoice_list, default_currency)
			except Exception, e:
				make_quickbooks_log(title=e.message, status="Error", method="sync_qb_pi_orders", message=frappe.get_traceback(),
						request_data=qb_orders, exception=True)

def valid_supplier_and_product(qb_orders):
	"""  valid_supplier data from ERPNEXT and store in ERPNEXT """ 
	from .sync_suppliers import create_Supplier
	supplier_id = qb_orders['VendorRef']['value'] 
	if supplier_id:
		if not frappe.db.get_value("Supplier", {"quickbooks_supp_id": supplier_id}, "name"):
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
		stock_item = update_stock(qb_orders['Line'], quickbooks_settings)
		# print stock_item, "updata update"
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
			"update_stock": 0 if stock_item == False else 1,
			"buying_price_list": quickbooks_settings.buying_price_list,
			"ignore_pricing_rule": 1,
			"apply_discount_on": "Net Total",
			"items": get_order_items(qb_orders, qb_orders['Line'], quickbooks_settings, stock_item),
			"taxes": get_individual_item_tax(qb_orders, qb_orders['Line'], quickbooks_settings, stock_item) if stock_item == True 
			else get_individual_count_based_expense_line(qb_orders, qb_orders['Line'], quickbooks_settings, stock_item),
			"tc_name": term.get('name') if term else "",
			"terms": term.get('terms')if term else ""
		})
		
		pi.flags.ignore_mandatory = True
		pi.save(ignore_permissions=True)
		pi.submit()
		quickbooks_purchase_invoice_list.append(qb_orders.get("Id"))
		frappe.db.commit()	
	return quickbooks_purchase_invoice_list

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

def get_individual_count_based_expense_line(qb_orders, order_items, quickbooks_settings, stock_item):
	taxes = []

	if not qb_orders.get('GlobalTaxCalculation') == 'NotApplicable':
		if stock_item == False:
			taxes_rate_list = {}
			account_head_list = []
			for i in get_order_items(qb_orders, order_items, quickbooks_settings, stock_item):
				account_head =json.loads(i['item_tax_rate']).keys()[0]
				if account_head in set(account_head_list) and float(i['quickbooks__tax_code_value']) != 0.0:
					taxes_rate_list[account_head] += float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
				elif i['quickbooks__tax_code_value'] != 0:
					taxes_rate_list[account_head] = float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
					account_head_list.append(account_head)

			if taxes_rate_list:
				for key, value in taxes_rate_list.iteritems():
					taxes.append({
						"category" : _("Total"),
						"charge_type": _("On Net Total"),
						"account_head": key,
						"description": _("Total Tax added from invoice"),
						"rate": 0,
						"tax_amount": value
						})
	return taxes

def calculate_tax_amount(qb_orders, order_items, quickbooks_settings, stock_item):
	""" calculate tax amount for all the item and add record in taxes """
	totol_tax =[]
	taxes_rate_list = {}
	account_head_list = set()
	for i in get_order_items(qb_orders, order_items, quickbooks_settings, stock_item):
		account_head =json.loads(i['item_tax_rate']).keys()[0]
		if account_head in account_head_list and float(i['quickbooks__tax_code_value']) != 0.0:
			taxes_rate_list[account_head] += float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
		elif i['quickbooks__tax_code_value'] != 0:
			taxes_rate_list[account_head] = float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
			account_head_list.add(account_head)

	if taxes_rate_list:
		for key, value in taxes_rate_list.iteritems():
			totol_tax.append({
				"charge_type": _("On Net Total"),
				"account_head": key,
				"description": _("Total Tax added from invoice"),
				"rate": 0,
				"tax_amount": value
				})
	return totol_tax

def get_individual_item_tax(qb_orders, order_items, quickbooks_settings, stock_item):
	"""tax break for individual item from QuickBooks"""
	taxes = []

	if stock_item == True:
		if not qb_orders.get('GlobalTaxCalculation') == 'NotApplicable':
			taxes.extend(calculate_tax_amount(qb_orders, order_items, quickbooks_settings, stock_item))

		account_expenses = []
		account_details = account_based_expense_line_detail(qb_orders, order_items, quickbooks_settings)
		for index,i in enumerate(account_details):
			if i['expense_account']:
				account_expenses.append({
						"charge_type": "Actual",
						"account_head": i['expense_account'],
						"description": i['expense_account'],
						"rate": 0,
						"tax_amount": i["rate"]
						})
		taxes.extend(account_expenses) if account_expenses else ''

		if not qb_orders.get('GlobalTaxCalculation') == 'NotApplicable':
			account_expenses_tax = {}
			account_head_tax_list = []
			account_tax_details = account_based_expense_line_detail(qb_orders, order_items, quickbooks_settings)

			for index,i in enumerate(account_tax_details):
				account_heads =json.loads(i['item_tax_rate']).keys()[0]

				if account_heads in set(account_head_tax_list) and float(i['quickbooks__tax_code_value']) != 0.0:
					account_expenses_tax[account_heads] += float(i['quickbooks__tax_code_value']*i['rate']*1/100)
				elif i['quickbooks__tax_code_value'] != 0:
					account_expenses_tax[account_heads] = float(i['quickbooks__tax_code_value']*i['rate']*1/100)
					account_head_tax_list.append(account_heads)

			taxes_on_account_details = []
			if account_expenses_tax:
				for key, value in account_expenses_tax.iteritems():
					taxes_on_account_details.append({
						"charge_type": _("Actual"),
						"account_head": key,
						"description": key,
						"rate": 0,
						"tax_amount": value
						})
			taxes.extend(taxes_on_account_details) if taxes_on_account_details else ''
	return taxes

def get_order_items(qb_orders, order_items, quickbooks_settings, stock_item):
	"""
	Get all the 'Items details' && 'Account details' from the Purachase Invoice(Bill) from the quickbooks
	PI (Bill) : During the creation of PI (Bill) in ERPNext from QuickBooks need to handle 3 scenario , 
				as Account details, Item details table record from Quickbooks record has to be manage in Item and Tax table in ERPNext
				
				So, In Quickbooks PI (Bill) can be created By 3 types:
				1. PI (Bill) with Account details record with and without taxes ,So in this case Stock should not get update, 
				   So during the creation PI in ERPNext, Account details record is populated in Item table. 
				2. PI (Bill) with  Item details record with and without taxes ,So in this case Stock should get updated, 
				   So during the creation PI in ERPNext, Item details record is populated in Item table.
				3. PI (Bill) with Item details and Account details record with and without taxes ,So in this case Stock should get updated, 
				   So during the creation PI in ERPNext, Item details record is populated in Item table and Account details record 
				   is populated in Tax table.. 
	"""
  	items = []
 	for qb_item in order_items:
 		"""
	 		Get all the Items details from PI(bill)
	 		It will excecute only in case of 2nd and 3rd scenario as explained above
 		"""
 		if qb_item.get('DetailType') == "ItemBasedExpenseLineDetail" and stock_item == True:
			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = item_based_expense_line_detail_tax_code_ref(qb_orders, qb_item, quickbooks_settings)
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
		if qb_item.get('DetailType') == "AccountBasedExpenseLineDetail" and stock_item == False:
		 	"""
		 		Get all Account details from PI(bill)
		 		It will excecute only in case of 2st scenario as explained above
		 	"""
			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = account_based_expense_line_detail_tax_code_ref(qb_orders, qb_item, quickbooks_settings)
		 	quickbooks_account_reference = qb_item.get('AccountBasedExpenseLineDetail').get('AccountRef').get('value')
		 	quickbooks_account = frappe.db.get_value("Account", {"quickbooks_account_id" : quickbooks_account_reference}, "name")
		 	items.append({
				"item_name": quickbooks_account,
				"description":qb_item.get('Description') + _(" Service Item") if qb_item.get('Description') else quickbooks_account,
				"rate": qb_item.get('Amount'),
				"qty": 1,
				"stock_uom": _("Nos"),
				"expense_account": quickbooks_account,
				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
				"quickbooks__tax_code_value": quickbooks__tax_code_value
			})
	return items

def item_based_expense_line_detail_tax_code_ref(qb_orders,qb_item, quickbooks_settings):
	"""
	this function tell about Tax Account(in which tax will going to be get booked) and how much tax percent amount will going
	to get booked in that particular account for each Entry
	"""
	item_wise_tax ={}
	tax_head = ''
	tax_percent = 0.0
	if not qb_orders.get('GlobalTaxCalculation') == 'NotApplicable':
		if qb_item.get('ItemBasedExpenseLineDetail').get('TaxCodeRef'):
			tax_code_id1 = qb_item.get('ItemBasedExpenseLineDetail').get('TaxCodeRef').get('value') if qb_item.get('ItemBasedExpenseLineDetail') else ''
			individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
							from 
								`tabQuickBooks TaxRate` as qbr,
								(select * from `tabQuickBooks PurchaseTaxRateList` where parent = {0}) as qbs 
							where 
								qbr.tax_rate_id = qbs.tax_rate_id """.format(tax_code_id1),as_dict=1)
			tax_head = individual_item_tax[0]['tax_head']
			tax_percent = flt(individual_item_tax[0]['tax_percent'])
			item_tax_rate = get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings)
			item_wise_tax[cstr(item_tax_rate)] = tax_percent
	return item_wise_tax, tax_head, tax_percent 

def account_based_expense_line_detail(qb_orders, order_items, quickbooks_settings):
	Expense = []
 	for qb_item in order_items:
		"""Get all Account details from PI(bill)"""
 		if qb_item.get('DetailType') == "AccountBasedExpenseLineDetail":
			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = account_based_expense_line_detail_tax_code_ref(qb_orders, qb_item, quickbooks_settings)
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


def account_based_expense_line_detail_tax_code_ref(qb_orders, qb_item, quickbooks_settings):
	"""
	this function tell about Tax Account(in which tax will going to be get booked) and how much tax percent amount will going
	to get booked in that particular account for each Entry
	"""
	item_wise_tax ={}
	tax_head = ''
	tax_percent = 0.0
	if not qb_orders.get('GlobalTaxCalculation') == 'NotApplicable':
		if qb_item.get('AccountBasedExpenseLineDetail').get('TaxCodeRef'):
			tax_code_id1 = qb_item.get('AccountBasedExpenseLineDetail').get('TaxCodeRef').get('value') if qb_item.get('AccountBasedExpenseLineDetail') else ''
			individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
							from 
								`tabQuickBooks TaxRate` as qbr,
								(select * from `tabQuickBooks PurchaseTaxRateList` where parent = {0}) as qbs 
							where 
								qbr.tax_rate_id = qbs.tax_rate_id """.format(tax_code_id1),as_dict=1)
			tax_head = individual_item_tax[0]['tax_head']
			tax_percent = flt(individual_item_tax[0]['tax_percent'])
			item_tax_rate = get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings)
			item_wise_tax[cstr(item_tax_rate)] = tax_percent
	return item_wise_tax, tax_head, tax_percent

def get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings):
	""" fetch respective tax head from Tax Head Mappe table """
	account_head_erpnext =frappe.db.get_value("Tax Head Mapper", {"tax_head_quickbooks": tax_head, \
			"parent": "Quickbooks Settings"}, "account_head_erpnext")
	if not account_head_erpnext:
		account_head_erpnext = quickbooks_settings.undefined_tax_account
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
