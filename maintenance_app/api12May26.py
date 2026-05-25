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
    mission.custom_service_type = planning.get("custom_service_type")
    mission.custom_work_type = planning.get("custom_work_type") or "Tech Mission"
    mission.custom_planned_starttime = planning.get("custom_planned_starttime")
    mission.custom_planned_endtime = planning.get("custom_planned_endtime")
    mission.custom_vehicle = planning.get("custom_vehicle")
    mission.custom_mission_status = "Scheduled"
    mission.custom_request_description = planning.get("custom_request_description")

    if (
    planning.get("custom_planned_starttime") and planning.get("custom_planned_endtime")
    and planning.custom_planned_starttime >= planning.custom_planned_endtime):
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

    if mission.meta.has_field("custom_planned_team"):
        mission.custom_planned_team = []
        _copy_planned_team(planning, mission)

    mission.save(ignore_permissions=True)

    planning.custom_reschedule_count = (
        planning.get("custom_reschedule_count") or 0
    ) + 1

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
            "custom_technician": row.custom_technician
        })


def _create_todos_for_mission(mission, planning):
    created = 0

    for row in planning.get("custom_planned_team") or []:
        technician = row.get("custom_technician")

        if not technician:
            continue

        #allocated_to = _get_user_from_technician(technician)
        allocated_to = technician

        if not allocated_to:
            frappe.log_error(
                f"Cannot create ToDo. Technician '{technician}' "
                f"is not a valid User and is not linked to an Employee user_id.",
                "Tech Mission ToDo Error"
            )
            continue

        desc = _build_todo_description(mission, planning)

        todo = frappe.new_doc("ToDo")
        todo.allocated_to = allocated_to
        todo.assigned_by = frappe.session.user
        todo.reference_type = "Tech Mission"
        todo.reference_name = mission.name
        todo.status = "Open"
        todo.priority = _get_ticket_priority(planning)
        todo.date = getdate(planning.custom_planned_starttime)
        todo.description = desc

        todo.insert(ignore_permissions=True)

        created += 1

    if created == 0:
        frappe.msgprint(
            "Mission created, but no ToDo was created. "
            "Check Planned Technicians: technician must be a User "
            "or Employee linked to a User ID."
        )


def _get_user_from_technician(technician):
    if frappe.db.exists("User", technician):
        return technician

    if frappe.db.exists("Employee", technician):
        return frappe.db.get_value("Employee", technician, "user_id")

    return None


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
        todo.description = (
            todo.description or ""
        ) + "<br><br><b>Closed due to replanning.</b>"

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
    open_intervention = frappe.db.get_value(
        "Mission Intervention",
        {
            "custom_parent_mission": mission_name,
            "docstatus": ["!=", 1]
        },
        "name"
    )

    return {"open_intervention": open_intervention}


@frappe.whitelist()
def create_intervention_from_mission(mission_name):
    mission = frappe.get_doc("Tech Mission", mission_name)

    open_intervention = frappe.db.get_value(
        "Mission Intervention",
        {
            "custom_parent_mission": mission.name,
            "docstatus": ["!=", 1]
        },
        "name"
    )

    if open_intervention:
        return {"intervention": open_intervention}

    mi = frappe.new_doc("Mission Intervention")

    mi.custom_parent_mission = mission.name
    mi.custom_service_ticket = mission.get("custom_service_ticket")
    mi.custom_planning_ref = mission.get("custom_tech_planning")
    mi.custom_parent_customer = mission.get("custom_parent_customer")
    mi.custom_branch = mission.get("custom_branch")
    mi.custom_asset = mission.get("custom_asset")
    mi.custom_service_type = mission.get("custom_service_type")
    mi.custom_planned_starttime = mission.get("custom_planned_starttime")
    mi.custom_planned_endtime = mission.get("custom_planned_endtime")
    mi.custom_vehicle = mission.get("custom_vehicle")

    mi.custom_intervention_type = "Service"
    mi.custom_work_outcome = ""

    _fill_equipment_snapshot(mi)
    _copy_team_to_intervention(mission, mi)

    mi.insert(ignore_permissions=True)

    mission.custom_mission_status = "Ongoing"
    mission.save(ignore_permissions=True)

    if mission.get("custom_service_ticket"):
        frappe.db.set_value(
            "Service Ticket",
            mission.custom_service_ticket,
            "custom_ticket_status",
            "In Progress"
        )

    frappe.db.commit()

    return {"intervention": mi.name}


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
def existing_function():
    pass


def existing_function():
    pass


#@frappe.whitelist()
#def create_quotation_from_service_ticket(ticket_name):
#   ticket = frappe.get_doc("Service Ticket", ticket_name)

#   if not ticket.get("custom_customer"):
#       frappe.throw("Customer is required before creating Quotation.")

#   quotation = frappe.new_doc("Quotation")
#   quotation.quotation_to = "Customer"
#   quotation.party_name = ticket.custom_customer
#   quotation.custom_service_ticket = ticket.name

#   quotation.append("items", {
#       "item_code": "SERVICE-CALL",
#       "qty": 1,
#       "rate": 0,
#       "description": ticket.get("custom_subject") or ticket.name
#   })

#   quotation.insert(ignore_permissions=True)

#   ticket.custom_commercial_status = "To Quote"
#   ticket.custom_ticket_status = "Under Review"
#   ticket.save(ignore_permissions=True)

#   frappe.db.commit()

#   return {"quotation": quotation.name}
@frappe.whitelist()
def create_todos_for_existing_mission(mission_name):
    mission = frappe.get_doc("Tech Mission", mission_name)

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
        todo.reference_type = "Tech Mission"
        todo.reference_name = mission.name
        todo.status = "Open"
        todo.description = "Tech Mission: " + mission.name
        todo.insert(ignore_permissions=True)

    frappe.db.commit()

    return {"ok": True}
