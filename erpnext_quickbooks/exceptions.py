from __future__ import unicode_literals
import frappe

class QuickbooksError(frappe.ValidationError): pass
class QuickbooksSetupError(frappe.ValidationError): pass
