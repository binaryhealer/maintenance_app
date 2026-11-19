"""Read-only audit of Custom Fields attached to maintenance_app-owned DocTypes.

Discovers both standard and nested app DocType JSON directories. It does not
modify Frappe records, DocType JSON, the install manifest, or hooks.
"""
from __future__ import annotations

import json
from pathlib import Path

import frappe


FIELD_PROPERTIES = (
    "fieldname", "label", "fieldtype", "options", "default", "description",
    "insert_after", "depends_on", "mandatory_depends_on", "read_only_depends_on",
    "fetch_from", "fetch_if_empty", "reqd", "read_only", "hidden", "no_copy",
    "allow_on_submit", "in_list_view", "in_standard_filter", "in_global_search",
    "in_preview", "unique", "permlevel", "print_hide", "collapsible",
    "collapsible_depends_on", "columns", "length", "translatable",
)


def find_app_doctype_jsons(app_root: Path) -> dict:
    """Return all app-owned DocType JSON definitions, including nested packages."""
    definitions = {}
    for path in sorted(app_root.rglob("doctype/*/*.json")):
        # Ignore unrelated JSON files and non-conventional paths.
        if path.stem != path.parent.name:
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if schema.get("doctype") != "DocType" or not schema.get("name"):
            continue
        if not isinstance(schema.get("fields"), list):
            continue
        name = schema["name"]
        definitions.setdefault(name, []).append({
            "path": str(path),
            "fields": {row["fieldname"]: row for row in schema["fields"]
                       if isinstance(row, dict) and row.get("fieldname")},
        })
    return definitions


def audit_owned_extras():
    app_root = Path(frappe.get_app_path("maintenance_app")).resolve()
    definitions = find_app_doctype_jsons(app_root)
    if not definitions:
        raise RuntimeError(
            f"No maintenance_app-owned DocType JSON definitions found under {app_root}"
        )

    records = frappe.get_all(
        "Custom Field",
        filters={"dt": ["in", sorted(definitions)]},
        fields=["name", "dt", "fieldname"],
        order_by="dt asc, fieldname asc",
        limit_page_length=10000,
    )

    items = []
    for row in records:
        doc = frappe.get_doc("Custom Field", row.name)
        source_paths = definitions[row.dt]
        canonical = min(source_paths, key=lambda p: (len(Path(p["path"]).parts), p["path"]))
        present = [p for p in source_paths if row.fieldname in p["fields"]]
        items.append({
            "doctype": row.dt,
            "fieldname": row.fieldname,
            "custom_field_record": row.name,
            "metadata": {name: doc.get(name) for name in FIELD_PROPERTIES if doc.get(name) is not None},
            "canonical_doctype_json": canonical["path"],
            "in_canonical_json": row.fieldname in canonical["fields"],
            "in_any_json": bool(present),
            "present_in_json_paths": [p["path"] for p in present],
            "other_json_paths": [p["path"] for p in source_paths if p not in present],
            "json_field_definitions": [
                {"source": p["path"], "field": p["fields"][row.fieldname]}
                for p in present
            ],
        })

    duplicate_jsons = {
        name: [item["path"] for item in entries]
        for name, entries in definitions.items() if len(entries) > 1
    }
    duplicate_field_differences = {}
    for name, entries in definitions.items():
        if len(entries) < 2:
            continue
        shared_fields = set.intersection(*(set(p["fields"]) for p in entries))
        differing = [fn for fn in sorted(shared_fields)
                     if any(p["fields"][fn] != entries[0]["fields"][fn] for p in entries[1:])]
        if differing:
            duplicate_field_differences[name] = differing

    missing = [f"{r['doctype']}.{r['fieldname']}" for r in items if not r["in_any_json"]]
    noncanonical = [f"{r['doctype']}.{r['fieldname']}" for r in items
                    if r["in_any_json"] and not r["in_canonical_json"]]
    report = {
        "site": frappe.local.site,
        "app_root": str(app_root),
        "app_owned_doctypes": len(definitions),
        "source_json_files": sum(len(v) for v in definitions.values()),
        "custom_field_records_on_app_doctypes": len(items),
        "records_missing_from_all_source_json": missing,
        "records_in_noncanonical_json_only": noncanonical,
        "duplicate_doctype_jsons_needing_review": duplicate_jsons,
        "duplicate_json_field_differences": duplicate_field_differences,
        "changed_database": False,
        "records": items,
    }
    safe_site = str(frappe.local.site).replace("/", "_")
    outfile = Path("/tmp") / f"maintenance_app_owned_extras_v5_{safe_site}.json"
    outfile.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "records"}
    summary["report_file"] = str(outfile)
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return summary
