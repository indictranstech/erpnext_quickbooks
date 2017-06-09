from __future__ import unicode_literals
import frappe
from frappe import _
import json
from frappe.utils import flt, cstr, nowdate
import requests.exceptions
from .utils import make_quickbooks_log, pagination
from pyqb.quickbooks.batch import batch_create, batch_delete

"""Sync all the Sales Invoice from Quickbooks to ERPNEXT"""
def sync_si_orders(quickbooks_obj): 
	"""Fetch invoice data from QuickBooks"""
	quickbooks_invoice_list = [] 
	business_objects = "Invoice"
	get_qb_invoice =  pagination(quickbooks_obj, business_objects)
	if get_qb_invoice:
		sync_qb_si_orders(get_qb_invoice, quickbooks_invoice_list)

def sync_qb_si_orders(get_qb_invoice, quickbooks_invoice_list):
	company_name = frappe.defaults.get_defaults().get("company")
	default_currency = frappe.db.get_value("Company" ,{"name":company_name},"default_currency")
	for qb_orders in get_qb_invoice:
		if valid_customer_and_product(qb_orders):
			try:
				create_order(qb_orders, quickbooks_invoice_list, default_currency)
			except Exception, e:
				make_quickbooks_log(title=e.message, status="Error", method="sync_qb_si_orders", message=frappe.get_traceback(),
						request_data=qb_orders, exception=True)
					
def valid_customer_and_product(qb_orders):
	""" Fetch valid_customer data from ERPNEXT and store in ERPNEXT """ 
	from .sync_customers import create_customer
	customer_id = qb_orders['CustomerRef'].get('value') 
	if customer_id:
		if not frappe.db.get_value("Customer", {"quickbooks_cust_id": customer_id}, "name"):
			create_customer(qb_orders['CustomerRef'], quickbooks_customer_list = [])
	else:
		raise _("Customer is mandatory to create order")
	return True

def create_order(qb_orders, quickbooks_invoice_list, default_currency):
	""" Store Sales Invoice in ERPNEXT """
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	create_sales_invoice(qb_orders, quickbooks_settings, quickbooks_invoice_list, default_currency)

def create_sales_invoice(qb_orders, quickbooks_settings, quickbooks_invoice_list, default_currency):
	si = frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": qb_orders.get("Id")}, "name")
	term_id = qb_orders.get('SalesTermRef').get('value') if qb_orders.get('SalesTermRef') else ""
	term = ""
	if term_id:
		term = frappe.db.get_value("Terms and Conditions", {"quickbooks_term_id": term_id}, ["name","terms"],as_dict=1)
	if not si:
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"quickbooks_invoce_id" : qb_orders.get("Id"),
			"naming_series": "SINV-",
			"currency" : qb_orders.get("CurrencyRef").get('value') if qb_orders.get("CurrencyRef") else default_currency,
			"conversion_rate" : qb_orders.get("ExchangeRate") if qb_orders.get("CurrencyRef") else 1,
			"quickbooks_invoice_no" : qb_orders.get("DocNumber"),
			"title": frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_orders['CustomerRef'].get('value')},"name"),
			"customer": frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_orders['CustomerRef'].get('value')},"name"),
			"posting_date": qb_orders.get('TxnDate'),
			"due_date": qb_orders.get('DueDate'),
			"territory" : frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_orders['CustomerRef'].get('value')},"territory"),
			"selling_price_list": quickbooks_settings.selling_price_list,
			"ignore_pricing_rule": 1,
			"update_stock": 1,
			"apply_discount_on": "Net Total",
			"items": get_order_items(qb_orders['Line'], quickbooks_settings),
			"taxes": get_individual_item_tax(qb_orders, qb_orders['Line'], quickbooks_settings),
			"tc_name": term.get('name') if term else "",
			"terms": term.get('terms')if term else ""

		})
		
		if qb_orders.get('BillAddr'):
			if not qb_orders.get('BillAddr').has_key("Long"):
				if not (qb_orders.get('BillAddr').has_key("Country") or qb_orders.get('BillAddr').has_key("City")):
					full_address, index = new_address_creation(qb_orders, si)
					if index != False:
						si.customer_address = create_address(full_address, si, qb_orders.get('BillAddr'), "Billing", index)
						si.address_display = full_address
					else:
						si.customer_address = get_address_name(full_address)
						si.address_display = full_address

		set_debit_to(si, qb_orders, quickbooks_settings, default_currency)

		si.flags.ignore_mandatory = True
		si.save(ignore_permissions=True)
		si.submit()
		quickbooks_invoice_list.append(qb_orders.get("id"))
		frappe.db.commit()	
	return quickbooks_invoice_list


