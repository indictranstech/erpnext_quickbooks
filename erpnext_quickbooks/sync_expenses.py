from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .utils import make_quickbooks_log, pagination
import csv
# from pyqb.quickbooks.batch import batch_create, batch_delete
# from pyqb.quickbooks.objects.customer import Customer 

def sync_expenses(quickbooks_obj):
	"""Fetch Expenses data from QuickBooks"""
	quickbooks_expense_list = []
	business_objects = "Purchase"
	get_qb_expenses = pagination(quickbooks_obj, business_objects)
	if get_qb_expenses:
		print get_qb_expenses,"--------"
		create_csv(get_qb_expenses)

def create_csv(l):
	with open('expense','w') as fp:
		a = csv.writer(fp)
		data =[l]
		a.writerows(data)
	
