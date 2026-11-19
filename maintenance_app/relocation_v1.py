"""Whole-equipment relocation v1 for maintenance_app.

Only used by MI Primary Action = Equipment Relocation when the MI has an
explicit custom_relocation_destination_type. Other existing actions unchanged.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

DESTINATIONS = ("Customer Branch", "Workshop", "Company Warehouse", "Customer Warehouse", "Other Location")
DISPOSITIONS = ("Pending Assessment", "Repair", "Return to Service", "Keep for Spare Parts", "Propose Scrap", "Return to Customer")
CONDITIONS = (
    "Operational",
    "Good",
    "Degraded",
    "Faulty",
    "Out of Service",
    "Awaiting Component",
    "Unknown",
)
CUSTODIANS = ("Customer", "Company", "Third Party")


def _custom_field(doctype, name, label, fieldtype, options=None):
    return {"fieldname": name, "label": label, "fieldtype": fieldtype,
            "options": options or "", "insert_after": "custom_asset_change_reason" if doctype == "Mission Intervention" else None}


def ensure_relocation_fields():
    """Run once during installation with bench --site ... execute ..."""
    defs = {
        "Mission Intervention": [
            _custom_field("Mission Intervention", "custom_relocation_destination_type", "Relocation Destination Type", "Select", "\n".join(("",) + DESTINATIONS)),
            _custom_field("Mission Intervention", "custom_relocation_warehouse", "Relocation Warehouse", "Link", "Warehouse"),
            _custom_field("Mission Intervention", "custom_relocation_details", "Relocation Position / Location Details", "Data"),
            _custom_field("Mission Intervention", "custom_relocation_condition", "Condition at Movement", "Select", "\n".join(("",) + CONDITIONS)),
            _custom_field("Mission Intervention", "custom_relocation_disposition", "Proposed Equipment Disposition", "Select", "\n".join(("",) + DISPOSITIONS)),
            _custom_field("Mission Intervention", "custom_relocation_custodian", "Destination Custodian", "Select", "\n".join(("",) + CUSTODIANS)),
        ],
        "Installed Equipment": [
            {"fieldname": "custom_relocation_location_reference", "label": "Current Storage/Location Reference", "fieldtype": "Data", "insert_after": "custom_location_status"},
            {"fieldname": "custom_relocation_location_detail", "label": "Current Location Detail", "fieldtype": "Data", "insert_after": "custom_relocation_location_reference"},
            {"fieldname": "custom_relocation_custodian", "label": "Current Custodian", "fieldtype": "Select", "options": "\n".join(("",) + CUSTODIANS), "insert_after": "custom_relocation_location_detail"},
        ],
        "Asset Lifecycle Log": [
            {"fieldname": "custom_relocation_origin_type", "label": "Previous Location Type", "fieldtype": "Data", "insert_after": "custom_previous_branch"},
            {"fieldname": "custom_relocation_destination_type", "label": "Destination Location Type", "fieldtype": "Data", "insert_after": "custom_new_branch"},
            {"fieldname": "custom_relocation_location_reference", "label": "Destination Reference", "fieldtype": "Data", "insert_after": "custom_relocation_destination_type"},
            {"fieldname": "custom_relocation_condition", "label": "Condition at Movement", "fieldtype": "Data", "insert_after": "custom_relocation_location_reference"},
            {"fieldname": "custom_relocation_disposition", "label": "Proposed Disposition", "fieldtype": "Data", "insert_after": "custom_relocation_condition"},
            {"fieldname": "custom_relocation_custodian", "label": "Destination Custodian", "fieldtype": "Data", "insert_after": "custom_relocation_disposition"},
        ],
    }
    for dt, rows in defs.items():
        for row in rows:
            if not frappe.get_meta(dt).has_field(row["fieldname"]):
                args = {k:v for k,v in row.items() if v is not None}
                create_custom_fields({dt: [args]}, update=True)
                frappe.clear_cache(doctype=dt)

    # Add real storage statuses instead of using misleading 'Pending Installation'.
    # Both underlying fields are already user-defined custom Select fields.
    for dt, fieldname, needed in (
        ("Installed Equipment", "custom_asset_status", ["In Storage"]),
        ("Installed Equipment", "custom_location_status", ["Other Location"]),
    ):
        cf_name = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
        if not cf_name:
            frappe.throw("STOP: Existing Custom Field missing: " + dt + "." + fieldname)
        cf = frappe.get_doc("Custom Field", cf_name)
        if cf.fieldtype != "Select":
            frappe.throw("STOP: Not a Select: " + fieldname)
        vals = [x.strip() for x in (cf.options or "").splitlines() if x.strip()]
        extras = [x for x in needed if x not in vals]
        if extras:
            cf.options = (cf.options or "").rstrip() + "\n" + "\n".join(extras)
            cf.save(ignore_permissions=True)
        frappe.clear_cache(doctype=dt)
    return "Relocation fields installed; storage statuses available."


def _reference(mi, dest_type):
    if dest_type == "Customer Branch":
        return mi.get("custom_new_branch")
    if dest_type == "Workshop":
        return mi.get("custom_company_workshop")
    if dest_type == "Company Warehouse":
        return mi.get("custom_relocation_warehouse")
    return (mi.get("custom_destination_location_text") or "").strip()


def _verify(mi):
    dest_type = (mi.get("custom_relocation_destination_type") or "").strip()
    if dest_type not in DESTINATIONS:
        frappe.throw("Choose a valid relocation destination type.")
    target = _reference(mi, dest_type)
    if not target:
        frappe.throw("Please select or enter the relocation destination.")
    if not (mi.get("custom_asset_change_reason") or "").strip():
        frappe.throw("Relocation reason is required.")
    if dest_type == "Customer Branch":
        if not frappe.db.exists("Client Branch", target):
            frappe.throw("Destination branch does not exist.")
        equipment = frappe.get_doc("Installed Equipment", mi.get("custom_asset"))
        branch = frappe.get_doc("Client Branch", target)
        current_customer = equipment.get("custom_parent_customer")
        branch_customer = branch.get("custom_parent_customer")
        if not current_customer or branch_customer != current_customer:
            frappe.throw("Destination branch must belong to the equipment's existing customer. Cross-customer transfers require RM approval.")
    if dest_type == "Workshop" and not frappe.db.exists("Company Workshop", target):
        frappe.throw("Destination workshop does not exist.")
    if dest_type == "Company Warehouse" and not frappe.db.exists("Warehouse", target):
        frappe.throw("Destination warehouse does not exist.")
    return dest_type, target


def _checked_mi(name, action=False):
    mi = frappe.get_doc("Mission Intervention", name)
    mi.check_permission("write")
    if mi.docstatus:
        frappe.throw("Only a draft intervention can be edited.")
    if not mi.get("custom_start_time"):
        frappe.throw("Check In before recording a relocation.")
    if not mi.get("custom_asset"):
        frappe.throw("Select the Installed Equipment first.")
    if mi.get("custom_intervention_type") != "Asset Relocation":
        frappe.throw("For this first version, relocation must be the main intervention type. Additional actions will follow.")
    return mi



def _get_approved_st_relocation(mi):
    """Get the RM-approved relocation for this MI's equipment."""

    ticket = mi.get("custom_service_ticket")
    equipment = mi.get("custom_asset")

    if not ticket or not equipment:
        frappe.throw(
            "MI must have a Service Ticket and Installed Equipment."
        )

    rows = frappe.get_all(
        "Service Ticket Movement Request",
        filters={
            "parent": ticket,
            "parenttype": "Service Ticket",
            "parentfield": "custom_movement_requests",
            "custom_equipment": equipment,
            "custom_movement_item_type": "Equipment",
            "custom_request_status": ["in", ["Approved", "Planned"]],
        },
        fields=[
            "name",
            "custom_destination_type",
            "custom_destination_branch",
            "custom_destination_workshop",
            "custom_destination_warehouse",
            "custom_destination_text",
            "custom_reason",
        ],
        limit_page_length=100,
    )

    if len(rows) != 1:
        frappe.throw(
            "Expected exactly one approved relocation request "
            "for this equipment. Found: " + str(len(rows))
        )

    row = rows[0]

    fields = {
        "Customer Branch": "custom_destination_branch",
        "Workshop": "custom_destination_workshop",
        "Company Warehouse": "custom_destination_warehouse",
        "Customer Warehouse": "custom_destination_warehouse",
        "Other Location": "custom_destination_text",
    }

    destination_field = fields.get(row.custom_destination_type)
    destination = row.get(destination_field) if destination_field else None

    if not destination:
        frappe.throw("Approved ST relocation destination is missing.")

    return row, destination



