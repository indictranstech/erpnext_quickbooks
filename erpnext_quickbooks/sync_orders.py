from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, nowdate
import requests.exceptions
from .utils import make_quickbooks_log


def sync_orders(quickbooks_obj): 
	"""Fetch invoice data from QuickBooks"""
	quickbooks_invoice_list = []
	invoice_query = """SELECT * FROM Invoice""" 
	qb_invoice = quickbooks_obj.query(invoice_query)
	get_qb_invoice =  qb_invoice['QueryResponse']	
	sync_qb_orders(get_qb_invoice)

def sync_qb_orders(get_qb_invoice):
	quickbooks_invoice_list = [] 
	for qb_orders in get_qb_invoice['Invoice']:
		if valid_customer_and_product(qb_orders):
			# create_order(qb_orders,quickbooks_invoice_list)
			try:
				create_order(qb_orders, quickbooks_invoice_list)
			except Exception, e:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				else:
					make_quickbooks_log(title=e.message, status="Error", method="sync_qb_orders", message=frappe.get_traceback(),
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
	create_sales_invoice(qb_orders, quickbooks_invoice_list, company=None)

def create_sales_invoice(qb_orders, quickbooks_invoice_list, company=None):
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
			"apply_discount_on": "Net Total",
			"items": get_order_items(qb_orders['Line']),
			"taxes": get_order_taxes(qb_orders)
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
			"description":order_items[qb_item]['Description'] if order_items[qb_item].get('Description') else item_code,
			"rate": order_items[qb_item].get('SalesItemLineDetail').get('UnitPrice'),
			"qty": order_items[qb_item].get('SalesItemLineDetail').get('Qty'),
			"stock_uom": _("Nos")			
		})
	return items

def get_item_code(qb_item):
	#item_code = frappe.db.get_value("Item", {"quickbooks_variant_id": qb_item.get("variant_id")}, "item_code")
	#if not item_code:
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": qb_item.get('SalesItemLineDetail').get('ItemRef').get('value')}, "item_code")

	return item_code


def get_order_taxes(qb_orders):
	taxes = []
	if not qb_orders['GlobalTaxCalculation'] == 'NotApplicable':
		if qb_orders['GlobalTaxCalculation'] == 'TaxExcluded' and qb_orders['TxnTaxDetail']['TaxLine']:
			#for tax in qb_orders['TxnTaxDetail']['TaxLine']:
			taxes.append({
				"charge_type": _("Actual"),
				"account_head": "Commission on Sales - ES",#get_tax_account_head(tax),
				"description": "Total Tax added from invoice",
				"tax_amount": qb_orders['TxnTaxDetail']['TotalTax'] 
				#"included_in_print_rate": set_included_in_print_rate(shopify_order)
			})
		# else:
		# 	for tax in qb_orders['TxnTaxDetail']['TaxLine']:
		# 			taxes.append({
		# 				"charge_type": _("On Net Total"),
		# 				"account_head": "Commission on Sales - ES",#get_tax_account_head(tax),
		# 				"description": "{0} - {1}%".format(tax.get("title"), tax.get("rate") * 100.0),
		# 				"rate": tax.get("rate") * 100.00
		# 				#"included_in_print_rate": set_included_in_print_rate(shopify_order)
		# 			})
			#taxes = update_taxes_with_shipping_lines(taxes, shopify_order.get("shipping_lines"))

	return taxes