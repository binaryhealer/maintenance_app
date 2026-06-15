import frappe
from frappe.utils import getdate


@frappe.whitelist()
def create_mission_from_planning(planning_name):
    planning = frappe.get_doc("Tech Planning", planning_name)

    if planning.get("custom_mission_ref"):
        return {"mission": planning.custom_mission_ref}

    _validate_planning(planning)

    mission = frappe.new_doc("Tech Mission")
    mission.custom_service_ticket = planning.get("custom_service_ticket")
    mission.custom_tech_planning = planning.name
    mission.custom_parent_customer = planning.get("custom_parent_customer")
    mission.custom_branch = planning.get("custom_branch")
    mission.custom_asset = planning.get("custom_asset")
    mission.custom_component_group = planning.get("custom_component_group")
    mission.custom_component_item = planning.get("custom_component_item")
    mission.custom_component_row_id = planning.get("custom_component_row_id")
    mission.custom_component_serial = planning.get("custom_component_serial")
    mission.custom_component_brand = planning.get("custom_component_brand")
    mission.custom_component_model = planning.get("custom_component_model")
    mission.custom_ticket_type = planning.get("custom_ticket_type") or "Service"
    mission.custom_service_type = planning.get("custom_service_type")
    mission.custom_work_type = planning.get("custom_work_type") or "Tech Mission"
    mission.custom_planned_starttime = planning.get("custom_planned_starttime")
    mission.custom_planned_endtime = planning.get("custom_planned_endtime")
    mission.custom_vehicle = planning.get("custom_vehicle")
    mission.custom_mission_status = "Scheduled"
    mission.custom_request_description = planning.get("custom_request_description")

    mission.custom_subject = planning.get("custom_subject")
    mission.custom_applicant = planning.get("custom_applicant")
    mission.custom_applicant_role = planning.get("custom_applicant_role")
    mission.custom_applicant_email = planning.get("custom_applicant_email")
    mission.custom_applicant_phone = planning.get("custom_applicant_phone")

    for row in planning.get("custom_branch_contacts") or []:
        mission.append("custom_branch_contacts", {
            "custom_contact": row.get("custom_contact"),
            "custom_contact_role": row.get("custom_contact_role"),
            "custom_phone": row.get("custom_phone"),
            "custom_email": row.get("custom_email")
        })

    for row in planning.get("custom_head_office_contacts") or []:
        mission.append("custom_head_office_contacts", {
            "custom_contact": row.get("custom_contact"),
            "custom_contact_role": row.get("custom_contact_role"),
            "custom_phone": row.get("custom_phone"),
            "custom_email": row.get("custom_email")
        })

    if (
        planning.get("custom_planned_starttime")
        and planning.get("custom_planned_endtime")
        and planning.custom_planned_starttime >= planning.custom_planned_endtime
    ):
        frappe.throw("Planned End Time must be after Planned Start Time.")

    _copy_planned_team(planning, mission)

    mission.insert(ignore_permissions=True)

    planning.custom_mission_ref = mission.name
    planning.custom_planning_status = "Planned"
    planning.save(ignore_permissions=True)

    if planning.get("custom_service_ticket"):
        ticket = frappe.get_doc("Service Ticket", planning.custom_service_ticket)
        ticket.custom_primary_mission_ref = mission.name
        ticket.custom_primary_planning_ref = planning.name
        ticket.custom_ticket_status = "Planned"
        ticket.custom_planning_status = "Fully Planned"
        ticket.save(ignore_permissions=True)

    _close_open_todos_for_mission(mission.name)
    _create_todos_for_mission(mission, planning)

    frappe.db.commit()
    return {"mission": mission.name}


@frappe.whitelist()
def replan_mission_from_planning(planning_name):
    planning = frappe.get_doc("Tech Planning", planning_name)

    if not planning.get("custom_mission_ref"):
        frappe.throw("No Tech Mission is linked to this planning.")

    if not planning.get("custom_reschedule_required"):
        frappe.throw("Please check Reschedule Required before replanning.")

    if not planning.get("custom_reschedule_reason"):
        frappe.throw("Please select a Reschedule Reason before replanning.")

    _validate_planning(planning)

    mission = frappe.get_doc("Tech Mission", planning.custom_mission_ref)

    mission.custom_planned_starttime = planning.get("custom_planned_starttime")
    mission.custom_planned_endtime = planning.get("custom_planned_endtime")
    mission.custom_vehicle = planning.get("custom_vehicle")
    mission.custom_request_description = planning.get("custom_request_description")
    mission.custom_subject = planning.get("custom_subject")
    mission.custom_applicant = planning.get("custom_applicant")
    mission.custom_applicant_role = planning.get("custom_applicant_role")
    mission.custom_applicant_email = planning.get("custom_applicant_email")
    mission.custom_applicant_phone = planning.get("custom_applicant_phone")
    mission.custom_component_group = planning.get("custom_component_group")
    mission.custom_component_item = planning.get("custom_component_item")
    mission.custom_component_row_id = planning.get("custom_component_row_id")
    mission.custom_component_serial = planning.get("custom_component_serial")
    mission.custom_component_brand = planning.get("custom_component_brand")
    mission.custom_component_model = planning.get("custom_component_model")

    if mission.meta.has_field("custom_branch_contacts"):
        mission.set("custom_branch_contacts", [])
        for row in planning.get("custom_branch_contacts") or []:
            mission.append("custom_branch_contacts", {
                "custom_contact": row.get("custom_contact"),
                "custom_contact_role": row.get("custom_contact_role"),
                "custom_phone": row.get("custom_phone"),
                "custom_email": row.get("custom_email")
            })

    if mission.meta.has_field("custom_head_office_contacts"):
        mission.set("custom_head_office_contacts", [])
        for row in planning.get("custom_head_office_contacts") or []:
            mission.append("custom_head_office_contacts", {
                "custom_contact": row.get("custom_contact"),
                "custom_contact_role": row.get("custom_contact_role"),
                "custom_phone": row.get("custom_phone"),
                "custom_email": row.get("custom_email")
            })

    if mission.meta.has_field("custom_planned_team"):
        mission.custom_planned_team = []
        _copy_planned_team(planning, mission)

    mission.save(ignore_permissions=True)

    planning.custom_reschedule_count = (planning.get("custom_reschedule_count") or 0) + 1
    planning.custom_reschedule_required = 0
    planning.custom_planning_status = "Planned"
    planning.save(ignore_permissions=True)

    _close_open_todos_for_mission(mission.name)
    _create_todos_for_mission(mission, planning)

    frappe.db.commit()
    return {"mission": mission.name}


def _validate_planning(planning):
    required = {
        "custom_service_ticket": "Service Ticket",
        "custom_parent_customer": "Customer",
        "custom_branch": "Client Branch",
        "custom_asset": "Target Equipment",
        "custom_planned_starttime": "Planned Start Time",
        "custom_planned_endtime": "Planned End Time",
    }

    for fieldname, label in required.items():
        if not planning.get(fieldname):
            frappe.throw(f"{label} is required.")

    if not planning.get("custom_planned_team"):
        frappe.throw("Please add at least one technician in Planned Team.")


def _copy_planned_team(source_doc, target_doc):
    if not target_doc.meta.has_field("custom_planned_team"):
        return

    for row in source_doc.get("custom_planned_team") or []:
        if not row.get("custom_technician"):
            continue
        target_doc.append("custom_planned_team", {
            "custom_technician": row.get("custom_technician")
        })


def _create_todos_for_mission(mission, planning):
    created = 0

    for row in planning.get("custom_planned_team") or []:
        technician = row.get("custom_technician")
        if not technician:
            continue

        todo = frappe.new_doc("ToDo")
        todo.allocated_to = technician
        todo.assigned_by = frappe.session.user
        todo.reference_type = "Tech Mission"
        todo.reference_name = mission.name
        todo.status = "Open"
        todo.priority = _get_ticket_priority(planning)
        todo.date = getdate(planning.custom_planned_starttime)
        todo.description = _build_todo_description(mission, planning)
        todo.insert(ignore_permissions=True)
        created += 1

    if created == 0:
        frappe.msgprint(
            "Mission created, but no ToDo was created. "
            "Check Planned Technicians: technician must be a User "
            "or Employee linked to a User ID."
        )