@frappe.whitelist()
def get_relocation_setup_v2(mi_name):
    mi = _checked_mi(mi_name)

    request, destination = _get_approved_st_relocation(mi)

    eq = frappe.get_doc("Installed Equipment", mi.custom_asset)

    dest_type = request.custom_destination_type

    return {
        "ok": True,
        "equipment": mi.custom_asset,
        "customer": eq.get("custom_parent_customer"),
        "current_branch": eq.get("custom_branch"),
        "location_status": eq.get("custom_location_status"),
        "ownership": eq.get("custom_ownership"),
        "approved_request": request.name,
        "destinations": list(DESTINATIONS),
        "branches": [],
        "workshops": [],
        "warehouses": [],
        "saved": {
            "destination_type": dest_type,
            "approved_destination": destination,
            "branch": destination if dest_type == "Customer Branch" else "",
            "workshop": destination if dest_type == "Workshop" else "",
            "warehouse": destination if dest_type == "Company Warehouse" else "",
            "details": mi.get("custom_relocation_details") or "",
            "reason": request.custom_reason or "",
            "condition": mi.get("custom_relocation_condition") or "",
            "disposition": mi.get("custom_relocation_disposition") or "",
            "custodian": mi.get("custom_relocation_custodian") or "",
        },
    }



@frappe.whitelist()
def save_relocation_v2(
    mi_name, destination_type=None, destination=None,
    details=None, reason=None, condition=None,
    disposition=None, custodian=None
):
    """Save RM-approved relocation instructions and technician observations."""

    mi = _checked_mi(mi_name)
    request, approved_destination = _get_approved_st_relocation(mi)

    dest_type = request.custom_destination_type
    destination = approved_destination
    reason = (request.custom_reason or "").strip()
    details = (details or "").strip()
    condition = (condition or "").strip()
    disposition = (disposition or "Pending Assessment").strip()

    if dest_type not in ("Customer Branch", "Workshop"):
        frappe.throw(
            "This relocation workflow currently supports "
            "Customer Branch and Workshop."
        )

    if not reason:
        frappe.throw("The ST Movement Request must contain a reason.")

    if len(details) > 140:
        frappe.throw("Location details exceed 140 characters.")

    allowed_conditions = [
        x.strip()
        for x in (
            frappe.get_meta("Equipment Movement")
            .get_field("custom_condition").options or ""
        ).splitlines()
        if x.strip()
    ]

    if condition not in allowed_conditions:
        frappe.throw("Select a valid Equipment Condition.")

    if disposition not in DISPOSITIONS:
        frappe.throw("Invalid proposed disposition.")

    existing = frappe.get_all(
        "Equipment Movement",
        filters={"custom_mission_intervention": mi.name},
        pluck="name",
        limit_page_length=3,
    )

    if len(existing) > 1:
        frappe.throw("Multiple movements exist for this MI.")

    if existing:
        mov = frappe.get_doc("Equipment Movement", existing[0])

        if mov.custom_applied:
            frappe.throw("This movement has already been applied.")

        if mov.custom_equipment != mi.custom_asset:
            frappe.throw("Movement equipment does not match MI.")
    else:
        eq = frappe.get_doc("Installed Equipment", mi.custom_asset)

        mov = frappe.new_doc("Equipment Movement")
        mov.custom_mission_intervention = mi.name
        mov.custom_service_ticket = mi.custom_service_ticket
        mov.custom_tech_mission = mi.custom_parent_mission
        mov.custom_equipment = mi.custom_asset
        mov.custom_scope = "Complete Equipment"
        mov.custom_source_type = eq.get("custom_location_status") or ""
        mov.custom_source_reference = (
            eq.get("custom_company_workshop")
            or eq.get("custom_branch")
            or ""
        )
        mov.custom_source_branch = eq.get("custom_branch")
        mov.custom_source_site_id = eq.get("custom_site_id")

    mov.custom_destination_type = dest_type

    for fieldname in (
        "custom_destination_branch",
        "custom_destination_workshop",
        "custom_destination_warehouse",
        "custom_destination_text",
    ):
        mov.set(fieldname, None)

    if dest_type == "Customer Branch":
        mov.custom_destination_branch = destination
        mov.custom_destination_detail = ""
    else:
        mov.custom_destination_workshop = destination
        mov.custom_destination_detail = details

    mov.custom_custodian = (
        "Customer" if dest_type == "Customer Branch" else "Company"
    )
    mov.custom_condition = condition
    mov.custom_proposed_disposition = disposition
    mov.custom_reason = reason

    # Store only existing, persistent MI fields.
    mi.custom_primary_action = "Equipment Relocation"
    mi.custom_relocation_destination_type = dest_type
    mi.custom_new_branch = (
        destination if dest_type == "Customer Branch" else None
    )
    mi.custom_company_workshop = (
        destination if dest_type == "Workshop" else None
    )
    mi.custom_destination_location_text = (
        details if dest_type == "Workshop" else None
    )
    mi.custom_asset_change_reason = reason

    _verify(mi)

    mi.save()

    if mov.is_new():
        mov.insert(ignore_permissions=True)
    else:
        mov.save(ignore_permissions=True)

    return {
        "ok": True,
        "mi": mi.name,
        "movement": mov.name,
        "destination_type": dest_type,
        "destination": destination,
        "condition": condition,
        "disposition": disposition,
    }



