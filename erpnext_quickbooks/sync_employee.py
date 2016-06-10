from __future__ import unicode_literals
import frappe
from frappe import _
from time import strftime
import requests.exceptions
from pyqb.quickbooks.batch import batch_create, batch_delete
from pyqb.quickbooks.objects.employee import Employee

def create_Employee(quickbooks_obj):
	""" Fetch Employee data from QuickBooks and store in ERPNEXT """ 

	employee = None
	quickbooks_employee_list = []
	employee_query = """SELECT Id, DisplayName, PrimaryPhone, Gender, PrimaryEmailAddr, BirthDate, HiredDate, ReleasedDate FROM Employee""" 
	qb_employee = quickbooks_obj.query(employee_query)
	get_qb_employee =  qb_employee['QueryResponse']['Employee']
	
	try:	
		employee = frappe.new_doc("Employee")
		for fields in get_qb_employee:
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
	return quickbooks_employee_list


""" Sync Employee data from ERPNext to Quickbooks """

def sync_erp_employees():
	"""Receive Response From Quickbooks and Update quickbooks_emp_id in Employee"""
	response_from_quickbooks = sync_erp_employees_to_quickbooks()
	if response_from_quickbooks:
		try:
			for response_obj in response_from_quickbooks.successes:
				if response_obj:
					frappe.db.sql("""UPDATE tabEmployee SET quickbooks_emp_id = %s WHERE employee_name ='%s'""" %(response_obj.Id, response_obj.DisplayName))
				else:
					raise _("Does not get any response from quickbooks")	
		except Exception, e:
			make_quickbooks_log(title=e.message, status="Error", method="sync_erp_employees", message=frappe.get_traceback(),
				request_data=response_obj, exception=True)

def sync_erp_employees_to_quickbooks():
	Employee_list = []
	for erp_employee in erp_employee_data():
		try:
			if erp_employee:
				create_erp_employee_to_quickbooks(erp_employee, Employee_list)
			else:
				raise _("Employee does not exist in ERPNext")
		except Exception, e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_quickbooks_log(title=e.message, status="Error", method="sync_erp_employees_to_quickbooks", message=frappe.get_traceback(),
					request_data=erp_employee, exception=True)
	results = batch_create(Employee_list)
	return results

def erp_employee_data():
	erp_employee = frappe.db.sql("""select employee_name, gender from `tabEmployee` where `quickbooks_emp_id` is NULL && employee_name is not null""" ,as_dict=1)
	return erp_employee

def create_erp_employee_to_quickbooks(erp_employee, Employee_list):
	employee_obj = Employee()
	employee_obj.DisplayName = erp_employee.employee_name
	employee_obj.GivenName = erp_employee.employee_name
	employee_obj.FamilyName = erp_employee.employee_name
	employee_obj.Gender = erp_employee.gender
	employee_obj.save()
	Employee_list.append(employee_obj)
	return Employee_list		
