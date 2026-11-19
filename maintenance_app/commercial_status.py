import frappe


def sync_ticket_invoice_readiness(doc, method=None):
    """Advance approved billable work to invoicing when resolved."""

    if doc.get("custom_ticket_status") != "Resolved":
        return

    if doc.get("custom_commercial_status") != "Ready for Planning":
        return

    references = doc.get("custom_commercial_references") or []

    sales_orders = {
        row.get("custom_reference_name")
        for row in references
        if row.get("custom_reference_type") == "Sales Order"
        and row.get("custom_reference_name")
    }

    for sales_order in sales_orders:
        if not frappe.db.exists("Sales Order", sales_order):
            continue

        status = frappe.db.get_value(
            "Sales Order", sales_order, "docstatus"
        )

        if int(status or 0) == 1:
            doc.custom_commercial_status = "To be Invoiced"
            return
