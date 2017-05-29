from __future__ import unicode_literals
import frappe
from frappe import _
import json
from frappe.utils import flt, cstr, nowdate
import requests.exceptions
from .utils import make_quickbooks_log, pagination
from pyqb.quickbooks.batch import batch_create, batch_delete

"""Sync all the Sales Invoice from Quickbooks to ERPNEXT"""
def sync_credit_notes(quickbooks_obj): 
	"""Fetch invoice data from QuickBooks"""
	quickbooks_credit_notes_list = [] 
	business_objects = "CreditMemo"
	get_qb_credit_notes =  pagination(quickbooks_obj, business_objects)
	if get_qb_credit_notes:
		sync_qb_credit_notes(get_qb_credit_notes, quickbooks_credit_notes_list)
		sync_qb_journal_entry_against_si(get_qb_credit_notes)

def sync_qb_credit_notes(get_qb_credit_notes, quickbooks_credit_notes_list):
	company_name = frappe.defaults.get_defaults().get("company")
	default_currency = frappe.db.get_value("Company" ,{"name":company_name},"default_currency")
	for qb_credit_note in get_qb_credit_notes:
		if valid_customer_and_product(qb_credit_note):
			try:
				create_note(qb_credit_note, quickbooks_credit_notes_list, default_currency)
			except Exception, e:
				make_quickbooks_log(title=e.message, status="Error", method="sync_qb_credit_notes", message=frappe.get_traceback(),
						request_data=qb_credit_note, exception=True)

def valid_customer_and_product(qb_credit_note):
	""" Fetch valid_customer data from ERPNEXT and store in ERPNEXT """ 
	from .sync_customers import create_customer
	customer_id = qb_credit_note['CustomerRef'].get('value') 
	if customer_id:
		if not frappe.db.get_value("Customer", {"quickbooks_cust_id": customer_id}, "name"):
			create_customer(qb_credit_note['CustomerRef'], quickbooks_customer_list = [])
	else:
		raise _("Customer is mandatory to create order")
	return True

def create_note(qb_credit_note, quickbooks_credit_notes_list, default_currency):
	""" Store Sales Invoice in ERPNEXT """
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	create_stock_entry(qb_credit_note, quickbooks_settings, quickbooks_credit_notes_list, default_currency)



def create_stock_entry(qb_credit_note, quickbooks_settings, quickbooks_credit_notes_list, default_currency):
	stock_entry = frappe.db.get_value("Stock Entry", {"quickbooks_credit_memo_id": str(qb_credit_note.get("Id"))+"-"+"CN"}, "name")
	if not stock_entry:
		items = get_item_stock(qb_credit_note['Line'], quickbooks_settings)
		if items:
			stock_entry = frappe.get_doc({
				"doctype": "Stock Entry",
				"naming_series" : "CN-SE-Qb-",
				"quickbooks_credit_memo_id" : str(qb_credit_note.get("Id"))+"-"+"CN",
				"posting_date" : qb_credit_note.get('TxnDate'),
				"purpose": "Material Receipt",
				"to_warehouse" : quickbooks_settings.warehouse,
				"quickbooks_customer_reference" : frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_credit_note['CustomerRef'].get('value')},"name"),
				"quickbooks_credit_memo_reference" : qb_credit_note.get("DocNumber"),
				"items" : items
				})
			stock_entry.flags.ignore_mandatory = True
			stock_entry.save(ignore_permissions=True)
			stock_entry.submit()

def get_item_stock(order_items, quickbooks_settings):
 	items = []
 	for qb_item in order_items:
 		shipp_item = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else 1
		if qb_item.get('SalesItemLineDetail') and shipp_item !="SHIPPING_ITEM_ID":
		 	item_code = get_item_code(qb_item)
		 	if item_code:
		 		items.append({
					"item_code": item_code,
					"rate": qb_item.get('SalesItemLineDetail').get('UnitPrice') if qb_item.get('SalesItemLineDetail').get('UnitPrice') else qb_item.get('Amount'),
					"qty": qb_item.get('SalesItemLineDetail').get('Qty') if qb_item.get('SalesItemLineDetail').get('Qty') else 1,
					"t_warehouse" : quickbooks_settings.warehouse,
					"warehouse": quickbooks_settings.warehouse,
					"uom": _("Nos")
					})
	return items


