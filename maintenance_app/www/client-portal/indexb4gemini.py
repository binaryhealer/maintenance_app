import frappe


def get_context(context):
    """
    Client Portal page controller
    Path should be:
    maintenance_app/www/client-portal/index.py
    """

    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/client-portal"
        raise frappe.Redirect

    user = frappe.session.user

    context.user = user
    context.user_full_name = frappe.db.get_value("User", user, "full_name") or user

    contact_name = frappe.db.get_value("Contact", {"user": user}, "name")

    if not contact_name:
        contact_name = frappe.db.get_value("Contact", {"email_id": user}, "name")

    if not contact_name:
        contact_rows = frappe.db.sql("""
            SELECT parent
            FROM `tabContact Email`
            WHERE email_id = %s
            LIMIT 1
        """, user)

        contact_name = contact_rows[0][0] if contact_rows else None

    context.contact = contact_name

    customer = None

    if contact_name:
        customer = frappe.db.get_value(
            "Dynamic Link",
            {
                "parenttype": "Contact",
                "parent": contact_name,
                "link_doctype": "Customer"
            },
            "link_name"
        )

    context.customer = customer
    context.customer_name = (
        frappe.db.get_value("Customer", customer, "customer_name")
        if customer else None
    )

    context.portal_ready = 1 if customer else 0

    return context
