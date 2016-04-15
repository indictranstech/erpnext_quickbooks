# -*- coding: utf-8 -*-
from __future__ import unicode_literals

app_name = "erpnext_quickbooks"
app_title = "Erpnext Quickbooks"
app_publisher = "Frappe Technologies Pvt. Ltd."
app_description = "Quickbooks connector for ERPNext"
app_icon = "icon-truck"
app_color = "grey"
app_email = "info@frappe.io"
app_version = "0.0.1"
app_license = "GNU GPL v3.0"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnext_quickbooks/css/erpnext_quickbooks.css"
# app_include_js = "/assets/erpnext_quickbooks/js/erpnext_quickbooks.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_quickbooks/css/erpnext_quickbooks.css"
# web_include_js = "/assets/erpnext_quickbooks/js/erpnext_quickbooks.js"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "erpnext_quickbooks.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "erpnext_quickbooks.install.before_install"
# after_install = "erpnext_quickbooks.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_quickbooks.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"erpnext_quickbooks.tasks.all"
# 	],
# 	"daily": [
# 		"erpnext_quickbooks.tasks.daily"
# 	],
# 	"hourly": [
# 		"erpnext_quickbooks.tasks.hourly"
# 	],
# 	"weekly": [
# 		"erpnext_quickbooks.tasks.weekly"
# 	]
# 	"monthly": [
# 		"erpnext_quickbooks.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "erpnext_quickbooks.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnext_quickbooks.event.get_events"
# }