def get_item_code(qb_item):
	#item_code = frappe.db.get_value("Item", {"quickbooks_variant_id": qb_item.get("variant_id")}, "item_code")
	#if not item_code:
	# item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id}, "item_code")
	quickbooks_item_id = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else ''
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id, "is_stock_item":1}, "item_code")

	return item_code


def sync_qb_journal_entry_against_si(get_qb_payment):
	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
	for recived_payment in get_qb_payment:
 		try:
 			if not frappe.db.get_value("Journal Entry", {"quickbooks_journal_entry_id": recived_payment.get('Id')+"CE"}, "name"):
 				create_journal_entry_against_si(recived_payment, quickbooks_settings)
 		except Exception, e:
 			make_quickbooks_log(title=e.message, status="Error", method="sync_qb_journal_entry_against_si", message=frappe.get_traceback(),
						request_data=recived_payment, exception=True)

def create_journal_entry_against_si(recived_payment, quickbooks_settings):
	# stock_entry =frappe.db.get_value("Stock Entry", {"quickbooks_credit_memo_id": recived_payment.get('Id')+"-"+"CN"}, "name")
	# if stock_entry:
	# ref_doc = frappe.get_doc("Stock Entry", stock_entry)
	si_je = frappe.get_doc({
		"doctype": "Journal Entry",
		"naming_series" : "CN-JV-Qb-",
		"quickbooks_journal_entry_id" : recived_payment.get('Id')+"CE",
		"voucher_type" : _("Credit Note"),
		"posting_date" : recived_payment.get('TxnDate'),
		"multi_currency": 1
	})
	get_journal_entry_account(si_je, recived_payment, quickbooks_settings)
	si_je.save()
	si_je.submit()
	frappe.db.commit()

def get_journal_entry_account(si_je, recived_payment, quickbooks_settings):
	accounts_entry(si_je, recived_payment, quickbooks_settings)


def accounts_entry(si_je, recived_payment, quickbooks_settings):
	append_row_credit_detail(si_je= si_je, recived_payment= recived_payment, quickbooks_settings= quickbooks_settings)
	append_row_debit_detail(si_je= si_je, recived_payment = recived_payment, quickbooks_settings= quickbooks_settings)

def append_row_credit_detail(si_je= None, recived_payment = None, quickbooks_settings= None):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")

	account = si_je.append("accounts", {})
	account.account = set_debit_to(si_je, recived_payment, quickbooks_settings, company_currency)
	account.party_type =  "Customer"
	account.party = frappe.db.get_value("Customer",{"quickbooks_cust_id":recived_payment['CustomerRef'].get('value')},"name")
	account.is_advance = "Yes"
	account.exchange_rate = recived_payment.get('ExchangeRate')
	account.credit = flt(recived_payment.get("TotalAmt") * recived_payment.get('ExchangeRate'), account.precision("credit"))
	account.credit_in_account_currency = flt(recived_payment.get("TotalAmt") , account.precision("credit_in_account_currency"))


def set_debit_to(si_je, recived_payment, quickbooks_settings, company_currency):
	"Set debit account"
	party_currency = recived_payment.get("CurrencyRef").get('value') if recived_payment.get("CurrencyRef") else company_currency
	if party_currency:
		debtors_account = frappe.db.get_value("Account", {"account_currency": party_currency, "quickbooks_account_id": ["!=",""], 'account_type': 'Receivable',\
			"company": quickbooks_settings.select_company, "root_type": "Asset", "is_group": "0"}, "name")
		return debtors_account



def append_row_debit_detail(si_je= None, recived_payment = None, quickbooks_settings= None):
	company_name = quickbooks_settings.select_company
	company_currency = frappe.db.get_value("Company", {"name": company_name}, "default_currency")

	account = si_je.append("accounts", {})
	account_ref1 = quickbooks_settings.bank_account
	account_ref = get_account_detail(account_ref1)
	account.account = account_ref.get('name')
	if account_ref.get('account_currency') == company_currency:
		account.exchange_rate = 1
		account.debit_in_account_currency = flt(recived_payment.get("TotalAmt") * recived_payment.get('ExchangeRate') , account.precision("debit_in_account_currency"))
	else:
		account.exchange_rate = recived_payment.get('ExchangeRate')
		account.debit_in_account_currency = flt(recived_payment.get("TotalAmt") , account.precision("debit_in_account_currency"))

	account.is_advance = "No"

