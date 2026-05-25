app_name = "maintenance_app"
app_title = "Maintenance App"
app_publisher = "Gotech Ltd"
app_description = "Support and Maintenance App"
app_email = "gerrard@gotechmu.com"
app_license = "unlicense"

website_route_rules = [
    {"from_route": "/tech", "to_route": "tech"},
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "maintenance_app",
# 		"logo": "/assets/maintenance_app/logo.png",
# 		"title": "Maintenance App",
# 		"route": "/maintenance_app",
# 		"has_permission": "maintenance_app.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/maintenance_app/css/maintenance_app.css"
# app_include_js = "/assets/maintenance_app/js/maintenance_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/maintenance_app/css/maintenance_app.css"
# web_include_js = "/assets/maintenance_app/js/maintenance_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "maintenance_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "maintenance_app/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "maintenance_app.utils.jinja_methods",
# 	"filters": "maintenance_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "maintenance_app.install.before_install"
# after_install = "maintenance_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "maintenance_app.uninstall.before_uninstall"
# after_uninstall = "maintenance_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "maintenance_app.utils.before_app_install"
# after_app_install = "maintenance_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "maintenance_app.utils.before_app_uninstall"
# after_app_uninstall = "maintenance_app.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "maintenance_app.notifications.get_notification_config"

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
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"maintenance_app.tasks.all"
# 	],
# 	"daily": [
# 		"maintenance_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"maintenance_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"maintenance_app.tasks.weekly"
# 	],
# 	"monthly": [
# 		"maintenance_app.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "maintenance_app.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "maintenance_app.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "maintenance_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "maintenance_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["maintenance_app.utils.before_request"]
# after_request = ["maintenance_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["maintenance_app.utils.before_job"]
# after_job = ["maintenance_app.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"maintenance_app.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# ~/frappe-bench/apps/maintenance_app/maintenance_app/hooks.py

#app_name = "maintenance_app"

# Use the full asset path to bypass nesting confusion
#doctype_js = {
 #   "HD Ticket": "/assets/maintenance_app/js/hd_ticket.js"
#}
app_name = "maintenance_app"

doctype_js = {
    "HD Ticket": "public/js/hd_ticket.js"
}
