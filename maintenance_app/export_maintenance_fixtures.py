import json
from pathlib import Path

import frappe


MODULE_NAME = "Maintenance App"


def export_maintenance_fixtures():
    app_path = Path(
        frappe.get_app_path("maintenance_app")
    )

    fixtures_path = app_path / "fixtures"
    fixtures_path.mkdir(parents=True, exist_ok=True)

    maintenance_doctypes = frappe.get_all(
        "DocType",
        filters={
            "module": MODULE_NAME
        },
        pluck="name"
    )

    maintenance_doctypes = sorted(
        set(maintenance_doctypes)
    )

    export_client_scripts(
        fixtures_path,
        maintenance_doctypes
    )

    export_server_scripts(
        fixtures_path,
        maintenance_doctypes
    )

    print(
        "Exported Maintenance App scripts for "
        f"{len(maintenance_doctypes)} DocTypes."
    )


def export_client_scripts(
    fixtures_path,
    maintenance_doctypes
):
    records = []

    if maintenance_doctypes:
        names = frappe.get_all(
            "Client Script",
            filters={
                "dt": ["in", maintenance_doctypes]
            },
            pluck="name"
        )

        for name in names:
            doc = frappe.get_doc(
                "Client Script",
                name
            )

            records.append(
                clean_document(doc)
            )

    write_json(
        fixtures_path / "maintenance_client_script.json",
        records
    )


def export_server_scripts(
    fixtures_path,
    maintenance_doctypes
):
    records = []

    if maintenance_doctypes:
        names = frappe.get_all(
            "Server Script",
            filters={
                "reference_doctype": [
                    "in",
                    maintenance_doctypes
                ]
            },
            pluck="name"
        )

        for name in names:
            doc = frappe.get_doc(
                "Server Script",
                name
            )

            records.append(
                clean_document(doc)
            )

    write_json(
        fixtures_path / "maintenance_server_script.json",
        records
    )


def clean_document(doc):
    data = doc.as_dict(
        no_nulls=False
    )

    excluded_fields = {
        "creation",
        "modified",
        "modified_by",
        "owner",
        "docstatus",
        "idx",
        "_user_tags",
        "_comments",
        "_assign",
        "_liked_by",
        "_seen"
    }

    for fieldname in excluded_fields:
        data.pop(fieldname, None)

    return data


def write_json(path, records):
    path.write_text(
        json.dumps(
            records,
            indent=2,
            ensure_ascii=False,
            default=str
        )
        + "\n",
        encoding="utf-8"
    )

    print(
        f"Exported {len(records)} records to {path}"
    )