def get_account_detail(account_ref):
	return frappe.db.get_value("Account", {"name": account_ref}, ["name", "account_currency"], as_dict=1)





# """Sync all the Sales Invoice from Quickbooks to ERPNEXT"""
# def sync_credit_notes(quickbooks_obj): 
# 	"""Fetch invoice data from QuickBooks"""
# 	quickbooks_credit_notes_list = [] 
# 	business_objects = "CreditMemo"
# 	get_qb_credit_notes =  pagination(quickbooks_obj, business_objects)
# 	if get_qb_credit_notes:
# 		sync_qb_credit_notes(get_qb_credit_notes, quickbooks_credit_notes_list)

# def sync_qb_credit_notes(get_qb_credit_notes, quickbooks_credit_notes_list):
# 	company_name = frappe.defaults.get_defaults().get("company")
# 	default_currency = frappe.db.get_value("Company" ,{"name":company_name},"default_currency")
# 	for qb_credit_note in get_qb_credit_notes:
# 		if valid_customer_and_product(qb_credit_note):
# 			try:
# 				create_note(qb_credit_note, quickbooks_credit_notes_list, default_currency)
# 			except Exception, e:
# 				make_quickbooks_log(title=e.message, status="Error", method="sync_qb_credit_notes", message=frappe.get_traceback(),
# 						request_data=qb_credit_note, exception=True)
					
# def valid_customer_and_product(qb_credit_note):
# 	""" Fetch valid_customer data from ERPNEXT and store in ERPNEXT """ 
# 	from .sync_customers import create_customer
# 	customer_id = qb_credit_note['CustomerRef'].get('value') 
# 	if customer_id:
# 		if not frappe.db.get_value("Customer", {"quickbooks_cust_id": customer_id}, "name"):
# 			create_customer(qb_credit_note['CustomerRef'], quickbooks_customer_list = [])
# 	else:
# 		raise _("Customer is mandatory to create order")
# 	return True

# def create_note(qb_credit_note, quickbooks_credit_notes_list, default_currency):
# 	""" Store Sales Invoice in ERPNEXT """
# 	quickbooks_settings = frappe.get_doc("Quickbooks Settings", "Quickbooks Settings")
# 	create_credit_note(qb_credit_note, quickbooks_settings, quickbooks_credit_notes_list, default_currency)

# def create_credit_note(qb_credit_note, quickbooks_settings, quickbooks_credit_notes_list, default_currency):
# 	si = frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": str(qb_credit_note.get("Id"))+"-"+"CN"}, "name")
# 	term_id = qb_credit_note.get('SalesTermRef').get('value') if qb_credit_note.get('SalesTermRef') else ""
# 	term = ""
# 	if term_id:
# 		term = frappe.db.get_value("Terms and Conditions", {"quickbooks_term_id": term_id}, ["name","terms"],as_dict=1)
# 	if not si:
# 		si = frappe.get_doc({
# 			"doctype": "Sales Invoice",
# 			"quickbooks_invoce_id" : str(qb_credit_note.get("Id"))+"-"+"CN",
# 			"naming_series": "CREDIT-NOTE-",
# 			"currency" : qb_credit_note.get("CurrencyRef").get('value') if qb_credit_note.get("CurrencyRef") else default_currency,
# 			"conversion_rate" : qb_credit_note.get("ExchangeRate") if qb_credit_note.get("CurrencyRef") else 1,
# 			"quickbooks_invoice_no" : qb_credit_note.get("DocNumber"),
# 			"title": frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_credit_note['CustomerRef'].get('value')},"name"),
# 			"customer": frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_credit_note['CustomerRef'].get('value')},"name"),
# 			"posting_date": qb_credit_note.get('TxnDate'),
# 			"due_date": qb_credit_note.get('DueDate'),
# 			"territory" : frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_credit_note['CustomerRef'].get('value')},"territory"),
# 			"selling_price_list": quickbooks_settings.selling_price_list,
# 			"ignore_pricing_rule": 1,
# 			"update_stock": 1,
# 			"apply_discount_on": "Net Total",
# 			"items": get_order_items(qb_credit_note['Line'], quickbooks_settings),
# 			"taxes": get_individual_item_tax(qb_credit_note, qb_credit_note['Line'], quickbooks_settings),
# 			"tc_name": term.get('name') if term else "",
# 			"terms": term.get('terms')if term else ""

