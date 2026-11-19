import json
from pathlib import Path

import frappe


FIXTURE_FILES = [
    ("Client Script", "maintenance_client_script.json"),
    ("Server Script", "maintenance_server_script.json"),
]


def import_maintenance_fixtures():
    """
    Import Maintenance App GUI Client Scripts and Server Scripts
    after bench migrate.
    """
    from maintenance_app.notifications.install import (
        ensure_contact_applicant_field,
        copy_legacy_external_contact_role,
    )

    ensure_contact_applicant_field()
    copy_legacy_external_contact_role()
    # Future fresh installations: create the editable update Notification disabled.
    # Never replace administrator edits to an existing Notification.
    from maintenance_app.notifications.tech_mission import ensure_tm_updated_notification
    ensure_tm_updated_notification()


    fixtures_path = (
        Path(frappe.get_app_path("maintenance_app"))
        / "fixtures"
    )

    for doctype, filename in FIXTURE_FILES:
        file_path = fixtures_path / filename

        if not file_path.exists():
            print(
                f"Skipping {doctype}: fixture file not found: "
                f"{file_path}"
            )
            continue

        records = json.loads(
            file_path.read_text(encoding="utf-8")
        )

        imported = 0

        for record in records:
            name = record.get("name")

            if not name:
                continue

            if frappe.db.exists(doctype, name):
                doc = frappe.get_doc(doctype, name)

                doc.update(record)
                doc.flags.ignore_permissions = True
                doc.flags.ignore_validate_update_after_submit = True
                doc.save(ignore_permissions=True)
            else:
                doc = frappe.get_doc(record)

                doc.flags.ignore_permissions = True
                doc.insert(ignore_permissions=True)

            imported += 1

        print(
            f"Imported {imported} {doctype} record(s) "
            f"from {filename}"
        )

    frappe.clear_cache()
