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
