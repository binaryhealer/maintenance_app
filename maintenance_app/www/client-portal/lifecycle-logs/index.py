#lifecyslce for clients to view
import frappe

def get_context(context):
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.local.flags.redirect_to = "/login"
        raise frappe.PermissionError("Not logged in")

    context.log_name = frappe.form_dict.get("name")
    context.asset = frappe.form_dict.get("asset")
    context.event = frappe.form_dict.get("event")

    context.no_header = 1
    context.no_sidebar = 1

    return context