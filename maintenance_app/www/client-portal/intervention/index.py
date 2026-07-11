#shows MI to ST

import frappe

def get_context(context):
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.local.flags.redirect_to = "/login"
        raise frappe.PermissionError("Not logged in")

    intervention_name = frappe.form_dict.get("name") or frappe.form_dict.get("intervention")

    if not intervention_name:
        frappe.throw("Intervention name is required.")

    context.intervention_name = intervention_name
    context.no_header = 1
    context.no_sidebar = 1

    return context