from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions


def sync_orders(quickbooks_obj,get_series): 
	"""Fetch invoice data from QuickBooks"""
	quickbooks_invoice_list = []
	invoice_query = """SELECT * FROM Invoice""" 
	#invoice_query = """SELECT * FROM Invoice where DocNumber IN ('1016', '1015')"""
	fetch_invoice_qb = quickbooks_obj.query(invoice_query)
	qb_invoice =  fetch_invoice_qb['QueryResponse']	
	sync_qb_orders(qb_invoice)

def sync_qb_orders():
	quickbooks_invoice_list = [] 
	data = [{u'AllowOnlineACHPayment': False, u'domain': u'QBO', u'CurrencyRef': {u'name': u'Indian Rupee', u'value': u'INR'}, u'HomeBalance': 130.0, u'PrintStatus': u'NotSet', u'BillEmail': {u'Address': u'jdrew@myemail.com'}, u'SalesTermRef': {u'value': u'3'}, u'GlobalTaxCalculation': u'NotApplicable', u'TotalAmt': 130.0, u'Line': [{u'Description': u'book of Dan brown', u'DetailType': u'SalesItemLineDetail', u'SalesItemLineDetail': {u'Qty': 1, u'UnitPrice': 120, u'ItemRef': {u'name': u'inventory Book', u'value': u'19'}}, u'LineNum': 1, u'Amount': 120.0, u'Id': u'1'}, {u'Description': u'nut & bolt as non inventory item', u'DetailType': u'SalesItemLineDetail', u'SalesItemLineDetail': {u'Qty': 1, u'UnitPrice': 10, u'ItemRef': {u'name': u'Nuts and bolt', u'value': u'20'}}, u'LineNum': 2, u'Amount': 10.0, u'Id': u'2'}, {u'DetailType': u'SubTotalLineDetail', u'Amount': 130.0, u'SubTotalLineDetail': {}}], u'DueDate': u'2016-05-22', u'MetaData': {u'CreateTime': u'2016-04-22T04:00:12-07:00', u'LastUpdatedTime': u'2016-04-22T04:07:21-07:00'}, u'DocNumber': u'1015', u'sparse': False, u'Deposit': 0, u'Balance': 130.0, u'CustomerRef': {u'name': u'Bond Jame', u'value': u'73'}, u'TxnTaxDetail': {u'TotalTax': 0}, u'AllowOnlineCreditCardPayment': False, u'SyncToken': u'1', u'LinkedTxn': [], u'ExchangeRate': 1, u'ShipAddr': {u'City': u'kota', u'Country': u'India', u'Line1': u'A- 108 shivam enclave bajrang nagar', u'PostalCode': u'324006', u'Lat': u'25.17941', u'Long': u'75.86330769999999', u'CountrySubDivisionCode': u'Rajasthan', u'Id': u'13'}, u'HomeTotalAmt': 130.0, u'TxnDate': u'2016-04-22', u'EmailStatus': u'NotSet', u'BillAddr': {u'City': u'kota', u'Country': u'India', u'Line1': u'A- 108 shivam enclave bajrang nagar', u'PostalCode': u'324006', u'Lat': u'25.17941', u'Long': u'75.86330769999999', u'CountrySubDivisionCode': u'Rajasthan', u'Id': u'13'}, u'CustomField': [], u'Id': u'152', u'AllowOnlinePayment': False, u'AllowIPNPayment': False}, {u'AllowOnlineACHPayment': False, u'domain': u'QBO', u'CurrencyRef': {u'name': u'Indian Rupee', u'value': u'INR'}, u'HomeBalance': 100.0, u'PrintStatus': u'NotSet', u'BillEmail': {u'Address': u'jdrew@myemail.com'}, u'SalesTermRef': {u'value': u'3'}, u'GlobalTaxCalculation': u'NotApplicable', u'TotalAmt': 100.0, u'Line': [{u'LineNum': 1, u'Amount': 100.0, u'SalesItemLineDetail': {u'Qty': 1, u'UnitPrice': 100, u'ItemRef': {u'name': u'mouse', u'value': u'26'}}, u'Id': u'1', u'DetailType': u'SalesItemLineDetail'}, {u'DetailType': u'SubTotalLineDetail', u'Amount': 100.0, u'SubTotalLineDetail': {}}], u'DueDate': u'2016-05-22', u'MetaData': {u'CreateTime': u'2016-04-22T04:06:29-07:00', u'LastUpdatedTime': u'2016-04-22T04:06:29-07:00'}, u'DocNumber': u'1016', u'sparse': False, u'Deposit': 0, u'Balance': 100.0, u'CustomerRef': {u'name': u'Bond Jame', u'value': u'73'}, u'TxnTaxDetail': {u'TotalTax': 0}, u'AllowOnlineCreditCardPayment': False, u'SyncToken': u'0', u'LinkedTxn': [], u'ExchangeRate': 1, u'ShipAddr': {u'City': u'kota', u'Country': u'India', u'Line1': u'A- 108 shivam enclave bajrang nagar', u'PostalCode': u'324006', u'Lat': u'25.17941', u'Long': u'75.86330769999999', u'CountrySubDivisionCode': u'Rajasthan', u'Id': u'13'}, u'HomeTotalAmt': 100.0, u'TxnDate': u'2016-04-22', u'EmailStatus': u'NotSet', u'BillAddr': {u'City': u'kota', u'Country': u'India', u'Line1': u'A- 108 shivam enclave bajrang nagar', u'PostalCode': u'324006', u'Lat': u'25.17941', u'Long': u'75.86330769999999', u'CountrySubDivisionCode': u'Rajasthan', u'Id': u'13'}, u'CustomField': [], u'Id': u'154', u'AllowOnlinePayment': False, u'AllowIPNPayment': False}]
	#for qb_orders in qb_invoice['Invoice']:
	for qb_orders in data:
		if valid_customer_and_product(qb_orders):
			#create_order(qb_orders,quickbooks_invoice_list)
			try:
				create_order(qb_orders,quickbooks_invoice_list)
			except Exception, e:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				