def _get_ticket_priority(planning):
    if not planning.get("custom_service_ticket"):
        return "Medium"

    priority = frappe.db.get_value(
        "Service Ticket",
        planning.custom_service_ticket,
        "custom_priority"
    )

    mapping = {
        "Low": "Low",
        "Normal": "Medium",
        "High": "High",
        "Urgent": "High"
    }

    return mapping.get(priority, "Medium")


def _close_open_todos_for_mission(mission_name):
    todos = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Tech Mission",
            "reference_name": mission_name,
            "status": "Open"
        },
        pluck="name"
    )

    for todo_name in todos:
        todo = frappe.get_doc("ToDo", todo_name)
        todo.status = "Closed"
        todo.description = (todo.description or "") + "<br><br><b>Closed due to replanning.</b>"
        todo.save(ignore_permissions=True)


def _build_todo_description(mission, planning):
    return f"""
<b>Tech Mission:</b> {mission.name}<br>
<b>Service Ticket:</b> {planning.get("custom_service_ticket") or ""}<br>
<b>Customer:</b> {planning.get("custom_parent_customer") or ""}<br>
<b>Branch:</b> {planning.get("custom_branch") or ""}<br>
<b>Equipment:</b> {planning.get("custom_asset") or ""}<br>
<b>Planned:</b> {planning.get("custom_planned_starttime") or ""} to {planning.get("custom_planned_endtime") or ""}<br><br>
<b>Request:</b><br>
{planning.get("custom_request_description") or ""}
"""


@frappe.whitelist()
def get_open_intervention_for_mission(mission_name):
    intervention = frappe.db.get_value(
        "Mission Intervention",
        {
            "custom_parent_mission": mission_name,
            "docstatus": 0
        },
        "name"
    )

    return {"open_intervention": intervention}


@frappe.whitelist()
def create_intervention_from_mission(mission_name):
    mission = frappe.get_doc("Tech Mission", mission_name)

    open_intervention = frappe.db.get_value(
        "Mission Intervention",
        {
            "custom_parent_mission": mission.name,
            "docstatus": 0
        },
        "name"
    )

    if open_intervention:
        return {"intervention": open_intervention}

    if mission.get("custom_mission_status") in ["Completed", "Closed"]:
        frappe.throw("This mission is completed. Cannot create a new intervention.")

    mi = frappe.new_doc("Mission Intervention")
    _populate_mi_from_mission(mi, mission, mission.get("custom_asset"))
    mi.insert(ignore_permissions=True)

    _set_mission_and_ticket_in_progress(mission)
    frappe.db.commit()

    return {"intervention": mi.name}


@frappe.whitelist()
def create_additional_intervention_from_mission(
        mission_name,
        asset_name,
        reason=None,
        subject=None,
        intervention_type=None
    ):

    if not mission_name:
        frappe.throw("Tech Mission is required.")

    if not asset_name:
        frappe.throw("Please select equipment for the additional intervention.")

    mission = frappe.get_doc("Tech Mission", mission_name)

    if mission.get("custom_mission_status") == "Cancelled":
        frappe.throw("This mission is cancelled. Cannot create additional intervention.")

    mi = frappe.new_doc("Mission Intervention")
    _populate_mi_from_mission(mi, mission, asset_name)

    if subject and mi.meta.has_field("custom_subject"):
        mi.custom_subject = subject

    if intervention_type and mi.meta.has_field("custom_intervention_type"):
        mi.custom_intervention_type = intervention_type

    if mi.meta.has_field("custom_additional_mi"):
        mi.custom_additional_mi = 1

    if mi.meta.has_field("custom_additional_mi_reason"):
        mi.custom_additional_mi_reason = reason

    mi.insert(ignore_permissions=True)

    _set_mission_and_ticket_in_progress(mission)
    frappe.db.commit()

    return {"intervention": mi.name}

@frappe.whitelist()
def change_mi_equipment(mi_name, actual_equipment, reason):
    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    if not actual_equipment:
        frappe.throw("Actual Equipment is required.")

    mi = frappe.get_doc("Mission Intervention", mi_name)

    if mi.docstatus != 0:
        frappe.throw("Equipment can only be changed while MI is still draft.")

    original_equipment = mi.get("custom_asset")

    if original_equipment == actual_equipment:
        frappe.throw("Actual equipment is same as current equipment.")

    mi.custom_original_equipment = original_equipment
    mi.custom_asset = actual_equipment
    mi.custom_equipment_changed = 1
    mi.custom_equipment_change_reason = reason

    _fill_equipment_snapshot(mi)

    mi.save(ignore_permissions=True)

    if mi.get("custom_service_ticket"):
        ticket = frappe.get_doc("Service Ticket", mi.custom_service_ticket)

        ticket.custom_wrong_equipment_reported = 1
        ticket.custom_actual_equipment = actual_equipment
        ticket.custom_equipment_change_reason = reason

        ticket.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "ok": True,
        "mission_intervention": mi.name,
        "original_equipment": original_equipment,
        "actual_equipment": actual_equipment
    }

@frappe.whitelist()
def open_or_create_mi(mission_name):
    if not mission_name:
        frappe.throw("Tech Mission is required.")

    result = create_intervention_from_mission(mission_name)
    return {"intervention": result.get("intervention")}


def _populate_mi_from_mission(mi, mission, asset_name):
    mi.custom_parent_mission = mission.name
    mi.custom_service_ticket = mission.get("custom_service_ticket")
    mi.custom_planning_ref = mission.get("custom_tech_planning")
    mi.custom_parent_customer = mission.get("custom_parent_customer")
    mi.custom_branch = mission.get("custom_branch")
    mi.custom_asset = asset_name
    mi.custom_component_group = mission.get("custom_component_group")
    mi.custom_component_item = mission.get("custom_component_item")
    mi.custom_component_row_id = mission.get("custom_component_row_id")
    mi.custom_component_serial = mission.get("custom_component_serial")
    mi.custom_component_brand = mission.get("custom_component_brand")
    mi.custom_component_model = mission.get("custom_component_model")
    mi.custom_service_type = mission.get("custom_service_type")
    mi.custom_planned_starttime = mission.get("custom_planned_starttime")
    mi.custom_planned_endtime = mission.get("custom_planned_endtime")
    mi.custom_vehicle = mission.get("custom_vehicle")
    mi.custom_intervention_type = mission.get("custom_ticket_type") or "Service"
    mi.custom_work_outcome = ""

    mi.custom_subject = mission.get("custom_subject")
    mi.custom_applicant = mission.get("custom_applicant")
    mi.custom_applicant_role = mission.get("custom_applicant_role")
    mi.custom_applicant_email = mission.get("custom_applicant_email")
    mi.custom_applicant_phone = mission.get("custom_applicant_phone")

    for row in mission.get("custom_branch_contacts") or []:
        mi.append("custom_branch_contacts", {
            "custom_contact": row.get("custom_contact"),
            "custom_contact_role": row.get("custom_contact_role"),
            "custom_phone": row.get("custom_phone"),
            "custom_email": row.get("custom_email")
        })

    for row in mission.get("custom_head_office_contacts") or []:
        mi.append("custom_head_office_contacts", {
            "custom_contact": row.get("custom_contact"),
            "custom_contact_role": row.get("custom_contact_role"),
            "custom_phone": row.get("custom_phone"),
            "custom_email": row.get("custom_email")
        })

    _fill_equipment_snapshot(mi)
    _copy_team_to_intervention(mission, mi)


def _set_mission_and_ticket_in_progress(mission):
    mission.custom_mission_status = "Ongoing"
    mission.save(ignore_permissions=True)

    if mission.get("custom_service_ticket"):
        frappe.db.set_value(
            "Service Ticket",
            mission.custom_service_ticket,
            "custom_ticket_status",
            "In Progress"
        )


