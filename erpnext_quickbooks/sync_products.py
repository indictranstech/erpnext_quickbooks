from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import nowdate
import requests.exceptions
from frappe.utils import cstr, flt, cint
from .utils import make_quickbooks_log
from pyqb.quickbooks.batch import batch_create
from pyqb.quickbooks.objects.item import Item

def create_Item(quickbooks_obj):
	""" Fetch Item data from QuickBooks and store in ERPNEXT """ 
 
	item = None
	quickbooks_item_list = []
	quickbook_product = []
	record_count = quickbooks_obj.query("""SELECT count(*) from Item""")
	total_record = record_count['QueryResponse']['totalCount']
	limit_count = 90
	total_page = total_record / limit_count
	STARTPOSITION,MAXRESULTS = 0,0  
	for i in range(total_page + 1):
		MAXRESULTS = STARTPOSITION + limit_count
		item_query = """SELECT * FROM Item ORDER BY Id ASC STARTPOSITION {0} MAXRESULTS {1} """.format(STARTPOSITION, MAXRESULTS)
		fetch_item_qb = quickbooks_obj.query(item_query)
		qb_item =  fetch_item_qb['QueryResponse']
		if qb_item:
			quickbook_product.extend(qb_item['Item'])
		STARTPOSITION = STARTPOSITION + limit_count
	
	try:
		if qb_item:
			item = frappe.new_doc("Item")
			for fields in quickbook_product:
				if not frappe.db.get_value("Item", {"quickbooks_item_id": str(fields.get('Id'))}, "name"):
					item.quickbooks_item_id = cstr(fields.get('Id'))
					item.item_code = cstr(fields.get('Name')) or cstr(fields.get('Id'))
					item.item_name = cstr(fields.get('Name'))
					item.is_stock_item = False if fields.get('Type') == 'NonInventory' or fields.get('Type') == 'Service' else True
					item.stock_uom = _("Nos")
					item.item_group = _("Consumable")
					item.disabled = True if fields.get('Active') == 'True' else False
					item.description = fields.get('Description') if fields.get('Description') else fields.get('Name')
					quickbooks_item_list.append(str(fields.get('Id')))
					item.insert()
	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
	return item

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