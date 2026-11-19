"""Equipment Movement v2: no new Mission Intervention columns.

The movement document is authoritative for source/destination, and is applied
once from the existing MI primary action on_submit pipeline.
"""
import frappe
from frappe.utils import now_datetime

TYPES = ("Customer Branch", "Workshop", "Company Warehouse", "Customer Warehouse", "Other Location")
CONDITIONS = (
    "Operational",
    "Good",
    "Degraded",
    "Faulty",
    "Out of Service",
    "Awaiting Component",
    "Unknown",
)
DISPOSITIONS = ("Pending Assessment", "Repair", "Return to Service", "Keep for Spare Parts", "Propose Scrap", "Return to Customer")
CUSTODIANS = ("Customer", "Company", "Third Party")


def _mi(name, write=False):
    mi = frappe.get_doc("Mission Intervention", name)
    mi.check_permission("write" if write else "read")
    if write:
        if mi.docstatus != 0:
            frappe.throw("Only a draft intervention can have its movement edited.")
        if not mi.get("custom_start_time"):
            frappe.throw("Check in before recording an equipment movement.")
        if not mi.get("custom_asset"):
            frappe.throw("The MI must have an Installed Equipment.")
        if mi.get("custom_intervention_type") != "Asset Relocation":
            frappe.throw("Stage 1 supports Relocation as the main intervention only.")
        if mi.get("custom_primary_action") not in (None, "", "No Physical Change", "Equipment Relocation"):
            frappe.throw("This MI already has another primary equipment action.")
    return mi


def _one_movement(mi_name):
    names = frappe.get_all("Equipment Movement", filters={"custom_mission_intervention": mi_name},
                          pluck="name", order_by="creation asc", limit_page_length=3)
    if len(names) > 1:
        frappe.throw("Multiple equipment movements found for this MI. Resolve before proceeding.")
    return frappe.get_doc("Equipment Movement", names[0]) if names else None


def _reference(doc):
    t = doc.custom_destination_type
    return {
        "Customer Branch": doc.custom_destination_branch,
        "Workshop": doc.custom_destination_workshop,
        "Company Warehouse": doc.custom_destination_warehouse,
        "Customer Warehouse": doc.custom_destination_text,
        "Other Location": doc.custom_destination_text,
    }.get(t)


def _verify_destination(doc, equipment):
    t = doc.custom_destination_type
    if t not in TYPES:
        frappe.throw("Select a valid destination type.")
    ref = (_reference(doc) or "").strip()
    if not ref:
        frappe.throw("Specify the destination.")
    if t == "Customer Branch":
        branch = frappe.get_doc("Client Branch", ref)
        if branch.get("custom_parent_customer") != equipment.get("custom_parent_customer"):
            frappe.throw("Destination branch must belong to the equipment's current customer.")
    elif t == "Workshop":
        if not frappe.db.exists("Company Workshop", ref):
            frappe.throw("Selected workshop does not exist.")
    elif t == "Company Warehouse":
        if not frappe.db.exists("Warehouse", ref):
            frappe.throw("Selected warehouse does not exist.")
        if frappe.db.get_value("Warehouse", ref, "is_group"):
            frappe.throw("Select a leaf warehouse, not a warehouse group.")
        warehouse_company = frappe.db.get_value("Warehouse", ref, "company")
        ticket_company = frappe.db.get_value("Service Ticket", doc.custom_service_ticket, "custom_company") if doc.custom_service_ticket else None
        if ticket_company and warehouse_company and warehouse_company != ticket_company:
            frappe.throw("Warehouse company does not match the Service Ticket company.")
    if t == "Customer Branch" and doc.custom_custodian != "Customer":
        frappe.throw("Customer branch requires Customer custody.")
    if t in ("Workshop", "Company Warehouse") and doc.custom_custodian != "Company":
        frappe.throw("Company destinations require Company custody.")
    if doc.custom_custodian not in CUSTODIANS:
        frappe.throw("Select a valid custodian.")
    if doc.custom_condition and doc.custom_condition not in CONDITIONS:
        frappe.throw("Invalid condition.")
    if doc.custom_proposed_disposition and doc.custom_proposed_disposition not in DISPOSITIONS:
        frappe.throw("Invalid proposed disposition.")
    if not (doc.custom_reason or "").strip():
        frappe.throw("Movement reason is required.")
    return ref


