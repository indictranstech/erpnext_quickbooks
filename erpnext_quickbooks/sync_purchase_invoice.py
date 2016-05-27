from __future__ import unicode_literals
import frappe
from frappe import _
import json
import ast
from frappe.utils import flt, nowdate
import requests.exceptions
from .utils import make_quickbooks_log


"""Sync all the Purchase Invoice from Quickbooks to ERPNEXT"""

def sync_pi_orders(quickbooks_obj):
	quickbooks_purchase_invoice_list =[] 
	purchase_invoice_query = """SELECT * FROM Bill""" 
	qb_purchase_invoice = quickbooks_obj.query(purchase_invoice_query)
	get_qb_purchase_invoice =  qb_purchase_invoice['QueryResponse']	
	sync_qb_pi_orders(get_qb_purchase_invoice, quickbooks_purchase_invoice_list)

def sync_qb_pi_orders(get_qb_purchase_invoice, quickbooks_purchase_invoice_list):
	for qb_orders in get_qb_purchase_invoice['Bill']:
		if valid_supplier_and_product(qb_orders):
			try:
				create_purchase_invoice_order(qb_orders, quickbooks_purchase_invoice_list)
			except Exception, e:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				else:
					make_quickbooks_log(title=e.message, status="Error", method="sync_qb_pi_orders", message=frappe.get_traceback(),
						request_data=qb_orders, exception=True)

def valid_supplier_and_product(qb_orders):
	"""  valid_supplier data from ERPNEXT and store in ERPNEXT """ 
	supplier_id = qb_orders['VendorRef']['value'] 
	if supplier_id:
		if not frappe.db.get_value("Supplier", {"quickbooks_supp_id": supplier_id}, "name"):
			json_data = json.dumps(qb_orders['VendorRef'])
			create_Supplier(ast.literal_eval(json_data), quickbooks_supplier_list = [])		
	else:
		raise _("supplier is mandatory to create order")
	
	return True

def create_purchase_invoice_order(qb_orders, quickbooks_purchase_invoice_list, company=None):
	""" Store Sales Invoice in ERPNEXT """
	create_purchase_invoice(qb_orders, quickbooks_purchase_invoice_list, company=None)

def create_purchase_invoice(qb_orders, quickbooks_purchase_invoice_list, company=None):
	pi = frappe.db.get_value("Purchase Invoice", {"quickbooks_purchase_invoice_id": qb_orders.get("Id")}, "name") 
	if not pi:
		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"quickbooks_purchase_invoice_id" : qb_orders.get("Id"),
			"naming_series": "PI-Quickbooks-",
			"supplier": frappe.db.get_value("Supplier",{"quickbooks_supp_id":qb_orders['VendorRef'].get('value')},"name"),
			"posting_date": nowdate(),
			"buying_price_list": "Standard Buying",
			"ignore_pricing_rule": 1,
			"apply_discount_on": "Net Total",
			"items": get_order_items(qb_orders['Line']),
			"taxes": get_order_taxes(qb_orders)
		})
		pi.flags.ignore_mandatory = True
		pi.save(ignore_permissions=True)
		pi.submit()
		quickbooks_purchase_invoice_list.append(qb_orders.get("id"))
		frappe.db.commit()	
	return quickbooks_purchase_invoice_list

def get_order_items(order_items):
	"""Get all the 'Items details' && 'Account details' from the Purachase Invoice(Bill) from the quickbooks"""
 	items = []
 	for qb_item in order_items:
 		"""Get all the Items details from PI(bill)"""
 		if qb_item.get('DetailType') == "ItemBasedExpenseLineDetail":
			item_code = get_item_code(qb_item)
			items.append({
				"item_code": item_code if item_code else '',
				"item_name": item_code if item_code else qb_item['Description'],
				"description":qb_item['Description'] if qb_item.get('Description') else item_code,
				"price_list_rate": qb_item['ItemBasedExpenseLineDetail']['UnitPrice'],
				"qty": qb_item['ItemBasedExpenseLineDetail']['Qty'],
				"stock_uom": _("Nos")			
			})
		else:
		 	"""Get all Account details from PI(bill)"""
		 	quickbooks_account_reference = qb_item['AccountBasedExpenseLineDetail']['AccountRef']['value']
		 	quickbooks_account = frappe.db.get_value("Account", {"quickbooks_account_id" : quickbooks_account_reference}, "name")
		 	items.append({
				"item_name": qb_item['Description'] if qb_item.get('Description') else quickbooks_account,
				"description":qb_item['Description'] + _(" Service Item") if qb_item.get('Description') else quickbooks_account,
				"price_list_rate": qb_item['Amount'],
				"qty": 1,
				"expense_account": quickbooks_account,
				"stock_uom": _("Nos")			
			})
	return items

def get_item_code(qb_item):
	quickbooks_item_id = qb_item.get('ItemBasedExpenseLineDetail').get('ItemRef').get('value') if qb_item.get('ItemBasedExpenseLineDetail') else ''
	item_code = frappe.db.get_value("Item", {"quickbooks_item_id": quickbooks_item_id}, "item_code")
	return item_code


def get_order_taxes(qb_orders):
	taxes = []
	Default_company = frappe.defaults.get_defaults().get("company")
	Company_abbr = frappe.db.get_value("Company",{"name":Default_company},"abbr")
	
	if not qb_orders['GlobalTaxCalculation'] == 'NotApplicable':
		if qb_orders['GlobalTaxCalculation'] == 'TaxExcluded' and qb_orders['TxnTaxDetail']['TaxLine']:
			taxes.append({
				"category" : _("Total"),
				"charge_type": _("Actual"),
				"account_head": _("Commission on Sales") + " - " + Company_abbr, #get_tax_account_head(tax),
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
