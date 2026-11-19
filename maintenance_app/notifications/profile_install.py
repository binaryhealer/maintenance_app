"""Install GMAO Notification profiles without overwriting existing records."""

import json
from pathlib import Path

import frappe


PROFILE_DIR = Path(__file__).resolve().parent / "profiles"

PROFILES = {
    "tech_mission_created.json": "GMAO - Tech Mission Created",
    "tech_mission_updated.json": "GMAO - Tech Mission Updated",
    "service_ticket_awaiting_client.json": "GMAO - Service Ticket Awaiting Client",
    "service_ticket_resolved.json": "GMAO - Service Ticket Resolved",
    "service_ticket_closed.json": "GMAO - Service Ticket Closed",
}

SYSTEM_FIELDS = {
    "creation",
    "modified",
    "modified_by",
    "owner",
    "idx",
    "_user_tags",
    "_comments",
    "_assign",
    "_liked_by",
}


def clean_export(value):
    """Remove database-specific metadata from exported records."""
    if isinstance(value, list):
        return [clean_export(item) for item in value]

    if isinstance(value, dict):
        result = {
            key: clean_export(item)
            for key, item in value.items()
            if key not in SYSTEM_FIELDS and key != "__islocal"
        }
        return result

    return value


def install_gmao_notification_profiles():
    """Create missing, disabled GMAO Notification profiles."""
    for filename, expected_name in PROFILES.items():
        path = PROFILE_DIR / filename
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("doctype") != "Notification":
            frappe.throw(f"Invalid Notification export: {filename}")

        if data.get("name") != expected_name:
            frappe.throw(f"Unexpected Notification name: {filename}")

        if frappe.db.exists("Notification", expected_name):
            print(f"EXISTS: {expected_name}")
            continue

        data = clean_export(data)

        # Discard source-site child record identities.
        for row in data.get("recipients") or []:
            row.pop("name", None)
            row.pop("parent", None)
            row.pop("parenttype", None)
            row.pop("parentfield", None)

        # Never activate notifications automatically on deployment.
        data["enabled"] = 0

        doc = frappe.get_doc(data)
        doc.insert(ignore_permissions=True)

        print(f"CREATED DISABLED: {expected_name}")

    frappe.clear_cache()
    print("GMAO Notification profile installation completed.")
