from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions


def create_Item(quickbooks_obj):
	""" Fetch Item data from QuickBooks and store in ERPNEXT """ 
 
	item = None
	quickbooks_item_list = []
	item_query = """SELECT MetaData, Name, Sku, Description, Active, Taxable, SalesTaxIncluded, UnitPrice, Type, IncomeAccountRef, PurchaseTaxCodeRef, PurchaseCost, SalesTaxCodeRef, AbatementRate, ExpenseAccountRef, PurchaseTaxCodeRef,  SyncToken , MetaData FROM Item ORDER BY Id DESC""" 
	fetch_item_qb = quickbooks_obj.query(item_query)
	qb_item =  fetch_item_qb['QueryResponse']
	

	try:
		item = frappe.new_doc("Item")
		for fields in qb_item['Item']:
			if not frappe.db.get_value("Item", {"quickbooks_item_id": str(fields.get('Id'))}, "name"):
				item.quickbooks_item_id = cstr(fields.get('Id'))
				item.quickbooks_item_synctoken = cstr(fields.get('SyncToken'))
				#item.modified = fields['MetaData'].get('LastUpdatedTime')
				item.item_code = cstr(fields.get('Name')) or cstr(fields.get('Id'))
				item.item_name = cstr(fields.get('Name'))
				item.is_sales_item = 1
				item.stock_uom = _("Nos")
				item.item_group = "Consumable"
				item.is_stock_item = False if fields.get('Type') == 'NonInventory' else True
				item.disabled = True if fields.get('Active') == 'True' else False
				item.barcode = fields.get('Sku') if fields.get('Sku') else ''
				item.description = fields.get('Description') if fields.get('Description') else fields.get('Name')
				quickbooks_item_list.append(str(fields.get('Id')))
				item.insert()
	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e

	print "qb item list ",quickbooks_item_list
	return item