def _fill_equipment_snapshot(mi):
    if not mi.get("custom_asset"):
        return

    equipment = frappe.get_doc("Installed Equipment", mi.custom_asset)

    field_map = {
        "custom_asset_category": "custom_asset_category",
        "custom_client_asset_code": "custom_client_asset_code",
        "custom_asset_id": "custom_asset_id",
        "custom_make": "custom_make",
        "custom_model": "custom_model",
    }

    for mi_field, equipment_field in field_map.items():
        if mi.meta.has_field(mi_field):
            mi.set(mi_field, equipment.get(equipment_field))


def _copy_team_to_intervention(mission, mi):
    first_tech = None

    for row in mission.get("custom_planned_team") or []:
        tech = row.get("custom_technician")
        if not tech:
            continue

        if not first_tech:
            first_tech = tech

        if mi.meta.has_field("custom_intervention_team"):
            mi.append("custom_intervention_team", {
                "custom_technician": tech
            })

    if first_tech and mi.meta.has_field("custom_technician"):
        mi.custom_technician = first_tech


@frappe.whitelist()
def create_todos_for_existing_mission(mission_name):
    mission = frappe.get_doc("Tech Mission", mission_name)

    ticket = None
    if mission.get("custom_service_ticket"):
        ticket = frappe.get_doc("Service Ticket", mission.custom_service_ticket)

    for row in mission.get("custom_planned_team") or []:
        technician = row.get("custom_technician")
        if not technician:
            continue

        exists = frappe.db.exists("ToDo", {
            "reference_type": "Tech Mission",
            "reference_name": mission.name,
            "allocated_to": technician,
            "status": "Open"
        })

        if exists:
            continue

        todo = frappe.new_doc("ToDo")
        todo.allocated_to = technician
        todo.assigned_by = frappe.session.user
        todo.reference_type = "Tech Mission"
        todo.reference_name = mission.name
        todo.status = "Open"
        todo.priority = _get_ticket_priority_from_mission(mission)
        todo.date = getdate(mission.get("custom_planned_starttime") or frappe.utils.nowdate())
        todo.description = _build_direct_todo_description(mission, ticket)
        todo.insert(ignore_permissions=True)

    frappe.db.commit()
    return {"ok": True}


def _get_ticket_priority_from_mission(mission):
    if not mission.get("custom_service_ticket"):
        return "Medium"

    priority = frappe.db.get_value(
        "Service Ticket",
        mission.custom_service_ticket,
        "custom_priority"
    )

    mapping = {
        "Low": "Low",
        "Normal": "Medium",
        "High": "High",
        "Urgent": "High"
    }

    return mapping.get(priority, "Medium")


def _build_direct_todo_description(mission, ticket=None):
    subject = ""
    request_type = ""
    ticket_type = ""

    if ticket:
        subject = ticket.get("custom_subject") or ""
        request_type = ticket.get("custom_request_type") or ""
        ticket_type = ticket.get("custom_ticket_type") or ""

    return f"""
<b>Tech Mission:</b> {mission.name}<br>
<b>Service Ticket:</b> {mission.get("custom_service_ticket") or ""}<br>
<b>Customer:</b> {mission.get("custom_parent_customer") or ""}<br>
<b>Branch:</b> {mission.get("custom_branch") or ""}<br>
<b>Equipment:</b> {mission.get("custom_asset") or ""}<br>
<b>Planned:</b> {mission.get("custom_planned_starttime") or ""} to {mission.get("custom_planned_endtime") or ""}<br><br>

<b>Request:</b><br>
<b>Subject:</b> {subject}<br>
<b>Request Type:</b> {request_type}<br>
<b>Ticket Type:</b> {ticket_type}
"""


