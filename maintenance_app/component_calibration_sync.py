"""Synchronize calibration metadata from Equipment Component to its installed row(s).

Master Equipment Component is authoritative for Requires Calibration and Next Due.
Uses db.set_value on child rows to avoid saving a parent and recursive hooks.
"""
import frappe
from frappe.utils import cint

MASTER = "Equipment Component"
CHILD = "Installed Equipment Component"
PARENT = "Installed Equipment"


def _update_installed_row(row_name, flag, due_date):
    current = frappe.db.get_value(
        CHILD, row_name,
        ["custom_requires_calibration", "custom_next_calibration_date"],
        as_dict=True,
    )
    if current is None:
        return False
    data = {}
    if cint(current.custom_requires_calibration) != cint(flag):
        data["custom_requires_calibration"] = cint(flag)
    if (str(current.custom_next_calibration_date or "")
            != str(due_date or "")):
        data["custom_next_calibration_date"] = due_date or None
    if not data:
        return False
    frappe.db.set_value(CHILD, row_name, data, update_modified=False)
    return True


def on_component_update(doc, method=None):
    """After master save, update all its installed child row(s)."""
    if not doc.name:
        return
    if not frappe.get_meta(CHILD).has_field("custom_equipment_component"):
        return
    rows = frappe.get_all(
        CHILD,
        filters={"custom_equipment_component": doc.name},
        pluck="name",
        limit_page_length=0,
    )
    for row_name in rows:
        _update_installed_row(
            row_name,
            doc.get("custom_requires_calibration"),
            doc.get("custom_next_calibration_date"),
        )


def on_installed_equipment_validate(doc, method=None):
    """Populate new or changed installed rows before the parent is saved."""
    rows = doc.get("custom_installed_components") or []
    names = list({r.get("custom_equipment_component") for r in rows
                  if r.get("custom_equipment_component")})
    if not names:
        return
    data = frappe.get_all(
        MASTER,
        filters={"name": ["in", names]},
        fields=["name", "custom_requires_calibration", "custom_next_calibration_date"],
        limit_page_length=0,
    )
    by_name = {d.name: d for d in data}
    for row in rows:
        master_name = row.get("custom_equipment_component")
        if not master_name:
            continue
        master = by_name.get(master_name)
        if not master:
            frappe.throw("Installed component references missing Equipment Component: " + master_name)
        row.custom_requires_calibration = cint(master.custom_requires_calibration)
        row.custom_next_calibration_date = master.custom_next_calibration_date


def backfill_existing_rows():
    """Manually run once in bench console; returns sync counts, no commit."""
    scanned = updated = missing = 0
    rows = frappe.get_all(
        CHILD,
        filters={"custom_equipment_component": ["is", "set"]},
        fields=["name", "custom_equipment_component"],
        limit_page_length=0,
    )
    masters = {}
    for row in rows:
        scanned += 1
        name = row.custom_equipment_component
        if name not in masters:
            masters[name] = frappe.db.get_value(
                MASTER, name,
                ["custom_requires_calibration", "custom_next_calibration_date"],
                as_dict=True,
            )
        master = masters[name]
        if not master:
            missing += 1
            continue
        if _update_installed_row(row.name, master.custom_requires_calibration,
                                 master.custom_next_calibration_date):
            updated += 1
    return {"scanned": scanned, "updated": updated, "missing_masters": missing}