@frappe.whitelist()
def get_movement_setup(mi_name):
    mi = _mi(mi_name)
    eq = frappe.get_doc("Installed Equipment", mi.custom_asset)
    movement = _one_movement(mi.name)
    branches = frappe.get_all("Client Branch", filters={"custom_parent_customer": eq.get("custom_parent_customer")},
                              fields=["name"], limit_page_length=500) if eq.get("custom_parent_customer") else []
    workshops = frappe.get_all("Company Workshop", fields=["name"], limit_page_length=200) if frappe.db.exists("DocType", "Company Workshop") else []
    warehouses = frappe.get_all("Warehouse", filters={"is_group": 0}, fields=["name","company"], limit_page_length=500)
    saved = {}
    if movement:
        for field in ("destination_type", "destination_branch", "destination_workshop", "destination_warehouse", "destination_text", "destination_detail", "custodian", "condition", "proposed_disposition", "reason"):
            saved[field] = movement.get("custom_"+field)
    return {"ok": True, "equipment": eq.name, "current_branch": eq.get("custom_branch"),
            "location_status": eq.get("custom_location_status"), "ownership": eq.get("custom_ownership"),
            "branches": branches, "workshops": workshops, "warehouses": warehouses,
            "saved": saved, "movement": movement.name if movement else None}


@frappe.whitelist()
def save_movement(mi_name, destination_type, destination=None, details=None, reason=None, condition=None, disposition=None, custodian=None):
    mi = _mi(mi_name, write=True)
    if destination_type not in TYPES:
        frappe.throw("Unknown destination type.")
    destination = (destination or "").strip()
    reason = (reason or "").strip()
    details = (details or "").strip()
    if not destination or not reason:
        frappe.throw("Destination and reason are mandatory.")
    if len(destination)>140 or len(details)>500 or len(reason)>1000:
        frappe.throw("Destination details are too long.")
    if condition and condition not in CONDITIONS or disposition and disposition not in DISPOSITIONS:
        frappe.throw("Invalid condition or proposed disposition.")
    if custodian not in CUSTODIANS:
        frappe.throw("Select a custodian.")
    eq = frappe.get_doc("Installed Equipment", mi.custom_asset)
    mov = _one_movement(mi.name)
    if mov and mov.custom_applied:
        frappe.throw("Movement already applied; it cannot be changed.")
    if not mov:
        mov = frappe.new_doc("Equipment Movement")
        mov.custom_mission_intervention = mi.name
        mov.custom_service_ticket = mi.get("custom_service_ticket")
        mov.custom_tech_mission = mi.get("custom_parent_mission")
        mov.custom_equipment = mi.custom_asset
        mov.custom_scope = "Complete Equipment"
        mov.custom_source_type = eq.get("custom_location_status") or ""
        mov.custom_source_reference = eq.get("custom_company_workshop") or eq.get("custom_branch") or ""
        mov.custom_source_branch = eq.get("custom_branch")
        mov.custom_source_site_id = eq.get("custom_site_id")
    elif mov.custom_equipment != mi.custom_asset:
        frappe.throw("The MI equipment was changed after movement creation. Review the movement.")
    mov.custom_destination_type = destination_type
    for f in ("custom_destination_branch", "custom_destination_workshop", "custom_destination_warehouse", "custom_destination_text"):
        mov.set(f, None)
    destfield = {"Customer Branch":"custom_destination_branch", "Workshop":"custom_destination_workshop", "Company Warehouse":"custom_destination_warehouse", "Customer Warehouse":"custom_destination_text", "Other Location":"custom_destination_text"}[destination_type]
    mov.set(destfield, destination)
    mov.custom_destination_detail = details
    mov.custom_reason = reason
    mov.custom_condition = condition or "Unknown"
    mov.custom_proposed_disposition = disposition or "Pending Assessment"
    mov.custom_custodian = custodian
    _verify_destination(mov, eq)
    mov.save(ignore_permissions=True) if not mov.is_new() else mov.insert(ignore_permissions=True)
    mi.custom_primary_action = "Equipment Relocation"
    mi.save(ignore_permissions=True)
    return {"ok":True,"movement":mov.name}


def validate_movement_before_mi_submit(mi):
    if mi.get("custom_primary_action") != "Equipment Relocation":
        return
    mov = _one_movement(mi.name)
    if mov:
        if mov.custom_equipment != mi.custom_asset:
            frappe.throw("Equipment Movement does not match the MI equipment.")
        _verify_destination(mov, frappe.get_doc("Installed Equipment", mi.custom_asset))
        return
    # Do not block older MIs that use the legacy destination fields.
    if mi.get("custom_new_branch") or mi.get("custom_destination_location_text"):
        return
    frappe.throw("Save the Equipment Movement before submitting the relocation MI.")


