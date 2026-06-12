import frappe

def get_context(context):
    mi_name = frappe.form_dict.get("mi")

    if not mi_name:
        frappe.throw("Missing intervention reference")

    mi = frappe.get_doc("Mission Intervention", mi_name)

    if not mi.custom_branch:
        frappe.throw("No branch linked to this intervention")

    branch = frappe.get_doc("Client Branch", mi.custom_branch)

    context.mi = mi
    context.branch = branch
    context.branch_contacts = branch.get("custom_branch_contacts") or []
    context.ho_contacts = branch.get("custom_head_office_contacts") or []

    return context