@frappe.whitelist()
def create_sales_invoice_from_service_ticket(ticket_name):
    if not ticket_name:
        frappe.throw("Service Ticket is required.")

    ticket = frappe.get_doc("Service Ticket", ticket_name)

    if not ticket.custom_customer:
        frappe.throw("Customer is required on Service Ticket.")

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = ticket.custom_customer
    invoice.company = frappe.defaults.get_user_default("company")

    if invoice.meta.has_field("custom_service_ticket"):
        invoice.custom_service_ticket = ticket.name

    if invoice.meta.has_field("custom_branch"):
        invoice.custom_branch = ticket.custom_client_branch

    has_stock_parts = False

    for row in ticket.get("custom_used_parts") or []:
        if row.get("custom_billed"):
            continue
        if not row.get("custom_item_code"):
            continue

        qty = row.get("custom_qty") or 1
        item_row = invoice.append("items", {})
        item_row.item_code = row.custom_item_code
        item_row.qty = qty

        if row.get("custom_warehouse"):
            item_row.warehouse = row.custom_warehouse
            has_stock_parts = True

    if not invoice.items:
        frappe.throw("No unbilled parts found on this ticket.")

    if has_stock_parts:
        invoice.update_stock = 1

    invoice.insert(ignore_permissions=True)
    return {"sales_invoice": invoice.name}
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_items_under_group(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters
):
    equipment_group = filters.get("equipment_group")

    if not equipment_group:
        return []

    return frappe.db.sql("""
        SELECT
            name,
            item_name,
            item_group,
            brand
        FROM `tabItem`
        WHERE
            disabled = 0
            AND is_stock_item = 1
            AND custom_component_equipment_group = %(equipment_group)s
            AND (
                name LIKE %(txt)s
                OR item_name LIKE %(txt)s
            )
        ORDER BY item_name
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        "equipment_group": equipment_group,
        "txt": f"%{txt}%",
        "page_len": page_len,
        "start": start
    })
@frappe.whitelist()
def get_component_groups_for_equipment(equipment_name):

    if not equipment_name:
        return []

    equipment = frappe.get_doc("Installed Equipment", equipment_name)

    groups = []

    for row in equipment.get("custom_installed_components") or []:
        group_name = row.get("custom_item_group")

        if group_name and group_name not in groups:
            groups.append(group_name)

    groups.sort()

    return groups


@frappe.whitelist()
def get_components_for_equipment_group(
    equipment_name,
    component_group
):

    if not equipment_name:
        return []

    equipment = frappe.get_doc("Installed Equipment", equipment_name)

    results = []

    for row in equipment.get("custom_installed_components") or []:

        if component_group and row.get("custom_item_group") != component_group:
            continue

        results.append({
            "row_id": row.name,
            "component_group": row.get("custom_item_group"),
            "component_item": row.get("custom_component_item"),
            "serial": row.get("custom_serial_number"),
            "brand": row.get("custom_brand"),
            "model": row.get("custom_model")
        })

    return results
@frappe.whitelist()
def change_mi_component(mi_name, actual_component_item, reason):

    mi = frappe.get_doc("Mission Intervention", mi_name)

    if mi.docstatus != 0:
        frappe.throw("Cannot change component on submitted intervention.")

    if not mi.custom_asset:
        frappe.throw("No equipment linked to this intervention.")

    equipment = frappe.get_doc(
        "Installed Equipment",
        mi.custom_asset
    )

    selected_component = None

    for row in equipment.custom_installed_components or []:

        if row.custom_component_item == actual_component_item:
            selected_component = row
            break

    if not selected_component:
        frappe.throw(
            f"Component {actual_component_item} not found on selected equipment."
        )

    # Store original value once
    if not mi.custom_original_component_item:
        mi.custom_original_component_item = mi.custom_component_item

    mi.custom_component_changed = 1
    mi.custom_component_change_reason = reason

    mi.custom_component_item = selected_component.custom_component_item
    mi.custom_component_group = selected_component.custom_item_group
    mi.custom_component_row_id = selected_component.name
    mi.custom_component_serial = selected_component.custom_serial_number
    mi.custom_component_brand = selected_component.custom_brand
    mi.custom_component_model = selected_component.custom_model

    mi.save(ignore_permissions=True)

    # Update Tech Mission
    if mi.custom_parent_mission:

        mission = frappe.get_doc(
            "Tech Mission",
            mi.custom_parent_mission
        )

        mission.custom_component_item = mi.custom_component_item
        mission.custom_component_group = mi.custom_component_group
        mission.custom_component_row_id = mi.custom_component_row_id
        mission.custom_component_serial = mi.custom_component_serial
        mission.custom_component_brand = mi.custom_component_brand
        mission.custom_component_model = mi.custom_component_model

        mission.save(ignore_permissions=True)

    
    # Update Service Ticket
    ticket_name = mi.get("custom_service_ticket")

    if ticket_name:
        ticket = frappe.get_doc("Service Ticket", ticket_name)

        ticket.custom_wrong_component_reported = 1
        ticket.custom_actual_component_item = mi.get("custom_component_item")
        ticket.custom_component_change_reason = reason

        for row in ticket.get("custom_intervention_history") or []:
            if row.get("custom_mission_intervention") == mi.name:
                row.custom_component_item = mi.get("custom_component_item")
                break

        ticket.save(ignore_permissions=True)
        
        #ticket.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "status": "success"
    }


# =========================
# LAST SERVICE DATE HELPER
# =========================

@frappe.whitelist()
def update_last_service_date_from_intervention(mi_name):
    """
    Updates Installed Equipment Last Service Date from a submitted Mission Intervention.

    Note:
    This helper does not run by itself. The automatic update must be called from
    the Mission Intervention After Submit Server Script, or this method can be
    called manually/API-side if needed.
    """

    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    mi = frappe.get_doc("Mission Intervention", mi_name)

    return update_last_service_date_from_mi_doc(mi)


def update_last_service_date_from_mi_doc(mi):
    """
    Internal reusable helper.
    Updates Installed Equipment.custom_last_service_date when:
      - MI has equipment
      - Work Outcome is Work Completed
      - Intervention Type is Service / Preventive Maintenance / Calibration
    """

    if not mi.get("custom_asset"):
        return {
            "updated": False,
            "reason": "No equipment linked."
        }

    if mi.get("custom_work_outcome") != "Work Completed":
        return {
            "updated": False,
            "reason": "Work Outcome is not Work Completed."
        }

    if mi.get("custom_intervention_type") not in [
        "Service",
        "Preventive Maintenance",
        "Calibration"
    ]:
        return {
            "updated": False,
            "reason": "Intervention Type is not service-related."
        }

    service_date = (
        mi.get("custom_end_time")
        or mi.get("custom_start_time")
        or frappe.utils.now_datetime()
    )

    frappe.db.set_value(
        "Installed Equipment",
        mi.custom_asset,
        "custom_last_service_date",
        service_date
    )

    frappe.db.commit()

    return {
        "updated": True,
        "equipment": mi.custom_asset,
        "last_service_date": service_date
    }


# =========================
# COMPONENT DETAIL HELPERS
# =========================

@frappe.whitelist()
def get_component_details_for_equipment_item(equipment_name, component_item):
    """
    Returns installed component child-row details for a selected equipment + component item.
    Used by wrong-component / actual-component logic.
    """

    if not equipment_name or not component_item:
        return {}

    equipment = frappe.get_doc("Installed Equipment", equipment_name)

    fallback = None

    for row in equipment.get("custom_installed_components") or []:
        if row.get("custom_component_item") != component_item:
            continue

        if not fallback:
            fallback = row

        status = row.get("custom_status") or ""

        if status in ["", "Installed", "Active"]:
            return {
                "row_id": row.name,
                "component_group": row.get("custom_item_group"),
                "component_item": row.get("custom_component_item"),
                "serial": row.get("custom_serial_number"),
                "brand": row.get("custom_brand"),
                "model": row.get("custom_model")
            }

    if fallback:
        return {
            "row_id": fallback.name,
            "component_group": fallback.get("custom_item_group"),
            "component_item": fallback.get("custom_component_item"),
            "serial": fallback.get("custom_serial_number"),
            "brand": fallback.get("custom_brand"),
            "model": fallback.get("custom_model")
        }

    return {}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_installed_component_items_for_equipment(doctype, txt, searchfield, start, page_len, filters):
    """
    Link search for actual component item.
    Shows only Item records that exist inside selected Installed Equipment child table.
    """

    equipment_name = filters.get("equipment_name") if filters else None

    if not equipment_name:
        return []

    equipment = frappe.get_doc("Installed Equipment", equipment_name)

    item_codes = []

    for row in equipment.get("custom_installed_components") or []:
        item_code = row.get("custom_component_item")

        if item_code and item_code not in item_codes:
            item_codes.append(item_code)

    if not item_codes:
        return []

    return frappe.db.sql("""
        SELECT
            i.name,
            i.item_name
        FROM `tabItem` i
        WHERE
            i.name IN %(item_codes)s
            AND i.disabled = 0
            AND (
                i.name LIKE %(txt)s
                OR i.item_name LIKE %(txt)s
            )
        ORDER BY i.item_name
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        "item_codes": tuple(item_codes),
        "txt": f"%{txt}%",
        "page_len": page_len,
        "start": start
    })
#import frappe


@frappe.whitelist()
def open_existing_mi_for_mission(mission_name):
    if not mission_name:
        frappe.throw("Mission is required.")

    rows = frappe.get_all(
        "Mission Intervention",
        filters={"custom_parent_mission": mission_name},
        fields=["name"],
        order_by="creation desc",
        limit_page_length=1
    )

    if not rows:
        frappe.throw("No intervention found for this mission.")

    return {"intervention": rows[0].name}

    # ============================================================
# Equipment Selector API functions
# Add these to maintenance_app/api.py
# ============================================================

import frappe


@frappe.whitelist()
def get_eq_customers():
    """
    Returns all customers that have Installed Equipment,
    with branch count and open ticket count.
    """
    customers = frappe.db.sql("""
        SELECT
            c.name,
            c.customer_name,
            c.customer_group,
            COUNT(DISTINCT cb.name) AS branch_count,
            COUNT(DISTINCT st.name) AS open_tickets
        FROM `tabCustomer` c
        LEFT JOIN `tabClient Branch` cb
            ON cb.custom_parent_customer = c.name
        LEFT JOIN `tabInstalled Equipment` ie
            ON ie.custom_parent_customer = c.name
        LEFT JOIN `tabService Ticket` st
            ON st.custom_customer = c.name
            AND st.custom_ticket_status NOT IN ('Closed', 'Cancelled', 'Resolved')
        WHERE ie.name IS NOT NULL
        GROUP BY c.name, c.customer_name, c.customer_group
        ORDER BY c.customer_name
    """, as_dict=True)

    return customers


@frappe.whitelist()
def get_eq_branches(customer):
    """
    Returns all Client Branches for a customer with equipment count.
    """
    if not customer:
        return []

    branches = frappe.db.sql("""
        SELECT
            cb.name,
            cb.custom_branch AS branch_name,
            cb.custom_address AS address,
            COUNT(ie.name) AS equipment_count
        FROM `tabClient Branch` cb
        LEFT JOIN `tabInstalled Equipment` ie
            ON ie.custom_branch = cb.name
        WHERE cb.custom_parent_customer = %(customer)s
        GROUP BY cb.name, cb.custom_branch, cb.custom_address
        ORDER BY cb.custom_branch
    """, {"customer": customer}, as_dict=True)

    return branches


@frappe.whitelist()
def get_eq_equipment(customer, branch):
    """
    Returns all Installed Equipment for a branch with fields that exist on
    Installed Equipment.

    Important:
    Do not add fields here unless they exist on Installed Equipment.
    Current valid warranty/coverage fields are:
    - custom_warranty
    - custom_warranty_period_years
    - custom_coverage_type
    """
    if not branch:
        return []

    filters = {
        "custom_branch": branch
    }

    if customer:
        filters["custom_parent_customer"] = customer

    equipment = frappe.get_all(
        "Installed Equipment",
        filters=filters,
        fields=[
            "name",
            "custom_parent_customer",
            "custom_branch",
            "custom_asset_name",
            "custom_display_name",
            "custom_item_code",
            "custom_make",
            "custom_model",
            "custom_asset_category",
            "custom_asset_id",
            "custom_site_id",
            "custom_asset_status",
            "custom_asset_type",
            "custom_equipment_health",
            "custom_ownership",
            "custom_location_status",
            "custom_client_asset_code",
            "custom_last_service_date",
            "custom_next_maintenance_date",
            "custom_maint_frequency",
            "custom_maintenance_contract",
            "custom_sla_rule",
            "custom_warranty",
            "custom_warranty_period_years",
            "custom_coverage_type",
            "custom_commissioned_date"
        ],
        order_by="custom_asset_category, custom_asset_name"
    )

    return equipment