def set_debit_to(si, qb_orders, quickbooks_settings, default_currency):
	"Set debit account"
	party_currency = qb_orders.get("CurrencyRef").get('value') if qb_orders.get("CurrencyRef") else default_currency
	if party_currency:
		debtors_account = frappe.db.get_value("Account", {"account_currency": party_currency, "quickbooks_account_id": ["!=",""], 'account_type': 'Receivable',\
			"company": quickbooks_settings.select_company, "root_type": "Asset", "is_group": "0"}, "name")
		si.debit_to = debtors_account


def new_address_creation(qb_orders, si):
	address_list = frappe.db.sql("select concat(address_line1,address_line2) as address from `tabAddress` where customer='{}'".format(si.customer), as_list=1)
	customer_address_line = [x[0] for x in address_list]
	index = frappe.db.sql("select count(*) as count from `tabAddress` where customer = '{0}'".format(si.customer),as_dict=1)

	if qb_orders.get('BillAddr'):
		address = []
		bill_adress = qb_orders.get('BillAddr')
		for j in xrange(len(bill_adress)-1):
			if 'Line'+str(j+1) != 'Line1':
				address.append(bill_adress['Line'+str(j+1)])
		full_address = " ".join(address)
		if not full_address in customer_address_line:
			return full_address, int(index[0]['count'])+1
		else:
			return full_address, False

def get_address_name(full_address):
	return frappe.db.get_value("Address", {"address_line1":full_address[:len(full_address)/2], 
		"address_line2":full_address[len(full_address)/2:]}, "name")

def create_address(full_address, si, bill_adress, type_of_address, index):
	address_title, address_type = get_address_title_and_type(si.customer, type_of_address, index)
	qb_id = str(bill_adress.get("Id")) + str(address_type)
	try :
		address_customer = frappe.get_doc({
			"doctype": "Address",
			"quickbooks_address_id": qb_id,
			"address_title": address_title,
			"address_type": address_type,
			"address_line1": full_address[:len(full_address)/2] if full_address else '',
			"address_line2": full_address[len(full_address)/2:] if full_address else '',
			"customer": si.customer
		})
		address_customer.flags.ignore_mandatory = True
		address_customer.insert()
			
	except Exception, e:
		make_quickbooks_log(title=e.message, status="Error", method="create_customer_address", message=frappe.get_traceback(),
				request_data=bill_adress, exception=True)
	return address_customer.name
			
def get_address_title_and_type(customer_name, type_of_address, index):
	address_type = _(type_of_address)
	address_title = customer_name
	if frappe.db.get_value("Address", "{0}-{1}".format(customer_name.strip(), address_type)):
		address_title = "{0}-{1}".format(customer_name.strip(), index)
	return address_title, address_type 

