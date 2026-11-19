"""Persist configuration history after successful MI submission."""
import frappe
from frappe.utils import now_datetime


def on_mi_submitted(doc, method=None):
    if doc.get("custom_intervention_type") != "Config Change":
        return

    rows = doc.get("custom_config_changes") or []
    if not rows:
        frappe.throw("Enter at least one Config Change before submitting this MI.")
    if not doc.get("custom_asset"):
        frappe.throw("An Installed Equipment is required for Config Change history.")

    # A second submit should not occur for docstatus=1. This check also
    # protects against duplicate hook invocation in the same transaction.
    if frappe.db.exists("Config Update Log", {"custom_intervention": doc.name}):
        frappe.throw("Config Update Log records already exist for this intervention; review before retrying.")

    ticket_name = doc.get("custom_service_ticket") or doc.get("custom_parent_ticket") or ""
    ticket = frappe.get_doc("Service Ticket", ticket_name) if ticket_name and frappe.db.exists("Service Ticket", ticket_name) else None

    for number, row in enumerate(rows, 1):
        parameter = (row.get("custom_parameter") or "").strip()
        new_value = (row.get("custom_new_value") or "").strip()
        if not parameter or not new_value:
            frappe.throw(f"Config Change row {number} needs Parameter and New Value.")

        config_log = frappe.new_doc("Config Update Log")
        config_log.custom_parameter = parameter
        config_log.custom_current_value = row.get("custom_current_value") or ""
        config_log.custom_new_value = new_value
        config_log.custom_notes = row.get("custom_notes") or ""
        config_log.custom_config_datetime = row.get("custom_config_datetime") or now_datetime()
        config_log.custom_intervention = doc.name
        config_log.custom_related_asset = doc.get("custom_asset")
        config_log.custom_service_ticket = ticket_name
        if ticket:
            config_log.custom_customer = ticket.get("custom_customer")
            config_log.custom_branch = ticket.get("custom_client_branch")
        # Respect ordinary DocType validation and naming rules.
        config_log.insert(ignore_permissions=True)
