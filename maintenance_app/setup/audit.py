"""Read-only live-site Custom Field audit for maintenance_app.

Call through `bench --site dev.local execute maintenance_app.setup.audit.export_custom_field_audit`.
Outputs are *proposals*, not installed fields. Review the JSON and CSV before
replacing setup/custom_fields.json and committing to Git.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import re
import tempfile

import frappe


# Metadata needed for repeatable installation. Do NOT export user/business data,
# passwords, audit history, owners or names from Custom Field records.
FIELD_PROPERTIES = (
    "fieldname", "label", "fieldtype", "options", "default", "insert_after",
    "description", "depends_on", "mandatory_depends_on", "read_only_depends_on",
    "fetch_from", "fetch_if_empty", "reqd", "read_only", "hidden", "no_copy",
    "allow_on_submit", "allow_in_quick_entry", "in_list_view", "in_standard_filter",
    "in_global_search", "in_preview", "in_import_template", "search_index",
    "bold", "collapsible", "collapsible_depends_on", "columns", "width", "length",
    "precision", "unique", "permlevel", "print_hide", "print_hide_if_no_value",
    "print_width", "report_hide", "translatable", "show_dashboard", "placeholder",
    "ignore_user_permissions", "ignore_xss_filter", "sort_options", "non_negative",
    "link_filters", "is_virtual", "max_value", "min_value",
)


def _owned_documents(app_root):
    owned, fields = set(), defaultdict(set)
    location = app_root / "maintenance_app" / "doctype"
    if not location.exists():
        return owned, fields
    for filename in location.glob("*/*.json"):
        try:
            entry = json.loads(filename.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        dt = entry.get("name")
        if not dt or not isinstance(entry.get("fields"), list):
            continue
        owned.add(dt)
        for df in entry["fields"]:
            if df.get("fieldname"):
                fields[dt].add(df["fieldname"])
    return owned, fields


def _source_references(root):
    refs = defaultdict(list)
    regex = re.compile(r"\bcustom_[a-zA-Z0-9_]+\b")
    allowed = {".py", ".js", ".html", ".json", ".jinja", ".txt"}
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in allowed:
            continue
        parts = set(f.relative_to(root).parts)
        if parts.intersection({"fixtures", "__pycache__", ".git", "setup"}):
            continue
        if f.name in ("apiold.py", "hooks.md"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in set(regex.findall(text)):
            refs[name].append(str(f.relative_to(root)))
    return refs


def _cleanup_properties(cf):
    result = {}
    for p in FIELD_PROPERTIES:
        value = cf.get(p)
        if value is None:
            continue
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        result[p] = value
    return result


def export_custom_field_audit(output_dir=None):
    """Audit all exact custom_* fields; never modify site DB or source.

    By default writes reports under /tmp/maintenance_app_field_audit_<site>.
    Keeps all standard-DocType candidates (including unreferenced) for human
    review, and flags custom fields attached to app-owned DocTypes.
    """
    root = Path(frappe.get_app_path("maintenance_app"))
    own_dt, own_df = _owned_documents(root)
    refs = _source_references(root)
    site = (getattr(frappe.local, "site", None) or "site").replace("/", "_")
    directory = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / ("maintenance_app_field_audit_" + site)
    directory.mkdir(parents=True, exist_ok=True)

    # Capture *all* Custom Field records, then exact-prefix filter in Python.
    # SQL LIKE 'custom_%' would treat '_' as a wildcard without escaping.
    cf_rows = frappe.get_all(
        "Custom Field", fields=["*"], order_by="dt asc, idx asc",
        limit_page_length=0,
    )
    all_records = []
    manifest = defaultdict(list)
    on_own = []
    non_custom_prefix = []
    seen = set()
    for cf in cf_rows:
        if not str(cf.get("fieldname") or "").startswith("custom_"):
            non_custom_prefix.append({"doctype": cf.get("dt"), "fieldname": cf.get("fieldname")})
            continue
        dt, name = cf.get("dt"), cf.get("fieldname")
        if not dt or not name or (dt, name) in seen:
            continue
        seen.add((dt, name))
        properties = _cleanup_properties(cf)
        files = refs.get(name, [])
        entry = {
            "doctype": dt,
            "fieldname": name,
            "fieldtype": cf.get("fieldtype"),
            "label": cf.get("label"),
            "options": cf.get("options"),
            "insert_after": cf.get("insert_after"),
            "referenced_in_source": bool(files),
            "source_files_sample": files[:5],
            "belongs_to_app_doctype": dt in own_dt,
            "already_in_app_doctype_json": name in own_df.get(dt, set()),
        }
        all_records.append(entry)
        if dt in own_dt:
            on_own.append({**entry, "metadata": properties})
        else:
            manifest[dt].append(properties)

    rows = sorted(all_records, key=lambda r: (r["doctype"], r["fieldname"]))
    manifest = dict(sorted(manifest.items()))
    by_dt = Counter(row["doctype"] for row in rows if not row["belongs_to_app_doctype"])
    suspicious = [x for x in rows if not x["referenced_in_source"] and not x["belongs_to_app_doctype"]]

    def save_json(filename, data):
        (directory / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    save_json("candidate_standard_custom_fields_REVIEW.json", manifest)
    save_json("app_owned_custom_fields_REVIEW.json", on_own)
    save_json("all_custom_fields_audit.json", rows)
    save_json("other_non_custom_prefix_custom_fields_REVIEW.json", non_custom_prefix)

    # Effective field metadata can also be affected by Property Setters. Record
    # them explicitly rather than silently applying unrelated site overrides.
    target_dt = set(manifest)
    pset_rows = frappe.get_all("Property Setter", fields=["*"], limit_page_length=0)
    property_setters = [
        {
            "doctype": p.get("doc_type"),
            "fieldname": p.get("field_name"),
            "property": p.get("property"),
            "value": p.get("value"),
            "property_type": p.get("property_type"),
        }
        for p in pset_rows
        if p.get("doc_type") in target_dt and (
            str(p.get("field_name") or "").startswith("custom_")
            or not p.get("field_name")
        )
    ]
    save_json("standard_property_setters_REVIEW.json", property_setters)
    summary = {
        "source": site,
        "source_root": str(root),
        "number_of_app_owned_doctypes": len(own_dt),
        "custom_prefix_standard_field_count": sum(by_dt.values()),
        "custom_prefix_app_owned_extra_record_count": len(on_own),
        "standard_doctype_counts": dict(sorted(by_dt.items())),
        "unreferenced_standard_candidates_need_review": len(suspicious),
        "other_non_prefix_custom_fields": len(non_custom_prefix),
        "relevant_property_setters_need_review": len(property_setters),
        "important": "Candidates are not automatically approved. Exclude fields owned by unrelated apps. App-owned fields in this report need separate JSON reconciliation.",
    }
    save_json("summary.json", summary)
    with (directory / "custom_fields_audit.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "doctype", "fieldname", "fieldtype", "label", "options", "insert_after",
            "referenced_in_source", "belongs_to_app_doctype", "already_in_app_doctype_json", "source_files_sample"
        ])
        writer.writeheader()
        for r in rows:
            r = {**r, "source_files_sample": "; ".join(r["source_files_sample"])}
            writer.writerow(r)
    print(json.dumps(summary, indent=2))
    print("Audit only. NO Custom Field records or source files modified.")
    print("Reports:", directory)
    return str(directory)


def check_imported_script_drift():
    """Read-only: identify DB Client/Server Scripts a migration could overwrite."""
    root = Path(frappe.get_app_path("maintenance_app")) / "fixtures"
    files = (
        ("Client Script", "maintenance_client_script.json"),
        ("Server Script", "maintenance_server_script.json"),
    )
    differences = []
    for dt, filename in files:
        path = root / filename
        if not path.is_file():
            print("No fixture:", path)
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            name = item.get("name")
            if not name:
                continue
            existing = frappe.db.get_value(dt, name, "script")
            if existing is None:
                continue
            normalize = lambda x: (x or "").replace("\r\n", "\n").strip()
            if normalize(existing) != normalize(item.get("script")):
                differences.append(f"{dt}: {name}")
    if differences:
        print("STOP: Current DB scripts differ from migration fixture:")
        for item in differences:
            print("  -", item)
        print("Reconcile the fixture with current database scripts before bench migrate.")
    else:
        print("PASS: No Client/Server Script differences identified.")
    return differences