# 		})
		
# 		if qb_credit_note.get('BillAddr'):
# 			if not qb_credit_note.get('BillAddr').has_key("Long"):
# 				if not (qb_credit_note.get('BillAddr').has_key("Country") or qb_credit_note.get('BillAddr').has_key("City")):
# 					full_address, index = new_address_creation(qb_credit_note, si)
# 					if index != False:
# 						si.customer_address = create_address(full_address, si, qb_credit_note.get('BillAddr'), "Billing", index)
# 						si.address_display = full_address
# 					else:
# 						si.customer_address = get_address_name(full_address)
# 						si.address_display = full_address

# 		si.flags.ignore_mandatory = True
# 		si.save(ignore_permissions=True)
# 		si.submit()
# 		quickbooks_credit_notes_list.append(qb_credit_note.get("id"))


# 		from erpnext.controllers.sales_and_purchase_return import make_return_doc
# 		cn = make_return_doc("Sales Invoice", si.name, target_doc=None)
# 		cn.naming_series ="SINV-RET-"
# 		cn.flags.ignore_mandatory = True
# 		cn.save(ignore_permissions=True)
# 		cn.submit()
		
# 		frappe.db.commit()	
# 	return quickbooks_credit_notes_list

# # def get_individual_item_tax(order_items, quickbooks_settings):
# # 	"""tax break for individual item from QuickBooks"""
# # 	taxes = []
# # 	Default_company = frappe.defaults.get_defaults().get("company")
# # 	Company_abbr = frappe.db.get_value("Company",{"name":Default_company},"abbr")
# # 	tax_amount = 0
# # 	for i in get_order_items(order_items, quickbooks_settings):
# # 		if i['quickbooks__tax_code_value']:
# # 			tax_amount = flt(tax_amount) + (flt(i['quickbooks__tax_code_value']) * (i['qty'] *i['rate']))/100
# # 	if tax_amount:
# # 		taxes.append({
# # 				"charge_type": _("On Net Total"),
# # 				"account_head": get_tax_account_head(),
# # 				"description": _("Total Tax added from invoice"),
# # 				"rate": 0,
# # 				"tax_amount": tax_amount
# # 				})
# # 	return taxes
# # def new_address_creation(qb_credit_note, si):
# # 	address_list = frappe.db.sql("select concat(address_line1,address_line2) as address from `tabAddress` where customer='{}'".format(si.customer), as_list=1)
# # 	customer_address_line_1_2 = [x[0] for x in address_list]
# # 	index =frappe.db.sql("select count(*) as count from `tabAddress` where customer = '{0}'".format(si.customer),as_dict=1)
# # 	type_of_address ="Billing"
# # 	if qb_credit_note.get('BillAddr'):
# # 		address1 = []
# # 		full_address =''
# # 		bill_adress = qb_credit_note.get('BillAddr')
# # 		for j in range(len(bill_adress)-1):
# # 			if 'Line'+str(j+1) != 'Line1':
# # 				address1.append(bill_adress['Line'+str(j+1)])
# # 		full_address = " ".join(address1)
# # 		if not full_address in customer_address_line_1_2:
# # 			return create_address(full_address, si, bill_adress, type_of_address, int(index[0]['count'])+1)

# def new_address_creation(qb_credit_note, si):
# 	address_list = frappe.db.sql("select concat(address_line1,address_line2) as address from `tabAddress` where customer='{}'".format(si.customer), as_list=1)
# 	customer_address_line = [x[0] for x in address_list]
# 	index = frappe.db.sql("select count(*) as count from `tabAddress` where customer = '{0}'".format(si.customer),as_dict=1)
# 	# type_of_address ="Billing"
# 	if qb_credit_note.get('BillAddr'):
# 		address = []
# 		bill_adress = qb_credit_note.get('BillAddr')
# 		for j in xrange(len(bill_adress)-1):
# 			if 'Line'+str(j+1) != 'Line1':
# 				address.append(bill_adress['Line'+str(j+1)])
# 		full_address = " ".join(address)
# 		if not full_address in customer_address_line:
# 			return full_address, int(index[0]['count'])+1
# 		else:
# 			return full_address, False
# 			# return create_address(full_address, si, bill_adress, type_of_address, int(index[0]['count'])+1)

