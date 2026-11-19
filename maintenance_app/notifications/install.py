"""Idempotent setup for standard DocTypes used by Maintenance App.

The Service Ticket and child DocTypes are shipped as regular DocType JSON files.
Contact belongs to Frappe, so its checkbox is added as a Custom Field.
"""

import frappe


def ensure_contact_applicant_field():
    """Create the ISP Applicant checkbox on Contact, if missing.

    Safe to run on app installation and after every bench migrate. Never
    overwrites an administrator's existing field settings or values.
    """
    fieldname = "custom_allow_as_service_applicant"
    field_id = f"Contact-{fieldname}"

    if frappe.db.exists("Custom Field", field_id):
        return

    existing = frappe.get_meta("Contact").get_field(fieldname)
    if existing:
        return

    details = {
        "doctype": "Custom Field",
        "dt": "Contact",
        "fieldname": fieldname,
        "label": "Allow as Service Applicant",
        "fieldtype": "Check",
        "default": "0",
        "description": (
            "Permit this Contact to be selected as a Service Ticket Applicant "
            "even when it is not linked to the selected Customer or Branch."
        ),
    }
    if frappe.get_meta("Contact").has_field("custom_contact_scope"):
        details["insert_after"] = "custom_contact_scope"

    frappe.get_doc(details).insert(ignore_permissions=True)
    frappe.clear_cache(doctype="Contact")


def copy_legacy_external_contact_role():
    """Preserve the data from the originally misspelled cutom_role_company.

    The old field remains hidden in the child DocType. This migration copies
    values into the corrected custom_role_company field without deleting data.
    """
    dt = "Service Ticket External Contact"
    if not frappe.db.table_exists(dt):
        return

    old = "cutom_role_company"
    new = "custom_role_company"
    if not (frappe.db.has_column(dt, old) and frappe.db.has_column(dt, new)):
        return

    frappe.db.sql(
        """UPDATE `tabService Ticket External Contact`
           SET `custom_role_company` = `cutom_role_company`
         WHERE COALESCE(`custom_role_company`, '') = ''
           AND COALESCE(`cutom_role_company`, '') != ''"""
    )


def ensure_external_contact_field():
    """Create the Contact flag used to select ISP/external contacts."""
    fieldname = "custom_allow_as_external_contact"

    if frappe.db.exists("Custom Field", f"Contact-{fieldname}"):
        return

    if frappe.get_meta("Contact").has_field(fieldname):
        return

    details = {
        "doctype": "Custom Field",
        "dt": "Contact",
        "fieldname": fieldname,
        "label": "Allow as ISP / External Contact",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "custom_allow_as_service_applicant",
    }

    frappe.get_doc(details).insert(ignore_permissions=True)
    frappe.clear_cache(doctype="Contact")


def install_notification_contact_fields():
    """Install missing Contact fields without modifying existing settings."""
    ensure_contact_applicant_field()
    ensure_external_contact_field()