def valid_customer_and_product(qb_orders):
	""" Fetch valid_customer data from ERPNEXT and store in ERPNEXT """ 
	customer_id = qb_orders['CustomerRef'].get('value') 
	if customer_id:
		if not frappe.db.get_value("Customer", {"quickbooks_cust_id": customer_id}, "name"):
			json_data = json.dumps(qb_orders['CustomerRef'])
			create_customer(ast.literal_eval(json_data),quickbooks_customer_list = [])		
	else:
		raise _("Customer is mandatory to create order")
	
	return True

def create_order(qb_orders,quickbooks_invoice_list,company=None):
	""" Store Sales Invoice in ERPNEXT """
	create_sales_invoice(qb_orders,quickbooks_invoice_list,company=None)

def create_sales_invoice(qb_orders,quickbooks_invoice_list,company=None):
	si = frappe.db.get_value("Sales Invoice", {"quickbooks_invoce_id": qb_orders.get("Id")}, "name") 
	if not si:
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"quickbooks_invoce_id" : qb_orders.get("Id"),
			"naming_series": "SO-Quickbooks-",
			"customer": frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_orders['CustomerRef'].get('value')},"name"),
			"posting_date": nowdate(),
			"territory" : frappe.db.get_value("Customer",{"quickbooks_cust_id":qb_orders['CustomerRef'].get('value')},"territory"),
			"selling_price_list": "Standard Selling",
			"ignore_pricing_rule": 1,
			"debit_to" : "Debtors - ES",
			"apply_discount_on": "Net Total",
			"items": get_order_items(qb_orders['Line'])
		})
		si.flags.ignore_mandatory = True
		si.save(ignore_permissions=True)
		si.submit()
		quickbooks_invoice_list.append(qb_orders.get("id"))
		frappe.db.commit()	
	return quickbooks_invoice_list

def get_order_items(order_items):
 	items = []
	for qb_item in range(len(order_items) -1):
		item_code = get_item_code(order_items[qb_item])
		items.append({
			"item_code": item_code,
			"item_name": item_code,
			"rate": order_items[qb_item].get('SalesItemLineDetail').get('UnitPrice'),
			"qty": order_items[qb_item].get('SalesItemLineDetail').get('Qty'),
			"stock_uom": _("Nos"),
			"warehouse": "Finished Goods - ES",
			"income_account":"Sales - ES"
		})
	return items

def get_item_code(qb_item):
	#item_code = frappe.db.get_value("Item", {"quickbooks_variant_id": qb_item.get("variant_id")}, "item_code")
	#if not item_code:
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": qb_item.get('SalesItemLineDetail').get('ItemRef').get('value')}, "item_code")

	return item_code