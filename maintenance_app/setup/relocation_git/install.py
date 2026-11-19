"""Install missing Relocation configuration without overwriting existing records."""

import json
from pathlib import Path

import frappe


CONFIG_DIR = Path(__file__).resolve().parent

RECORDS = [
    ("movement_request_doctype.json", "DocType", "Service Ticket Movement Request"),
    ("service_ticket_movement_requests_field.json", "Custom Field", "Service Ticket-custom_movement_requests"),
    ("movement_request_property_setter.json", "Property Setter", "Service Ticket Movement Request-custom_request_status-read_only"),
    ("movement_approval_client_script.json", "Client Script", "Service Ticket - Movement Approval"),
]


def install_relocation_configuration():
    for filename, doctype, name in RECORDS:
        data = json.loads(
            (CONFIG_DIR / filename).read_text(encoding="utf-8")
        )

        if data.get("doctype") != doctype or data.get("name") != name:
            frappe.throw(f"Invalid Relocation configuration: {filename}")

        if frappe.db.exists(doctype, name):
            print(f"EXISTS: {doctype} | {name}")
            continue

        doc = frappe.get_doc(data)
        doc.insert(ignore_permissions=True)

        print(f"CREATED: {doctype} | {name}")

    frappe.clear_cache(doctype="Service Ticket")
    frappe.clear_cache(doctype="Service Ticket Movement Request")

    print("Relocation configuration installation completed.")
