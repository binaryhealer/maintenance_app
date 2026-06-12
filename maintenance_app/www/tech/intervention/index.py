import frappe

no_cache = 1


def get_context(context):
    mi_name = frappe.form_dict.get("name")

    if not mi_name:
        frappe.throw("Mission Intervention missing.")

    mi = frappe.get_doc("Mission Intervention", mi_name)

    context.mi = mi
    context.page_title = "MI " + mi.name