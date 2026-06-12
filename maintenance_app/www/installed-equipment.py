# ============================================================
# installed-equipment.py
# Frappe Web Page controller
# Path: maintenance_app/www/installed-equipment.py
# ============================================================

import frappe

def get_context(context):
    context.no_cache = 1

    # Require login
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/installed-equipment"
        raise frappe.Redirect

    # Require RM or Supervisor role
    allowed_roles = {"RM", "Maintenance Manager", "Maintenance Supervisor", "System Manager", "Administrator"}
    user_roles = set(frappe.get_roles(frappe.session.user))

    if not allowed_roles.intersection(user_roles):
        frappe.throw("You do not have permission to access this page.", frappe.PermissionError)

    context.title = "Installed Equipment"
    context.page_url = "/installed-equipment"