@frappe.whitelist()
def get_eq_logs(equipment):
    """
    Returns all logs for a specific Installed Equipment:
    - Asset Service Logs
    - Asset Lifecycle Logs
    - Config Update Logs
    - Installed Components (child table rows)
    """
    if not equipment:
        return { "service": [], "lifecycle": [], "config": [], "components": [] }

    service_logs = frappe.get_all(
        "Asset Service Log",
        filters={"custom_related_asset": equipment},
        fields=[
            "name",
            "creation",
            "custom_end_time",
            "custom_intervention_type",
            "custom_technician",
            "custom_work_outcome",
            "custom_notes",
            "custom_service_ticket",
            "custom_mission_ref",
            "custom_intervention_ref",
            "custom_duration",
            "custom_component_item",
            "custom_component_group",
            "custom_component_serial",
        ],
        order_by="creation",
        limit=100
    )

    lifecycle_logs = frappe.get_all(
        "Asset Lifecycle Log",
        filters={"custom_related_asset": equipment},
        fields=[
            "name",
            "custom_date",
            "custom_event",
            "custom_event_source",
            "custom_technician",
            "custom_action_taken",
            "custom_previous_branch",
            "custom_new_branch",
            "custom_previous_make",
            "custom_previous_model",
            "custom_previous_serial",
            "custom_new_make",
            "custom_new_model",
            "custom_new_serial",
            "custom_component_item",
            "custom_new_component_item",
            "custom_service_ticket",
            "custom_intervention_ref",
            "custom_mission_ref",
        ],
        order_by="custom_date desc",
        limit=100
    )

    config_logs = frappe.get_all(
        "Config Update Log",
        filters={"custom_related_asset": equipment},
        fields=[
            "name",
            "custom_config_datetime",
            "custom_parameter",
            "custom_current_value",
            "custom_new_value",
            "custom_technician",
            "custom_notes",
            "custom_service_ticket",
            "custom_intervention",
        ],
        order_by="custom_config_datetime desc",
        limit=100
    )

    # Components from child table on Installed Equipment
    eq_doc = frappe.get_doc("Installed Equipment", equipment)
    components = []

    for row in eq_doc.get("custom_installed_components") or []:
        components.append({
            "name": row.name,
            "custom_component_item": row.get("custom_component_item"),
            "custom_item_group": row.get("custom_item_group"),
            "custom_item_name": row.get("custom_item_name"),
            "custom_serial_number": row.get("custom_serial_number"),
            "custom_brand": row.get("custom_brand"),
            "custom_model": row.get("custom_model"),
            "custom_status": row.get("custom_status") or "Installed",
            "custom_notes": row.get("custom_notes"),
        })

    return {
        "service": service_logs,
        "lifecycle": lifecycle_logs,
        "config": config_logs,
        "components": components
    }
# ADD THIS FUNCTION TO maintenance_app/api.py

@frappe.whitelist()
def get_equipment_warranty_status(equipment_name):
    """
    Get warranty status for equipment
    DEBUG VERSION - logs everything
    """
    print("\n" + "="*60)
    print("GET_EQUIPMENT_WARRANTY_STATUS DEBUG")
    print("="*60)
    
    if not equipment_name:
        print("No equipment name provided")
        return None
    
    print(f"Equipment: {equipment_name}")
    
    try:
        today = frappe.utils.today()
        print(f"Today's date: {today}")
        
        # First, get ALL warranties for this equipment (no filters)
        print("\n[STEP 1] Getting ALL warranties for this equipment...")
        all_warranties = frappe.get_all(
            "Warranty",
            filters={
                "custom_installed_equipment": equipment_name
            },
            fields=[
                "name",
                "custom_warranty_title",
                "custom_warranty_status",
                "custom_warranty_start_date",
                "custom_warranty_end_date",
                "custom_coverage_type"
            ]
        )
        
        print(f"Total warranties found: {len(all_warranties)}")
        for w in all_warranties:
            print(f"  - {w['name']}: status={w['custom_warranty_status']}, end_date={w['custom_warranty_end_date']}")
        
        if not all_warranties:
            print("No warranties found for this equipment")
            return {
                "is_covered": False,
                "message": "No warranties found for this equipment"
            }
        
        # Now filter for ACTIVE status
        print("\n[STEP 2] Filtering for ACTIVE status...")
        active_warranties = [w for w in all_warranties if w.get('custom_warranty_status') == 'Active']
        print(f"Active warranties: {len(active_warranties)}")
        for w in active_warranties:
            print(f"  - {w['name']}: {w['custom_warranty_end_date']}")
        
        if not active_warranties:
            print("No active warranties")
            return {
                "is_covered": False,
                "message": "No active warranty (status not Active)"
            }
        
        # Filter for END DATE in future
        print(f"\n[STEP 3] Filtering for end_date > {today}...")
        future_warranties = [w for w in active_warranties if w.get('custom_warranty_end_date') and str(w.get('custom_warranty_end_date')) > str(today)]
        print(f"Future warranties: {len(future_warranties)}")
        for w in future_warranties:
            print(f"  - {w['name']}: {w['custom_warranty_end_date']}")
        
        if not future_warranties:
            print("No warranties with future end dates")
            return {
                "is_covered": False,
                "message": "No active warranty (all expired)"
            }
        
        # Get the latest warranty
        print("\n[STEP 4] Selecting latest warranty...")
        w = future_warranties[0]
        print(f"Selected: {w['name']}")
        
        end_date = frappe.utils.getdate(w["custom_warranty_end_date"])
        today_date = frappe.utils.getdate(today)
        days_remaining = (end_date - today_date).days
        
        print(f"End date: {end_date}")
        print(f"Today: {today_date}")
        print(f"Days remaining: {days_remaining}")
        
        result = {
            "is_covered": True,
            "warranty_name": w["name"],
            "warranty_title": w["custom_warranty_title"],
            "coverage_type": w.get("custom_coverage_type", ""),
            "warranty_end_date": str(w["custom_warranty_end_date"]),
            "days_remaining": days_remaining,
            "message": f"✓ Under Warranty - {w.get('custom_coverage_type', 'Coverage')} - Expires in {days_remaining} days"
        }
        
        print(f"\nResult: {result}")
        print("="*60 + "\n")
        
        return result
    
    except Exception as e:
        print(f"ERROR: {str(e)}")
        frappe.log_error(str(e), "Get Equipment Warranty Status Debug")
        return {
            "is_covered": False,
            "message": f"Error: {str(e)}"
        }
'''@frappe.whitelist()
def get_technicians():
    """
    Return active users for technician selection in the Installed Equipment web view.
    This uses User because Planned Technicians.custom_technician links to User.
    """
    try:
        return frappe.get_all(
            "User",
            filters={
                "enabled": 1,
                "name": ["not in", ["Guest", "Administrator"]]
            },
            fields=["name", "full_name"],
            order_by="full_name asc"
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get Technicians Error")
        return []'''

'''@frappe.whitelist()
def get_technicians():
    try:
        return frappe.db.sql("""
            SELECT DISTINCT
                u.name,
                u.full_name
            FROM tabUser u
            INNER JOIN tabHas Role r
                ON r.parent = u.name
            WHERE
                u.enabled = 1
                AND u.user_type = 'System User'
                AND r.role IN ('Tech', 'Head Of Tech')
            ORDER BY u.full_name ASC
        """, as_dict=True)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get Technicians Error")
        return []'''

@frappe.whitelist()
def get_technicians():
    try:
        tech_users = frappe.get_all(
            "Has Role",
            filters={
                "role": ["in", ["Tech", "Head Of Tech"]]
            },
            pluck="parent"
        )

        if not tech_users:
            return []

        return frappe.get_all(
            "User",
            filters={
                "name": ["in", list(set(tech_users))],
                "enabled": 1
            },
            fields=["name", "full_name"],
            order_by="full_name asc"
        )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get Technicians Error")
        return []
