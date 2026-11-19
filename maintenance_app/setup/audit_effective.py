"""Read-only maintenance_app audit v2: scan BOTH DocField and Custom Field.

Use: bench --site dev.local execute maintenance_app.setup.audit_effective.export_effective_custom_field_audit
Only produces reports under /tmp. It does not approve or install any field.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import gettempdir

import frappe
from maintenance_app.setup.audit import FIELD_PROPERTIES, _owned_documents, _source_references


def _candidate(df, previous_name):
    props = {}
    for p in FIELD_PROPERTIES:
        value = df.get(p)
        if value is None:
            continue
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        props[p] = value
    # DocField has an order (idx) but not insert_after. Convert the effective
    # position into the Custom Field install mechanism's insert_after anchor.
    if not props.get("insert_after") and previous_name:
        props["insert_after"] = previous_name
    return props


def export_effective_custom_field_audit(output_dir=None):
    """Read-only audit of all exact custom_ fields on non-app-owned DocTypes."""
    root = Path(frappe.get_app_path("maintenance_app"))
    owned, _ = _owned_documents(root)
    refs = _source_references(root)
    site = str(getattr(frappe.local, "site", "site") or "site").replace("/", "_")
    folder = Path(output_dir) if output_dir else Path(gettempdir()) / ("maintenance_app_effective_fields_" + site)
    folder.mkdir(parents=True, exist_ok=True)

    # MySQL / MariaDB: LEFT avoids interpreting '_' as SQL LIKE wildcard.
    native_rows = frappe.db.sql(
        """SELECT parent AS dt, fieldname, label, fieldtype, options, idx
           FROM `tabDocField`
           WHERE LEFT(fieldname, 7) = 'custom_'
           ORDER BY parent, idx""", as_dict=True
    )
    custom_rows = [
        row for row in frappe.get_all(
            "Custom Field", fields=["dt", "fieldname", "label", "fieldtype", "options", "idx", "insert_after"],
            limit_page_length=0
        )
        if str(row.get("fieldname") or "").startswith("custom_")
    ]
    docfield_lookup = {(r.dt, r.fieldname): r for r in native_rows}
    custom_lookup = {(r.dt, r.fieldname): r for r in custom_rows}
    keys = sorted(set(docfield_lookup) | set(custom_lookup))
    candidates = defaultdict(list)
    report = []
    errors = []
    field_types = Counter()
    source_counts = Counter()

    docnames = {r.name: r.module for r in frappe.get_all("DocType", fields=["name", "module"], limit_page_length=0)}
    by_dt = defaultdict(list)
    for dt, fieldname in keys:
        by_dt[dt].append(fieldname)

    for dt, names in sorted(by_dt.items()):
        if dt in owned:
            source_counts["app_owned_excluded"] += len(names)
            continue
        try:
            meta = frappe.get_meta(dt, cached=False)
        except Exception as exc:
            errors.append({"doctype": dt, "error": str(exc)})
            continue
        position = {f.fieldname: i for i, f in enumerate(meta.fields) if f.fieldname}
        for fieldname in names:
            native = docfield_lookup.get((dt, fieldname))
            custom = custom_lookup.get((dt, fieldname))
            source = ("both" if native and custom else ("DocField" if native else "Custom Field"))
            source_counts[source] += 1
            df = meta.get_field(fieldname)
            if not df:
                errors.append({"doctype": dt, "fieldname": fieldname, "error": "Field record exists but effective meta did not include it"})
                continue
            i = position.get(fieldname, -1)
            before = meta.fields[i - 1].fieldname if i > 0 else None
            definition = _candidate(df, before)
            if not definition.get("fieldname"):
                definition["fieldname"] = fieldname
            if not definition.get("label"):
                definition["label"] = native.label if native else custom.label
            if not definition.get("fieldtype"):
                definition["fieldtype"] = native.fieldtype if native else custom.fieldtype
            candidates[dt].append(definition)
            field_types[definition["fieldtype"]] += 1
            report.append({
                "doctype": dt,
                "doctype_module": docnames.get(dt),
                "fieldname": fieldname,
                "label": definition.get("label"),
                "fieldtype": definition.get("fieldtype"),
                "options": definition.get("options"),
                "insert_after": definition.get("insert_after"),
                "origin": source,
                "custom_field_db_record": bool(custom),
                "docfield_db_record": bool(native),
                "referenced_by_maintenance_app": bool(refs.get(fieldname)),
                "source_code_samples": refs.get(fieldname, [])[:4],
                "candidate_requires_review": True,
            })

    def save_json(filename, data):
        (folder / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    # Include the three Contact fields specifically so we can identify their
    # provenance even if metadata is being augmented beyond the two DB tables.
    contact_check = []
    for name in (
        "custom_allow_as_service_applicant",
        "custom_allow_as_external_contact",
        "custom_contact_scope",
    ):
        f = frappe.get_meta("Contact", cached=False).get_field(name)
        contact_check.append({
            "fieldname": name,
            "in_effective_meta": bool(f),
            "in_tabDocField": ("Contact", name) in docfield_lookup,
            "in_tabCustom_Field": ("Contact", name) in custom_lookup,
            "fieldtype": f.get("fieldtype") if f else None,
            "options": f.get("options") if f else None,
        })

    all_candidates = dict(sorted(candidates.items()))
    save_json("all_standard_field_candidates_REVIEW.json", all_candidates)
    save_json("field_origins_REVIEW.json", report)
    save_json("contact_field_origins.json", contact_check)
    save_json("read_errors.json", errors)
    summary = {
        "site": site,
        "standard_custom_prefix_fields_found": len(report),
        "origin_counts": dict(source_counts),
        "doctype_counts": dict(Counter(row["doctype"] for row in report)),
        "contact_field_origins": contact_check,
        "read_errors": len(errors),
        "important": "REVIEW ONLY: Do not copy all candidate fields into the install manifest automatically. Some may belong to other apps.",
    }
    save_json("summary_v2.json", summary)
    with (folder / "field_origins_REVIEW.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "doctype", "doctype_module", "fieldname", "label", "fieldtype", "options",
            "insert_after", "origin", "custom_field_db_record", "docfield_db_record",
            "referenced_by_maintenance_app", "source_code_samples", "candidate_requires_review",
        ])
        writer.writeheader()
        for row in report:
            writer.writerow({**row, "source_code_samples": "; ".join(row["source_code_samples"])})
    print(json.dumps(summary, indent=2, default=str))
    print("Audit complete: NO database or application files changed by this function.")
    print("Reports:", folder)
    return str(folder)
