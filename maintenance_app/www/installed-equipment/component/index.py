import frappe

no_cache = 1

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/installed-equipment/component"
        raise frappe.Redirect
    allowed_roles = {"RM","Maintenance Manager","Maintenance Supervisor","Maintenance Technician","System Manager","Administrator"}
    if not allowed_roles.intersection(set(frappe.get_roles())):
        frappe.throw("You are not permitted to access the Equipment Component web view.", frappe.PermissionError)
    context.title = "Equipment Component"
    context.page_url = "/installed-equipment/component"
    context.asset_version = "13"
    return context
