import frappe

def get_context(context):
    mi_name = frappe.form_dict.get("mi")

    if not mi_name:
        frappe.throw("Missing intervention reference")

    mi_doc = frappe.get_doc("Mission Intervention", mi_name)

    if not mi_doc.custom_branch:
        frappe.throw("No branch linked to this intervention")

    branch_doc = frappe.get_doc("Client Branch", mi_doc.custom_branch)

    context.mi = mi_doc
    context.branch = branch_doc
    context.branch_contacts = branch_doc.get("custom_branch_contacts") or []
    context.ho_contacts = branch_doc.get("custom_head_office_contacts") or []

    return context