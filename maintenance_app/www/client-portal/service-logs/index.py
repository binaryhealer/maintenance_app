#Service log display for clients

import frappe

def get_context(context):
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.local.flags.redirect_to = "/login"
        raise frappe.PermissionError("Not logged in")

    context.asset = frappe.form_dict.get("asset")
    context.component = frappe.form_dict.get("component")
    context.component_serial = frappe.form_dict.get("component_serial")

    context.no_header = 1
    context.no_sidebar = 1

    return context