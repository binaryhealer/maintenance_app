import frappe

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to access the client portal.", frappe.PermissionError)
    context.no_cache = 1
    return context