# ============================================================
# INSTALLED EQUIPMENT WEB VIEW - TICKET HELPERS
# ============================================================

def _safe_set(doc, fieldname, value):
    if doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def _get_primary_contact_details(contact_name):
    result = {
        "role": "",
        "email": "",
        "phone": ""
    }

    if not contact_name:
        return result

    try:
        contact = frappe.get_doc("Contact", contact_name)
    except Exception:
        return result

    result["role"] = contact.get("designation") or ""

    for row in contact.get("email_ids") or []:
        if row.get("is_primary"):
            result["email"] = row.get("email_id") or ""
            break
    if not result["email"] and contact.get("email_ids"):
        result["email"] = contact.email_ids[0].get("email_id") or ""

    for row in contact.get("phone_nos") or []:
        if row.get("is_primary_mobile_no") or row.get("is_primary_phone"):
            result["phone"] = row.get("phone") or ""
            break
    if not result["phone"] and contact.get("phone_nos"):
        result["phone"] = contact.phone_nos[0].get("phone") or ""

    return result


@frappe.whitelist()
def get_eq_applicants_for_equipment(equipment_name):
    """
    Return contacts linked to the equipment customer.
    Used by /installed-equipment web view ticket modal.
    """
    if not equipment_name:
        return []

    equipment = frappe.db.get_value(
        "Installed Equipment",
        equipment_name,
        ["custom_parent_customer", "custom_branch"],
        as_dict=True
    )

    if not equipment or not equipment.get("custom_parent_customer"):
        return []

    customer = equipment.get("custom_parent_customer")
    branch = equipment.get("custom_branch")

    contacts = frappe.db.sql("""
        SELECT DISTINCT
            c.name,
            c.first_name,
            c.last_name,
            c.designation,
            c.custom_contact_scope,
            c.custom_client_branch
        FROM `tabContact` c
        INNER JOIN `tabDynamic Link` dl
            ON dl.parent = c.name
            AND dl.parenttype = 'Contact'
            AND dl.link_doctype = 'Customer'
            AND dl.link_name = %(customer)s
        WHERE c.name IS NOT NULL
        ORDER BY c.first_name, c.last_name, c.name
    """, {"customer": customer}, as_dict=True)

    output = []
    for c in contacts:
        scope = c.get("custom_contact_scope")
        contact_branch = c.get("custom_client_branch")

        # Keep Head Office contacts and branch contacts for this branch.
        if scope == "Branch Level" and contact_branch and contact_branch != branch:
            continue

        label = " ".join([c.get("first_name") or "", c.get("last_name") or ""]).strip()
        if not label:
            label = c.get("name")

        if c.get("designation"):
            label = label + " - " + c.get("designation")

        output.append({
            "name": c.get("name"),
            "label": label,
            "designation": c.get("designation") or ""
        })

    return output


def _apply_equipment_coverage_to_ticket(ticket, equipment_name):
    """
    Applies Warranty / AMC / Billable logic server-side.
    This makes web-created tickets behave like Desk-created tickets.
    """
    if not equipment_name:
        return None

    warranty_info = None

    try:
        warranty_info = get_equipment_warranty_status(equipment_name)
    except Exception:
        warranty_info = None

    if warranty_info and warranty_info.get("is_covered"):
        _safe_set(ticket, "custom_service_type", "Warranty")

        if ticket.meta.has_field("custom_warranty"):
            ticket.custom_warranty = warranty_info.get("warranty_name")

        # If your Service Ticket has a maintenance contract field, leave it blank for standalone Warranty doctype.
        return warranty_info

    # No active warranty; check Maintenance Contract by customer.
    if ticket.get("custom_customer"):
        contracts = frappe.get_all(
            "Maintenance Contract",
            filters={
                "custom_customer": ticket.custom_customer,
                "custom_status": "Active"
            },
            fields=[
                "name",
                "custom_contract_type",
                "custom_default_sla_rule",
                "custom_start_date",
                "custom_end_date"
            ],
            order_by="custom_start_date desc"
        )

        today = frappe.utils.getdate()

        valid_contracts = []
        for c in contracts:
            start_ok = not c.get("custom_start_date") or frappe.utils.getdate(c.custom_start_date) <= today
            end_ok = not c.get("custom_end_date") or frappe.utils.getdate(c.custom_end_date) >= today
            if start_ok and end_ok:
                valid_contracts.append(c)

        if valid_contracts:
            contract = valid_contracts[0]
            _safe_set(ticket, "custom_maintenance_contract", contract.name)

            if contract.get("custom_default_sla_rule"):
                _safe_set(ticket, "custom_sla_rule", contract.custom_default_sla_rule)

            if contract.get("custom_contract_type") == "Warranty":
                _safe_set(ticket, "custom_service_type", "Warranty")
            elif contract.get("custom_contract_type") == "AMC":
                _safe_set(ticket, "custom_service_type", "AMC")
            else:
                _safe_set(ticket, "custom_service_type", "Billable")

            return {
                "is_covered": True,
                "coverage_type": contract.get("custom_contract_type"),
                "contract": contract.name,
                "message": "Covered by " + str(contract.get("custom_contract_type") or "Contract")
            }

    _safe_set(ticket, "custom_service_type", "Billable")
    return {
        "is_covered": False,
        "coverage_type": "Billable",
        "message": "No active warranty or contract found"
    }


@frappe.whitelist()
def create_service_ticket_from_equipment(
    equipment_name,
    request_type=None,
    ticket_type=None,
    subject=None,
    priority=None,
    description=None,
    technician=None,
    technicians=None,
    applicant=None
):
    """
    Create Service Ticket from /installed-equipment web view.

    Fixes:
    - Customer and Branch are fetched server-side from Installed Equipment.
    - Warranty/AMC/Billable service type is applied server-side.
    - Applicant details are copied.
    - Optional technician is added to planned team if the child table exists.
    - Returns created ticket name and coverage info so the web modal can open it.
    """
    if not equipment_name:
        frappe.throw("Equipment is required.")

    equipment = frappe.db.get_value(
        "Installed Equipment",
        equipment_name,
        [
            "name",
            "custom_parent_customer",
            "custom_branch",
            "custom_display_name",
            "custom_asset_name",
            "custom_asset_id"
        ],
        as_dict=True
    )

    if not equipment:
        frappe.throw("Installed Equipment not found: " + str(equipment_name))

    ticket = frappe.new_doc("Service Ticket")

    _safe_set(ticket, "custom_target_equipment", equipment.name)
    _safe_set(ticket, "custom_customer", equipment.custom_parent_customer)
    _safe_set(ticket, "custom_client_branch", equipment.custom_branch)

    _safe_set(ticket, "custom_subject", subject or ("Service Request - " + (equipment.custom_display_name or equipment.custom_asset_name or equipment.name)))
    _safe_set(ticket, "custom_request_type", request_type or "Breakdown")
    _safe_set(ticket, "custom_ticket_type", ticket_type or "Repair")
    _safe_set(ticket, "custom_priority", priority or "Normal")
    _safe_set(ticket, "custom_description", description or "")
    _safe_set(ticket, "custom_ticket_status", "Open")
    _safe_set(ticket, "custom_planning_status", "Not Required")
    _safe_set(ticket, "custom_commercial_status", "N/A")
    _safe_set(ticket, "custom_raised_by", frappe.session.user)

    if applicant:
        _safe_set(ticket, "custom_applicant", applicant)
        details = _get_primary_contact_details(applicant)
        _safe_set(ticket, "custom_applicant_role", details.get("role"))
        _safe_set(ticket, "custom_applicant_email", details.get("email"))
        _safe_set(ticket, "custom_applicant_phone", details.get("phone"))

    # Optional suggested technicians from web view.
    # Supports both old single technician and new multi-technician list.
    selected_technicians = []

    if technicians:
        if isinstance(technicians, str):
            try:
                import json
                selected_technicians = json.loads(technicians)
            except Exception:
                selected_technicians = [technicians]
        elif isinstance(technicians, (list, tuple)):
            selected_technicians = list(technicians)

    if technician and technician not in selected_technicians:
        selected_technicians.append(technician)

    if ticket.meta.has_field("custom_planned_team"):
        seen_techs = set()

        for tech in selected_technicians:
            if not tech or tech in seen_techs:
                continue

            seen_techs.add(tech)

            ticket.append("custom_planned_team", {
                "custom_technician": tech
            })

    coverage_info = _apply_equipment_coverage_to_ticket(ticket, equipment.name)

    ticket.insert(ignore_permissions=True)

    return {
        "ticket": ticket.name,
        "coverage": coverage_info,
        "customer": equipment.custom_parent_customer,
        "branch": equipment.custom_branch,
        "service_type": ticket.get("custom_service_type")
    }