# def get_address_name(full_address):
# 	return frappe.db.get_value("Address", {"address_line1":full_address[:len(full_address)/2], 
# 		"address_line2":full_address[len(full_address)/2:]}, "name")


# def create_address(full_address, si, bill_adress, type_of_address, index):
# 	address_title, address_type = get_address_title_and_type(si.customer, type_of_address, index)
# 	qb_id = str(bill_adress.get("Id")) + str(address_type)
# 	try :
# 		address_customer = frappe.get_doc({
# 			"doctype": "Address",
# 			"quickbooks_address_id": qb_id,
# 			"address_title": address_title,
# 			"address_type": address_type,
# 			"address_line1": full_address[:len(full_address)/2] if full_address else '',
# 			"address_line2": full_address[len(full_address)/2:] if full_address else '',
# 			"customer": si.customer
# 		})
# 		address_customer.flags.ignore_mandatory = True
# 		address_customer.insert()
			
# 	except Exception, e:
# 		make_quickbooks_log(title=e.message, status="Error", method="create_customer_address", message=frappe.get_traceback(),
# 				request_data=bill_adress, exception=True)
# 	return address_customer.name
			
# def get_address_title_and_type(customer_name, type_of_address, index):
# 	address_type = _(type_of_address)
# 	address_title = customer_name
# 	if frappe.db.get_value("Address", "{0}-{1}".format(customer_name.strip(), address_type)):
# 		address_title = "{0}-{1}".format(customer_name.strip(), index)
# 	return address_title, address_type 



# def get_individual_item_tax(qb_credit_note, order_items, quickbooks_settings):
# 	"""tax break for individual item from QuickBooks"""
# 	taxes = []
# 	if not qb_credit_note.get('GlobalTaxCalculation') == 'NotApplicable':
# 		taxes_rate_list = {}
# 		account_head_list = set()

# 		for i in get_order_items(order_items, quickbooks_settings):
# 			account_head =json.loads(i['item_tax_rate']).keys()[0] if json.loads(i['item_tax_rate']).keys() else '' 
# 			if account_head in account_head_list and i['quickbooks__tax_code_value'] != 0:
# 				taxes_rate_list[account_head] += float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
# 			elif i['quickbooks__tax_code_value'] != 0:
# 				taxes_rate_list[account_head] = float(i['quickbooks__tax_code_value']*i['rate']*i['qty']/100)
# 				account_head_list.add(account_head)

# 		if taxes_rate_list:
# 			for key, value in taxes_rate_list.iteritems():
# 				taxes.append({
# 					"charge_type": _("On Net Total"),
# 					"account_head": key,
# 					"description": _("Total Tax added from invoice"),
# 					"rate": 0,
# 					"tax_amount": value
# 					})

# 		shipping_charges = get_order_shipping_detail(order_items, quickbooks_settings) 
# 		if shipping_charges:
# 			taxes.extend(shipping_charges)
# 	# for i in get_order_items(order_items, quickbooks_settings):
# 	# 	if i['quickbooks__tax_code_value']:
# 	# 		tax_amount = flt(tax_amount) + (flt(i['quickbooks__tax_code_value']) * (i['qty'] *i['rate']))/100
# 	# if tax_amount:
# 	# 	taxes.append({
# 	# 			"charge_type": _("On Net Total"),
# 	# 			"account_head": get_tax_account_head(),
# 	# 			"description": _("Total Tax added from invoice"),
# 	# 			"rate": 0,
# 	# 			"tax_amount": tax_amount
# 	# 			})
# 	return taxes

