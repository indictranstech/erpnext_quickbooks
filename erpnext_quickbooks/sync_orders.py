from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions

def create_Invoice(quickbooks_obj):
	""" Fetch Invoice data from QuickBooks and store in ERPNEXT """ 
	
	invoice = None
	quickbooks_invoice_list = []
	invoice_query = """SELECT * FROM Invoice""" 
	fetch_invoice_qb = quickbooks_obj.query(invoice_query)
	qb_invoice =  fetch_invoice_qb['QueryResponse']
	
	try:
		for fields in qb_invoice['Invoice']:
			customer_id = fields['CustomerRef'].get('value') 
			if customer_id:
				if not frappe.db.get_value("Customer", {"quickbooks_cust_id": customer_id}, "name"):
					json_data = json.dumps(fields['CustomerRef'])
					create_customer(ast.literal_eval(json_data),quickbooks_customer_list = [])		
			else:
				raise _("Customer is mandatory to create order")

	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e

	# print "qb invoice list ",quickbooks_invoice_list	
	return True

# code is working 		

# def valid_customer_and_product(quickbooks_obj):
# 	""" Fetch Invoice data from QuickBooks and store in ERPNEXT """ 
	
# 	invoice = None
# 	quickbooks_invoice_list = []
# 	invoice_query = """SELECT * FROM Invoice""" 
# 	fetch_invoice_qb = quickbooks_obj.query(invoice_query)
# 	qb_invoice =  fetch_invoice_qb['QueryResponse']
	
# 	try:
# 		for fields in qb_invoice['Invoice']:
# 			customer_id = fields['CustomerRef'].get('value') 
# 			if customer_id:
# 				if not frappe.db.get_value("Customer", {"quickbooks_cust_id": customer_id}, "name"):
# 					json_data = json.dumps(fields['CustomerRef'])
# 					create_customer(ast.literal_eval(json_data),quickbooks_customer_list = [])		
# 			else:
# 				raise _("Customer is mandatory to create order")

# 	except Exception, e:
# 		if e.args[0] and e.args[0].startswith("402"):
# 			raise e
	
# 	return True

# end of working code