"""
Maintenance Contract API Functions
maintenance_app/api_mc.py
"""

import frappe
from frappe import _
from frappe.utils import getdate, add_days, date_diff
from datetime import timedelta

@frappe.whitelist()
def get_active_contract_for_equipment(equipment_name):
    """
    Get active maintenance contract for equipment
    Used by Service Ticket to auto-set service type and SLA
    """
    equipment = frappe.get_doc('Installed Equipment', equipment_name)
    
    today = getdate()
    
    contracts = frappe.get_list(
        'Maintenance Contract',
        filters={
            'custom_customer': equipment.custom_parent_customer,
            'custom_status': 'Active'
        },
        fields=['name', 'custom_contract_type', 'custom_default_sla_rule', 
                'custom_response_time_hours', 'custom_resolution_time_hours',
                'custom_end_date']
    )
    
    if not contracts:
        return None
    
    # Check if equipment is in any active contract
    for contract in contracts:
        contract_doc = frappe.get_doc('Maintenance Contract', contract['name'])
        
        # Check if equipment is covered
        for equipment_row in (contract_doc.custom_covered_equipment or []):
            if equipment_row.custom_equipment == equipment_name and equipment_row.custom_covered:
                return {
                    'contract_name': contract['name'],
                    'contract_type': contract['custom_contract_type'],
                    'sla_rule': contract['custom_default_sla_rule'],
                    'response_time_hours': contract['custom_response_time_hours'],
                    'resolution_time_hours': contract['custom_resolution_time_hours'],
                    'service_type': contract['custom_contract_type']
                }
    
    return None


@frappe.whitelist()
def check_contract_coverage(equipment_name):
    """
    Check if equipment has active contract coverage
    Returns coverage details if covered
    """
    contract = get_active_contract_for_equipment(equipment_name)
    
    if not contract:
        return {
            'is_covered': False,
            'message': 'No active maintenance contract'
        }
    
    contract_doc = frappe.get_doc('Maintenance Contract', contract['contract_name'])
    equipment_row = None
    
    for row in contract_doc.custom_covered_equipment:
        if row.custom_equipment == equipment_name:
            equipment_row = row
            break
    
    if not equipment_row:
        return {
            'is_covered': False,
            'message': 'Equipment not in active contract'
        }
    
    return {
        'is_covered': True,
        'contract_name': contract['contract_name'],
        'contract_type': contract['contract_type'],
        'coverage_type': equipment_row.custom_coverage_type,
        'includes_parts': contract_doc.custom_includes_parts,
        'includes_labour': contract_doc.custom_includes_labour,
        'sla_rule': contract['sla_rule'],
        'message': f"Covered under {contract['contract_type']} - {equipment_row.custom_coverage_type}"
    }


@frappe.whitelist()
def get_contract_consumption(contract_name, consumption_type=None):
    """
    Get consumption details for contract
    Returns: {included, used, remaining}
    """
    contract = frappe.get_doc('Maintenance Contract', contract_name)
    
    consumption = consumption_type or contract.custom_consumption_type
    
    if consumption == 'Ticket-based':
        return {
            'type': 'Ticket-based',
            'included': contract.custom_included_tickets or 0,
            'used': contract.custom_used_tickets or 0,
            'remaining': contract.custom_remaining_tickets or 0,
            'percent_used': ((contract.custom_used_tickets or 0) / (contract.custom_included_tickets or 1)) * 100
        }
    
    elif consumption == 'Hour-based':
        return {
            'type': 'Hour-based',
            'included': contract.custom_included_hours or 0,
            'used': contract.custom_used_hours or 0,
            'remaining': contract.custom_remaining_hours or 0,
            'percent_used': ((contract.custom_used_hours or 0) / (contract.custom_included_hours or 1)) * 100
        }
    
    else:  # Unlimited
        return {
            'type': 'Unlimited',
            'included': 'Unlimited',
            'used': 0,
            'remaining': 'Unlimited',
            'percent_used': 0
        }


@frappe.whitelist()
def activate_maintenance_contract(contract_name):
    """
    Activate a maintenance contract (change status from Draft to Active)
    """
    contract = frappe.get_doc('Maintenance Contract', contract_name)
    
    if contract.custom_status != 'Draft':
        frappe.throw(_('Only Draft contracts can be activated'))
    
    contract.custom_status = 'Active'
    contract.save()
    
    frappe.db.commit()
    
    return {
        'success': True,
        'message': f'Contract {contract_name} activated'
    }


@frappe.whitelist()
def renew_maintenance_contract(contract_name, new_end_date, new_start_date=None):
    """
    Renew a maintenance contract
    Creates new contract with updated dates or updates existing
    """
    contract = frappe.get_doc('Maintenance Contract', contract_name)
    
    today = getdate()
    new_end = getdate(new_end_date)
    new_start = getdate(new_start_date) if new_start_date else getdate()
    
    if new_end <= new_start:
        frappe.throw(_('New end date must be after start date'))
    
    # Update existing contract
    contract.custom_start_date = new_start
    contract.custom_end_date = new_end
    contract.custom_status = 'Renewed'
    
    # Reset consumption counters
    if contract.custom_consumption_type == 'Ticket-based':
        contract.custom_used_tickets = 0
    elif contract.custom_consumption_type == 'Hour-based':
        contract.custom_used_hours = 0
    
    contract.save()
    frappe.db.commit()
    
    return {
        'success': True,
        'message': f'Contract {contract_name} renewed until {new_end_date}'
    }


@frappe.whitelist()
def update_contract_consumption(contract_name, hours_used=0, tickets_used=0):
    """
    Update contract consumption when ticket is created/closed
    """
    contract = frappe.get_doc('Maintenance Contract', contract_name)
    
    if contract.custom_consumption_type == 'Ticket-based':
        contract.custom_used_tickets = (contract.custom_used_tickets or 0) + tickets_used
        contract.custom_remaining_tickets = (contract.custom_included_tickets or 0) - contract.custom_used_tickets
        
        if contract.custom_remaining_tickets <= 0:
            frappe.msgprint(
                _('Contract {} has no remaining tickets').format(contract_name),
                alert=True
            )
    
    elif contract.custom_consumption_type == 'Hour-based':
        contract.custom_used_hours = (contract.custom_used_hours or 0) + hours_used
        contract.custom_remaining_hours = (contract.custom_included_hours or 0) - contract.custom_used_hours
        
        if contract.custom_remaining_hours <= 0:
            frappe.msgprint(
                _('Contract {} has no remaining hours').format(contract_name),
                alert=True
            )
    
    contract.save()
    frappe.db.commit()


@frappe.whitelist()
def get_customer_active_contracts(customer_name):
    """
    Get all active contracts for a customer
    Used by Client Portal
    """
    today = getdate()
    
    contracts = frappe.get_list(
        'Maintenance Contract',
        filters={
            'custom_customer': customer_name,
            'custom_status': 'Active'
        },
        fields=[
            'name',
            'custom_contract_title',
            'custom_contract_type',
            'custom_start_date',
            'custom_end_date',
            'custom_days_remaining',
            'custom_contract_value',
            'custom_billing_frequency',
            'custom_paid_status'
        ]
    )
    
    for contract in contracts:
        contract['equipment_count'] = frappe.db.count(
            'MC Contract Equipment',
            {'parent': contract['name'], 'custom_covered': 1}
        )
    
    return contracts


