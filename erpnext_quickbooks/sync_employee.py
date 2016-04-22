from __future__ import unicode_literals
import frappe
from frappe import _
from time import strftime
import requests.exceptions

def create_Employee(quickbooks_obj):
	""" Fetch Employee data from QuickBooks and store in ERPNEXT """ 

	employee = None
	quickbooks_employee_list = []
	employee_query = """SELECT Id, DisplayName, PrimaryPhone, Gender, PrimaryEmailAddr, BirthDate, HiredDate, ReleasedDate FROM Employee""" 
	fetch_employee_qb = quickbooks_obj.query(employee_query)
	qb_employee =  fetch_employee_qb['QueryResponse']
	
	try:	
		employee = frappe.new_doc("Employee")
		for fields in qb_employee['Employee']:
			if not frappe.db.get_value("Employee", {"quickbooks_emp_id": str(fields.get('Id'))}, "name"):
				employee.employee_name = fields.get('DisplayName')
				employee.quickbooks_emp_id = str(fields.get('Id'))
				employee.date_of_joining = fields.get('HiredDate') if fields.get('HiredDate') else strftime("%Y-%m-%d")
				employee.date_of_birth = fields.get('BirthDate') if fields.get('BirthDate') else "2016-04-01"
				employee.gender = fields.get('Gender') if fields.get('Gender') else "Male"
				employee.cell_number =fields['Mobile'].get('FreeFormNumber','') if fields.get('Mobile') else ''
				employee.personal_email =fields['PrimaryEmailAddr'].get('Address','') if fields.get('PrimaryEmailAddr') else ''
				employee.insert()
				quickbooks_employee_list.append(str(fields.get('Id')))
	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e

	print "qb employee list ",quickbooks_employee_list
	return quickbooks_employee_list
