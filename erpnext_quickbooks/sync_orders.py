from __future__ import unicode_literals
import frappe
from frappe import _
import json
from frappe.utils import flt, cstr, nowdate
import requests.exceptions
from .utils import make_quickbooks_log
from pyqb.quickbooks.batch import batch_create, batch_delete

"""Sync all the Sales Invoice from Quickbooks to ERPNEXT"""
def sync_si_orders(quickbooks_obj): 
	"""Fetch invoice data from QuickBooks"""
	quickbooks_invoice_list = [] 
	invoice_query = """SELECT * FROM Invoice""" 
	qb_invoice = quickbooks_obj.query(invoice_query)
	if qb_invoice['QueryResponse']:
		get_qb_invoice =  qb_invoice['QueryResponse']
		sync_qb_si_orders(get_qb_invoice, quickbooks_invoice_list)

def sync_qb_si_orders(get_qb_invoice, quickbooks_invoice_list):
	for qb_orders in get_qb_invoice['Invoice']:
		if valid_customer_and_product(qb_orders):
			try:
				create_order(qb_orders, quickbooks_invoice_list)
			except Exception, e:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				else:
					make_quickbooks_log(title=e.message, status="Error", method="sync_qb_si_orders", message=frappe.get_traceback(),
						request_data=qb_orders, exception=True)
					
def valid_customer_and_product(qb_orders):
	""" Fetch valid_customer data from ERPNEXT and store in ERPNEXT """ 
	customer_id = qb_orders['CustomerRef'].get('value') 
	if customer_id:
		if not frappe.db.get_value("Customer", {"quickbooks_cust_id": customer_id}, "name"):
			json_data = json.dumps(qb_orders['CustomerRef'])
			create_customer(ast.literal_eval(json_data), quickbooks_customer_list = [])		
	else:
		raise _("Customer is mandatory to create order")
	
	return True

def create_order(qb_orders, quickbooks_invoice_list, company=None):
	""" Store Sales Invoice in ERPNEXT """
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	create_sales_invoice(qb_orders, quickbooks_settings, quickbooks_invoice_list, company=None)

def create_sales_invoice(qb_orders, quickbooks_settings, quickbooks_invoice_list, company=None):
	si = frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": qb_orders.get("Id")}, "name") 
	if not si:
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"quickbooks_invoce_id" : qb_orders.get("Id"),
			"naming_series": "SINV-",
			"quickbooks_invoice_no" : qb_orders.get("DocNumber"),
			"title": frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_orders['CustomerRef'].get('value')},"name"),
			"customer": frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_orders['CustomerRef'].get('value')},"name"),
			"posting_date": qb_orders.get('TxnDate'),
			"territory" : frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_orders['CustomerRef'].get('value')},"territory"),
			"selling_price_list": quickbooks_settings.selling_price_list,
			"ignore_pricing_rule": 1,
			"apply_discount_on": "Net Total",
			"items": get_order_items(qb_orders['Line'], quickbooks_settings),
			"taxes": get_individual_item_tax(qb_orders['Line'], quickbooks_settings)
		})
		si.flags.ignore_mandatory = True
		si.save(ignore_permissions=True)
		si.submit()
		quickbooks_invoice_list.append(qb_orders.get("id"))
		frappe.db.commit()	
	return quickbooks_invoice_list

def get_individual_item_tax(order_items, quickbooks_settings):
	"""tax break for individual item from QuickBooks"""
	taxes = []
	Default_company = frappe.defaults.get_defaults().get("company")
	Company_abbr = frappe.db.get_value("Company",{"name":Default_company},"abbr")
	tax_amount = 0
	for i in get_order_items(order_items, quickbooks_settings):
		if i['quickbooks__tax_code_value']:
			tax_amount = flt(tax_amount) + (flt(i['quickbooks__tax_code_value']) * (i['qty'] *i['rate']))/100
	if tax_amount:
		taxes.append({
				"charge_type": _("On Net Total"),
				"account_head": get_tax_account_head(),
				"description": _("Total Tax added from invoice"),
				"rate": 0,
				"tax_amount": tax_amount
				})
	return taxes