def _put(doc, fieldname, value):
    if doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def apply_whole_equipment_relocation(mi):
    """Apply one RM-approved movement through the completing MI.

    All changes participate in the caller's MI transaction.
    """

    dest_type, dest = _verify(mi)
    request, approved_dest = _get_approved_st_relocation(mi)

    if dest_type != request.custom_destination_type or dest != approved_dest:
        frappe.throw("Relocation differs from the RM-approved destination.")

    if mi.get("custom_work_outcome") != "Work Completed":
        frappe.throw("Relocation requires Work Completed.")

    if dest_type not in ("Customer Branch", "Workshop"):
        frappe.throw("Unsupported relocation execution destination.")

    locked = frappe.db.sql(
        """
        SELECT custom_request_status, custom_executed_mi,
               custom_equipment_movement
        FROM `tabService Ticket Movement Request`
        WHERE name = %s
        FOR UPDATE
        """,
        (request.name,),
        as_dict=True,
    )

    if not locked:
        frappe.throw("Approved movement request not found.")

    state = locked[0]

    movement_names = frappe.get_all(
        "Equipment Movement",
        filters={"custom_mission_intervention": mi.name},
        pluck="name",
        limit_page_length=3,
    )

    if len(movement_names) != 1:
        frappe.throw(
            "Exactly one saved Equipment Movement is required."
        )

    mov_name = movement_names[0]

    movement_lock = frappe.db.sql(
        """
        SELECT custom_applied
        FROM `tabEquipment Movement`
        WHERE name = %s
        FOR UPDATE
        """,
        (mov_name,),
        as_dict=True,
    )

    mov = frappe.get_doc("Equipment Movement", mov_name)

    if (
        state.custom_request_status == "Completed"
        and state.custom_executed_mi == mi.name
        and state.custom_equipment_movement == mov.name
        and movement_lock
        and movement_lock[0].custom_applied
    ):
        return {
            "equipment": mov.custom_equipment,
            "movement": mov.name,
            "log": mov.custom_lifecycle_log,
            "request": request.name,
            "already_applied": True,
        }

    if state.custom_request_status not in ("Approved", "Planned"):
        frappe.throw("Movement request is not approved for execution.")

    if state.custom_executed_mi or state.custom_equipment_movement:
        frappe.throw("Movement request already has execution references.")

    if not movement_lock or movement_lock[0].custom_applied:
        frappe.throw("Equipment Movement has already been applied.")

    if mov.custom_equipment != mi.get("custom_asset"):
        frappe.throw("Equipment Movement does not match the MI.")

    if mov.custom_destination_type != dest_type:
        frappe.throw("Movement destination type differs from approval.")

    mov_dest = (
        mov.custom_destination_branch
        if dest_type == "Customer Branch"
        else mov.custom_destination_workshop
    )

    if mov_dest != dest:
        frappe.throw("Movement destination differs from RM approval.")

    allowed_conditions = [
        value.strip()
        for value in (
            frappe.get_meta("Installed Equipment")
            .get_field("custom_operational_status").options or ""
        ).splitlines()
        if value.strip()
    ]

    condition = (mov.custom_condition or "").strip()

    if not condition or condition not in allowed_conditions:
        frappe.throw("Save a valid Condition at Movement first.")

    # Relocation cannot declare an equipment installed and operational.
    if condition == "Operational":
        frappe.throw(
            "Operational is confirmed during Installation. "
            "For functional equipment awaiting installation, select Good."
        )

    eq = frappe.get_doc("Installed Equipment", mi.custom_asset)

    if eq.get("custom_asset_status") in (
        "Retired", "Scrapped", "Lost", "Decommissioned"
    ):
        frappe.throw(
            "Equipment has a terminal status. RM review is required."
        )

    previous_branch = eq.get("custom_branch")
    previous_slot = eq.get("custom_site_id")
    previous_location_type = eq.get("custom_location_status")
    previous_condition = eq.get("custom_operational_status")

    if dest_type == "Customer Branch":
        _put(eq, "custom_branch", dest)
        _put(eq, "custom_company_workshop", None)
        _put(eq, "custom_location_status", "Client Site")
        _put(eq, "custom_asset_status", "Pending Installation")
        new_branch = dest
    else:
        _put(eq, "custom_branch", None)
        _put(eq, "custom_company_workshop", dest)
        _put(eq, "custom_location_status", "Workshop")
        _put(eq, "custom_asset_status", "In Workshop")
        new_branch = None

    # Only Installation MI assigns a new Site Position / Slot ID.
    _put(eq, "custom_site_id", None)

    # Technician-confirmed condition.
    _put(eq, "custom_operational_status", condition)

    _put(eq, "custom_relocation_location_reference", dest)
    _put(
        eq,
        "custom_relocation_location_detail",
        mov.custom_destination_detail or "",
    )
    _put(eq, "custom_relocation_custodian", mov.custom_custodian)

    eq.save(ignore_permissions=True)

    log = frappe.new_doc("Asset Lifecycle Log")

    values = {
        "custom_date": (
            mi.get("custom_end_time") or frappe.utils.now_datetime()
        ),
        "custom_customer": eq.get("custom_parent_customer"),
        "custom_branch": previous_branch,
        "custom_related_asset": eq.name,
        "custom_technician": (
            mi.get("custom_technician") or frappe.session.user
        ),
        "custom_service_ticket": mi.get("custom_service_ticket"),
        "custom_mission_ref": mi.get("custom_parent_mission"),
        "custom_intervention_ref": mi.name,
        "custom_event_source": "Intervention",
        "custom_event": "Relocated",
        "custom_equipment_still_on_site": (
            "Yes" if dest_type == "Customer Branch" else "No"
        ),
        "custom_previous_branch": previous_branch,
        "custom_previous_site_id": previous_slot,
        "custom_previous_site_position": previous_slot,
        "custom_new_branch": new_branch,
        "custom_new_site_id": None,
        "custom_new_site_position": None,
        "custom_company_workshop": (
            dest if dest_type == "Workshop" else None
        ),
        "custom_relocation_origin_type": previous_location_type,
        "custom_relocation_destination_type": dest_type,
        "custom_relocation_location_reference": dest,
        "custom_relocation_condition": condition,
        "custom_relocation_disposition": (
            mov.custom_proposed_disposition
        ),
        "custom_relocation_custodian": mov.custom_custodian,
        "custom_asset_change_reason": mov.custom_reason,
        "custom_action_taken": (
            "Relocated from {0} to {1}: {2}. "
            "Condition changed from {3} to {4}. "
            "Proposed disposition: {5}. "
            "Reason: {6}"
        ).format(
            previous_branch or previous_location_type or "Unspecified",
            dest_type,
            dest,
            previous_condition or "Unknown",
            condition,
            mov.custom_proposed_disposition or "Pending Assessment",
            mov.custom_reason or "",
        ),
    }

    for fieldname, value in values.items():
        _put(log, fieldname, value)

    log.insert(ignore_permissions=True)

    if log.docstatus == 0:
        log.submit()

    frappe.db.set_value(
        "Equipment Movement",
        mov.name,
        {
            "custom_applied": 1,
            "custom_applied_at": frappe.utils.now_datetime(),
            "custom_lifecycle_log": log.name,
        },
        update_modified=False,
    )

    frappe.db.set_value(
        "Service Ticket Movement Request",
        request.name,
        {
            "custom_executed_mi": mi.name,
            "custom_equipment_movement": mov.name,
            "custom_actual_destination_type": dest_type,
            "custom_actual_destination_reference": dest,
            "custom_deviation": 0,
            "custom_request_status": "Completed",
        },
        update_modified=False,
    )

    return {
        "equipment": eq.name,
        "movement": mov.name,
        "log": log.name,
        "request": request.name,
        "destination_type": dest_type,
    }