def get_individual_item_tax(qb_orders, order_items, quickbooks_settings):
	"""tax break for individual item from QuickBooks"""
	taxes = []
	if not qb_orders.get('GlobalTaxCalculation') == 'NotApplicable':
		taxes_rate_list = {}
		account_head_list = set()

		for i in get_order_items(order_items, quickbooks_settings):
			account_head =json.loads(i['item_tax_rate']).keys()[0] if json.loads(i['item_tax_rate']).keys() else '' 
			if account_head in account_head_list and i['quickbooks__tax_code_value'] != 0:
				taxes_rate_list[account_head] += flt(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
			elif i['quickbooks__tax_code_value'] != 0:
				taxes_rate_list[account_head] = flt(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
				account_head_list.add(account_head)

		if taxes_rate_list:
			for key, value in taxes_rate_list.iteritems():
				taxes.append({
					"charge_type": _("On Net Total"),
					"account_head": key,
					"description": _("Total Tax added from invoice"),
					"rate": 0,
					"tax_amount": value
					})

		shipping_charges = get_order_shipping_detail(order_items, quickbooks_settings) 
		if shipping_charges:
			taxes.extend(shipping_charges)

	return taxes

def get_order_items(order_items, quickbooks_settings):
 	items = []
 	for qb_item in order_items:
 		shipp_item = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else 1
		if qb_item.get('SalesItemLineDetail') and shipp_item !="SHIPPING_ITEM_ID":
		 	item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = tax_code_ref(qb_item, quickbooks_settings)
			item_code = get_item_code(qb_item)
			items.append({
				"item_code": item_code.get('item_code'),
				"item_name": item_code.get('item_name') if item_code else item_code.get('item_code'),
				"description": qb_item.get('Description') if qb_item.get('Description') else item_code.get('item_name'),
				"rate": qb_item.get('SalesItemLineDetail').get('UnitPrice') if qb_item.get('SalesItemLineDetail').get('UnitPrice') else qb_item.get('Amount'),
				"qty": qb_item.get('SalesItemLineDetail').get('Qty') if qb_item.get('SalesItemLineDetail').get('Qty') else 1,
				"income_account": quickbooks_settings.cash_bank_account,
				"warehouse": quickbooks_settings.warehouse,
				"stock_uom": _("Nos"),
				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
				"quickbooks__tax_code_value": quickbooks__tax_code_value
			})
	return items

def get_order_shipping_detail(order_items, quickbooks_settings):
 	Shipping = []
 	for qb_item in order_items:
 		shipp_item = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else 1
		if qb_item.get('SalesItemLineDetail') and shipp_item =="SHIPPING_ITEM_ID":
			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = tax_code_ref(qb_item, quickbooks_settings)
			Shipping.append({
				"charge_type": _("Actual"),
				"account_head": quickbooks_settings.shipping_account,
				"description": _("Total Shipping cost {}".format(qb_item.get('Amount'))),
				"rate": 0,
				"tax_amount": qb_item.get('Amount')
				})
			Shipping.append({
				"charge_type": _("Actual"),
				"account_head": item_tax_rate.keys()[0],
				"description": _("Tax applied on shipping {}".format(flt(quickbooks__tax_code_value * qb_item.get('Amount')/100))),
				"rate": 0,
				"tax_amount": flt(quickbooks__tax_code_value * qb_item.get('Amount')/100)
				})
	return Shipping

def tax_code_ref(qb_item, quickbooks_settings):
	item_wise_tax ={}
	individual_item_tax = ''
	if qb_item.get('SalesItemLineDetail').get('TaxCodeRef'):
		tax_code_id1 = qb_item.get('SalesItemLineDetail').get('TaxCodeRef').get('value') if qb_item.get('SalesItemLineDetail') else ''
		query = """
				select 
					qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
				from
					`tabQuickBooks TaxRate` as qbr,
					(select * from `tabQuickBooks SalesTaxRateList` where parent = {0}) as qbs 
				where
					qbr.tax_rate_id = qbs.tax_rate_id """.format(tax_code_id1)
		individual_item_tax =  frappe.db.sql(query, as_dict=1)
		item_tax_rate = get_tax_head_mapped_to_particular_account(individual_item_tax[0]['tax_head'], quickbooks_settings)
		item_wise_tax[cstr(item_tax_rate)] = flt(individual_item_tax[0]['tax_percent'])
	return item_wise_tax, cstr(individual_item_tax[0]['tax_head']) if individual_item_tax else '', flt(individual_item_tax[0]['tax_percent']) if individual_item_tax else 0

def get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings):
	""" fetch respective tax head from Tax Head Mappe table """
	account_head_erpnext = frappe.db.get_value("Tax Head Mapper", {"tax_head_quickbooks": tax_head, \
			"parent": "Quickbooks Settings"}, "account_head_erpnext")
	if not account_head_erpnext:
		account_head_erpnext = quickbooks_settings.undefined_tax_account
	return account_head_erpnext

def get_item_code(qb_item):
	#item_code = frappe.db.get_value("Item", {"quickbooks_variant_id": qb_item.get("variant_id")}, "item_code")
	#if not item_code:
	quickbooks_item_id = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else ''
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id}, ["item_code","item_name"],as_dict=1)
	return item_code

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