def get_order_items(order_items, quickbooks_settings):
 	items = []
 	for qb_item in order_items:
		if qb_item.get('SalesItemLineDetail'):
		 	item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = tax_code_ref(qb_item)
			item_code = get_item_code(qb_item)
			items.append({
				"item_code": item_code if item_code else '',
				"item_name": qb_item.get('Description')[:35] if qb_item.get('Description') else '',
				"description": qb_item.get('Description') if qb_item.get('Description') else '',
				"rate": qb_item.get('SalesItemLineDetail').get('UnitPrice') if qb_item.get('SalesItemLineDetail').get('UnitPrice') else qb_item.get('Amount'),
				"qty": qb_item.get('SalesItemLineDetail').get('Qty') if qb_item.get('SalesItemLineDetail').get('Qty') else 1,
				"income_account": quickbooks_settings.cash_bank_account,
				"stock_uom": _("Nos"),
				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
				"quickbooks__tax_code_value": quickbooks__tax_code_value
			})
	return items

def tax_code_ref(qb_item):
	# print qb_item.get('SalesItemLineDetail'), "gggggggggggggggggggggggg"
	item_wise_tax ={}
	individual_item_tax = ''
	if qb_item.get('SalesItemLineDetail').get('TaxCodeRef'):
		tax_code_id1 = qb_item.get('SalesItemLineDetail').get('TaxCodeRef').get('value') if qb_item.get('SalesItemLineDetail') else ''
		individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
						from 
							`tabQuickBooks TaxRate` as qbr,
							(select * from `tabQuickBooks SalesTaxRateList` where parent = {0}) as qbs 
						where 
							qbr.name = qbs.tax_rate_id """.format(tax_code_id1),as_dict=1)
		item_wise_tax[cstr(get_tax_account_head())] = flt(individual_item_tax[0]['tax_percent'])
	return item_wise_tax, cstr(individual_item_tax[0]['tax_head']) if individual_item_tax else '', flt(individual_item_tax[0]['tax_percent']) if individual_item_tax else 0

def get_item_code(qb_item):
	#item_code = frappe.db.get_value("Item", {"quickbooks_variant_id": qb_item.get("variant_id")}, "item_code")
	#if not item_code:
	quickbooks_item_id = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else ''
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id}, "item_code")
	return item_code


def get_order_taxes(qb_orders):
	taxes = []
	Default_company = frappe.defaults.get_defaults().get("company")
	Company_abbr = frappe.db.get_value("Company",{"name":Default_company},"abbr")

	if not qb_orders.get('GlobalTaxCalculation') == 'NotApplicable':
		if qb_orders.get('GlobalTaxCalculation') == 'TaxExcluded' and qb_orders.get('TxnTaxDetail').get('TaxLine'):
			taxes.append({
				"charge_type": _("Actual"),
				"account_head": get_tax_account_head(),
				"description": _("Total Tax added from invoice"),
				"tax_amount": qb_orders.get('TxnTaxDetail').get('TotalTax') 
			})
	return taxes



def get_tax_account_head():
	tax_account =  frappe.db.get_value("Quickbooks Tax Account", \
		{"parent": "Quickbooks Settings"}, "tax_account")

	if not tax_account:
		frappe.throw("Tax Account not specified for QuickBooks Tax ")

	return tax_account




from pyqb.quickbooks.batch import batch_create, batch_delete
from pyqb.quickbooks.objects.invoice import Invoice
from pyqb.quickbooks.objects.detailline import SaleItemLine, SalesItemLineDetail


"""	Sync Invoices Records From ERPNext to QuickBooks """
def sync_erp_sales_invoices(quickbooks_obj):
	"""Receive Response From Quickbooks and Update quickbooks_invoce_id in Invoices"""
	response_from_quickbooks = sync_erp_sales_invoices_to_quickbooks(quickbooks_obj)
	if response_from_quickbooks:
		try:
			for response_obj in response_from_quickbooks.successes:
				if response_obj:
					frappe.db.sql("""UPDATE `tabSales Invoice` SET quickbooks_invoce_id = %s WHERE name ='%s'""" %(response_obj.Id, response_obj.DocNumber))
					frappe.db.commit()
				else:
					raise _("Does not get any response from quickbooks")	
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_erp_sales_invoices", message=frappe.get_traceback(),
				request_data=response_obj, exception=True)

def sync_erp_sales_invoices_to_quickbooks(quickbooks_obj):
	"""Sync ERPNext Invoice to QuickBooks"""
	Sales_invoice_list = []
	for erp_sales_invoice in erp_sales_invoice_data():
		try:
			if erp_sales_invoice:
				create_erp_sales_invoice_to_quickbooks(erp_sales_invoice, Sales_invoice_list)
			else:
				raise _("Sales invoice does not exist in ERPNext")
		except Exception, e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_quickbooks_log(title=e.message, status="Error", method="sync_erp_sales_invoices_to_quickbooks", message=frappe.get_traceback(),
					request_data=erp_sales_invoice, exception=True)
	results = batch_create(Sales_invoice_list)
	return results

def erp_sales_invoice_data():
	"""ERPNext Invoices Record"""
	erp_sales_invoice = frappe.db.sql("""select `name` ,`customer_name`, `taxes_and_charges` from  `tabSales Invoice` where `quickbooks_invoce_id` is NULL and is_pos is FALSE and docstatus = 1""" ,as_dict=1)
	return erp_sales_invoice

def erp_sales_invoice_item_data(invoice_name):
	"""ERPNext Invoice Items Record of Particular Invoice"""
	erp_sales_invoice_item = frappe.db.sql("""SELECT `idx`, `description`, `rate`, `item_code`, `qty` from `tabSales Invoice Item` where parent = '%s'""" %(invoice_name), as_dict=1)
	return erp_sales_invoice_item

def create_erp_sales_invoice_to_quickbooks(erp_sales_invoice, Sales_invoice_list):
	sales_invoice_obj = Invoice()
	sales_invoice_obj.DocNumber = erp_sales_invoice.name
	sales_invoice_item(sales_invoice_obj, erp_sales_invoice)
	customer_ref(sales_invoice_obj, erp_sales_invoice)
	if erp_sales_invoice.get('taxes_and_charges'):
		sales_invoice_obj.GlobalTaxCalculation = "TaxExcluded"
	else:
		sales_invoice_obj.GlobalTaxCalculation = "NotApplicable"
	sales_invoice_obj.save()
	Sales_invoice_list.append(sales_invoice_obj)
	return Sales_invoice_list		

def customer_ref(sales_invoice_obj, erp_sales_invoice):
	quickbooks_cust_id = frappe.db.get_value("Customer", {"name": erp_sales_invoice.get('customer_name')}, "quickbooks_cust_id")
	sales_invoice_obj.CustomerRef = {"value": quickbooks_cust_id}

def sales_invoice_item(sales_invoice_obj, erp_sales_invoice):
	invoice_name = erp_sales_invoice.name
	for invoice_item in erp_sales_invoice_item_data(invoice_name):
		line = SaleItemLine()
		line.LineNum = invoice_item.idx
		line.Description = invoice_item.description
		line.Amount = flt(invoice_item.rate) * flt(invoice_item.qty)
		line.SalesItemLineDetail = SalesItemLineDetail()
		line.SalesItemLineDetail.ItemRef = item_ref(invoice_item) 
		line.SalesItemLineDetail.Qty = invoice_item.qty
		line.SalesItemLineDetail.UnitPrice =invoice_item.rate
		line.SalesItemLineDetail.TaxCodeRef = TaxCodeRef(erp_sales_invoice)
		sales_invoice_obj.Line.append(line)
		
def item_ref(invoice_item):
	quickbooks_item_id = frappe.db.get_value("Item", {"name": invoice_item.get('item_code')}, "quickbooks_item_id")
	return {"value": quickbooks_item_id, "name": invoice_item.get('item_code')}

def TaxCodeRef(erp_sales_invoice):
	quickbooks_sales_tax_id = frappe.db.get_value("Sales Taxes and Charges Template", {"name": erp_sales_invoice.get('taxes_and_charges')}, "quickbooks_sales_tax_id")
	# print quickbooks_sales_tax_id,""
	# return {"value": quickbooks_sales_tax_id}
	return {"value": "11"}