@frappe.whitelist()
def get_contract_summary(customer_name):
    """
    Get contract summary for dashboard
    Returns: {total_contracts, active, expiring_soon, expired}
    """
    today = getdate()
    expiring_soon_date = add_days(today, 30)
    
    contracts = frappe.get_list(
        'Maintenance Contract',
        filters={'custom_customer': customer_name},
        fields=['name', 'custom_status', 'custom_end_date']
    )
    
    active_count = 0
    expiring_soon_count = 0
    expired_count = 0
    total_value = 0
    
    for contract in contracts:
        if contract['custom_status'] == 'Active':
            active_count += 1
            
            if contract['custom_end_date']:
                end_date = getdate(contract['custom_end_date'])
                if end_date <= today:
                    expired_count += 1
                elif end_date <= expiring_soon_date:
                    expiring_soon_count += 1
        
        # Calculate total value
        contract_doc = frappe.get_doc('Maintenance Contract', contract['name'])
        if contract_doc.custom_contract_value:
            total_value += contract_doc.custom_contract_value
    
    return {
        'total_contracts': len(contracts),
        'active_contracts': active_count,
        'expiring_soon': expiring_soon_count,
        'expired': expired_count,
        'total_value': total_value
    }


@frappe.whitelist()
def get_contract_details(contract_name):
    """
    Get detailed contract info for display
    """
    contract = frappe.get_doc('Maintenance Contract', contract_name)
    
    equipment_list = []
    for equipment in (contract.custom_covered_equipment or []):
        if equipment.custom_covered:
            equipment_list.append({
                'name': equipment.custom_equipment,
                'code': equipment.custom_client_asset_code,
                'coverage_type': equipment.custom_coverage_type,
                'branch': equipment.custom_branch
            })
    
    branches_list = []
    for branch in (contract.custom_covered_branches or []):
        if branch.custom_covered:
            branches_list.append(branch.custom_branch)
    
    return {
        'name': contract.name,
        'title': contract.custom_contract_title,
        'customer': contract.custom_customer,
        'type': contract.custom_contract_type,
        'status': contract.custom_status,
        'start_date': contract.custom_start_date,
        'end_date': contract.custom_end_date,
        'days_remaining': contract.custom_days_remaining,
        'contract_value': contract.custom_contract_value,
        'currency': contract.custom_currency,
        'includes_parts': contract.custom_includes_parts,
        'includes_labour': contract.custom_includes_labour,
        'includes_transport': contract.custom_includes_transport,
        'sla_rule': contract.custom_default_sla_rule,
        'response_time': contract.custom_response_time_hours,
        'resolution_time': contract.custom_resolution_time_hours,
        'consumption_type': contract.custom_consumption_type,
        'included_hours': contract.custom_included_hours,
        'used_hours': contract.custom_used_hours,
        'remaining_hours': contract.custom_remaining_hours,
        'equipment': equipment_list,
        'branches': branches_list,
        'service_hours': contract.custom_service_hours,
        'auto_renew': contract.custom_auto_renew,
        'internal_notes': contract.custom_internal_notes
    }


@frappe.whitelist()
def get_equipment_mc_info(equipment_name):
    """
    Get maintenance contract info for equipment
    Returns contract details if equipment is covered
    Used by IE form to display MC coverage
    """
    equipment = frappe.get_doc('Installed Equipment', equipment_name)
    
    today = getdate()
    
    # Find contracts that cover this equipment
    contracts = frappe.get_list(
        'Maintenance Contract',
        filters={
            'custom_customer': equipment.custom_parent_customer,
            'custom_status': 'Active'
        },
        fields=['name', 'custom_contract_type', 'custom_end_date', 
                'custom_days_remaining', 'custom_includes_parts',
                'custom_includes_labour', 'custom_includes_transport']
    )
    
    if not contracts:
        return None
    
    # Check if equipment is in any contract
    for contract_data in contracts:
        contract = frappe.get_doc('Maintenance Contract', contract_data['name'])
        
        for equipment_row in (contract.custom_covered_equipment or []):
            if equipment_row.custom_equipment == equipment_name and equipment_row.custom_covered:
                # Found! Return details
                days_left = contract_data.get('custom_days_remaining') or 0
                
                return {
                    'contract_name': contract_data['name'],
                    'contract_type': contract_data['custom_contract_type'],
                    'coverage_type': equipment_row.custom_coverage_type,
                    'is_active': contract_data['custom_contract_type'] != 'Expired',
                    'end_date': contract_data['custom_end_date'],
                    'days_remaining': days_left,
                    'includes_parts': contract_data['custom_includes_parts'],
                    'includes_labour': contract_data['custom_includes_labour'],
                    'includes_transport': contract_data['custom_includes_transport']
                }
    
    return None





@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_service_ticket_applicants(doctype, txt, searchfield, start, page_len, filters):
    customer = filters.get("customer")
    branch = filters.get("branch")

    if not customer:
        return []

    allowed = []

    if branch:
        branch_contacts = frappe.get_all(
            "Contact",
            filters={
                "custom_contact_scope": "Branch Level",
                "custom_client_branch": branch
            },
            pluck="name"
        )
        allowed.extend(branch_contacts)

    linked_contacts = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Contact",
            "link_doctype": "Customer",
            "link_name": customer
        },
        pluck="parent"
    )

    if linked_contacts:
        ho_contacts = frappe.get_all(
            "Contact",
            filters={
                "name": ["in", linked_contacts],
                "custom_contact_scope": "Head Office Level"
            },
            pluck="name"
        )
        allowed.extend(ho_contacts)

    allowed = list(set(allowed))

    if not allowed:
        return []

    if len(allowed) == 1:
        allowed.append("_dummy_")

    return frappe.db.sql("""
        SELECT
            name,
            full_name
        FROM `tabContact`
        WHERE
            name IN %(allowed)s
            AND (
                name LIKE %(txt)s
                OR full_name LIKE %(txt)s
                OR email_id LIKE %(txt)s
                OR phone LIKE %(txt)s
                OR mobile_no LIKE %(txt)s
            )
        ORDER BY full_name
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        "allowed": tuple(allowed),
        "txt": f"%{txt}%",
        "page_len": page_len,
        "start": start
    })

    
# ============================================================
# CLIENT PORTAL API
# ============================================================

@frappe.whitelist()
def client_portal_get_branches(customer):
    if not customer:
        return []

    return frappe.get_all(
        "Client Branch",
        filters={"custom_parent_customer": customer},
        fields=[
            "name",
            "custom_branch",
            "custom_address",
            "custom_site_type"
        ],
        order_by="custom_branch asc"
    )


@frappe.whitelist()
def client_portal_get_equipment(customer, branch=None):
    if not customer:
        return []

    filters = {
        "custom_parent_customer": customer
    }

    if branch:
        filters["custom_branch"] = branch

    return frappe.get_all(
        "Installed Equipment",
        filters=filters,
        fields=[
            "name",
            "custom_parent_customer",
            "custom_branch",
            "custom_asset_name",
            "custom_display_name",
            "custom_asset_category",
            "custom_asset_id",
            "custom_make",
            "custom_model",
            "custom_asset_status",
            "custom_equipment_health",
            "custom_warranty",
            "custom_maintenance_contract",
            "custom_next_maintenance",
            "custom_last_service_date"
        ],
        order_by="custom_asset_category, custom_asset_name"
    )


@frappe.whitelist()
def client_portal_get_tickets(customer):
    if not customer:
        return []

    return frappe.get_all(
        "Service Ticket",
        filters={"custom_customer": customer},
        fields=[
            "name",
            "custom_subject",
            "custom_ticket_status",
            "custom_service_type",
            "custom_client_branch",
            "custom_target_equipment",
            "custom_opening_date",
            "creation"
        ],
        order_by="creation desc",
        limit=50
    )


@frappe.whitelist()
def client_portal_get_contracts(customer):
    if not customer:
        return []

    return frappe.get_all(
        "Maintenance Contract",
        filters={
            "custom_customer": customer,
            "custom_status": "Active"
        },
        fields=[
            "name",
            "custom_contract_title",
            "custom_contract_type",
            "custom_start_date",
            "custom_end_date",
            "custom_status"
        ],
        order_by="custom_end_date asc"
    )