# def get_order_items(order_items, quickbooks_settings):
#  	items = []
#  	for qb_item in order_items:
#  		shipp_item = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else 1
# 		if qb_item.get('SalesItemLineDetail') and shipp_item !="SHIPPING_ITEM_ID":
# 		 	item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = tax_code_ref(qb_item, quickbooks_settings)
# 			item_code = get_item_code(qb_item)
# 			items.append({
# 				"item_code": item_code if item_code else '',
# 				"item_name": item_code if item_code else qb_item.get('Description')[:35],
# 				"description": qb_item.get('Description') if qb_item.get('Description') else '',
# 				"rate": qb_item.get('SalesItemLineDetail').get('UnitPrice') if qb_item.get('SalesItemLineDetail').get('UnitPrice') else qb_item.get('Amount'),
# 				"qty": qb_item.get('SalesItemLineDetail').get('Qty') if qb_item.get('SalesItemLineDetail').get('Qty') else 1,
# 				"income_account": quickbooks_settings.cash_bank_account,
# 				"warehouse": quickbooks_settings.warehouse,
# 				"stock_uom": _("Nos"),
# 				"item_tax_rate": '{0}'.format(json.dumps(item_tax_rate)),
# 				"quickbooks_tax_code_ref": quickbooks_tax_code_ref,
# 				"quickbooks__tax_code_value": quickbooks__tax_code_value
# 			})
# 	return items

# def get_order_shipping_detail(order_items, quickbooks_settings):
#  	Shipping = []
#  	for qb_item in order_items:
#  		shipp_item = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else 1
# 		if qb_item.get('SalesItemLineDetail') and shipp_item =="SHIPPING_ITEM_ID":
# 			item_tax_rate, quickbooks_tax_code_ref, quickbooks__tax_code_value = tax_code_ref(qb_item, quickbooks_settings)
# 			Shipping.append({
# 				"charge_type": _("Actual"),
# 				"account_head": quickbooks_settings.shipping_account,
# 				"description": _("Total Shipping cost {}".format(qb_item.get('Amount'))),
# 				"rate": 0,
# 				"tax_amount": qb_item.get('Amount')
# 				})
# 			Shipping.append({
# 				"charge_type": _("Actual"),
# 				"account_head": item_tax_rate.keys()[0],
# 				"description": _("Tax applied on shipping {}".format(float(quickbooks__tax_code_value * qb_item.get('Amount')/100))),
# 				"rate": 0,
# 				"tax_amount": float(quickbooks__tax_code_value * qb_item.get('Amount')/100)
# 				})
# 	return Shipping

# def tax_code_ref(qb_item, quickbooks_settings):
# 	item_wise_tax ={}
# 	individual_item_tax = ''
# 	if qb_item.get('SalesItemLineDetail').get('TaxCodeRef'):
# 		tax_code_id1 = qb_item.get('SalesItemLineDetail').get('TaxCodeRef').get('value') if qb_item.get('SalesItemLineDetail') else ''
# 		individual_item_tax =  frappe.db.sql("""select qbr.name, qbr.display_name as tax_head, qbr.rate_value as tax_percent
# 						from 
# 							`tabQuickBooks TaxRate` as qbr,
# 							(select * from `tabQuickBooks SalesTaxRateList` where parent = {0}) as qbs 
# 						where 
# 							qbr.tax_rate_id = qbs.tax_rate_id """.format(tax_code_id1),as_dict=1)
# 		item_tax_rate = get_tax_head_mapped_to_particular_account(individual_item_tax[0]['tax_head'], quickbooks_settings)
# 		item_wise_tax[cstr(item_tax_rate)] = flt(individual_item_tax[0]['tax_percent'])
# 	return item_wise_tax, cstr(individual_item_tax[0]['tax_head']) if individual_item_tax else '', flt(individual_item_tax[0]['tax_percent']) if individual_item_tax else 0

# def get_tax_head_mapped_to_particular_account(tax_head, quickbooks_settings):
# 	""" fetch respective tax head from Tax Head Mappe table """
# 	account_head_erpnext = frappe.db.get_value("Tax Head Mapper", {"tax_head_quickbooks": tax_head, \
# 			"parent": "Quickbooks Settings"}, "account_head_erpnext")
# 	if not account_head_erpnext:
# 		account_head_erpnext = quickbooks_settings.undefined_tax_account
# 	return account_head_erpnext

# def get_item_code(qb_item):
# 	#item_code = frappe.db.get_value("Item", {"quickbooks_variant_id": qb_item.get("variant_id")}, "item_code")
# 	#if not item_code:
# 	quickbooks_item_id = qb_item.get('SalesItemLineDetail').get('ItemRef').get('value') if qb_item.get('SalesItemLineDetail') else ''
# 	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id}, "item_code")
# 	return item_code



