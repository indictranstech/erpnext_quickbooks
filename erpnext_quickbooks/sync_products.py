from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import nowdate
import requests.exceptions
from frappe.utils import cstr, flt, cint
from .utils import make_quickbooks_log, pagination
from pyqb.quickbooks.batch import batch_create
from pyqb.quickbooks.objects.item import Item


def sync_items(quickbooks_obj):
	"""Fetch Items data from QuickBooks"""
	quickbooks_item_list = []
	business_objects = "Item"
	get_qb_item = pagination(quickbooks_obj, business_objects)
	if get_qb_item:
		sync_qb_items(get_qb_item, quickbooks_item_list)
	
def sync_qb_items(get_qb_item, quickbooks_item_list):
	for qb_item in get_qb_item:
		if not frappe.db.get_value("Item", {"quickbooks_item_id": qb_item.get('Id')}, "name"):
			create_Item(qb_item, quickbooks_item_list)

def create_Item(qb_item, quickbooks_item_list):
	""" store Items data in ERPNEXT """ 
	item = None
	try:	
		item = frappe.get_doc({
			"doctype": "Item",
			"quickbooks_item_id" : cstr(qb_item.get('Id')),
			"item_code" : cstr(qb_item.get('Name')) or cstr(qb_item.get('Id')),
			"item_name" : cstr(qb_item.get('Name')),
			"is_stock_item" : False if qb_item.get('Type') == 'NonInventory' or qb_item.get('Type') == 'Service' else True,
			"stock_uom" : _("Nos"),
			"item_group" : _("Consumable"),
			"disabled" : True if qb_item.get('Active') == 'True' else False,
			"description" : qb_item.get('Description') if qb_item.get('Description') else qb_item.get('Name'),
		})
		item.flags.ignore_mandatory = True
		item.insert()
				
		frappe.db.commit()
		quickbooks_item_list.append(item.quickbooks_item_id)
	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_quickbooks_log(title=e.message, status="Error", method="create_Item", message=frappe.get_traceback(),
				request_data=qb_item, exception=True)

	return quickbooks_item_list

def sync_erp_items():
	response_from_quickbooks = sync_erp_items_to_quickbooks()
	if response_from_quickbooks:
		try:
			for response_obj in response_from_quickbooks.successes:
				if response_obj:
					frappe.db.sql("""UPDATE tabItem SET quickbooks_item_id = %s WHERE item_code ='%s'""" %(response_obj.Id, response_obj.Name))
				else:
					raise _("Does not get any response from quickbooks")	
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_erp_items", message=frappe.get_traceback(),
				request_data=response_obj, exception=True)

def sync_erp_items_to_quickbooks():
	Item_list = []
	for erp_item in erp_item_data():
		try:
			if erp_item:
				create_erp_item_to_quickbooks(erp_item, Item_list)
			else:
				raise _("Item does not exist in ERPNext")
		except Exception, e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_quickbooks_log(title=e.message, status="Error", method="sync_erp_items_to_quickbooks", message=frappe.get_traceback(),
					request_data=erp_item, exception=True)
	results = batch_create(Item_list)
	return results

def erp_item_data():
	erp_item = frappe.db.sql("""select item_code, item_name, is_stock_item, Description from `tabItem` where `quickbooks_item_id` is NULL""" ,as_dict=1)
	return erp_item

def create_erp_item_to_quickbooks(erp_item, Item_list):
	item_obj = Item()
	item_obj.Name = erp_item.item_code
	item_obj.FullyQualifiedName = erp_item.item_code
	item_obj.Description = erp_item.Description if erp_item.Description else erp_item.item_name
	item_type_and_Inventory_start_date(item_obj, erp_item)
	item_obj.AssetAccountRef = asset_account_ref(erp_item)
	item_obj.ExpenseAccountRef = expense_account_ref(erp_item)
	item_obj.IncomeAccountRef = income_account_ref(erp_item)
	item_obj.save()
	Item_list.append(item_obj)
	return Item_list

def item_type_and_Inventory_start_date(item_obj, erp_item):
	if erp_item.is_stock_item == True:
		item_obj.Type = "Inventory"
		item_obj.TrackQtyOnHand = True
		item_obj.QtyOnHand = 0
		item_obj.InvStartDate = nowdate()
	else:
		item_obj.Type = "NonInventory"

def income_account_ref(erp_item):
	account_type = erp_item.get(income_account)
	return income_account(erp_item, account_type)
	
def income_account(erp_item, account_type):
	if erp_item.is_stock_item == True:
		if account_type:
			quickbooks_account_id = frappe.db.get_value("Accounts", {"name": account_type}, "quickbooks_account_id") 
			return {"value": quickbooks_account_id, "name": account_type}
		else:
			return {"value": "21", "name": "Sales of Product Income"}
	else:
		return {"value": "21", "name": "Sales of Product Income"}
		
def expense_account_ref(erp_item):
	account_type = erp_item.get(expense_account)
	return expense_account(erp_item, account_type)

def expense_account(erp_item, account_type):
	if erp_item.is_stock_item == True:
		if account_type:
			quickbooks_account_id = frappe.db.get_value("Accounts", {"name": account_type}, "quickbooks_account_id") 
			return {"value": quickbooks_account_id, "name": account_type}
		else:
			return {"value": "28", "name": "Cost of sales"}
	else:
		return {"value": "28", "name": "Cost of sales"}

def asset_account_ref(erp_item):
	return asset_account(erp_item)

def asset_account(erp_item):
	if not erp_item.is_stock_item == False:
		return {"value": "27", "name": "Inventory Asset"}