def apply_movement_for_mi(mi):
    """Called only by existing primary-action submit handler; idempotent."""
    mov = _one_movement(mi.name)
    if not mov:
        return False  # retain old relocation backend for legacy MIs
    if mov.custom_equipment != mi.custom_asset:
        frappe.throw("Equipment Movement does not match this MI.")
    if mi.get("custom_work_outcome") != "Work Completed":
        return False
    # Row lock protects concurrent retry after MI submission.
    row = frappe.db.sql("SELECT custom_applied FROM `tabEquipment Movement` WHERE name=%s FOR UPDATE", (mov.name,), as_dict=True)[0]
    if row.custom_applied:
        return True
    eq = frappe.get_doc("Installed Equipment", mi.custom_asset)
    ref = _verify_destination(mov, eq)
    if mov.custom_destination_type == "Customer Branch":
        branch = frappe.get_doc("Client Branch", ref)
        eq.custom_branch = ref
        eq.custom_site_id = branch.get("custom_site_id") if branch.meta.has_field("custom_site_id") else None
        eq.custom_company_workshop = None
        eq.custom_location_status = "Client Site"
    elif mov.custom_destination_type == "Workshop":
        eq.custom_branch = None
        eq.custom_site_id = None
        eq.custom_company_workshop = ref
        eq.custom_location_status = "Workshop"
    else:
        eq.custom_branch = None
        eq.custom_site_id = None
        eq.custom_company_workshop = None
        # The full warehouse/customer storage address remains on Equipment Movement.
        eq.custom_location_status = "Warehouse" if mov.custom_destination_type in ("Company Warehouse", "Customer Warehouse") else "In Transit"
    # Do not change ownership, condition, status, or disposal status here.
    eq.save(ignore_permissions=True)
    log = frappe.new_doc("Asset Lifecycle Log")
    values = {
        "custom_customer": eq.get("custom_parent_customer"),
        "custom_branch": mov.custom_source_branch,
        "custom_related_asset": eq.name,
        "custom_date": now_datetime(),
        "custom_event": "Relocated",
        "custom_event_source": "Intervention",
        "custom_previous_branch": mov.custom_source_branch,
        "custom_previous_site_id": mov.custom_source_site_id,
        "custom_new_branch": mov.custom_destination_branch,
        "custom_new_site_id": eq.get("custom_site_id"),
        "custom_service_ticket": mi.get("custom_service_ticket"),
        "custom_mission_ref": mi.get("custom_parent_mission"),
        "custom_intervention_ref": mi.name,
        "custom_asset_change_reason": mov.custom_reason,
        "custom_action_taken": ("Relocated from {0}: {1} to {2}: {3}. Custody: {4}. Condition: {5}. Proposed disposition: {6}. Position: {7}. Reason: {8}").format(
             mov.custom_source_type or "Unknown",mov.custom_source_reference or "-",mov.custom_destination_type,ref,
             mov.custom_custodian,mov.custom_condition or "Unknown",mov.custom_proposed_disposition or "Pending Assessment",
             mov.custom_destination_detail or "-",mov.custom_reason)
    }
    for field, value in values.items():
        if log.meta.has_field(field): log.set(field,value)
    log.insert(ignore_permissions=True)
    if log.docstatus == 0: log.submit()
    frappe.db.set_value("Equipment Movement",mov.name,{"custom_applied":1,"custom_applied_at":now_datetime(),"custom_lifecycle_log":log.name},update_modified=False)
    return True


def cleanup_failed_stage1_field():
    """Remove *only* orphan metadata created by the failed MI schema alteration.

    No existing MI values are touched. The previous destination-type field is
    deliberately retained because it has a real backing column.
    """
    dt = "Mission Intervention"
    fieldname = "custom_relocation_warehouse"
    row = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
    if not row:
        return "No orphan Custom Field metadata found."
    if frappe.db.has_column(dt, fieldname):
        frappe.throw("STOP: The warehouse column exists. No cleanup performed.")
    # A failed CREATE COLUMN left metadata but no actual column. Deleting just
    # the metadata avoids another table rebuild on the oversized MI table.
    frappe.db.delete("Custom Field", {"name": row})
    frappe.clear_cache(doctype=dt)
    frappe.db.commit()
    return "Removed orphan Custom Field metadata: " + row
