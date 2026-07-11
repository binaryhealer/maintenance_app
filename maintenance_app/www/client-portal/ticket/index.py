# pfor cient portal display ticket summary

import frappe

def get_context(context):
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.local.flags.redirect_to = "/login"
        raise frappe.PermissionError("Not logged in")

    ticket_name = frappe.form_dict.get("name")

    if not ticket_name:
        frappe.throw("Ticket name is required.")

    context.ticket_name = ticket_name
    context.no_header = 1
    context.no_sidebar = 1

    return context