"""Version-safe Custom Field registration for maintenance_app.

Our own DocTypes belong in their regular DocType JSON files. Only fields on
other apps' DocTypes belong in setup/custom_fields.json. Existing custom fields
are NOT overwritten by default. The manifest is audited on dev.local and
committed to Git; no runtime field discovery is performed on fresh sites.
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _manifest_path():
    return Path(__file__).with_name("custom_fields.json")


def _load_manifest():
    data = json.loads(_manifest_path().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Custom Field manifest must be a {DocType: [fields]} object")
    seen = set()
    for dt, fields in data.items():
        if not isinstance(dt, str) or not dt:
            raise ValueError("Invalid DocType in field manifest")
        if not isinstance(fields, list):
            raise ValueError(f"Custom fields for {dt} must be a list")
        for f in fields:
            if not isinstance(f, dict):
                raise ValueError(f"Invalid field on {dt}")
            name = f.get("fieldname", "")
            if not name.startswith("custom_") or not f.get("fieldtype"):
                raise ValueError(f"Invalid field declaration: {dt}.{name}")
            if (dt, name) in seen:
                raise ValueError(f"Duplicate field declaration: {dt}.{name}")
            seen.add((dt, name))
    return data


def _owned_doctypes():
    """Identify app-owned DocTypes by their shipped JSON, not module labels."""
    app_path = Path(frappe.get_app_path("maintenance_app"))
    path = app_path / "maintenance_app" / "doctype"
    names = set()
    if path.is_dir():
        for file in path.glob("*/*.json"):
            try:
                doc = json.loads(file.read_text(encoding="utf-8"))
                if doc.get("doctype") == "DocType" and doc.get("name"):
                    names.add(doc["name"])
                elif doc.get("name") and doc.get("fields") is not None:
                    names.add(doc["name"])
            except (ValueError, OSError):
                continue
    return names


def _ordered_fields(dt, fields):
    """Allow insert_after to refer to other manifest fields on the same DocType."""
    remaining = list(fields)
    ordered = []
    while remaining:
        pending_names = {f["fieldname"] for f in remaining}
        ready = [f for f in remaining if f.get("insert_after") not in pending_names]
        if not ready:
            raise ValueError(f"Circular insert_after dependency on {dt}")
        ordered.extend(ready)
        ready_names = {f["fieldname"] for f in ready}
        remaining = [f for f in remaining if f["fieldname"] not in ready_names]
    return ordered


def _existing_definition(dt, name):
    return frappe.db.get_value(
        "Custom Field", {"dt": dt, "fieldname": name},
        ["name", "fieldtype", "options"], as_dict=True
    )


def _inventory():
    registry = _load_manifest()
    owned = _owned_doctypes()
    pending = defaultdict(list)
    report = {"missing": [], "existing": [], "provided_by_doctype": [], "mismatch": [], "skipped": []}
    for dt, fields in registry.items():
        if dt in owned:
            raise ValueError(
                f"{dt} belongs to maintenance_app. Define its fields in DocType JSON, "
                "or explicitly review a migration exception."
            )
        if not frappe.db.exists("DocType", dt):
            report["skipped"].append(f"{dt}: DocType not installed")
            continue
        declared_names = {f["fieldname"] for f in fields}
        for f in _ordered_fields(dt, fields):
            field = _existing_definition(dt, f["fieldname"])
            key = f'{dt}.{f["fieldname"]}'
            if field:
                report["existing"].append(key)
                if (field.fieldtype or "") != (f.get("fieldtype") or "") or (
                    (field.options or "") != (f.get("options") or "")
                ):
                    report["mismatch"].append({
                        "field": key,
                        "existing_type": field.fieldtype,
                        "expected_type": f["fieldtype"],
                        "existing_options": field.options or "",
                        "expected_options": f.get("options") or "",
                    })
                continue
            # A field may be present as a regular DocField (tabDocField),
            # rather than a Custom Field (tabCustom Field). This happens on
            # existing customized sites. Creating a second field with the same
            # fieldname would be unsafe. Leave it untouched and report its source.
            meta_field = frappe.get_meta(dt).get_field(f["fieldname"])
            if meta_field:
                report["provided_by_doctype"].append(key)
                actual_type = meta_field.get("fieldtype") or ""
                actual_options = meta_field.get("options") or ""
                expected_options = f.get("options") or ""
                if actual_type != (f.get("fieldtype") or "") or actual_options != expected_options:
                    report["mismatch"].append({
                        "field": key,
                        "source": "DocField / effective Meta (not Custom Field)",
                        "existing_type": actual_type,
                        "expected_type": f.get("fieldtype") or "",
                        "existing_options": actual_options,
                        "expected_options": expected_options,
                    })
                continue
            anchor = f.get("insert_after")
            candidate = dict(f)
            # GMAO-v4 missing layout-anchor fallback (source-managed)
            # ERPNext v16 deployments may lack legacy/UI-only anchor fields.
            # Preserve the audited position wherever it exists. Otherwise,
            # append ONLY this missing field, preserving its name and data.
            if anchor and anchor != "append" and anchor not in declared_names:
                if not frappe.get_meta(dt).get_field(anchor):
                    candidate["insert_after"] = "append"
                    report.setdefault("anchor_fallbacks", []).append({
                        "field": key,
                        "requested_anchor": anchor,
                        "fallback": "append",
                    })
            pending[dt].append(candidate)
            report["missing"].append(key)
    return dict(pending), report


def verify_custom_fields():
    """Read-only inventory. Run via bench execute before/after migrate."""
    _, report = _inventory()
    print(json.dumps(report, indent=2))
    return report


def install_custom_fields():
    """Create missing fields only. Never delete or alter existing fields/data.

    In Frappe v16 create_custom_fields(..., update=True) will update existing
    records. We intentionally use update=False to protect site overrides.
    Manage any required field migration separately after reviewing differences.
    """
    pending, report = _inventory()
    for conflict in report["mismatch"]:
        print("CUSTOM FIELD DEFINITION DIFFERS (left unchanged):", conflict)
    for warning in report["skipped"]:
        print("CUSTOM FIELD SKIPPED:", warning)
    if pending:
        create_custom_fields(pending, update=False)
    print(
        "maintenance_app custom fields: ",
        len(report["missing"]), "created;",
        len(report["existing"]), "Custom Field records already existed;",
        len(report["provided_by_doctype"]), "already provided by DocType metadata;",
        len(report["mismatch"]), "definition differences;",
        len(report["skipped"]), "skipped doctypes."
    )
    return report


def _call_previous_hook(path):
    if path and path not in (
        "maintenance_app.setup.install.after_install",
        "maintenance_app.setup.install.after_migrate",
    ):
        frappe.get_attr(path)()


def after_install():
    """Preserve the original install hook, then install app-owned extensions."""
    from maintenance_app.setup.legacy_hooks import PREVIOUS_AFTER_INSTALL
    # The old notification install hook only created the Contact Applicant
    # checkbox, which is now defined centrally in custom_fields.json.
    if PREVIOUS_AFTER_INSTALL != (
        "maintenance_app.notifications.install.ensure_contact_applicant_field"
    ):
        _call_previous_hook(PREVIOUS_AFTER_INSTALL)
    from maintenance_app.setup.relocation_git.install import (
        install_relocation_configuration,
    )
    install_relocation_configuration()
    install_custom_fields()
    # Existing app-owned Custom Field records are handled as a separate,
    # non-destructive compatibility exception until explicitly migrated.
    from maintenance_app.setup.owned_fields import install_owned_custom_fields
    install_owned_custom_fields()
    # Create only missing, DISABLED notification records; respect administrator edits.
    from maintenance_app.notifications.service_ticket import ensure_st_status_notifications
    ensure_st_status_notifications()


def after_migrate():
    """Ensure fields exist before importing current GUI Script fixtures."""
    from maintenance_app.setup.legacy_hooks import PREVIOUS_AFTER_MIGRATE
    from maintenance_app.setup.relocation_git.install import (
        install_relocation_configuration,
    )
    install_relocation_configuration()
    install_custom_fields()
    # Existing app-owned Custom Field records are handled as a separate,
    # non-destructive compatibility exception until explicitly migrated.
    from maintenance_app.setup.owned_fields import install_owned_custom_fields
    install_owned_custom_fields()
    # Create only missing, DISABLED notification records; respect administrator edits.
    from maintenance_app.notifications.service_ticket import ensure_st_status_notifications
    ensure_st_status_notifications()
    _call_previous_hook(PREVIOUS_AFTER_MIGRATE)
