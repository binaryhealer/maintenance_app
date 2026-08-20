import frappe
from frappe.utils import getdate


MAINTENANCE_TECHNICIAN_ROLES = (
    "Maintenance Technician",
    "Maintenance Supervisor",
)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_maintenance_technicians(
    doctype, txt, searchfield, start, page_len, filters=None
):
    """Return enabled Users who can perform maintenance field work."""
    return frappe.db.sql(
        """
        SELECT DISTINCT
            u.name,
            COALESCE(NULLIF(u.full_name, ''), u.name) AS full_name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` hr
            ON hr.parent = u.name
            AND hr.parenttype = 'User'
        WHERE
            hr.role IN %(roles)s
            AND u.enabled = 1
            AND u.name NOT IN ('Administrator', 'Guest')
            AND (
                u.name LIKE %(txt)s
                OR u.full_name LIKE %(txt)s
            )
        ORDER BY full_name, u.name
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "roles": MAINTENANCE_TECHNICIAN_ROLES,
            "txt": "%" + (txt or "") + "%",
            "start": int(start or 0),
            "page_len": int(page_len or 20),
        },
    )


def _validate_maintenance_technicians(technicians):
    """Reject assignment of users without an allowed maintenance role."""
    invalid = []

    for user in technicians or []:
        if not user:
            continue

        if not frappe.db.get_value("User", user, "enabled"):
            invalid.append(user)
            continue

        allowed = frappe.db.exists(
            "Has Role",
            {
                "parent": user,
                "parenttype": "User",
                "role": ["in", list(MAINTENANCE_TECHNICIAN_ROLES)],
            },
        )

        if not allowed:
            invalid.append(user)

    if invalid:
        frappe.throw(
            "Only users with Maintenance Technician or Maintenance Supervisor "
            "role may be assigned: {0}".format(", ".join(invalid))
        )


@frappe.whitelist()
def create_mission_from_planning(planning_name):
    planning = frappe.get_doc("Tech Planning", planning_name)

    if planning.get("custom_mission_ref"):
        return {"mission": planning.custom_mission_ref}

    _validate_planning(planning)

    mission = frappe.new_doc("Tech Mission")
    mission.custom_service_ticket = planning.get("custom_service_ticket")
    if mission.meta.has_field("custom_company"):
        mission.custom_company = planning.get("custom_company") or None
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
    mission.custom_target_component_name = planning.get("custom_target_component_name")
    mission.custom_parent_equipment = planning.get("custom_parent_equipment")
    mission.custom_ticket_type = planning.get("custom_ticket_type") or "Service"
    mission.custom_service_type = planning.get("custom_service_type")
    mission.custom_work_type = planning.get("custom_work_type") or "Tech Mission"
    mission.custom_planned_starttime = planning.get("custom_planned_starttime")
    mission.custom_planned_endtime = planning.get("custom_planned_endtime")
    mission.custom_vehicle = None
    if mission.meta.has_field("custom_external_vehicle"):
        mission.custom_external_vehicle = planning.get("custom_external_vehicle") or None
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
    if mission.meta.has_field("custom_vehicle"):
        mission.custom_vehicle = _get_common_team_vehicle(mission)

    mission.insert(ignore_permissions=True)
    _sync_service_ticket_planning_from_mission(mission)

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
    if mission.meta.has_field("custom_external_vehicle"):
        mission.custom_external_vehicle = planning.get("custom_external_vehicle") or None
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
    mission.custom_target_component_name = planning.get("custom_target_component_name")
    mission.custom_parent_equipment = planning.get("custom_parent_equipment")

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

    if mission.meta.has_field("custom_vehicle"):
        mission.custom_vehicle = _get_common_team_vehicle(mission)

    mission.save(ignore_permissions=True)
    _sync_service_ticket_planning_from_mission(mission)

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
    """
    Copy Planned Team rows while preserving the technician -> vehicle mapping.
    The Planned Technicians child DocType is shared by the planning workflow.
    """
    if not target_doc.meta.has_field("custom_planned_team"):
        return

    for row in source_doc.get("custom_planned_team") or []:
        technician = row.get("custom_technician")

        if not technician:
            continue

        values = {
            "custom_technician": technician
        }

        # Safe even during staged rollout: only add the field when it exists
        # on the child row DocType.
        if row.meta.has_field("custom_assigned_vehicle"):
            values["custom_assigned_vehicle"] = (
                row.get("custom_assigned_vehicle") or None
            )

        target_doc.append("custom_planned_team", values)

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

    if mi.meta.has_field("custom_mi_purpose"):
        mi.custom_mi_purpose = "Initial"

    mi.insert(ignore_permissions=True)

    _sync_mi_register_and_status(mi.name, save_mission=True)
    frappe.db.commit()

    return {"intervention": mi.name}


@frappe.whitelist()
def get_additional_mi_components(equipment_name):
    """Return currently installed permanent components for Additional MI target selection."""
    if not equipment_name:
        return []

    equipment = frappe.get_doc("Installed Equipment", equipment_name)
    results = []

    for row in equipment.get("custom_installed_components") or []:
        status = (row.get("custom_status") or "").strip()

        # Keep blank/Active/Installed as current; exclude clearly removed/inactive rows.
        if status and status not in ["Active", "Installed"]:
            continue

        component_name = row.get("custom_equipment_component")
        if not component_name:
            continue

        component = frappe.get_doc("Equipment Component", component_name)

        display_name = (
            component.get("custom_display_name")
            or row.get("custom_display_name")
            or component.get("custom_equipment_type")
            or row.get("custom_equipment_type")
            or component.name
        )

        serial = (
            component.get("custom_serial_number")
            or component.get("custom_serial")
            or row.get("custom_serial_number")
        )

        results.append({
            "row_id": row.name,
            "equipment_component": component.name,
            "display_name": display_name,
            "serial": serial,
        })

    return results


def _set_additional_mi_component_target(mi, component_row_id):
    """
    Set a component as the target of a NEW Additional MI.

    This is target selection, not a wrong-component correction:
    it must not modify the original Tech Mission or Service Ticket.
    """
    if not mi.get("custom_asset"):
        frappe.throw("Installed Equipment is required before selecting a component.")

    equipment = frappe.get_doc("Installed Equipment", mi.custom_asset)
    selected_row = None

    for row in equipment.get("custom_installed_components") or []:
        if row.name == component_row_id:
            selected_row = row
            break

    if not selected_row:
        frappe.throw("Selected component was not found on the selected equipment.")

    status = (selected_row.get("custom_status") or "").strip()
    if status and status not in ["Active", "Installed"]:
        frappe.throw("The selected component is not currently installed.")

    component_name = selected_row.get("custom_equipment_component")
    if not component_name:
        frappe.throw(
            "The selected installed component row is not linked "
            "to an Equipment Component master."
        )

    component = frappe.get_doc("Equipment Component", component_name)

    component_label = (
        component.get("custom_display_name")
        or selected_row.get("custom_display_name")
        or component.get("custom_equipment_type")
        or selected_row.get("custom_equipment_type")
        or component.name
    )

    component_item = (
        component.get("custom_component_item")
        or component.get("custom_equipment_type")
        or selected_row.get("custom_equipment_type")
        or component_label
    )

    component_group = (
        component.get("custom_component_group")
        or selected_row.get("custom_component_group")
        or selected_row.get("custom_item_group")
    )

    component_serial = (
        component.get("custom_serial_number")
        or component.get("custom_serial")
        or selected_row.get("custom_serial_number")
    )

    component_brand = (
        component.get("custom_make")
        or component.get("custom_brand")
        or selected_row.get("custom_brand")
    )

    component_model = (
        component.get("custom_model")
        or selected_row.get("custom_model")
    )

    _set_if_present = lambda fieldname, value: (
        mi.set(fieldname, value) if mi.meta.has_field(fieldname) else None
    )

    equipment_label = (
        equipment.get("custom_display_name")
        or equipment.get("custom_asset_name")
        or equipment.get("custom_client_asset_code")
        or equipment.name
    )

    _set_if_present(
        "custom_parent_equipment",
        equipment_label
    )
    _set_if_present("custom_equipment_component", component.name)
    _set_if_present("custom_target_component_name", component_label)
    _set_if_present("custom_component_item", component_item)
    _set_if_present("custom_component_row_id", selected_row.name)
    _set_if_present("custom_component_group", component_group)
    _set_if_present("custom_component_serial", component_serial)
    _set_if_present("custom_component_brand", component_brand)
    _set_if_present("custom_component_model", component_model)


@frappe.whitelist()
def create_additional_intervention_from_mission(
        mission_name,
        asset_name,
        reason=None,
        subject=None,
        intervention_type=None,
        target_scope="Equipment",
        component_row_id=None
    ):

    if not mission_name:
        frappe.throw("Tech Mission is required.")

    if not asset_name:
        frappe.throw("Please select equipment for the additional intervention.")

    mission = frappe.get_doc("Tech Mission", mission_name)

    if mission.get("custom_mission_status") in ["Cancelled", "Completed", "Closed"]:
        frappe.throw(
            "This mission is completed/cancelled. "
            "Cannot create an additional intervention."
        )

    if asset_name == mission.get("custom_asset"):
        frappe.throw(
            "Additional MI is for another equipment discovered during the same mission. "
            "Please select a different equipment."
        )

    additional_equipment = frappe.get_doc("Installed Equipment", asset_name)

    if (
        mission.get("custom_parent_customer")
        and additional_equipment.get("custom_parent_customer")
        != mission.get("custom_parent_customer")
    ):
        frappe.throw(
            "The selected equipment does not belong to the mission customer."
        )

    if (
        mission.get("custom_branch")
        and additional_equipment.get("custom_branch")
        != mission.get("custom_branch")
    ):
        frappe.throw(
            "Additional MI equipment must belong to the same branch/site as the mission."
        )

    target_scope = (target_scope or "Equipment").strip()

    if target_scope not in ["Equipment", "Component"]:
        frappe.throw("Invalid Additional MI target type.")

    if target_scope == "Component" and not component_row_id:
        frappe.throw("Please select the component to work on.")

    mi = frappe.new_doc("Mission Intervention")

    # Copy mission/customer/team/planning context, but never copy the
    # original equipment's component target into an Additional MI.
    _populate_mi_from_mission(
        mi,
        mission,
        asset_name,
        copy_original_component=False
    )

    # Whole-equipment target: give the PWA a readable target/faulty item.
    if target_scope == "Equipment":
        equipment_label = (
            additional_equipment.get("custom_display_name")
            or additional_equipment.get("custom_asset_name")
            or additional_equipment.get("custom_client_asset_code")
            or additional_equipment.name
        )

        if mi.meta.has_field("custom_target_component_name"):
            mi.custom_target_component_name = equipment_label

        if mi.meta.has_field("custom_parent_equipment"):
            mi.custom_parent_equipment = None

        if mi.meta.has_field("custom_equipment_component"):
            mi.custom_equipment_component = None

    else:
        # Component target: parent/main equipment remains in custom_asset and
        # custom_parent_equipment; the permanent COMP-xxxxx is the target.
        _set_additional_mi_component_target(mi, component_row_id)

    if subject and mi.meta.has_field("custom_subject"):
        mi.custom_subject = subject

    if intervention_type and mi.meta.has_field("custom_intervention_type"):
        mi.custom_intervention_type = intervention_type

    if mi.meta.has_field("custom_additional_mi"):
        mi.custom_additional_mi = 1

    if mi.meta.has_field("custom_additional_mi_reason"):
        mi.custom_additional_mi_reason = reason

    if mi.meta.has_field("custom_mi_purpose"):
        mi.custom_mi_purpose = "Additional Equipment"

    mi.insert(ignore_permissions=True)

    _sync_mi_register_and_status(mi.name, save_mission=True)
    frappe.db.commit()

    return {
        "intervention": mi.name,
        "equipment": asset_name,
        "target_scope": target_scope,
        "equipment_component": mi.get("custom_equipment_component"),
    }


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
    # After _fill_equipment_snapshot(mi)
    actual_equipment_doc = frappe.get_doc("Installed Equipment", actual_equipment)

    actual_equipment_label = (
        actual_equipment_doc.get("custom_display_name")
        or actual_equipment_doc.get("custom_asset_name")
        or actual_equipment_doc.name
    )

    mi.custom_target_component_name = actual_equipment_label
    mi.custom_parent_equipment = actual_equipment_label

    mi.custom_component_item = ""
    mi.custom_component_row_id = ""
    mi.custom_component_group = ""
    mi.custom_component_serial = ""
    mi.custom_component_brand = ""
    mi.custom_component_model = ""

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


'''def _populate_mi_from_mission(mi, mission, asset_name):
    mi.custom_parent_mission = mission.name
    mi.custom_service_ticket = mission.get("custom_service_ticket")
    if mi.meta.has_field("custom_company"):
        mi.custom_company = mission.get("custom_company") or None
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
    mi.custom_target_component_name = mission.get("custom_target_component_name")
    mi.custom_parent_equipment = mission.get("custom_parent_equipment")
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
    _copy_team_to_intervention(mission, mi)'''

###############################################################################
# fucnction populates the fields in mi when created from tech mission         #
###############################################################################



def _populate_mi_from_mission(
        mi,
        mission,
        asset_name,
        copy_original_component=True
    ):
    mi.custom_parent_mission = mission.name
    mi.custom_service_ticket = mission.get("custom_service_ticket")
    mi.custom_planning_ref = mission.get("custom_tech_planning")
    mi.custom_parent_customer = mission.get("custom_parent_customer")
    mi.custom_branch = mission.get("custom_branch")
    mi.custom_asset = asset_name

    is_original_equipment = (
        asset_name
        and mission.get("custom_asset")
        and asset_name == mission.get("custom_asset")
    )

    # Component details belong to the original mission target only.
    # Additional MI records for another equipment must start clean.
    if copy_original_component and is_original_equipment:
        mi.custom_component_group = mission.get("custom_component_group")
        mi.custom_component_item = mission.get("custom_component_item")
        mi.custom_component_row_id = mission.get("custom_component_row_id")
        mi.custom_component_serial = mission.get("custom_component_serial")
        mi.custom_component_brand = mission.get("custom_component_brand")
        mi.custom_component_model = mission.get("custom_component_model")
        mi.custom_target_component_name = mission.get("custom_target_component_name")
        mi.custom_parent_equipment = mission.get("custom_parent_equipment")
    else:
        component_fields = [
            "custom_component_group",
            "custom_component_item",
            "custom_component_row_id",
            "custom_component_serial",
            "custom_component_brand",
            "custom_component_model",
            "custom_target_component_name",
            "custom_parent_equipment",
            "custom_equipment_component",
        ]

        for fieldname in component_fields:
            if mi.meta.has_field(fieldname):
                mi.set(fieldname, None)

    mi.custom_service_type = mission.get("custom_service_type")
    mi.custom_planned_starttime = mission.get("custom_planned_starttime")
    mi.custom_planned_endtime = mission.get("custom_planned_endtime")

    # MI.custom_vehicle is the operational van/stock source.
    # It comes from the first/primary technician's Planned Team row.
    if mi.meta.has_field("custom_vehicle"):
        mi.custom_vehicle = _get_primary_assigned_vehicle(mission)

    if mi.meta.has_field("custom_external_vehicle"):
        mi.custom_external_vehicle = (
            mission.get("custom_external_vehicle") or None
        )

    mi.custom_intervention_type = (
        mission.get("custom_ticket_type") or "Service"
    )
    mi.custom_work_outcome = ""

    # Technician-facing priority and SLA deadlines
    if mi.meta.has_field("custom_priority"):
        mi.custom_priority = mission.get("custom_priority")

    if mi.meta.has_field("custom_response_due"):
        mi.custom_response_due = mission.get("custom_response_due")

    if mi.meta.has_field("custom_resolution_due"):
        mi.custom_resolution_due = mission.get("custom_resolution_due")

    mi.custom_subject = mission.get("custom_subject")
    mi.custom_applicant = mission.get("custom_applicant")
    mi.custom_applicant_role = mission.get("custom_applicant_role")
    mi.custom_applicant_email = mission.get("custom_applicant_email")
    mi.custom_applicant_phone = mission.get("custom_applicant_phone")

    # Permanent component ID from the Service Ticket is valid only for
    # the mission's original equipment.
    if (
        copy_original_component
        and is_original_equipment
        and mission.get("custom_service_ticket")
        and mi.meta.has_field("custom_equipment_component")
    ):
        ticket = frappe.get_doc(
            "Service Ticket",
            mission.custom_service_ticket
        )

        component_name = (
            ticket.get("custom_equipment_component")
            or ticket.get("custom_target_component")
        )

        if component_name:
            mi.custom_equipment_component = component_name

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

    # Rebuild the equipment-level snapshot from the actually selected asset.
    _fill_equipment_snapshot(mi)
    _copy_team_to_intervention(mission, mi)


def _get_mi_register_status(mi):
    """Return the live workflow status shown in Tech Mission intervention table."""
    if int(mi.docstatus or 0) == 2:
        return "Cancelled"

    if int(mi.docstatus or 0) == 1:
        return "Submitted"

    if mi.get("custom_end_time"):
        return "Checked Out"

    if mi.get("custom_start_time"):
        return "Checked In"

    return "Draft"


def _get_mission_hold_reason_from_outcome(outcome):
    mapping = {
        "Continue Work": "Follow-up Visit / Work to Continue",
        "Waiting for Parts": "Waiting for Parts",
        "Waiting for Client": "Waiting for Client",
        "To Quote (Billable)": "To Quote",
        "Could Not Complete": "Could Not Complete",
    }
    return mapping.get(outcome or "")


def _set_ticket_status_from_mission(mission, status, hold_reason=None):
    ticket_name = mission.get("custom_service_ticket")
    if not ticket_name:
        return

    ticket = frappe.get_doc("Service Ticket", ticket_name)

    if ticket.meta.has_field("custom_ticket_status"):
        ticket.custom_ticket_status = status

    if ticket.meta.has_field("custom_hold_reason"):
        ticket.custom_hold_reason = hold_reason or ""

    # A reopened/active mission must not retain stale resolution metadata.
    if status in ["In Progress", "On Hold"]:
        if ticket.meta.has_field("custom_resolution_source_mi"):
            ticket.custom_resolution_source_mi = None
        if ticket.meta.has_field("custom_resolution_date"):
            ticket.custom_resolution_date = None
        if ticket.meta.has_field("custom_resolved_by"):
            ticket.custom_resolved_by = None

    ticket.save(ignore_permissions=True)


def _sync_mi_row_to_mission(mission, mi):
    """
    Create or update the live MI row in Tech Mission.custom_intervention_table.

    The same row is maintained from Draft -> Checked In -> Checked Out ->
    Submitted.  The existing child table therefore becomes the live
    intervention register instead of appearing only after submission.
    """
    if not mission.meta.has_field("custom_intervention_table"):
        return None

    target_row = None

    for row in mission.get("custom_intervention_table") or []:
        if row.get("custom_intervention_reference") == mi.name:
            target_row = row
            break

    if target_row is None:
        target_row = mission.append("custom_intervention_table", {})

    values = {
        "custom_date": (
            mi.get("custom_end_time")
            or mi.get("custom_start_time")
            or mi.get("custom_planned_starttime")
            or frappe.utils.now_datetime()
        ),
        "custom_intervention_reference": mi.name,
        "custom_technician": mi.get("custom_technician"),
        "custom_hours": mi.get("custom_hours_worked") or 0,
        "custom_status": _get_mi_register_status(mi),
        "custom_work_progress": mi.get("custom_work_progress") or "",
    }

    tech_count = len(mission.get("custom_planned_team") or []) or 1
    values["custom_technician_count"] = tech_count

    # Billable hours are meaningful only after submission.
    if int(mi.docstatus or 0) == 1:
        physical_hours = mi.get("custom_hours_worked") or 0
        billable_hours = physical_hours

        if mission.get("custom_count_each_technician"):
            billable_hours = physical_hours * tech_count

        values["custom_billable_hours"] = round(billable_hours, 2)

        if mi.meta.has_field("custom_billable_hours"):
            mi.db_set(
                "custom_billable_hours",
                round(billable_hours, 2),
                update_modified=False
            )

    for fieldname, value in values.items():
        if target_row.meta.has_field(fieldname):
            target_row.set(fieldname, value)

    return target_row


def _recalculate_mission_status_from_mis(mission):
    """
    Aggregate TM/ST status from ALL Mission Interventions.

    Rules:
      * Checked-in work -> TM Ongoing / ST In Progress.
      * Normal draft Initial/Additional work -> Ongoing / In Progress.
      * A future untouched Follow-up draft does not restart SLA by itself.
      * If no active work exists and a submitted MI is waiting -> On Hold.
      * Only when no open/draft MI and no unresolved waiting MI remains
        can the mission complete.
    """
    mi_meta = frappe.get_meta("Mission Intervention")

    query_fields = [
        "name",
        "docstatus",
        "custom_start_time",
        "custom_end_time",
        "custom_work_outcome",
        "creation",
        "modified",
    ]

    for optional_field in [
        "custom_mi_purpose",
        "custom_previous_intervention",
        "custom_additional_mi",
    ]:
        if mi_meta.has_field(optional_field):
            query_fields.append(optional_field)

    rows = frappe.get_all(
        "Mission Intervention",
        filters={"custom_parent_mission": mission.name},
        fields=query_fields,
        order_by="creation asc",
        limit_page_length=1000
    )

    if not rows:
        return {
            "mission_status": mission.get("custom_mission_status"),
            "ticket_status": None,
            "hold_reason": None,
        }

    active_drafts = []
    untouched_followups = []

    for row in rows:
        if int(row.get("docstatus") or 0) != 0:
            continue

        purpose = (row.get("custom_mi_purpose") or "").strip()

        # Legacy/current sites may not yet have custom_mi_purpose.
        # custom_previous_intervention is enough to identify a follow-up.
        is_follow_up = (
            purpose == "Follow-up"
            or bool(row.get("custom_previous_intervention"))
        )

        if row.get("custom_start_time"):
            active_drafts.append(row)
        elif is_follow_up:
            untouched_followups.append(row)
        else:
            active_drafts.append(row)

    if active_drafts:
        mission.custom_mission_status = "Ongoing"
        if mission.meta.has_field("custom_hold_reason"):
            mission.custom_hold_reason = ""
        _set_ticket_status_from_mission(mission, "In Progress", "")
        return {
            "mission_status": "Ongoing",
            "ticket_status": "In Progress",
            "hold_reason": "",
        }

    # A waiting submitted MI stops being a blocker once it has a newer
    # follow-up MI linked to it.
    followed_sources = {
        row.get("custom_previous_intervention")
        for row in rows
        if row.get("custom_previous_intervention")
    }

    waiting_candidates = []

    for row in rows:
        if int(row.get("docstatus") or 0) != 1:
            continue

        if row.get("name") in followed_sources:
            continue

        hold_reason = _get_mission_hold_reason_from_outcome(
            row.get("custom_work_outcome")
        )

        if hold_reason:
            waiting_candidates.append((row, hold_reason))

    if waiting_candidates:
        waiting_row, hold_reason = waiting_candidates[-1]
        mission.custom_mission_status = "On Hold"

        if mission.meta.has_field("custom_hold_reason"):
            mission.custom_hold_reason = hold_reason

        _set_ticket_status_from_mission(
            mission,
            "On Hold",
            hold_reason
        )

        return {
            "mission_status": "On Hold",
            "ticket_status": "On Hold",
            "hold_reason": hold_reason,
            "source_mi": waiting_row.get("name"),
        }

    # An untouched future Follow-up keeps the mission on hold until work
    # actually starts.  Normally its predecessor supplies the reason.
    if untouched_followups:
        latest_followup = untouched_followups[-1]
        previous_name = latest_followup.get("custom_previous_intervention")
        previous_outcome = None

        if previous_name:
            previous_outcome = frappe.db.get_value(
                "Mission Intervention",
                previous_name,
                "custom_work_outcome"
            )

        hold_reason = (
            _get_mission_hold_reason_from_outcome(previous_outcome)
            or "Follow-up Visit / Work to Continue"
        )

        mission.custom_mission_status = "On Hold"

        if mission.meta.has_field("custom_hold_reason"):
            mission.custom_hold_reason = hold_reason

        _set_ticket_status_from_mission(
            mission,
            "On Hold",
            hold_reason
        )

        return {
            "mission_status": "On Hold",
            "ticket_status": "On Hold",
            "hold_reason": hold_reason,
        }

    # No open work and no unresolved waiting outcome remains.
    mission.custom_mission_status = "Completed"

    if mission.meta.has_field("custom_hold_reason"):
        mission.custom_hold_reason = ""

    ticket_name = mission.get("custom_service_ticket")
    if ticket_name:
        ticket = frappe.get_doc("Service Ticket", ticket_name)

        if ticket.meta.has_field("custom_ticket_status"):
            ticket.custom_ticket_status = "Resolved"

        if ticket.meta.has_field("custom_hold_reason"):
            ticket.custom_hold_reason = ""

        ticket.save(ignore_permissions=True)

    return {
        "mission_status": "Completed",
        "ticket_status": "Resolved",
        "hold_reason": "",
    }


def _sync_mi_register_and_status(mi_name, save_mission=True):
    mi = frappe.get_doc("Mission Intervention", mi_name)

    if not mi.get("custom_parent_mission"):
        return {"ok": False, "reason": "MI has no Tech Mission."}

    mission = frappe.get_doc("Tech Mission", mi.custom_parent_mission)

    _sync_mi_row_to_mission(mission, mi)
    status_result = _recalculate_mission_status_from_mis(mission)

    if mission.meta.has_field("custom_total_actual_hours"):
        total_actual_hours = 0
        for row in mission.get("custom_intervention_table") or []:
            total_actual_hours += row.get("custom_billable_hours") or 0
        mission.custom_total_actual_hours = round(total_actual_hours, 2)

    if save_mission:
        mission.save(ignore_permissions=True)

    return {
        "ok": True,
        "mission": mission.name,
        "mi": mi.name,
        "mi_status": _get_mi_register_status(mi),
        **status_result,
    }


@frappe.whitelist()
def sync_mi_to_mission_register(mi_name):
    """Public Desk/PWA helper used after MI Check In / Check Out saves."""
    result = _sync_mi_register_and_status(mi_name, save_mission=True)
    frappe.db.commit()
    return result

def _set_mission_and_ticket_in_progress(mission):
    mission.custom_mission_status = "Ongoing"

    if mission.meta.has_field("custom_hold_reason"):
        mission.custom_hold_reason = ""

    mission.save(ignore_permissions=True)

    if mission.get("custom_service_ticket"):
        ticket = frappe.get_doc(
            "Service Ticket",
            mission.custom_service_ticket
        )

        if ticket.meta.has_field("custom_ticket_status"):
            ticket.custom_ticket_status = "In Progress"

        if ticket.meta.has_field("custom_hold_reason"):
            ticket.custom_hold_reason = ""

        ticket.save(ignore_permissions=True)


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
    """
    Copy the mission team to the MI while preserving Assigned Vehicle.

    The first valid Planned Team row remains the current primary technician
    for the existing MI design. MI.custom_vehicle is therefore set from the
    same first row.
    """
    first_tech = None
    first_vehicle = None

    for row in mission.get("custom_planned_team") or []:
        tech = row.get("custom_technician")
        vehicle = row.get("custom_assigned_vehicle")

        if not tech:
            continue

        if not first_tech:
            first_tech = tech
            first_vehicle = vehicle

        if mi.meta.has_field("custom_intervention_team"):
            child_values = {
                "custom_technician": tech
            }

            if row.meta.has_field("custom_assigned_vehicle"):
                child_values["custom_assigned_vehicle"] = (
                    vehicle or None
                )

            mi.append("custom_intervention_team", child_values)

    if first_tech and mi.meta.has_field("custom_technician"):
        mi.custom_technician = first_tech

    if mi.meta.has_field("custom_vehicle"):
        mi.custom_vehicle = first_vehicle or None

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

    company = ticket.get("custom_company")
    if not company:
        frappe.throw("Company is required on Service Ticket.")

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = ticket.custom_customer
    invoice.company = company

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
            "component_group": row.get("custom_component_group") or row.get("custom_item_group"),
            "component_item": (
                row.get("custom_display_name")
                or row.get("custom_equipment_type")
                or row.get("custom_component")
                or row.name
            ),
            "component_ref": row.get("custom_component"),
            "equipment_type": row.get("custom_equipment_type"),
            "serial": row.get("custom_serial_number"),
            "brand": row.get("custom_brand"),
            "model": row.get("custom_model")
        })    


       
    return results

###################################################################
#the following fucntion helps change a wrongly logged component   #
###################################################################


@frappe.whitelist()
def change_mi_component(mi_name, component_row_id, reason):
    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    if not component_row_id:
        frappe.throw("Actual component is required.")

    if not reason:
        frappe.throw("Reason is required.")

    mi = frappe.get_doc("Mission Intervention", mi_name)
    is_additional_mi = bool(mi.get("custom_additional_mi"))

    if mi.docstatus != 0:
        frappe.throw(
            "Cannot change component on a submitted intervention."
        )

    if not mi.get("custom_asset"):
        frappe.throw(
            "No equipment linked to this intervention."
        )

    equipment = frappe.get_doc(
        "Installed Equipment",
        mi.custom_asset
    )

    selected_row = None

    for row in equipment.get(
        "custom_installed_components"
    ) or []:
        if row.name == component_row_id:
            selected_row = row
            break

    if not selected_row:
        frappe.throw(
            "Selected component was not found on this equipment."
        )

    component_name = selected_row.get(
        "custom_equipment_component"
    )

    if not component_name:
        frappe.throw(
            "The selected installed component row is not linked "
            "to an Equipment Component master."
        )

    component = frappe.get_doc(
        "Equipment Component",
        component_name
    )

    component_label = (
        component.get("custom_display_name")
        or selected_row.get("custom_display_name")
        or component.get("custom_equipment_type")
        or component.name
    )

    component_item = (
        component.get("custom_component_item")
        or component.get("custom_equipment_type")
        or selected_row.get("custom_equipment_type")
        or component_label
    )

    component_group = (
        component.get("custom_component_group")
        or selected_row.get("custom_component_group")
        or selected_row.get("custom_item_group")
    )

    component_serial = (
        component.get("custom_serial_number")
        or component.get("custom_serial")
        or selected_row.get("custom_serial_number")
    )

    component_brand = (
        component.get("custom_make")
        or component.get("custom_brand")
        or selected_row.get("custom_brand")
    )

    component_model = (
        component.get("custom_model")
        or selected_row.get("custom_model")
    )

    # On the original MI this action means "correct the reported component".
    # On an Additional MI it can also be used to select a component on the
    # newly selected equipment, so it must not mark the original report wrong.
    if not is_additional_mi:
        if not mi.get("custom_original_component_item"):
            mi.custom_original_component_item = (
                mi.get("custom_target_component_name")
                or mi.get("custom_component_item")
                or ""
            )

        mi.custom_component_changed = 1
        mi.custom_component_change_reason = reason

    if mi.meta.has_field("custom_equipment_component"):
        mi.custom_equipment_component = component.name

    if mi.meta.has_field("custom_target_component_name"):
        mi.custom_target_component_name = component_label

    if mi.meta.has_field("custom_component_item"):
        mi.custom_component_item = component_item

    if mi.meta.has_field("custom_component_row_id"):
        mi.custom_component_row_id = selected_row.name

    if mi.meta.has_field("custom_component_group"):
        mi.custom_component_group = component_group

    if mi.meta.has_field("custom_component_serial"):
        mi.custom_component_serial = component_serial

    if mi.meta.has_field("custom_component_brand"):
        mi.custom_component_brand = component_brand

    if mi.meta.has_field("custom_component_model"):
        mi.custom_component_model = component_model

    mi.save(ignore_permissions=True)

    if mi.get("custom_parent_mission") and not is_additional_mi:
        mission = frappe.get_doc(
            "Tech Mission",
            mi.custom_parent_mission
        )

        if mission.meta.has_field(
            "custom_target_component_name"
        ):
            mission.custom_target_component_name = (
                component_label
            )

        if mission.meta.has_field("custom_component_item"):
            mission.custom_component_item = component_item

        if mission.meta.has_field(
            "custom_component_row_id"
        ):
            mission.custom_component_row_id = (
                selected_row.name
            )

        if mission.meta.has_field(
            "custom_component_group"
        ):
            mission.custom_component_group = (
                component_group
            )

        if mission.meta.has_field(
            "custom_component_serial"
        ):
            mission.custom_component_serial = (
                component_serial
            )

        if mission.meta.has_field(
            "custom_component_brand"
        ):
            mission.custom_component_brand = (
                component_brand
            )

        if mission.meta.has_field(
            "custom_component_model"
        ):
            mission.custom_component_model = (
                component_model
            )

        mission.save(ignore_permissions=True)

    '''if mi.get("custom_service_ticket"):
        ticket = frappe.get_doc(
            "Service Ticket",
            mi.custom_service_ticket
        )

        if ticket.meta.has_field(
            "custom_wrong_component_reported"
        ):
            ticket.custom_wrong_component_reported = 1

        if ticket.meta.has_field(
            "custom_equipment_component"
        ):
            ticket.custom_equipment_component = (
                component.name
            )

        if ticket.meta.has_field(
            "custom_target_component"
        ):
            ticket.custom_target_component = (
                component.name
            )

        if ticket.meta.has_field(
            "custom_target_component_name"
        ):
            ticket.custom_target_component_name = (
                component_label
            )

        if ticket.meta.has_field(
            "custom_component_row_id"
        ):
            ticket.custom_component_row_id = (
                selected_row.name
            )

        if ticket.meta.has_field(
            "custom_component_group"
        ):
            ticket.custom_component_group = (
                component_group
            )

        if ticket.meta.has_field(
            "custom_component_item"
        ):
            ticket.custom_component_item = (
                component_item
            )

        if ticket.meta.has_field(
            "custom_component_serial"
        ):
            ticket.custom_component_serial = (
                component_serial
            )

        if ticket.meta.has_field(
            "custom_component_brand"
        ):
            ticket.custom_component_brand = (
                component_brand
            )

        if ticket.meta.has_field(
            "custom_component_model"
        ):
            ticket.custom_component_model = (
                component_model
            )

        if ticket.meta.has_field(
            "custom_actual_component_item"
        ):
            ticket.custom_actual_component_item = (
                component_item
            )

        if ticket.meta.has_field(
            "custom_component_change_reason"
        ):
            ticket.custom_component_change_reason = (
                reason
            )'''
    if mi.get("custom_service_ticket") and not is_additional_mi:
        ticket = frappe.get_doc(
            "Service Ticket",
            mi.custom_service_ticket
        )

    # Keep the original reported component unchanged.
    # Only record that the report was wrong and what the technician found.

        if ticket.meta.has_field("custom_wrong_component_reported"):
            ticket.custom_wrong_component_reported = 1

        if ticket.meta.has_field("custom_actual_component_item"):
            ticket.custom_actual_component_item = component_item

        if ticket.meta.has_field("custom_component_change_reason"):
            ticket.custom_component_change_reason = reason

        ticket.save(ignore_permissions=True)


        for row in ticket.get(
            "custom_intervention_history"
        ) or []:
            if (
                row.get("custom_mission_intervention")
                == mi.name
            ):
                if row.meta.has_field(
                    "custom_component_item"
                ):
                    row.custom_component_item = (
                        component_item
                    )

                if row.meta.has_field(
                    "custom_component_serial"
                ):
                    row.custom_component_serial = (
                        component_serial
                    )

                break

        ticket.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "status": "success",
        "component_row_id": selected_row.name,
        "equipment_component": component.name,
        "actual_component": component_label,
        "component_item": component_item,
        "component_group": component_group,
        "component_brand": component_brand,
        "component_model": component_model,
        "component_serial": component_serial
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

        if status in ["", "Installed" ]:
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
'''

for web view IE

'''

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

    '''service_logs = frappe.get_all(
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
    )'''


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
        order_by="creation desc",
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
            "row_id": row.name,

            # Permanent Equipment Component master (COMP-xxxxx).
            "custom_equipment_component": row.get("custom_equipment_component"),
            "equipment_component": row.get("custom_equipment_component"),

            "custom_component": row.get("custom_component"),
            "custom_display_name": row.get("custom_display_name"),
            "custom_equipment_type": row.get("custom_equipment_type"),
            "custom_component_group": row.get("custom_component_group"),

            # keep old keys as fallback so old JS does not break
            "custom_component_item": (
                row.get("custom_display_name")
                or row.get("custom_equipment_type")
                or row.get("custom_component_item")
                or row.get("custom_component")
            ),
            "custom_item_group": (
                row.get("custom_component_group")
                or row.get("custom_item_group")
            ),

            "custom_item_name": row.get("custom_item_name"),
            "custom_serial_number": row.get("custom_serial_number"),
            "custom_brand": row.get("custom_brand"),
            "custom_model": row.get("custom_model"),
            "custom_status": "Installed" if row.get("custom_status") == "Active" else (row.get("custom_status") or "Installed"),
            "custom_notes": row.get("custom_notes"),
        })

    #frappe.throw("service_logs: " + str(len(service_logs)))    

    return {
        "service": service_logs,
        "lifecycle": lifecycle_logs,
        "config": config_logs,
        "components": components
    }
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


def _current_user_display_name():
    return (
        frappe.db.get_value("User", frappe.session.user, "full_name")
        or frappe.session.user
    )


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
    component_row_id=None,
    request_type=None,
    ticket_type=None,
    subject=None,
    priority=None,
    description=None,
    technician=None,
    technicians=None,
    applicant=None
):
    if not equipment_name:
        frappe.throw("Equipment is required.")

    if not frappe.db.exists("Installed Equipment", equipment_name):
        frappe.throw("Installed Equipment not found: " + str(equipment_name))

    # Use the full Installed Equipment document so the Service Ticket
    # inherits operational context from the equipment record.
    equipment = frappe.get_doc("Installed Equipment", equipment_name)

    component_row = None
    target_label = (
        equipment.custom_display_name
        or equipment.custom_asset_name
        or equipment.name
    )

    component_master = None

    if component_row_id:
        # Backward compatible: accept legacy child row ID or permanent COMP-xxxxx ID.
        if frappe.db.exists("Equipment Component", component_row_id):
            component_master = frappe.get_doc("Equipment Component", component_row_id)
            equipment_doc = frappe.get_doc("Installed Equipment", equipment.name)
            for candidate in equipment_doc.get("custom_installed_components") or []:
                if candidate.get("custom_equipment_component") == component_master.name:
                    component_row = candidate
                    break

            if not component_row:
                frappe.throw(
                    "Component " + str(component_master.name)
                    + " is not currently linked to Installed Equipment "
                    + str(equipment.name) + "."
                )

            target_label = (
                component_master.get("custom_display_name")
                or component_master.get("custom_equipment_type")
                or component_master.name
            )
        else:
            component_row = frappe.get_doc("Installed Equipment Component", component_row_id)
            permanent_component = component_row.get("custom_equipment_component")
            if permanent_component and frappe.db.exists("Equipment Component", permanent_component):
                component_master = frappe.get_doc("Equipment Component", permanent_component)

            target_label = (
                (component_master.get("custom_display_name") if component_master else None)
                or component_row.get("custom_display_name")
                or component_row.get("custom_equipment_type")
                or component_row.get("custom_component")
                or component_row.name
            )

    ticket = frappe.new_doc("Service Ticket")

    _safe_set(ticket, "custom_target_equipment", equipment.name)
    _safe_set(ticket, "custom_customer", equipment.get("custom_parent_customer"))
    _safe_set(ticket, "custom_client_branch", equipment.get("custom_branch"))

    # --------------------------------------------------------
    # Equipment / site context
    # --------------------------------------------------------
    # Company is the service provider for this Installed Equipment.
    # Support both field names used across the GMAO build.
    company_value = (
        equipment.get("custom_company")
        or equipment.get("custom_company_workshop")
    )

    # Prefer values stored directly on Installed Equipment.
    client_type_value = equipment.get("custom_client_type")
    region_value = equipment.get("custom_region")

    # Older equipment may not have the classification fields populated.
    # In that case Client Branch remains the fallback/source of truth.
    branch_name = equipment.get("custom_branch")

    if branch_name and frappe.db.exists("Client Branch", branch_name):
        branch_doc = frappe.get_doc("Client Branch", branch_name)

        if not client_type_value:
            client_type_value = branch_doc.get("custom_site_type")

        if not region_value:
            region_value = branch_doc.get("custom_region")

    _safe_set(ticket, "custom_company", company_value)
    _safe_set(ticket, "custom_client_type", client_type_value)
    _safe_set(ticket, "custom_region", region_value)

    _safe_set(ticket, "custom_target_component_name", target_label)

    if component_row:
        _safe_set(ticket, "custom_component_row_id", component_row.name)

        permanent_component_name = (
            component_master.name if component_master
            else component_row.get("custom_equipment_component")
        )
        if permanent_component_name:
            _safe_set(ticket, "custom_equipment_component", permanent_component_name)
            _safe_set(ticket, "custom_target_component", permanent_component_name)

        _safe_set(ticket, "custom_component_group", (component_master.get("custom_component_group") if component_master else None) or component_row.get("custom_component_group"))
        _safe_set(ticket, "custom_component_brand", (component_master.get("custom_make") if component_master else None) or component_row.get("custom_brand"))
        _safe_set(ticket, "custom_component_model", (component_master.get("custom_model") if component_master else None) or component_row.get("custom_model"))
        _safe_set(ticket, "custom_component_serial", (component_master.get("custom_serial_number") if component_master else None) or component_row.get("custom_serial_number"))
        _safe_set(ticket, "custom_actual_component_item", (component_master.get("custom_item") if component_master else None) or component_row.get("custom_component"))
        _safe_set(ticket, "custom_component_item", (component_master.get("custom_item") if component_master else None) or component_row.get("custom_component") or component_row.get("custom_equipment_type"))

    _safe_set(ticket, "custom_subject", subject or ("Service Request - " + target_label))
    _safe_set(ticket, "custom_request_type", request_type or "Breakdown")
    _safe_set(ticket, "custom_ticket_type", ticket_type or "Repair")
    _safe_set(ticket, "custom_priority", priority or "Normal")
    _safe_set(ticket, "custom_description", description or "")
    _safe_set(ticket, "custom_ticket_status", "Open")
    _safe_set(ticket, "custom_planning_status", "Not Required")
    _safe_set(ticket, "custom_commercial_status", "N/A")
    _safe_set(ticket, "custom_raised_by", _current_user_display_name())

    if applicant:
        _safe_set(ticket, "custom_applicant", applicant)
        details = _get_primary_contact_details(applicant)
        _safe_set(ticket, "custom_applicant_role", details.get("role"))
        _safe_set(ticket, "custom_applicant_email", details.get("email"))
        _safe_set(ticket, "custom_applicant_phone", details.get("phone"))

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

    '''frappe.throw(f"""
    target_label: {target_label}
    component_row: {component_row.name if component_row else None}

    Has custom_target_component_name: {ticket.meta.has_field("custom_target_component_name")}
    Has custom_component_row_id: {ticket.meta.has_field("custom_component_row_id")}
    Has custom_component_group: {ticket.meta.has_field("custom_component_group")}
    Has custom_component_brand: {ticket.meta.has_field("custom_component_brand")}
    Has custom_component_model: {ticket.meta.has_field("custom_component_model")}
    Has custom_component_serial: {ticket.meta.has_field("custom_component_serial")}
    """)'''

    '''frappe.throw(
    "Before insert: "
    + str(ticket.get("custom_target_component_name"))
    )'''

    if component_row:
        ticket.custom_target_component = component_row.get("custom_component")
        ticket.custom_target_component_name = target_label
        ticket.custom_component_row_id = component_row.name
        ticket.custom_component_group = component_row.get("custom_component_group")
        ticket.custom_component_brand = component_row.get("custom_brand")
        ticket.custom_component_model = component_row.get("custom_model")
        ticket.custom_component_serial = component_row.get("custom_serial_number")


    ticket.insert(ignore_permissions=True)

    if component_row:
        frappe.db.set_value(
            "Service Ticket",
            ticket.name,
            {
                "custom_target_component": (
                    component_master.name if component_master
                    else component_row.get("custom_equipment_component")
                    or component_row.get("custom_component")
                ),
                "custom_equipment_component": (
                    component_master.name if component_master
                    else component_row.get("custom_equipment_component")
                ),
                "custom_target_component_name": target_label,
                "custom_component_row_id": component_row.name,
                "custom_component_group": component_row.get("custom_component_group"),
                "custom_component_brand": component_row.get("custom_brand"),
                "custom_component_model": component_row.get("custom_model"),
                "custom_component_serial": component_row.get("custom_serial_number"),
            },
            update_modified=False
        )



    if component_row:
        frappe.db.set_value(
            "Service Ticket",
            ticket.name,
            {
                "custom_target_component_name": target_label,
                "custom_component_row_id": component_row.name,
                "custom_component_group": component_row.get("custom_component_group"),
                "custom_component_brand": component_row.get("custom_brand"),
                "custom_component_model": component_row.get("custom_model"),
                "custom_component_serial": component_row.get("custom_serial_number"),
            },
            update_modified=False
        )

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

def get_client_portal_context():
    user = frappe.session.user

    contact_name = frappe.db.get_value(
        "Contact Email",
        {"email_id": user},
        "parent"
    )

    if not contact_name:
        frappe.throw("No Contact linked to this user.")

    customer = frappe.db.get_value(
        "Dynamic Link",
        {
            "parent": contact_name,
            "parenttype": "Contact",
            "link_doctype": "Customer"
        },
        "link_name"
    )

    scope = frappe.db.get_value(
        "Contact",
        contact_name,
        "custom_contact_scope"
    )

    branch = frappe.db.get_value(
        "Contact",
        contact_name,
        "custom_client_branch"
    )

    return {
        "customer": customer,
        "scope": scope,
        "branch": branch
    }

'''@frappe.whitelist()
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
    )'''

@frappe.whitelist()
def client_portal_get_branches(customer=None):
    ctx = get_client_portal_context()

    filters = {
        "custom_parent_customer": ctx["customer"]
    }

    if ctx["scope"] == "Branch Level":
        filters["name"] = ctx["branch"]

    return frappe.get_all(
        "Client Branch",
        filters=filters,
        fields=[
            "name",
            "custom_branch",
            "custom_address",
            "custom_site_type"
        ],
        order_by="custom_branch asc"
    )


'''@frappe.whitelist()
def client_portal_get_equipment(customer, branch=None):
    if not customer:
        return []

    filters = {"custom_parent_customer": customer}
    if branch:
        filters["custom_branch"] = branch

    # 1. Fetch parent records
    equipment_list = frappe.get_all(
        "Installed Equipment",
        filters=filters,
        fields=[
            "name",
            "custom_branch",
            "custom_asset_name",
            "custom_asset_category",
            "custom_model",
            "custom_asset_status",
            "custom_equipment_health",
            "custom_last_service_date",
            "custom_next_maintenance_date"
        ],
        order_by="custom_asset_category, custom_asset_name"
    )

    # 2. Map and stitch child components dynamically
    for eq in equipment_list:
        eq["components"] = frappe.get_all(
            "Installed Equipment Component",
            filters={"parent": eq["name"], "parenttype": "Installed Equipment"},
            fields=[
                "name",
                "custom_component_group",
                "custom_display_name",
                "custom_component",
                "custom_status",
                "custom_serial_number"
            ]
        )
    
    return equipment_list '''


'''@frappe.whitelist()
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
    ) '''



# ============================================================
# Build installed Equipment components
# ============================================================

'''@frappe.whitelist()
def build_components_for_equipment(equipment_name):
    equipment = frappe.get_doc("Installed Equipment", equipment_name)

    if not equipment.get("custom_equipment_template"):
        frappe.throw("Please select Equipment Template first.")

    template = frappe.get_doc(
        "Equipment Template",
        equipment.custom_equipment_template
    )

    created = 0

    for row in template.get("custom_components") or []:
        qty = row.get("custom_qty") or 1

        for i in range(qty):
            component = frappe.new_doc("Equipment Component")

            component.custom_parent_equipment = equipment.name
            component.custom_customer = equipment.get("custom_parent_customer")
            component.custom_branch = equipment.get("custom_branch")
            component.custom_component_group = row.get("custom_component_group")
            component.custom_equipment_type = row.get("custom_equipment_type")
            component.custom_status = "Active"

            type_name = row.get("custom_equipment_type") or "Component"

            component.custom_display_name = (
                f"{equipment.get('custom_display_name') or equipment.name} - {type_name}"
            )

            if qty > 1:
                component.custom_display_name = (
                    f"{equipment.get('custom_display_name') or equipment.name} - "
                    f"{type_name} {i + 1}"
                )

            component.insert(ignore_permissions=True)

            equipment.append("custom_installed_components", {
                "custom_component": component.name,
                "custom_display_name": component.custom_display_name,
                "custom_component_group": component.custom_component_group,
                "custom_equipment_type": component.custom_equipment_type,
                "custom_brand": component.get("custom_make"),
                "custom_model": component.get("custom_model"),
                "custom_serial_number": component.get("custom_serial_number"),
                "custom_status": "Active"
            })

            created += 1

    equipment.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "created": created
    }'''

@frappe.whitelist()
def build_components_for_equipment(equipment_name):
    equipment = frappe.get_doc("Installed Equipment", equipment_name)

    if not equipment.get("custom_equipment_template"):
        frappe.throw("Please select Equipment Template first.")

    # Prevent duplicate component creation.
    existing_rows = equipment.get("custom_installed_components") or []

    if existing_rows:
        frappe.throw(
            "Components have already been built for this equipment. "
            "Remove or correct the existing components before building again."
        )

    template = frappe.get_doc(
        "Equipment Template",
        equipment.custom_equipment_template
    )

    template_rows = template.get("custom_components") or []

    if not template_rows:
        frappe.throw("The selected Equipment Template has no components.")

    created = 0
    created_components = []

    for template_row in template_rows:
        qty = int(template_row.get("custom_qty") or 1)

        if qty < 1:
            continue

        component_group = template_row.get("custom_component_group")
        component_type = template_row.get("custom_equipment_type")
        type_name = component_type or "Component"

        for index in range(qty):
            # -----------------------------------------
            # 1. Create the permanent component master
            # -----------------------------------------
            component = frappe.new_doc("Equipment Component")

            component.custom_parent_equipment = equipment.name
            component.custom_customer = equipment.get(
                "custom_parent_customer"
            )
            component.custom_branch = equipment.get("custom_branch")
            component.custom_component_group = component_group
            component.custom_equipment_type = component_type
            component.custom_status = "Installed"

            # Insert first so the permanent COMP-xxxxx ID exists.
            # The permanent component display name must not include the
            # parent equipment because the component can move later.
            component.insert(ignore_permissions=True)

            component_description = (
                component.get("custom_equipment_type")
                or component.get("custom_component_group")
                or "Component"
            )

            component_serial = (
                component.get("custom_serial_number")
                or component.get("custom_serial")
            )

            display_name_parts = [
                str(component_description),
                str(component.name)
            ]

            if component_serial:
                display_name_parts.append(str(component_serial))

            display_name = " - ".join(display_name_parts)

            component.db_set(
                "custom_display_name",
                display_name,
                update_modified=False
            )
            component.custom_display_name = display_name

            # -----------------------------------------
            # 2. Create the current IE component row
            # -----------------------------------------
            equipment.append(
                "custom_installed_components",
                {
                    # Permanent link to Equipment Component
                    "custom_equipment_component": component.name,

                    "custom_display_name": component.custom_display_name,
                    "custom_component_group": component.custom_component_group,
                    "custom_equipment_type": component.custom_equipment_type,
                    "custom_brand": component.get("custom_make"),
                    "custom_model": component.get("custom_model"),
                    "custom_serial_number": (
                        component.get("custom_serial_number")
                        or component.get("custom_serial")
                    ),
                    "custom_status": "Installed"
                }
            )

            created_components.append(component.name)
            created += 1

    equipment.save(ignore_permissions=True)

    return {
        "created": created,
        "components": created_components
    }

'''@frappe.whitelist()
def create_component_ticket(equipment_name, component_name, request_type, subject):
    equipment = frappe.get_doc("Installed Equipment", equipment_name)
    component = frappe.get_doc("Equipment Component", component_name)

    ticket = frappe.new_doc("Service Ticket")

    ticket.custom_customer = equipment.get("custom_parent_customer")
    ticket.custom_client_branch = equipment.get("custom_branch")
    ticket.custom_parent_equipment = equipment.name
    ticket.custom_target_equipment = equipment.name
    ticket.custom_target_component = component.name

    if ticket.meta.has_field("custom_target_component_name"):
        ticket.custom_target_component_name = component.get("custom_display_name") or component.name

    ticket.custom_component_group = component.get("custom_component_group")
    ticket.custom_component_brand = component.get("custom_make")
    ticket.custom_component_model = component.get("custom_model")
    ticket.custom_component_serial = component.get("custom_serial_number")

    ticket.custom_request_type = request_type
    ticket.custom_subject = subject
    ticket.custom_ticket_status = "Open"
    ticket.custom_commercial_status = "N/A"

    if ticket.meta.has_field("custom_raised_by"):
        ticket.custom_raised_by = _current_user_display_name()

    ticket.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ticket": ticket.name}'''

@frappe.whitelist()
def create_component_ticket(equipment_name, component_name, request_type, subject):
    equipment = frappe.get_doc("Installed Equipment", equipment_name)
    component = frappe.get_doc("Equipment Component", component_name)

    ticket = frappe.new_doc("Service Ticket")

    ticket.custom_customer = equipment.get("custom_parent_customer")
    ticket.custom_client_branch = equipment.get("custom_branch")
    ticket.custom_parent_equipment = equipment.name
    ticket.custom_target_equipment = equipment.name

    if ticket.meta.has_field("custom_company"):
        ticket.custom_company = equipment.get("custom_company") or None

    # Existing component reference
    ticket.custom_target_component = component.name

    # New permanent Equipment Component ID link
    if ticket.meta.has_field("custom_equipment_component"):
        ticket.custom_equipment_component = component.name

    if ticket.meta.has_field("custom_target_component_name"):
        ticket.custom_target_component_name = (
            component.get("custom_display_name")
            or component.name
        )

    ticket.custom_component_group = component.get("custom_component_group")
    ticket.custom_component_brand = component.get("custom_make")
    ticket.custom_component_model = component.get("custom_model")
    ticket.custom_component_serial = component.get("custom_serial_number")

    ticket.custom_request_type = request_type
    ticket.custom_subject = subject
    ticket.custom_ticket_status = "Open"
    ticket.custom_commercial_status = "N/A"

    if ticket.meta.has_field("custom_raised_by"):
        ticket.custom_raised_by = _current_user_display_name()

    ticket.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ticket": ticket.name}  

# ============================================================
# 🖥️ DEDICATED CLIENT PORTAL WORKSPACE API ENDPOINTS
# ============================================================

'''@frappe.whitelist()
def client_portal_get_branches(customer):
    """Fetches unique branch physical locations assigned to a customer entity."""
    if not customer:
        return []
    return frappe.get_all(
        "Client Branch",
        filters={"custom_parent_customer": customer},
        fields=["name", "custom_branch", "custom_address", "custom_site_type"],
        order_by="custom_branch asc"
    )'''


import frappe
from frappe import _

@frappe.whitelist()
def client_portal_get_equipment(customer, branch=None):
    """
    Master equipment fetcher for the client portal dashboard workspace.
    Queries parent assets and deeply resolves properties hidden inside linked 
    Equipment Component master entries to fix blank Make, Model, and Serials.
    """
    ctx = get_client_portal_context()

    filters = {
        "custom_parent_customer": ctx["customer"]
    }

    if ctx["scope"] == "Branch Level":
        filters["custom_branch"] = ctx["branch"]

    # 1. Fetch parent records cleanly
    equipment_list = frappe.get_all(
        "Installed Equipment",
        filters=filters,
        fields=[
            "name",
            "custom_branch",
            "custom_asset_name",
            "custom_asset_category",
            "custom_model",
            "custom_asset_status",
            "custom_equipment_health",
            "custom_last_service_date",
            "custom_next_maintenance_date"
        ],
        order_by="custom_asset_category, custom_asset_name"
    )

    # 2. INTEGRATED FRIEND FIX: Deeply crack open data keys across the linked templates
    for eq in equipment_list:
        try:
            child_rows = frappe.db.get_values(
                "Installed Equipment Component",
                filters={
                    "parent": eq["name"],
                    "parenttype": "Installed Equipment",
                    "parentfield": "custom_installed_components"
                },
                fieldname=[
                    "name",
                    "custom_component",
                    "custom_component_group",
                    "custom_equipment_type",
                    "custom_display_name",
                    "custom_brand",
                    "custom_model",
                    "custom_serial_number",
                    "custom_status"
                ],
                as_dict=True
            ) or []

            components = []

            for row in child_rows:
                component_doc = None

                # Look into the master record link if it exists on this child row
                if row.get("custom_component"):
                    try:
                        component_doc = frappe.db.get_value(
                            "Equipment Component",
                            row.get("custom_component"),
                            [
                                "name",
                                "custom_display_name",
                                "custom_component_group",
                                "custom_equipment_type",
                                "custom_make",
                                "custom_model",
                                "custom_serial_number",
                                "custom_status"
                            ],
                            as_dict=True
                        )
                    except Exception:
                        component_doc = None

                # Smart title matching resolution
                display_name = (
                    (component_doc or {}).get("custom_display_name")
                    or row.get("custom_display_name")
                    or row.get("custom_equipment_type")
                    or row.get("custom_component")
                    or "Unnamed Component"
                )

                # Append perfectly structured payload mapping definitions for client side scripts
                components.append({
                    "name": row.get("custom_component") or row.get("name"),
                    "custom_component": row.get("custom_component"),
                    "custom_component_group": (
                        (component_doc or {}).get("custom_component_group")
                        or row.get("custom_component_group")
                        or "General / Auxiliary System"
                    ),
                    "custom_equipment_type": (
                        (component_doc or {}).get("custom_equipment_type")
                        or row.get("custom_equipment_type")
                        or ""
                    ),
                    "custom_display_name": display_name,
                    "custom_brand": (
                        (component_doc or {}).get("custom_make")
                        or row.get("custom_brand")
                        or "-"
                    ),
                    "custom_model": (
                        (component_doc or {}).get("custom_model")
                        or row.get("custom_model")
                        or "-"
                    ),
                    "custom_serial_number": (
                        (component_doc or {}).get("custom_serial_number")
                        or row.get("custom_serial_number")
                        or "N/A"
                    ),
                    "custom_status": (
                        (component_doc or {}).get("custom_status")
                        or row.get("custom_status")
                        or "Installed"
                    )
                })

            eq["components"] = components

        except Exception as e:
            frappe.log_error(
                f"Portal component load failure for asset {eq.get('name')}: {str(e)}"
            )
            eq["components"] = []
    
    return equipment_list


'''@frappe.whitelist()
def client_portal_get_branches(customer):
    """Fetches all operating branches linked to the active Customer profile."""
    if not customer:
        return []
    return frappe.get_all(
        "Client Branch",
        filters={"custom_parent_customer": customer},
        fields=["name", "custom_branch", "custom_address", "custom_site_type"]
    ) '''


@frappe.whitelist()
def client_portal_get_contracts(customer):
    """Fetches active SLAs and maintenance contracts linked to the Customer profile."""
    if not customer:
        return []
    return frappe.get_all(
        "Maintenance Contract",
        filters={"custom_customer": customer, "custom_status": "Active"},
        fields=["name", "custom_contract_title", "custom_contract_type", "custom_end_date", "custom_status"]
    )


@frappe.whitelist()
def client_portal_get_tickets(customer):
    """Fetches all customer support and intervention tickets matching the account."""

    ctx = get_client_portal_context()

    filters = {
        "custom_customer": ctx["customer"]
    }

    if ctx["scope"] == "Branch Level":
        filters["custom_client_branch"] = ctx["branch"]

    return frappe.get_all(
        "Service Ticket",
        filters=filters,
        fields=[
            "name",
            "custom_subject",
            "custom_client_branch",
            "custom_target_equipment",
            "custom_target_component_name",
            "custom_ticket_status",
            "custom_opening_date",
            "creation",
            "modified",
            "custom_resolution_details"
        ],
        order_by="creation desc"
    )


# =======================================================================================
# DEDICATED CLIENT PORTAL Helpder FOR rENDERING TICKET/SERVICE LOGS AND mi PAGES        =
# =======================================================================================

@frappe.whitelist()
def client_portal_get_ticket_detail(ticket_name):
    if not ticket_name:
        frappe.throw("Ticket is required.")

    ctx = get_client_portal_context()

    ticket = frappe.db.get_value(
        "Service Ticket",
        ticket_name,
        [
            "name",
            "custom_customer",
            "custom_subject",
            "custom_description",
            "custom_ticket_status",
            "custom_priority",
            "custom_request_type",
            "custom_client_branch",
            "custom_target_equipment",
            "custom_parent_equipment",
            "custom_target_component_name",
            "custom_target_component",
            "custom_applicant",
            "custom_applicant_email",
            "custom_applicant_phone",
            "custom_opening_date",
            "custom_resolution_date",
            "custom_closed_date",
            "custom_resolution_details",
            "custom_wrong_equipment_reported",
            "custom_actual_equipment",
            "custom_equipment_change_reason"
        ],
        as_dict=True
    )

    equipment_display = None

    if ticket.get("custom_target_equipment"):
        equipment_display = frappe.db.get_value(
            "Installed Equipment",
            ticket.get("custom_target_equipment"),
            "custom_display_name"
        ) or frappe.db.get_value(
            "Installed Equipment",
            ticket.get("custom_target_equipment"),
            "custom_asset_name"
        )

    ticket["target_equipment_display"] = equipment_display or ticket.get("custom_target_equipment")

    #frappe.throw(str(ticket))
    if not ticket:
        frappe.throw("Ticket not found.")

    if ticket.get("custom_customer") != ctx["customer"]:
        frappe.throw("You are not allowed to view this ticket.", frappe.PermissionError)

    if ctx["scope"] == "Branch Level" and ticket.get("custom_client_branch") != ctx["branch"]:
        frappe.throw("You are not allowed to view this ticket.", frappe.PermissionError)

    interventions = frappe.get_all(
        "Mission Intervention",
        filters={
            "custom_service_ticket": ticket_name
        },
        fields=[
            "name",
            "custom_start_time",
            "custom_end_time",
            "custom_technician",
            "custom_intervention_type",
            "custom_work_outcome",
            "custom_hours_worked",
            "custom_work_progress"
        ],
        order_by="creation asc"
    )

    return {
        "ticket": ticket,
        "interventions": interventions
    }

@frappe.whitelist()
def client_portal_get_intervention_detail(intervention_name):
    if not intervention_name:
        frappe.throw("Intervention is required.")

    ctx = get_client_portal_context()

    mi = frappe.db.get_value(
        "Mission Intervention",
        intervention_name,
        [
            "name",
            "custom_service_ticket",
            "custom_parent_mission",
            "custom_parent_customer",
            "custom_branch",
            "custom_asset",
            "custom_target_component_name",
            "custom_component_item",
            "custom_component_group",
            "custom_component_serial",
            "custom_intervention_type",
            "custom_service_type",
            "custom_technician",
            "custom_start_time",
            "custom_end_time",
            "custom_hours_worked",
            "custom_work_outcome",
            "custom_work_progress",
            "custom_signatory_name",
            "custom_client_signature",
            "custom_tech_signature",
            "custom_quality_score",
            "custom_hse_score",
            "custom_swap_classification",            
            "custom_new_asset",
            "custom_asset_change_reason"
        ],
        as_dict=True
    )

    if not mi:
        frappe.throw("Intervention not found.")

    if mi.get("custom_parent_customer") != ctx["customer"]:
        frappe.throw("You are not allowed to view this intervention.", frappe.PermissionError)

    if ctx["scope"] == "Branch Level" and mi.get("custom_branch") != ctx["branch"]:
        frappe.throw("You are not allowed to view this intervention.", frappe.PermissionError)

    equipment_display = None
    if mi.get("custom_asset"):
        equipment_display = frappe.db.get_value(
            "Installed Equipment",
            mi.get("custom_asset"),
            "custom_asset_name"
        )

    new_equipment_display = None
    if mi.get("custom_new_asset"):
        new_equipment_display = frappe.db.get_value(
            "Installed Equipment",
            mi.get("custom_new_asset"),
            "custom_asset_name"
        )

    technician_display = mi.get("custom_technician")
    if mi.get("custom_technician"):
        technician_display = frappe.db.get_value(
            "User",
            mi.get("custom_technician"),
            "full_name"
        ) or mi.get("custom_technician")

    parts = []
    mi_doc = frappe.get_doc("Mission Intervention", intervention_name)

    for row in mi_doc.get("custom_parts_table") or []:
        parts.append({
            "item_code": row.get("custom_item_code"),
            "item_name": row.get("custom_item_name"),
            "qty": row.get("custom_qty"),
            "serial_no": row.get("custom_serial_no") or row.get("custom_serial_number")
        })

    return {
        "intervention": mi,
        "equipment_display": equipment_display or mi.get("custom_asset"),
        "new_equipment_display": new_equipment_display or mi.get("custom_new_asset"),
        "technician_display": technician_display,
        "parts": parts
    }

'''@frappe.whitelist()
def client_portal_get_service_logs(asset=None, component=None, component_serial=None, date_from=None, date_to=None, branch=None):
    ctx = get_client_portal_context()

    filters = {
        "custom_customer": ctx["customer"]
    }

    if ctx["scope"] == "Branch Level":
        filters["custom_branch"] = ctx["branch"]
    elif branch:
        filters["custom_branch"] = branch

    if asset:
        filters["custom_related_asset"] = asset

    if component_serial:
        filters["custom_component_serial"] = component_serial
    elif component:
        filters["custom_component_item"] = component

    if date_from:
        filters["custom_end_time"] = [">=", date_from]

    if date_to:
        filters["custom_end_time"] = ["<=", date_to]

    logs = frappe.get_all(
        "Asset Service Log",
        filters=filters,
        fields=[
            "name",
            "creation",
            "custom_end_time",
            "custom_related_asset",
            "custom_branch",
            "custom_service_ticket",
            "custom_mission_ref",
            "custom_intervention_ref",
            "custom_technician",
            "custom_intervention_type",
            "custom_work_outcome",
            "custom_notes",
            "custom_duration",
            "custom_component_item",
            "custom_component_group",
            "custom_component_serial"
        ],
        order_by="custom_end_time desc, creation desc",
        limit=200
    )

    for row in logs:
        row["equipment_display"] = frappe.db.get_value(
            "Installed Equipment",
            row.get("custom_related_asset"),
            "custom_asset_name"
        ) or row.get("custom_related_asset")

        row["technician_display"] = frappe.db.get_value(
            "User",
            row.get("custom_technician"),
            "full_name"
        ) or row.get("custom_technician")

    return logs'''

@frappe.whitelist()
def client_portal_get_service_logs(asset=None, component=None, component_serial=None, date_from=None, date_to=None, branch=None):
    ctx = get_client_portal_context()

    # Initialize filters as a list of conditions to prevent key overwriting
    filters = [
        ["custom_customer", "=", ctx["customer"]]
    ]

    if ctx["scope"] == "Branch Level":
        filters.append(["custom_branch", "=", ctx["branch"]])
    elif branch:
        filters.append(["custom_branch", "=", branch])

    if asset:
        filters.append(["custom_related_asset", "=", asset])

    if component_serial:
        filters.append(["custom_component_serial", "=", component_serial])
    elif component:
        filters.append(["custom_component_item", "=", component])

    if date_from:
        filters.append(["custom_end_time", ">=", date_from])

    if date_to:
        filters.append(["custom_end_time", "<=", date_to])

    logs = frappe.get_all(
        "Asset Service Log",
        filters=filters,
        fields=[
            "name",
            "creation",
            "custom_end_time",
            "custom_related_asset",
            "custom_branch",
            "custom_service_ticket",
            "custom_mission_ref",
            "custom_intervention_ref",
            "custom_technician",
            "custom_intervention_type",
            "custom_work_outcome",
            "custom_notes",
            "custom_duration",
            "custom_component_item",
            "custom_component_group",
            "custom_component_serial"
        ],
        order_by="custom_end_time desc, creation desc",
        limit=200
    )

    for row in logs:
        row["equipment_display"] = frappe.db.get_value(
            "Installed Equipment",
            row.get("custom_related_asset"),
            "custom_asset_name"
        ) or row.get("custom_related_asset")

        row["technician_display"] = frappe.db.get_value(
            "User",
            row.get("custom_technician"),
            "full_name"
        ) or row.get("custom_technician")

    return logs

import frappe

@frappe.whitelist()
def client_portal_get_lifecycle_logs(asset=None, branch=None, event_type=None, date_from=None, date_to=None):
    """Get lifecycle logs for customer"""
    
    ctx = get_client_portal_context()
    
    filters = {
        "custom_customer": ctx["customer"]
    }
    
    if ctx["scope"] == "Branch Level":
        filters["custom_branch"] = ctx["branch"]
    elif branch:
        filters["custom_branch"] = branch
    
    if asset:
        filters["custom_related_asset"] = asset
    
    if event_type:
        filters["custom_event"] = event_type
    
    if date_from:
        filters["custom_date"] = [">=", date_from]
    
    if date_to:
        filters["custom_date"] = ["<=", date_to]
    
    try:
        logs = frappe.get_all(
            "Asset Lifecycle Log",
            filters=filters,
            fields=[
                "name",
                "creation",
                "custom_date",
                "custom_branch",
                "custom_related_asset",
                "custom_event",
                "custom_event_source",
                "custom_action_taken",
                "custom_technician",
                "custom_service_ticket",
                "custom_intervention_ref",
                "custom_billing_analysis",
                "custom_new_asset",
                "custom_new_branch",
                "custom_component_item",
                "custom_component_serial",
                "custom_new_component_item",
                "custom_new_component_serial"
            ],
            order_by="custom_date desc, creation desc",
            limit=250
        )
        
        # Enrich with display names
        for row in logs:
            if row.get("custom_related_asset"):
                row["equipment_display"] = frappe.db.get_value(
                    "Installed Equipment",
                    row.get("custom_related_asset"),
                    "custom_asset_name"
                ) or row.get("custom_related_asset")
            else:
                row["equipment_display"] = "-"
            
            if row.get("custom_technician"):
                row["technician_display"] = frappe.db.get_value(
                    "User",
                    row.get("custom_technician"),
                    "full_name"
                ) or row.get("custom_technician")
            else:
                row["technician_display"] = "-"
        
        return logs
    
    except Exception as e:
        frappe.log_error(title="Client Portal Lifecycle API Error", message=frappe.get_traceback())
        return []


@frappe.whitelist()
def client_portal_get_preventive_maintenance(branch=None):
    """Return preventive-maintenance dates for equipment visible to the portal user.

    Security is derived from the logged-in Contact -> Customer mapping.
    Branch Level contacts are restricted to their assigned branch.
    """
    ctx = get_client_portal_context()

    if not ctx.get("customer"):
        frappe.throw("No Customer linked to this portal user.", frappe.PermissionError)

    filters = [
        ["Installed Equipment", "custom_parent_customer", "=", ctx["customer"]],
        ["Installed Equipment", "custom_next_maintenance_date", "is", "set"]
    ]

    if ctx.get("scope") == "Branch Level":
        if not ctx.get("branch"):
            frappe.throw("No branch is assigned to this Branch Level portal user.", frappe.PermissionError)
        filters.append(["Installed Equipment", "custom_branch", "=", ctx["branch"]])
    elif branch:
        filters.append(["Installed Equipment", "custom_branch", "=", branch])

    rows = frappe.get_all(
        "Installed Equipment",
        filters=filters,
        fields=[
            "name",
            "custom_branch",
            "custom_asset_name",
            "custom_display_name",
            "custom_asset_category",
            "custom_asset_status",
            "custom_next_maintenance_date"
        ],
        order_by="custom_next_maintenance_date asc, custom_branch asc, custom_asset_name asc",
        limit=500
    )

    branch_names = {}
    for row in rows:
        branch_id = row.get("custom_branch")
        if branch_id and branch_id not in branch_names:
            branch_names[branch_id] = (
                frappe.db.get_value("Client Branch", branch_id, "custom_branch")
                or branch_id
            )

        row["branch_display"] = branch_names.get(branch_id) or branch_id or "-"
        row["equipment_display"] = (
            row.get("custom_display_name")
            or row.get("custom_asset_name")
            or row.get("name")
        )

    return rows

@frappe.whitelist()
def client_portal_get_planned_interventions(branch=None, mission_type=None, date_from=None, date_to=None):
    """Get planned and overdue interventions from Tech Mission for the logged-in customer.

    Includes Scheduled and Ongoing missions with a planned date, even when the
    planned date has already passed. Completed, Closed and Cancelled missions
    are intentionally excluded because this view represents work still to be done.
    """

    ctx = get_client_portal_context()

    # Keep unfinished planned work visible even when its planned date is overdue.
    valid_statuses = ["Scheduled", "Ongoing"]

    filters = [
        ["Tech Mission", "custom_parent_customer", "=", ctx["customer"]],
        ["Tech Mission", "custom_mission_status", "in", valid_statuses],
        ["Tech Mission", "custom_planned_starttime", "is", "set"]
    ]

    if ctx["scope"] == "Branch Level":
        filters.append(["Tech Mission", "custom_branch", "=", ctx["branch"]])
    elif branch:
        filters.append(["Tech Mission", "custom_branch", "=", branch])

    if mission_type:
        filters.append(["Tech Mission", "custom_service_type", "=", mission_type])

    # Optional user-selected date filters still apply when provided.
    if date_from:
        filters.append(["Tech Mission", "custom_planned_starttime", ">=", date_from])

    if date_to:
        filters.append(["Tech Mission", "custom_planned_endtime", "<=", date_to])

    missions = frappe.get_all(
        "Tech Mission",
        filters=filters,
        fields=[
            "name",
            "custom_planned_starttime",
            "custom_planned_endtime",
            "custom_asset",
            "custom_branch",
            "custom_service_type",
            "custom_ticket_type",
            "custom_mission_status",
            "custom_subject",
            "custom_target_component_name",
            "custom_parent_equipment",
            "custom_component_item",
            "custom_component_serial",
            "custom_applicant",
            "custom_applicant_email",
            "custom_applicant_phone",
            "custom_request_description",
            "custom_planned_team"
        ],
        order_by="custom_planned_starttime asc",
        limit=100
    )

    # Enrich with display names
    for row in missions:
        if row.get("custom_asset"):
            row["equipment_display"] = frappe.db.get_value(
                "Installed Equipment",
                row.get("custom_asset"),
                "custom_asset_name"
            ) or row.get("custom_asset")
        else:
            row["equipment_display"] = row.get("custom_parent_equipment", "-")

        if row.get("custom_planned_team"):
            team_list = frappe.get_list(
                "Planned Technicians",
                filters={"parent": row.get("name"), "parenttype": "Tech Mission"},
                fields=["custom_technician"],
                limit=1
            )
            if team_list:
                tech_id = team_list[0].get("custom_technician")
                row["technician_display"] = frappe.db.get_value(
                    "User",
                    tech_id,
                    "full_name"
                ) or tech_id
            else:
                row["technician_display"] = "-"
        else:
            row["technician_display"] = "-"

    return missions


# ============================================================
# HSE INVESTIGATION TICKET
# ============================================================

@frappe.whitelist()
def create_investigation_ticket(hse_report_name):
    if not hse_report_name:
        frappe.throw("HSE Incident Report is required.")

    report = frappe.get_doc("HSE Incident Report", hse_report_name)

    if report.get("custom_investigation_ticket"):
        return {"ticket": report.custom_investigation_ticket}

    ticket = frappe.new_doc("Service Ticket")

    _safe_set(ticket, "custom_customer", report.get("custom_customer"))
    _safe_set(ticket, "custom_client_branch", report.get("custom_branch"))
    _safe_set(ticket, "custom_target_equipment", report.get("custom_equipment"))

    _safe_set(
        ticket,
        "custom_subject",
        "HSE Investigation - " + (report.get("custom_incident_type_name") or report.name)
    )

    description = (
        "HSE Incident Report: " + report.name + "\n"
        + "Incident Type: " + str(report.get("custom_incident_type_name") or "") + "\n"
        + "Severity: " + str(report.get("custom_severity") or "") + "\n\n"
        + str(report.get("custom_description") or "")
    )

    _safe_set(ticket, "custom_description", description)
    _safe_set(ticket, "custom_request_type", "General Request")
    _safe_set(ticket, "custom_ticket_type", "Incident Investigation")
    _safe_set(ticket, "custom_priority", "High" if report.get("custom_severity") in ["High", "Critical"] else "Normal")
    _safe_set(ticket, "custom_ticket_status", "Open")
    _safe_set(ticket, "custom_planning_status", "Not Required")
    _safe_set(ticket, "custom_commercial_status", "N/A")
    _safe_set(ticket, "custom_raised_by", _current_user_display_name())
    _safe_set(ticket, "custom_hse_incident_report", report.name)

    ticket.insert(ignore_permissions=True)

    report.custom_investigation_ticket = ticket.name
    report.custom_incident_status = "Investigation Created"
    report.save(ignore_permissions=True)

    frappe.db.commit()

    return {"ticket": ticket.name}

# ============================================================
# HSE INCIDENT REPORTS
# Creates HSE Incident Report records from Mission Intervention
# child table: custom_incidents (MI Incident Detail)
# Call from MI After Submit Server Script:
#     maintenance_app.api.create_hse_incident_reports(doc)
# ============================================================

def create_hse_incident_reports(mi):
    if not mi or not mi.get("custom_incidents"):
        return {"created": 0, "skipped": 0}

    created = 0
    skipped = 0

    for row in mi.get("custom_incidents") or []:
        if not row.get("custom_incident_type_name"):
            skipped += 1
            continue

        existing = frappe.db.exists("HSE Incident Report", {
            "custom_mission_intervention": mi.name,
            "custom_mi_incident_row": row.name
        })

        if existing:
            skipped += 1
            continue

        incident = frappe.new_doc("HSE Incident Report")

        incident.custom_incident_status = "Open"
        incident.custom_incident_type_name = row.get("custom_incident_type_name")
        incident.custom_severity = row.get("custom_severity")
        incident.custom_incident_datetime = row.get("custom_incident_datetime")
        incident.custom_description = row.get("custom_description")
        incident.custom_immediate_action = row.get("custom_immediate_action")
        incident.custom_requires_investigation = row.get("custom_requires_investigation")
        incident.custom_photo = row.get("custom_photo")

        service_ticket = mi.get("custom_service_ticket") or mi.get("custom_parent_ticket")

        incident.custom_service_ticket = service_ticket
        incident.custom_tech_mission = mi.get("custom_parent_mission")
        incident.custom_mission_intervention = mi.name

        incident.custom_customer = mi.get("custom_parent_customer") or mi.get("custom_customer")
        incident.custom_branch = mi.get("custom_branch")
        incident.custom_equipment = (
            mi.get("custom_target_component_name")
            or mi.get("custom_parent_equipment")
            or mi.get("custom_asset")
        )
        incident.custom_component = (
            mi.get("custom_target_component_name")
            or mi.get("custom_component_item")
            or mi.get("custom_component_group")
        )
        incident.custom_technician = get_mi_technicians(mi)
        incident.custom_mi_incident_row = row.name

        incident.insert(ignore_permissions=True)

        if service_ticket:
            ticket = frappe.get_doc("Service Ticket", service_ticket)

            exists_on_ticket = False
            for trow in ticket.get("custom_incidents") or []:
                if trow.get("custom_hse_incident_report") == incident.name:
                    exists_on_ticket = True
                    break

            if not exists_on_ticket:
                ticket.append("custom_incidents", {
                    "custom_hse_incident_report": incident.name,
                    "custom_incident_type": row.get("custom_incident_type_name"),
                    "custom_severity": row.get("custom_severity"),
                    "custom_status": "Open",
                    "custom_incident_datetime": row.get("custom_incident_datetime"),
                    "custom_description": row.get("custom_description")
                })

            if ticket.meta.has_field("custom_has_incident"):
                ticket.custom_has_incident = 1

            if ticket.meta.has_field("custom_incident_count"):
                ticket.custom_incident_count = len(ticket.get("custom_incidents") or [])

            ticket.save(ignore_permissions=True)

        created += 1

    return {"created": created, "skipped": skipped}


def get_mi_technicians(mi):
    names = []

    for table_field in ["custom_intervention_team", "custom_planned_team", "custom_team"]:
        for row in mi.get(table_field) or []:
            technician = row.get("custom_technician")
            if technician and technician not in names:
                names.append(technician)

    if not names:
        technician = mi.get("custom_technician") or mi.owner or frappe.session.user
        names.append(technician)

    return ", ".join(names)


###########################################
# component filtering for same site swap  #
###########################################


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_same_site_replacement_components(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters
):
    filters = filters or {}

    current_equipment = filters.get("current_equipment")
    outgoing_component = filters.get("outgoing_component")

    if not current_equipment or not outgoing_component:
        return []

    current_equipment_values = frappe.db.get_value(
        "Installed Equipment",
        current_equipment,
        [
            "custom_parent_customer",
            "custom_branch",
            "custom_asset_type",
            "custom_asset_category"
        ],
        as_dict=True
    )

    if not current_equipment_values:
        return []

    outgoing_values = frappe.db.get_value(
        "Equipment Component",
        outgoing_component,
        [
            "custom_component_group",
            "custom_equipment_type"
        ],
        as_dict=True
    )

    if not outgoing_values:
        return []

    return frappe.db.sql(
        """
        SELECT
            ec.name,
            ec.custom_display_name,
            ec.custom_serial_number,
            ec.custom_parent_equipment
        FROM `tabEquipment Component` ec

        INNER JOIN `tabInstalled Equipment` parent_equipment
            ON parent_equipment.name = ec.custom_parent_equipment

        WHERE
            ec.name != %(outgoing_component)s

            AND ec.custom_parent_equipment IS NOT NULL
            AND ec.custom_parent_equipment != %(current_equipment)s

            AND ec.custom_customer = %(customer)s
            AND ec.custom_branch = %(branch)s

            AND ec.custom_status = 'Installed'

            AND (
                %(component_group)s IS NULL
                OR %(component_group)s = ''
                OR ec.custom_component_group = %(component_group)s
            )

            AND (
                %(equipment_type)s IS NULL
                OR %(equipment_type)s = ''
                OR ec.custom_equipment_type = %(equipment_type)s
            )

            AND (
                %(asset_type)s IS NULL
                OR %(asset_type)s = ''
                OR parent_equipment.custom_asset_type = %(asset_type)s
            )

            AND (
                %(asset_category)s IS NULL
                OR %(asset_category)s = ''
                OR parent_equipment.custom_asset_category = %(asset_category)s
            )

            AND (
                ec.name LIKE %(txt)s
                OR ec.custom_display_name LIKE %(txt)s
                OR ec.custom_serial_number LIKE %(txt)s
                OR ec.custom_parent_equipment LIKE %(txt)s
            )

        ORDER BY
            ec.custom_display_name,
            ec.custom_parent_equipment

        LIMIT %(page_len)s OFFSET %(start)s
        """,
        {
            "current_equipment": current_equipment,
            "outgoing_component": outgoing_component,
            "customer": current_equipment_values.get(
                "custom_parent_customer"
            ),
            "branch": current_equipment_values.get("custom_branch"),
            "asset_type": current_equipment_values.get(
                "custom_asset_type"
            ),
            "asset_category": current_equipment_values.get(
                "custom_asset_category"
            ),
            "component_group": outgoing_values.get(
                "custom_component_group"
            ),
            "equipment_type": outgoing_values.get(
                "custom_equipment_type"
            ),
            "txt": "%" + txt + "%",
            "page_len": page_len,
            "start": start
        }
    )

# ============================================================
# MISSION INTERVENTION - REPLACEMENT COMPONENT SEARCH
# ============================================================

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_replacement_components(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters
):
    """
    Link-field query for Mission Intervention.custom_new_equipment_component.

    Supported replacement sources:
    - Same Site
    - Another Site
    - Workshop
    - Stock
    - Customer Supplied
    - New Component

    The selected value is always an Equipment Component permanent ID
    such as COMP-00045.

    For Stock, availability is verified against ERPNext Serial No:
    Equipment Component.custom_item + custom_serial_number must match
    an active serial currently located in the selected warehouse.
    """

    filters = filters or {}

    replacement_source = filters.get("replacement_source")
    current_equipment = filters.get("current_equipment")
    outgoing_component = filters.get("outgoing_component")
    customer = filters.get("customer")
    current_branch = filters.get("current_branch")
    source_branch = filters.get("source_branch")
    source_warehouse = filters.get("source_warehouse")
    company_workshop = filters.get("company_workshop")

    if not replacement_source or not current_equipment:
        return []

    # During component replacement, compatibility is derived from the
    # outgoing component. During installation-only there is no outgoing
    # component, so the query remains available without that comparison.
    outgoing_values = {}

    if outgoing_component:
        outgoing_values = frappe.db.get_value(
            "Equipment Component",
            outgoing_component,
            [
                "custom_component_group",
                "custom_equipment_type"
            ],
            as_dict=True
        ) or {}

    current_equipment_values = frappe.db.get_value(
        "Installed Equipment",
        current_equipment,
        [
            "custom_parent_customer",
            "custom_branch",
            "custom_asset_type",
            "custom_asset_category"
        ],
        as_dict=True
    )

    if not current_equipment_values:
        return []

    customer = (
        customer
        or current_equipment_values.get("custom_parent_customer")
    )

    current_branch = (
        current_branch
        or current_equipment_values.get("custom_branch")
    )

    values = {
        "outgoing_component": outgoing_component,
        "current_equipment": current_equipment,
        "customer": customer,
        "current_branch": current_branch,
        "source_branch": source_branch,
        "source_warehouse": source_warehouse,
        "company_workshop": company_workshop,
        "component_group": outgoing_values.get("custom_component_group"),
        "equipment_type": outgoing_values.get("custom_equipment_type"),
        "asset_type": current_equipment_values.get("custom_asset_type"),
        "asset_category": current_equipment_values.get(
            "custom_asset_category"
        ),
        "txt": "%" + (txt or "") + "%",
        "page_len": page_len,
        "start": start
    }

    compatibility_conditions = """
        AND (
            %(component_group)s IS NULL
            OR %(component_group)s = ''
            OR ec.custom_component_group = %(component_group)s
        )

        AND (
            %(equipment_type)s IS NULL
            OR %(equipment_type)s = ''
            OR ec.custom_equipment_type = %(equipment_type)s
        )
    """

    text_condition = """
        AND (
            ec.name LIKE %(txt)s
            OR IFNULL(ec.custom_display_name, '') LIKE %(txt)s
            OR IFNULL(ec.custom_serial_number, '') LIKE %(txt)s
            OR IFNULL(ec.custom_make, '') LIKE %(txt)s
            OR IFNULL(ec.custom_model, '') LIKE %(txt)s
            OR IFNULL(ec.custom_part_number, '') LIKE %(txt)s
        )
    """

    select_columns = """
        SELECT DISTINCT
            ec.name,
            CONCAT_WS(
                ' | ',
                NULLIF(ec.custom_display_name, ''),
                NULLIF(ec.custom_serial_number, ''),
                NULLIF(ec.custom_parent_equipment, '')
            ) AS description
    """

    common_conditions = """
        WHERE
            (
                %(outgoing_component)s IS NULL
                OR %(outgoing_component)s = ''
                OR ec.name != %(outgoing_component)s
            )
    """

    # --------------------------------------------------------
    # SAME SITE
    # Existing installed component on another equipment at
    # the same customer branch.
    # --------------------------------------------------------
    if replacement_source == "Same Site":
        return frappe.db.sql(
            select_columns
            + """
            FROM `tabEquipment Component` ec
            INNER JOIN `tabInstalled Equipment` ie
                ON ie.name = ec.custom_parent_equipment
            """
            + common_conditions
            + """
                AND ec.custom_status = 'Installed'
                AND ec.custom_parent_equipment IS NOT NULL
                AND ec.custom_parent_equipment != %(current_equipment)s
                AND ec.custom_customer = %(customer)s
                AND ec.custom_branch = %(current_branch)s

                AND (
                    %(asset_type)s IS NULL
                    OR %(asset_type)s = ''
                    OR ie.custom_asset_type = %(asset_type)s
                )

                AND (
                    %(asset_category)s IS NULL
                    OR %(asset_category)s = ''
                    OR ie.custom_asset_category = %(asset_category)s
                )
            """
            + compatibility_conditions
            + text_condition
            + """
            ORDER BY ec.custom_display_name, ec.custom_parent_equipment
            LIMIT %(page_len)s OFFSET %(start)s
            """,
            values
        )

    # --------------------------------------------------------
    # ANOTHER SITE
    # Existing installed component on another equipment at
    # the selected source branch.
    # --------------------------------------------------------
    if replacement_source == "Another Site":
        if not source_branch:
            return []

        return frappe.db.sql(
            select_columns
            + """
            FROM `tabEquipment Component` ec
            INNER JOIN `tabInstalled Equipment` ie
                ON ie.name = ec.custom_parent_equipment
            """
            + common_conditions
            + """
                AND ec.custom_status = 'Installed'
                AND ec.custom_parent_equipment IS NOT NULL
                AND ec.custom_parent_equipment != %(current_equipment)s
                AND ec.custom_customer = %(customer)s
                AND ec.custom_branch = %(source_branch)s

                AND (
                    %(asset_type)s IS NULL
                    OR %(asset_type)s = ''
                    OR ie.custom_asset_type = %(asset_type)s
                )

                AND (
                    %(asset_category)s IS NULL
                    OR %(asset_category)s = ''
                    OR ie.custom_asset_category = %(asset_category)s
                )
            """
            + compatibility_conditions
            + text_condition
            + """
            ORDER BY ec.custom_display_name, ec.custom_parent_equipment
            LIMIT %(page_len)s OFFSET %(start)s
            """,
            values
        )

    # --------------------------------------------------------
    # STOCK
    # Equipment Component must be linked to an ERPNext Item,
    # have a serial number, be uninstalled, and its Serial No
    # must currently be in the selected warehouse.
    # --------------------------------------------------------
    if replacement_source == "Stock":
        if not source_warehouse:
            return []

        serial_meta = frappe.get_meta("Serial No")

        if (
            not serial_meta.has_field("item_code")
            or not serial_meta.has_field("warehouse")
        ):
            return []

        serial_status_condition = ""

        if serial_meta.has_field("status"):
            serial_status_condition = """
                AND IFNULL(sn.status, 'Active') NOT IN (
                    'Inactive',
                    'Delivered',
                    'Consumed'
                )
            """

        return frappe.db.sql(
            select_columns
            + """
            FROM `tabEquipment Component` ec
            INNER JOIN `tabSerial No` sn
                ON sn.name = ec.custom_serial_number
                AND sn.item_code = ec.custom_item
            """
            + common_conditions
            + """
                AND ec.custom_parent_equipment IS NULL
                AND ec.custom_item IS NOT NULL
                AND ec.custom_item != ''
                AND ec.custom_serial_number IS NOT NULL
                AND ec.custom_serial_number != ''
                AND ec.custom_status IN ('Available', 'Repaired')
                AND sn.warehouse = %(source_warehouse)s
            """
            + serial_status_condition
            + compatibility_conditions
            + text_condition
            + """
            ORDER BY ec.custom_display_name, ec.custom_serial_number
            LIMIT %(page_len)s OFFSET %(start)s
            """,
            values
        )

    # --------------------------------------------------------
    # WORKSHOP
    # Repaired, uninstalled components. Where the optional
    # workshop link exists on Equipment Component, also filter
    # by the selected workshop.
    # --------------------------------------------------------
    if replacement_source == "Workshop":
        if not company_workshop:
            return []

        workshop_condition = ""

        if frappe.get_meta("Equipment Component").has_field(
            "custom_company_workshop"
        ):
            workshop_condition = """
                AND ec.custom_company_workshop = %(company_workshop)s
            """

        return frappe.db.sql(
            select_columns
            + """
            FROM `tabEquipment Component` ec
            """
            + common_conditions
            + """
                AND ec.custom_parent_equipment IS NULL
                AND ec.custom_status = 'Repaired'
            """
            + workshop_condition
            + compatibility_conditions
            + text_condition
            + """
            ORDER BY ec.custom_display_name, ec.custom_serial_number
            LIMIT %(page_len)s OFFSET %(start)s
            """,
            values
        )

    # --------------------------------------------------------
    # CUSTOMER SUPPLIED
    # Existing customer-owned/uninstalled component records.
    # A separate create-component action is still needed when
    # the supplied component has not yet been registered.
    # --------------------------------------------------------
    if replacement_source == "Customer Supplied":
        return frappe.db.sql(
            select_columns
            + """
            FROM `tabEquipment Component` ec
            """
            + common_conditions
            + """
                AND ec.custom_parent_equipment IS NULL
                AND ec.custom_customer = %(customer)s
                AND ec.custom_status IN ('Available', 'Repaired')
            """
            + compatibility_conditions
            + text_condition
            + """
            ORDER BY ec.custom_display_name, ec.custom_serial_number
            LIMIT %(page_len)s OFFSET %(start)s
            """,
            values
        )

    # --------------------------------------------------------
    # NEW COMPONENT
    # Shows already-created available component masters.
    # Creating a brand-new COMP record from the MI will be
    # handled by a separate button/dialog.
    # --------------------------------------------------------
    if replacement_source == "New Component":
        return frappe.db.sql(
            select_columns
            + """
            FROM `tabEquipment Component` ec
            """
            + common_conditions
            + """
                AND (
                    ec.custom_parent_equipment IS NULL
                    OR ec.custom_parent_equipment = ''
                )
                AND TRIM(IFNULL(ec.custom_status, '')) = 'Available'
            """
            + compatibility_conditions
            + text_condition
            + """
            ORDER BY ec.custom_display_name, ec.custom_serial_number
            LIMIT %(page_len)s OFFSET %(start)s
            """,
            values
        )

    return []

# ============================================================
# MISSION INTERVENTION - STOCK COMPONENT SELECTION
# ============================================================

def _get_component_item_defaults(item_code):
    """
    Return Equipment Component defaults from Item.
    Every field is read defensively so optional custom fields do not break
    the workflow.
    """
    item = frappe.get_doc("Item", item_code)

    return {
        "item_code": item.name,
        "item_name": item.get("item_name") or item.name,
        "brand": item.get("brand") or "",
        "component_group": (
            item.get("custom_component_group")
            or item.get("custom_component_equipment_group")
            or ""
        ),
        "equipment_type": item.get("custom_equipment_type") or "",
        "model": (
            item.get("custom_default_component_model")
            or item.get("custom_default_model")
            or ""
        ),
        "part_number": (
            item.get("custom_component_part_number")
            or item.get("custom_part_number")
            or ""
        )
    }


def _validate_stock_serial(item_code, serial_no, warehouse):
    """
    Confirm that one exact ERPNext Serial No belongs to the selected Item
    and is currently located in the selected warehouse.
    """
    if not item_code:
        frappe.throw("Item is required.")

    if not serial_no:
        frappe.throw("Serial No is required.")

    if not warehouse:
        frappe.throw("Source Warehouse is required.")

    serial_values = frappe.db.get_value(
        "Serial No",
        serial_no,
        ["item_code", "warehouse"],
        as_dict=True
    )

    if not serial_values:
        frappe.throw(
            "ERPNext Serial No was not found: " + str(serial_no)
        )

    if serial_values.get("item_code") != item_code:
        frappe.throw(
            "Serial No "
            + str(serial_no)
            + " belongs to Item "
            + str(serial_values.get("item_code") or "")
            + ", not "
            + str(item_code)
            + "."
        )

    if serial_values.get("warehouse") != warehouse:
        frappe.throw(
            "Serial No "
            + str(serial_no)
            + " is not currently available in Warehouse "
            + str(warehouse)
            + "."
        )

    return serial_values


@frappe.whitelist()
def get_stock_component_items(
    warehouse,
    outgoing_component=None,
    search_text=None
):
    """
    Return serialized Items that are physically available in the selected
    warehouse and are allowed to become Equipment Components.

    Compatibility is based on the outgoing Equipment Component's
    Component Group and Equipment Type when those values are available.
    """
    if not warehouse:
        return []

    item_meta = frappe.get_meta("Item")
    serial_meta = frappe.get_meta("Serial No")

    if (
        not item_meta.has_field("custom_is_equipment_component")
        or not serial_meta.has_field("warehouse")
        or not serial_meta.has_field("item_code")
    ):
        return []

    outgoing_group = ""
    outgoing_type = ""

    if outgoing_component:
        outgoing_values = frappe.db.get_value(
            "Equipment Component",
            outgoing_component,
            ["custom_component_group", "custom_equipment_type"],
            as_dict=True
        ) or {}

        outgoing_group = outgoing_values.get("custom_component_group") or ""
        outgoing_type = outgoing_values.get("custom_equipment_type") or ""

    values = {
        "warehouse": warehouse,
        "outgoing_group": outgoing_group,
        "outgoing_type": outgoing_type,
        "txt": "%" + (search_text or "") + "%"
    }

    group_condition = ""
    if item_meta.has_field("custom_component_group"):
        group_condition = """
            AND (
                %(outgoing_group)s = ''
                OR i.custom_component_group = %(outgoing_group)s
            )
        """
    elif item_meta.has_field("custom_component_equipment_group"):
        group_condition = """
            AND (
                %(outgoing_group)s = ''
                OR i.custom_component_equipment_group = %(outgoing_group)s
            )
        """

    type_condition = ""
    if item_meta.has_field("custom_equipment_type"):
        type_condition = """
            AND (
                %(outgoing_type)s = ''
                OR i.custom_equipment_type = %(outgoing_type)s
            )
        """

    status_condition = ""
    if serial_meta.has_field("status"):
        status_condition = """
            AND IFNULL(sn.status, 'Active') NOT IN (
                'Inactive',
                'Delivered',
                'Consumed'
            )
        """

    rows = frappe.db.sql(
        """
        SELECT
            i.name AS item_code,
            i.item_name,
            i.brand,
            COUNT(DISTINCT sn.name) AS available_serial_count
        FROM `tabItem` i
        INNER JOIN `tabSerial No` sn
            ON sn.item_code = i.name
        WHERE
            i.disabled = 0
            AND i.is_stock_item = 1
            AND i.has_serial_no = 1
            AND i.custom_is_equipment_component = 1
            AND sn.warehouse = %(warehouse)s
            AND (
                i.name LIKE %(txt)s
                OR IFNULL(i.item_name, '') LIKE %(txt)s
                OR IFNULL(i.brand, '') LIKE %(txt)s
            )
        """
        + status_condition
        + group_condition
        + type_condition
        + """
        GROUP BY
            i.name,
            i.item_name,
            i.brand
        ORDER BY
            i.item_name,
            i.name
        """,
        values,
        as_dict=True
    )

    return rows


@frappe.whitelist()
def get_available_component_serials(
    warehouse,
    item_code,
    search_text=None
):
    """
    Return the exact Serial Nos for one serialized Item currently available
    in the selected warehouse.

    Also returns the associated Equipment Component when the serial has
    already entered the maintenance lifecycle.
    """
    if not warehouse or not item_code:
        return []

    serial_meta = frappe.get_meta("Serial No")

    filters = {
        "warehouse": warehouse,
        "item_code": item_code
    }

    fields = ["name", "item_code", "warehouse"]

    if serial_meta.has_field("status"):
        fields.append("status")

    if serial_meta.has_field("custom_equipment_component"):
        fields.append("custom_equipment_component")

    serial_rows = frappe.get_all(
        "Serial No",
        filters=filters,
        fields=fields,
        order_by="name asc",
        limit_page_length=500
    )

    txt = (search_text or "").strip().lower()
    output = []

    for row in serial_rows:
        if txt and txt not in (row.get("name") or "").lower():
            continue

        status = row.get("status") or "Active"

        if status in ["Inactive", "Delivered", "Consumed"]:
            continue

        component_name = row.get("custom_equipment_component")

        if not component_name:
            matches = frappe.get_all(
                "Equipment Component",
                filters={
                    "custom_item": item_code,
                    "custom_serial_number": row.get("name")
                },
                fields=["name"],
                limit_page_length=2
            )

            if len(matches) > 1:
                frappe.throw(
                    "Multiple Equipment Component records exist for Item "
                    + str(item_code)
                    + " and Serial No "
                    + str(row.get("name"))
                    + "."
                )

            if matches:
                component_name = matches[0].name

        output.append({
            "serial_no": row.get("name"),
            "item_code": item_code,
            "warehouse": warehouse,
            "equipment_component": component_name or ""
        })

    return output


@frappe.whitelist()
def find_or_create_stock_equipment_component(
    mi_name,
    item_code,
    serial_no,
    warehouse
):
    """
    Find the Equipment Component for one exact Item + Serial No, or create it
    on demand when the serialized stock unit is selected in a draft MI.

    The new component is created as Available. It becomes Installed only when
    the Mission Intervention is submitted.
    """
    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    mi = frappe.get_doc("Mission Intervention", mi_name)

    if mi.docstatus != 0:
        frappe.throw(
            "A stock component can only be selected while the Mission "
            "Intervention is in Draft."
        )

    if mi.get("custom_replacement_source") != "Stock":
        frappe.throw(
            "Replacement Source must be Stock before selecting a warehouse component."
        )

    if mi.get("custom_replacement_warehouse") != warehouse:
        frappe.throw(
            "The selected warehouse does not match the Mission Intervention "
            "Replacement Source Warehouse."
        )

    _validate_stock_serial(item_code, serial_no, warehouse)

    item = frappe.get_doc("Item", item_code)

    if not item.get("is_stock_item"):
        frappe.throw("The selected Item is not a stock Item.")

    if not item.get("has_serial_no"):
        frappe.throw("The selected Item is not configured for Serial Nos.")

    if (
        item.meta.has_field("custom_is_equipment_component")
        and not item.get("custom_is_equipment_component")
    ):
        frappe.throw(
            "The selected Item is not marked as an Equipment Component Item."
        )

    defaults = _get_component_item_defaults(item_code)

    # Check the reverse link first.
    linked_component = None
    serial_meta = frappe.get_meta("Serial No")

    if serial_meta.has_field("custom_equipment_component"):
        linked_component = frappe.db.get_value(
            "Serial No",
            serial_no,
            "custom_equipment_component"
        )

    matches = frappe.get_all(
        "Equipment Component",
        filters={
            "custom_item": item_code,
            "custom_serial_number": serial_no
        },
        fields=[
            "name",
            "custom_status",
            "custom_parent_equipment"
        ],
        limit_page_length=3
    )

    if len(matches) > 1:
        frappe.throw(
            "Multiple Equipment Component records exist for Item "
            + str(item_code)
            + " and Serial No "
            + str(serial_no)
            + ". Please correct the duplicates before continuing."
        )

    component_name = linked_component or (
        matches[0].name if matches else None
    )

    created = False

    if component_name:
        if not frappe.db.exists("Equipment Component", component_name):
            frappe.throw(
                "Serial No "
                + str(serial_no)
                + " links to missing Equipment Component "
                + str(component_name)
                + "."
            )

        component = frappe.get_doc(
            "Equipment Component",
            component_name
        )

        if component.get("custom_item") != item_code:
            frappe.throw(
                "The linked Equipment Component belongs to a different Item."
            )

        if component.get("custom_serial_number") != serial_no:
            frappe.throw(
                "The linked Equipment Component has a different Serial Number."
            )

        if component.get("custom_parent_equipment"):
            frappe.throw(
                "The selected Equipment Component is already installed on "
                + str(component.get("custom_parent_equipment"))
                + "."
            )

        if component.get("custom_status") not in [
            "Available",
            "Repaired"
        ]:
            frappe.throw(
                "The selected Equipment Component has status "
                + str(component.get("custom_status"))
                + " and cannot be installed from stock."
            )

    else:
        component = frappe.new_doc("Equipment Component")

        if component.meta.has_field("custom_item"):
            component.custom_item = item_code

        if component.meta.has_field("custom_serial_number"):
            component.custom_serial_number = serial_no

        if component.meta.has_field("custom_status"):
            component.custom_status = "Available"

        if component.meta.has_field("custom_parent_equipment"):
            component.custom_parent_equipment = None

        if component.meta.has_field("custom_customer"):
            component.custom_customer = mi.get("custom_parent_customer")

        if component.meta.has_field("custom_branch"):
            component.custom_branch = mi.get("custom_branch")

        if component.meta.has_field("custom_component_group"):
            component.custom_component_group = defaults.get(
                "component_group"
            )

        if component.meta.has_field("custom_equipment_type"):
            component.custom_equipment_type = defaults.get(
                "equipment_type"
            )

        if component.meta.has_field("custom_display_name"):
            component_description = (
                defaults.get("item_name")
                or defaults.get("equipment_type")
                or defaults.get("component_group")
                or item_code
                or "Component"
            )

            # Temporary value before insert. It is replaced below after
            # the permanent COMP-xxxxx document ID has been generated.
            component.custom_display_name = str(component_description)

        if component.meta.has_field("custom_make"):
            component.custom_make = defaults.get("brand")

        if component.meta.has_field("custom_model"):
            component.custom_model = defaults.get("model")

        if component.meta.has_field("custom_part_number"):
            component.custom_part_number = defaults.get(
                "part_number"
            )

        component.insert(ignore_permissions=True)
        component_name = component.name

        if component.meta.has_field("custom_display_name"):
            component_description = (
                defaults.get("item_name")
                or defaults.get("equipment_type")
                or defaults.get("component_group")
                or item_code
                or "Component"
            )

            display_name_parts = [
                str(component_description),
                str(component.name)
            ]

            if serial_no:
                display_name_parts.append(str(serial_no))

            component_display_name = " - ".join(display_name_parts)

            component.db_set(
                "custom_display_name",
                component_display_name,
                update_modified=False
            )
            component.custom_display_name = component_display_name
        created = True

    # Keep Serial No -> Equipment Component synchronized.
    if serial_meta.has_field("custom_equipment_component"):
        frappe.db.set_value(
            "Serial No",
            serial_no,
            "custom_equipment_component",
            component_name,
            update_modified=False
        )

    return {
        "equipment_component": component_name,
        "created": created,
        "item_code": item_code,
        "item_name": defaults.get("item_name"),
        "brand": defaults.get("brand"),
        "serial_no": serial_no,
        "warehouse": warehouse,
        "qty": 1,
        "stock_movement_type": "Material Issue"
    }



# ============================================================
# INSTALLED EQUIPMENT - CONTROLLED WORKSHOP STATUS
# ============================================================

@frappe.whitelist()
def update_equipment_workshop_status(
    equipment_name,
    company_workshop,
    workshop_action,
    reason
):
    """
    Controlled administrative action for equipment physically held
    at a company workshop.

    Supported actions:
      - Ready Workshop Spare
      - Out of Service
      - Awaiting Component

    Equipment Status remains "In Workshop"; Operational Status
    describes whether the equipment is ready or unavailable.
    """

    if not equipment_name:
        frappe.throw("Installed Equipment is required.")

    if not company_workshop:
        frappe.throw("Company Workshop is required.")

    if not workshop_action:
        frappe.throw("Workshop Action is required.")

    if not reason:
        frappe.throw("Reason is required.")

    action_map = {
        "Ready Workshop Spare": "Operational",
        "Out of Service": "Out of Service",
        "Awaiting Component": "Awaiting Component"
    }

    if workshop_action not in action_map:
        frappe.throw("Invalid Workshop Action.")

    equipment = frappe.get_doc(
        "Installed Equipment",
        equipment_name
    )

    previous_status = equipment.get("custom_asset_status") or ""
    previous_health = ""
    previous_branch = equipment.get("custom_branch") or ""
    previous_workshop = equipment.get("custom_company_workshop") or ""

    if not equipment.meta.has_field("custom_asset_status"):
        frappe.throw(
            "Installed Equipment is missing custom_asset_status."
        )

    operational_status_field = None

    # Prefer known fieldnames, then fall back to the field label.
    for candidate in [
        "custom_operational_status",
        "operational_status",
        "custom_equipment_operational_status"
    ]:
        if equipment.meta.has_field(candidate):
            operational_status_field = candidate
            break

    if not operational_status_field:
        for df in equipment.meta.fields:
            if (
                (df.label or "").strip().lower() == "operational status"
            ):
                operational_status_field = df.fieldname
                break

    if not operational_status_field:
        frappe.throw(
            'Installed Equipment is missing a field labelled "Operational Status".'
        )

    previous_health = equipment.get(operational_status_field) or ""

    if not equipment.meta.has_field("custom_company_workshop"):
        frappe.throw(
            "Installed Equipment is missing custom_company_workshop."
        )

    equipment.custom_asset_status = "In Workshop"
    equipment.set(
        operational_status_field,
        action_map[workshop_action]
    )
    equipment.custom_company_workshop = company_workshop

    if equipment.meta.has_field("custom_location_status"):
        equipment.custom_location_status = "Workshop"

    # Workshop equipment is no longer assigned to a client site/customer.
    if equipment.meta.has_field("custom_branch"):
        equipment.custom_branch = ""

    if equipment.meta.has_field("custom_parent_customer"):
        equipment.custom_parent_customer = ""

    equipment.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "ok": True,
        "equipment": equipment.name,
        "asset_status": equipment.custom_asset_status,
        "operational_status": equipment.get(operational_status_field),
        "company_workshop": equipment.custom_company_workshop,
        "reason": reason,
        "previous": {
            "asset_status": previous_status,
            "operational_status": previous_health,
            "branch": previous_branch,
            "company_workshop": previous_workshop
        }
    }

# ============================================================
# TECH MISSION REASSIGNMENT / RESCHEDULING
# ============================================================


@frappe.whitelist()
def update_tech_mission_assignment_and_schedule(
    mission_name,
    action,
    reason,
    old_technician=None,
    new_technician=None,
    planned_start=None,
    planned_end=None,
    assigned_vehicle=None,
    vehicle=None
):
    """
    Shared server method for Tech Mission changes.

    Supported actions:
      - Replace Technician
      - Add Technician
      - Remove Technician
      - Change Vehicle
      - Reschedule Mission
      - Reassign and Reschedule

    Planning rules:
      - Technician -> Vehicle mapping lives in custom_planned_team.
      - The same company Vehicle may be assigned to multiple technicians.
      - If custom_external_vehicle is filled, an internal Vehicle may be blank.
      - Every successful TM planning change is written back to Service Ticket.
      - Draft MI is synchronized; submitted MI is preserved.
    """

    if not mission_name:
        frappe.throw("Tech Mission is required.")

    if not action:
        frappe.throw("Action is required.")

    if not reason:
        frappe.throw("Change Reason is required.")

    allowed_actions = [
        "Replace Technician",
        "Add Technician",
        "Remove Technician",
        "Change Vehicle",
        "Reschedule Mission",
        "Reassign and Reschedule"
    ]

    if action not in allowed_actions:
        frappe.throw("Invalid Tech Mission change action.")

    mission = frappe.get_doc("Tech Mission", mission_name)

    if mission.get("custom_mission_status") in [
        "Completed",
        "Closed",
        "Cancelled"
    ]:
        frappe.throw(
            "Completed, Closed, or Cancelled missions cannot be changed."
        )

    previous_start = mission.get("custom_planned_starttime")
    previous_end = mission.get("custom_planned_endtime")
    previous_vehicle = mission.get("custom_vehicle")
    previous_team = _get_mission_team_rows(mission)
    previous_technicians = [
        row["technician"] for row in previous_team
    ]

    team_rows = [
        {
            "technician": row["technician"],
            "vehicle": row.get("vehicle")
        }
        for row in previous_team
    ]

    schedule_action = action in [
        "Reschedule Mission",
        "Reassign and Reschedule"
    ]

    team_action = action in [
        "Replace Technician",
        "Add Technician",
        "Remove Technician",
        "Change Vehicle",
        "Reassign and Reschedule"
    ]

    # Backward compatibility with the old client argument.
    if assigned_vehicle is None and vehicle:
        assigned_vehicle = vehicle

    external_vehicle = mission.get("custom_external_vehicle")

    def require_vehicle_if_needed(technician, selected_vehicle):
        if not selected_vehicle and not external_vehicle:
            frappe.throw(
                "Please assign a Vehicle to technician "
                + str(technician)
                + ", or fill Hired / External Vehicle on the mission."
            )

    # --------------------------------------------------------
    # Team changes
    # --------------------------------------------------------
    if action in ["Replace Technician", "Reassign and Reschedule"]:
        if not old_technician:
            frappe.throw("Current Technician is required.")

        if not new_technician:
            frappe.throw("New Technician is required.")

        if old_technician == new_technician:
            frappe.throw(
                "New Technician must be different from Current Technician."
            )

        old_index = next(
            (
                i for i, row in enumerate(team_rows)
                if row["technician"] == old_technician
            ),
            None
        )

        if old_index is None:
            frappe.throw(
                "The selected Current Technician is not assigned to this mission."
            )

        if any(
            row["technician"] == new_technician
            for row in team_rows
            if row["technician"] != old_technician
        ):
            frappe.throw(
                "The New Technician is already assigned to this mission."
            )

        # Preserve the old technician's vehicle unless RM explicitly supplies
        # another one in the dialog.
        replacement_vehicle = (
            assigned_vehicle
            if assigned_vehicle is not None
            else team_rows[old_index].get("vehicle")
        )

        require_vehicle_if_needed(
            new_technician,
            replacement_vehicle
        )

        team_rows[old_index] = {
            "technician": new_technician,
            "vehicle": replacement_vehicle or None
        }

    elif action == "Add Technician":
        if not new_technician:
            frappe.throw("New Technician is required.")

        if any(
            row["technician"] == new_technician
            for row in team_rows
        ):
            frappe.throw(
                "This technician is already assigned to the mission."
            )

        require_vehicle_if_needed(
            new_technician,
            assigned_vehicle
        )

        team_rows.append({
            "technician": new_technician,
            "vehicle": assigned_vehicle or None
        })

    elif action == "Remove Technician":
        if not old_technician:
            frappe.throw("Technician to remove is required.")

        if not any(
            row["technician"] == old_technician
            for row in team_rows
        ):
            frappe.throw(
                "The selected technician is not assigned to this mission."
            )

        team_rows = [
            row for row in team_rows
            if row["technician"] != old_technician
        ]

        if not team_rows:
            frappe.throw(
                "At least one technician must remain assigned to the Tech Mission."
            )

    elif action == "Change Vehicle":
        if not old_technician:
            frappe.throw("Technician is required.")

        row = next(
            (
                row for row in team_rows
                if row["technician"] == old_technician
            ),
            None
        )

        if not row:
            frappe.throw(
                "The selected technician is not assigned to this mission."
            )

        require_vehicle_if_needed(
            old_technician,
            assigned_vehicle
        )

        row["vehicle"] = assigned_vehicle or None

    # --------------------------------------------------------
    # Schedule changes
    # --------------------------------------------------------
    new_start = previous_start
    new_end = previous_end

    if schedule_action:
        if not planned_start:
            frappe.throw("New Planned Start is required.")

        if not planned_end:
            frappe.throw("New Planned End is required.")

        new_start = frappe.utils.get_datetime(planned_start)
        new_end = frappe.utils.get_datetime(planned_end)

        if new_end <= new_start:
            frappe.throw(
                "New Planned End must be after New Planned Start."
            )

    # --------------------------------------------------------
    # Audit/history row
    # --------------------------------------------------------
    if mission.meta.has_field("custom_change_history"):
        mission.append(
            "custom_change_history",
            {
                "custom_change_type": _get_mission_change_type(action),
                "custom_previous_start": previous_start,
                "custom_previous_end": previous_end,
                "custom_previous_vehicle": previous_vehicle,
                "custom_previous_technicians": ", ".join(
                    previous_technicians
                ),
                "custom_change_reason": reason,
                "custom_changed_on": frappe.utils.now_datetime(),
                "custom_changed_by": frappe.session.user
            }
        )

    # --------------------------------------------------------
    # Apply live values
    # --------------------------------------------------------
    if team_action:
        _set_mission_team_rows(mission, team_rows)

    if schedule_action:
        mission.custom_planned_starttime = new_start
        mission.custom_planned_endtime = new_end

    if _mission_has_started_work(mission.name):
        mission.custom_mission_status = "Ongoing"
    elif mission.get("custom_mission_status") not in ["Ongoing", "On Hold"]:
        mission.custom_mission_status = "Scheduled"

    mission.save(ignore_permissions=True)

    # IMPORTANT: TM is the active planning editor after creation.
    # Dates, external vehicle and the full technician -> vehicle mapping
    # are written back to Service Ticket.
    _sync_service_ticket_planning_from_mission(mission)

    current_technicians = _get_mission_technicians(mission)

    removed_technicians = [
        tech for tech in previous_technicians
        if tech not in current_technicians
    ]

    added_technicians = [
        tech for tech in current_technicians
        if tech not in previous_technicians
    ]

    # --------------------------------------------------------
    # Synchronize ToDos
    # --------------------------------------------------------
    for technician in removed_technicians:
        _close_mission_todos_for_technician(
            mission,
            technician,
            reason,
            action
        )

    if schedule_action:
        for technician in current_technicians:
            _refresh_mission_todo(
                mission,
                technician,
                reason,
                action
            )

    for technician in added_technicians:
        _create_mission_todo_for_technician(
            mission,
            technician,
            reason,
            action
        )

    # --------------------------------------------------------
    # Synchronize draft MI only. Submitted MIs remain historical.
    # --------------------------------------------------------
    _sync_draft_mi_from_mission(mission)

    frappe.db.commit()

    return {
        "ok": True,
        "mission": mission.name,
        "action": action,
        "previous_technicians": previous_technicians,
        "current_technicians": current_technicians,
        "planned_start": mission.get("custom_planned_starttime"),
        "planned_end": mission.get("custom_planned_endtime"),
        "vehicle": mission.get("custom_vehicle"),
        "external_vehicle": mission.get("custom_external_vehicle"),
        "team": _get_mission_team_rows(mission),
        "mission_status": mission.get("custom_mission_status")
    }

def _get_mission_technicians(mission):
    technicians = []

    for row in mission.get("custom_planned_team") or []:
        technician = row.get("custom_technician")

        if technician and technician not in technicians:
            technicians.append(technician)

    return technicians


def _get_mission_team_rows(mission):
    """
    Return the current ordered technician -> vehicle mapping.
    """
    rows = []

    for row in mission.get("custom_planned_team") or []:
        technician = row.get("custom_technician")

        if not technician:
            continue

        rows.append({
            "technician": technician,
            "vehicle": row.get("custom_assigned_vehicle") or None
        })

    return rows


def _get_primary_assigned_vehicle(mission):
    """
    For the current MI design, the first Planned Team row is the primary tech.
    Its assigned company vehicle is the MI stock-source vehicle.
    """
    for row in mission.get("custom_planned_team") or []:
        if row.get("custom_technician"):
            return row.get("custom_assigned_vehicle") or None

    return None


def _get_common_team_vehicle(mission):
    """
    Legacy/summary parent vehicle:
    return a vehicle only when every nonblank assignment resolves to one
    common vehicle. Multiple vehicles -> blank.
    """
    vehicles = []

    for row in mission.get("custom_planned_team") or []:
        vehicle = row.get("custom_assigned_vehicle")

        if vehicle and vehicle not in vehicles:
            vehicles.append(vehicle)

    return vehicles[0] if len(vehicles) == 1 else None


def _set_mission_team_rows(mission, team_rows):
    mission.set("custom_planned_team", [])

    for item in team_rows:
        technician = item.get("technician")

        if not technician:
            continue

        mission.append(
            "custom_planned_team",
            {
                "custom_technician": technician,
                "custom_assigned_vehicle": item.get("vehicle") or None
            }
        )

    # Keep old mission-level field only as a compatibility summary.
    if mission.meta.has_field("custom_vehicle"):
        mission.custom_vehicle = _get_common_team_vehicle(mission)


def _get_mission_change_type(action):
    mapping = {
        "Replace Technician": "Technician Reassigned",
        "Add Technician": "Technician Added",
        "Remove Technician": "Technician Removed",
        "Change Vehicle": "Vehicle Assignment Changed",
        "Reschedule Mission": "Schedule Changed",
        "Reassign and Reschedule": "Schedule and Technician Changed"
    }

    return mapping.get(action, action)

def _mission_has_started_work(mission_name):
    return bool(
        frappe.db.exists(
            "Mission Intervention",
            {
                "custom_parent_mission": mission_name
            }
        )
    )


def _close_mission_todos_for_technician(
    mission,
    technician,
    reason,
    action
):
    todo_names = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Tech Mission",
            "reference_name": mission.name,
            "allocated_to": technician,
            "status": "Open"
        },
        pluck="name"
    )

    note = (
        "<br><br><b>Assignment changed.</b>"
        "<br><b>Action:</b> " + str(action)
        + "<br><b>Reason:</b> " + str(reason)
        + "<br><b>Changed By:</b> " + str(frappe.session.user)
        + "<br><b>Changed On:</b> "
        + str(frappe.utils.now_datetime())
    )

    for todo_name in todo_names:
        todo = frappe.get_doc("ToDo", todo_name)
        todo.status = "Closed"
        todo.description = (todo.description or "") + note
        todo.save(ignore_permissions=True)


def _create_mission_todo_for_technician(
    mission,
    technician,
    reason=None,
    action=None
):
    exists = frappe.db.exists(
        "ToDo",
        {
            "reference_type": "Tech Mission",
            "reference_name": mission.name,
            "allocated_to": technician,
            "status": "Open"
        }
    )

    if exists:
        return exists

    ticket = None

    if mission.get("custom_service_ticket"):
        ticket = frappe.get_doc(
            "Service Ticket",
            mission.custom_service_ticket
        )

    todo = frappe.new_doc("ToDo")
    todo.allocated_to = technician
    todo.assigned_by = frappe.session.user
    todo.reference_type = "Tech Mission"
    todo.reference_name = mission.name
    todo.status = "Open"
    todo.priority = _get_ticket_priority_from_mission(mission)
    todo.date = getdate(
        mission.get("custom_planned_starttime")
        or frappe.utils.nowdate()
    )
    todo.description = _build_direct_todo_description(
        mission,
        ticket
    )

    if reason:
        todo.description += (
            "<br><br><b>Assignment Update:</b> "
            + str(action or "Mission Updated")
            + "<br><b>Reason:</b> "
            + str(reason)
        )

    todo.insert(ignore_permissions=True)
    return todo.name


def _refresh_mission_todo(
    mission,
    technician,
    reason,
    action
):
    todo_name = frappe.db.get_value(
        "ToDo",
        {
            "reference_type": "Tech Mission",
            "reference_name": mission.name,
            "allocated_to": technician,
            "status": "Open"
        },
        "name"
    )

    if not todo_name:
        return _create_mission_todo_for_technician(
            mission,
            technician,
            reason,
            action
        )

    ticket = None

    if mission.get("custom_service_ticket"):
        ticket = frappe.get_doc(
            "Service Ticket",
            mission.custom_service_ticket
        )

    todo = frappe.get_doc("ToDo", todo_name)
    todo.date = getdate(
        mission.get("custom_planned_starttime")
        or frappe.utils.nowdate()
    )
    todo.priority = _get_ticket_priority_from_mission(mission)
    todo.description = _build_direct_todo_description(
        mission,
        ticket
    )
    todo.description += (
        "<br><br><b>Schedule Updated:</b> "
        + str(action)
        + "<br><b>Reason:</b> "
        + str(reason)
    )
    todo.save(ignore_permissions=True)

    return todo.name



def _sync_draft_mi_from_mission(mission):
    """
    Keep draft MI aligned with the current TM plan.
    Submitted MI is intentionally not touched.
    """
    draft_mis = frappe.get_all(
        "Mission Intervention",
        filters={
            "custom_parent_mission": mission.name,
            "docstatus": 0
        },
        pluck="name"
    )

    team_rows = _get_mission_team_rows(mission)
    current_technicians = [
        row["technician"] for row in team_rows
    ]

    primary_vehicle = _get_primary_assigned_vehicle(mission)

    for mi_name in draft_mis:
        mi = frappe.get_doc(
            "Mission Intervention",
            mi_name
        )

        if mi.meta.has_field("custom_planned_starttime"):
            mi.custom_planned_starttime = mission.get(
                "custom_planned_starttime"
            )

        if mi.meta.has_field("custom_planned_endtime"):
            mi.custom_planned_endtime = mission.get(
                "custom_planned_endtime"
            )

        if mi.meta.has_field("custom_external_vehicle"):
            mi.custom_external_vehicle = (
                mission.get("custom_external_vehicle") or None
            )

        if mi.meta.has_field("custom_vehicle"):
            mi.custom_vehicle = primary_vehicle

        if mi.meta.has_field("custom_intervention_team"):
            mi.set("custom_intervention_team", [])

            for team_row in team_rows:
                mi.append(
                    "custom_intervention_team",
                    {
                        "custom_technician": team_row["technician"],
                        "custom_assigned_vehicle": (
                            team_row.get("vehicle") or None
                        )
                    }
                )

        if mi.meta.has_field("custom_technician"):
            mi.custom_technician = (
                current_technicians[0]
                if current_technicians
                else None
            )

        mi.save(ignore_permissions=True)


def _sync_service_ticket_planning_from_mission(mission):
    """
    Copy the current Tech Mission planning state back to Service Ticket.

    TM is the active planning editor after mission creation. This synchronizes:
      - planned dates
      - external / hired vehicle
      - full Planned Team technician -> assigned vehicle mapping
      - technician summary
      - legacy common-vehicle summary
    """

    ticket_name = mission.get("custom_service_ticket")

    if not ticket_name:
        return

    ticket = frappe.get_doc("Service Ticket", ticket_name)
    technicians = _get_mission_technicians(mission)

    if ticket.meta.has_field("custom_primary_mission_ref"):
        ticket.custom_primary_mission_ref = mission.name

    if ticket.meta.has_field("custom_planned_starttime"):
        ticket.custom_planned_starttime = mission.get(
            "custom_planned_starttime"
        )

    if ticket.meta.has_field("custom_planned_endtime"):
        ticket.custom_planned_endtime = mission.get(
            "custom_planned_endtime"
        )

    if ticket.meta.has_field("custom_external_vehicle"):
        ticket.custom_external_vehicle = (
            mission.get("custom_external_vehicle") or None
        )

    if ticket.meta.has_field("custom_planned_team"):
        ticket.set("custom_planned_team", [])

        for row in mission.get("custom_planned_team") or []:
            technician = row.get("custom_technician")

            if not technician:
                continue

            ticket.append(
                "custom_planned_team",
                {
                    "custom_technician": technician,
                    "custom_assigned_vehicle": (
                        row.get("custom_assigned_vehicle") or None
                    )
                }
            )

    # Keep this old field only as a compatibility/current-summary field.
    if ticket.meta.has_field("custom_planned_vehicle"):
        ticket.custom_planned_vehicle = (
            _get_common_team_vehicle(mission)
        )

    if ticket.meta.has_field("custom_planned_technicians"):
        ticket.custom_planned_technicians = ", ".join(technicians)

    ticket.save(ignore_permissions=True)

# ============================================================
# CREATE SERVICE TICKET FROM INSTALLED EQUIPMENT / COMPONENT
# ============================================================

@frappe.whitelist()
def create_ticket_from_installed_equipment(
    equipment_name,
    subject,
    description,
    request_type,
    ticket_type,
    priority,
    technicians=None,
    work_type="Quick Intervention",
    component_name=None
):
    """
    Create one Service Ticket from an Installed Equipment record.

    When component_name is supplied, the ticket targets that permanent
    Equipment Component while retaining the parent Installed Equipment.
    """

    if not equipment_name:
        frappe.throw("Installed Equipment is required.")

    if not subject:
        frappe.throw("Subject is required.")

    if not description:
        frappe.throw("Description is required.")

    if not request_type:
        frappe.throw("Request Type is required.")

    if not ticket_type:
        frappe.throw("Ticket Type is required.")

    if not priority:
        frappe.throw("Priority is required.")

    allowed_ticket_types = {
        "Breakdown": ["Repair", "Service"],
        "Maintenance Request": [
            "Preventive Maintenance",
            "Service",
            "Calibration",
            "Commissioning"
        ],
        "General Request": [
            "Installation",
            "Survey",
            "Training",
            "Audit",
            "Incident Investigation",
            "Asset Relocation",
            "Config Change",
            "Swap",
            "Loan",
            "Service"
        ]
    }

    if request_type not in allowed_ticket_types:
        frappe.throw("Invalid Request Type.")

    if ticket_type not in allowed_ticket_types[request_type]:
        frappe.throw(
            "Ticket Type {0} is not valid for Request Type {1}.".format(
                ticket_type,
                request_type
            )
        )

    allowed_work_types = ["Quick Intervention", "Tech Mission"]

    if work_type not in allowed_work_types:
        frappe.throw("Invalid Work Type.")

    technician_list = frappe.parse_json(technicians) if technicians else []

    if not isinstance(technician_list, list):
        technician_list = [technician_list]

    technician_list = list(dict.fromkeys(
        [tech for tech in technician_list if tech]
    ))

    if not technician_list:
        frappe.throw("Please select at least one technician.")

    _validate_maintenance_technicians(technician_list)

    equipment = frappe.get_doc("Installed Equipment", equipment_name)
    component = None

    if component_name:
        component = frappe.get_doc("Equipment Component", component_name)

        if component.get("custom_parent_equipment") != equipment.name:
            frappe.throw(
                "The selected component is not installed on this equipment."
            )

    ticket = frappe.new_doc("Service Ticket")

    ticket.custom_customer = equipment.get("custom_parent_customer")
    ticket.custom_client_branch = equipment.get("custom_branch")
    ticket.custom_target_equipment = equipment.name

    if ticket.meta.has_field("custom_company"):
        ticket.custom_company = equipment.get("custom_company") or None

    # Client Type and Region come from Client Branch, which is the
    # source of truth for these classifications.
    branch_name = equipment.get("custom_branch")

    if branch_name:
        branch_doc = frappe.get_doc("Client Branch", branch_name)

        if ticket.meta.has_field("custom_client_type"):
            ticket.custom_client_type = (
                branch_doc.get("custom_site_type") or None
            )

        if ticket.meta.has_field("custom_region"):
            region_value = branch_doc.get("custom_region")

            if region_value:
                region_field = branch_doc.meta.get_field("custom_region")
                region_doctype = region_field.options if region_field else None

                if region_doctype:
                    region_meta = frappe.get_meta(region_doctype)
                    title_field = region_meta.title_field

                    if title_field and title_field != "name":
                        region_title = frappe.db.get_value(
                            region_doctype,
                            region_value,
                            title_field
                        )
                        ticket.custom_region = region_title or region_value
                    else:
                        ticket.custom_region = region_value
                else:
                    ticket.custom_region = region_value
            else:
                ticket.custom_region = None


    ticket.custom_request_type = request_type
    ticket.custom_ticket_type = ticket_type
    ticket.custom_priority = priority
    ticket.custom_subject = subject
    ticket.custom_description = description
    ticket.custom_ticket_status = "Open"
    ticket.custom_commercial_status = "N/A"
    ticket.custom_work_type = work_type

    if work_type == "Tech Mission":
        ticket.custom_planning_required = 1
        ticket.custom_planning_status = "Required"
    else:
        ticket.custom_planning_required = 0
        ticket.custom_planning_status = "Not Required"

    if ticket.meta.has_field("custom_parent_equipment"):
        ticket.custom_parent_equipment = (
            equipment.name if component else ""
        )

    if component:
        ticket.custom_target_component = component.name

        if ticket.meta.has_field("custom_equipment_component"):
            ticket.custom_equipment_component = component.name

        if ticket.meta.has_field("custom_target_component_name"):
            ticket.custom_target_component_name = (
                component.get("custom_display_name")
                or component.get("custom_equipment_type")
                or component.name
            )

        if ticket.meta.has_field("custom_component_group"):
            ticket.custom_component_group = component.get(
                "custom_component_group"
            )

        if ticket.meta.has_field("custom_component_brand"):
            ticket.custom_component_brand = component.get("custom_make")

        if ticket.meta.has_field("custom_component_model"):
            ticket.custom_component_model = component.get("custom_model")

        if ticket.meta.has_field("custom_component_serial"):
            ticket.custom_component_serial = (
                component.get("custom_serial_number")
                or component.get("custom_serial")
            )
    else:
        if ticket.meta.has_field("custom_target_component_name"):
            ticket.custom_target_component_name = (
                equipment.get("custom_display_name")
                or equipment.get("custom_asset_name")
                or equipment.name
            )

    if ticket.meta.has_field("custom_maintenance_contract"):
        ticket.custom_maintenance_contract = equipment.get(
            "custom_maintenance_contract"
        )

    if ticket.meta.has_field("custom_sla_rule"):
        ticket.custom_sla_rule = equipment.get("custom_sla_rule")

    if ticket.meta.has_field("custom_raised_by"):
        ticket.custom_raised_by = _current_user_display_name()

    if ticket.meta.has_field("custom_planned_team"):
        for technician in technician_list:
            ticket.append(
                "custom_planned_team",
                {"custom_technician": technician}
            )

    ticket.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "ticket": ticket.name,
        "target_type": "Component" if component else "Equipment"
    }

# ============================================================
# CREATE INSTALLATION TICKET FROM EQUIPMENT COMPONENT
# ============================================================

@frappe.whitelist()
def create_installation_ticket_from_component(
    component_name,
    destination_equipment,
    subject,
    description,
    priority,
    technicians=None,
    work_type="Quick Intervention"
):
    """
    Create an Installation Service Ticket for an Equipment Component.

    Supports:
      - a standalone component with no current parent equipment;
      - a component already linked to equipment but being installed,
        reinstalled, or transferred to the selected destination equipment.

    Important:
      The Equipment Component master is not moved or marked Installed here.
      Its customer, branch, parent equipment, and status must only be updated
      after the Installation MI is successfully submitted.
    """

    if not component_name:
        frappe.throw("Equipment Component is required.")

    if not destination_equipment:
        frappe.throw("Destination Installed Equipment is required.")

    if not subject:
        frappe.throw("Subject is required.")

    if not description:
        frappe.throw("Description is required.")

    if not priority:
        frappe.throw("Priority is required.")

    if work_type not in ["Quick Intervention", "Tech Mission"]:
        frappe.throw("Invalid Work Type.")

    technician_list = frappe.parse_json(technicians) if technicians else []

    if not isinstance(technician_list, list):
        technician_list = [technician_list]

    technician_list = list(dict.fromkeys(
        [technician for technician in technician_list if technician]
    ))

    if not technician_list:
        frappe.throw("Please select at least one technician.")

    _validate_maintenance_technicians(technician_list)

    component = frappe.get_doc(
        "Equipment Component",
        component_name
    )

    equipment = frappe.get_doc(
        "Installed Equipment",
        destination_equipment
    )

    customer = equipment.get("custom_parent_customer")
    branch = equipment.get("custom_branch")

    if not customer:
        frappe.throw(
            "The destination Installed Equipment has no Customer."
        )

    if not branch:
        frappe.throw(
            "The destination Installed Equipment has no Branch."
        )

    ticket = frappe.new_doc("Service Ticket")

    ticket.custom_customer = customer
    ticket.custom_client_branch = branch
    ticket.custom_target_equipment = equipment.name

    if ticket.meta.has_field("custom_company"):
        ticket.custom_company = equipment.get("custom_company") or None

    # Client Type and Region come from the destination Client Branch.
    # This keeps installation tickets aligned with normal Service Tickets.
    if branch:
        branch_doc = frappe.get_doc("Client Branch", branch)

        if ticket.meta.has_field("custom_client_type"):
            ticket.custom_client_type = (
                branch_doc.get("custom_site_type") or None
            )

        if ticket.meta.has_field("custom_region"):
            ticket.custom_region = (
                branch_doc.get("custom_region") or None
            )
    ticket.custom_request_type = "General Request"
    ticket.custom_ticket_type = "Installation"
    ticket.custom_priority = priority
    ticket.custom_subject = subject
    ticket.custom_description = description
    ticket.custom_ticket_status = "Open"
    ticket.custom_commercial_status = "N/A"
    ticket.custom_work_type = work_type

    if work_type == "Tech Mission":
        ticket.custom_planning_required = 1
        ticket.custom_planning_status = "Required"
    else:
        ticket.custom_planning_required = 0
        ticket.custom_planning_status = "Not Required"

    if ticket.meta.has_field("custom_target_component"):
        ticket.custom_target_component = component.name

    if ticket.meta.has_field("custom_equipment_component"):
        ticket.custom_equipment_component = component.name

    if ticket.meta.has_field("custom_parent_equipment"):
        ticket.custom_parent_equipment = equipment.name

    if ticket.meta.has_field("custom_target_component_name"):
        ticket.custom_target_component_name = (
            component.get("custom_display_name")
            or component.get("custom_equipment_type")
            or component.name
        )

    if ticket.meta.has_field("custom_component_group"):
        ticket.custom_component_group = component.get(
            "custom_component_group"
        )

    if ticket.meta.has_field("custom_component_brand"):
        ticket.custom_component_brand = component.get("custom_make")

    if ticket.meta.has_field("custom_component_model"):
        ticket.custom_component_model = component.get("custom_model")

    if ticket.meta.has_field("custom_component_serial"):
        ticket.custom_component_serial = (
            component.get("custom_serial_number")
            or component.get("custom_serial")
        )

    if ticket.meta.has_field("custom_maintenance_contract"):
        ticket.custom_maintenance_contract = equipment.get(
            "custom_maintenance_contract"
        )

    if ticket.meta.has_field("custom_sla_rule"):
        ticket.custom_sla_rule = equipment.get("custom_sla_rule")

    if ticket.meta.has_field("custom_raised_by"):
        ticket.custom_raised_by = _current_user_display_name()

    if ticket.meta.has_field("custom_planned_team"):
        for technician in technician_list:
            ticket.append(
                "custom_planned_team",
                {
                    "custom_technician": technician
                }
            )

    ticket.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "ticket": ticket.name,
        "component": component.name,
        "destination_equipment": equipment.name,
        "customer": customer,
        "branch": branch
    }

# ============================================================
# INTERNAL EQUIPMENT COMPONENT WEB VIEW
# ============================================================

def _component_webview_allowed():
    allowed_roles = {
        "RM", "Maintenance Manager", "Maintenance Supervisor",
        "Maintenance Technician", "System Manager", "Administrator",
    }
    return bool(allowed_roles.intersection(set(frappe.get_roles())))

def _component_webview_require_access():
    if not _component_webview_allowed():
        frappe.throw("You are not permitted to access the Equipment Component web view.", frappe.PermissionError)

def _component_query_existing_fields(doctype, requested_fields):
    meta = frappe.get_meta(doctype)
    return [f for f in requested_fields if f in {"name","creation","modified","docstatus"} or meta.has_field(f)]

def _component_get_tickets(component_name):
    meta = frappe.get_meta("Service Ticket")
    fields = _component_query_existing_fields("Service Ticket", [
        "name","creation","modified","custom_opening_date","custom_subject",
        "custom_ticket_status","custom_priority","custom_request_type","custom_ticket_type",
        "custom_target_equipment","custom_client_branch","custom_equipment_component",
        "custom_target_component","custom_target_component_name","custom_component_serial"
    ])
    names=set()
    for fieldname in ["custom_equipment_component","custom_target_component"]:
        if meta.has_field(fieldname):
            names.update(frappe.get_all("Service Ticket", filters={fieldname:component_name}, pluck="name", limit_page_length=500))
    if not names: return []
    return frappe.get_all("Service Ticket", filters={"name":["in",list(names)]}, fields=fields, order_by="creation desc", limit_page_length=500)

def _component_get_service_logs(component, tickets):
    meta=frappe.get_meta("Asset Service Log")
    fields=_component_query_existing_fields("Asset Service Log", [
        "name","creation","custom_end_time","custom_related_asset","custom_service_ticket",
        "custom_mission_ref","custom_intervention_ref","custom_technician","custom_intervention_type",
        "custom_work_outcome","custom_notes","custom_duration","custom_component_item",
        "custom_component_group","custom_component_serial","custom_equipment_component"
    ])
    filters=[]
    if meta.has_field("custom_equipment_component"): filters.append({"custom_equipment_component":component.name})
    ticket_names=[r.name for r in tickets]
    if ticket_names and meta.has_field("custom_service_ticket"): filters.append({"custom_service_ticket":["in",ticket_names]})
    serial=component.get("custom_serial_number")
    if serial and meta.has_field("custom_component_serial"): filters.append({"custom_component_serial":serial})
    rows={}
    for flt in filters:
        for row in frappe.get_all("Asset Service Log", filters=flt, fields=fields, order_by="creation desc", limit_page_length=500): rows[row.name]=row
    out=list(rows.values()); out.sort(key=lambda r:str(r.get("custom_end_time") or r.get("creation") or ""), reverse=True)
    for row in out:
        tech=row.get("custom_technician")
        if tech: row["technician_display"]=frappe.db.get_value("User",tech,"full_name") or tech
    return out

def _component_get_lifecycle_logs(component):
    meta=frappe.get_meta("Asset Lifecycle Log")
    fields=_component_query_existing_fields("Asset Lifecycle Log", [
        "name","creation","custom_date","custom_related_asset","custom_event","custom_event_source",
        "custom_technician","custom_action_taken","custom_previous_branch","custom_new_branch",
        "custom_service_ticket","custom_intervention_ref","custom_mission_ref","custom_component_item",
        "custom_component_serial","custom_new_component_item","custom_new_component_serial","custom_equipment_component"
    ])
    filters=[]
    if meta.has_field("custom_equipment_component"): filters.append({"custom_equipment_component":component.name})
    serial=component.get("custom_serial_number")
    if serial and meta.has_field("custom_component_serial"): filters.append({"custom_component_serial":serial})
    if serial and meta.has_field("custom_new_component_serial"): filters.append({"custom_new_component_serial":serial})
    rows={}
    for flt in filters:
        for row in frappe.get_all("Asset Lifecycle Log", filters=flt, fields=fields, order_by="creation desc", limit_page_length=500): rows[row.name]=row
    out=list(rows.values()); out.sort(key=lambda r:str(r.get("custom_date") or r.get("creation") or ""), reverse=True)
    for row in out:
        tech=row.get("custom_technician")
        if tech: row["technician_display"]=frappe.db.get_value("User",tech,"full_name") or tech
    return out

def _component_get_config_logs(component):
    meta=frappe.get_meta("Config Update Log")
    fields=_component_query_existing_fields("Config Update Log", [
        "name","creation","custom_config_datetime","custom_related_asset","custom_parameter",
        "custom_current_value","custom_new_value","custom_technician","custom_notes",
        "custom_service_ticket","custom_intervention","custom_component_serial","custom_equipment_component"
    ])
    filters=[]
    if meta.has_field("custom_equipment_component"): filters.append({"custom_equipment_component":component.name})
    serial=component.get("custom_serial_number")
    if serial and meta.has_field("custom_component_serial"): filters.append({"custom_component_serial":serial})
    rows={}
    for flt in filters:
        for row in frappe.get_all("Config Update Log", filters=flt, fields=fields, order_by="creation desc", limit_page_length=500): rows[row.name]=row
    out=list(rows.values()); out.sort(key=lambda r:str(r.get("custom_config_datetime") or r.get("creation") or ""), reverse=True)
    for row in out:
        tech=row.get("custom_technician")
        if tech: row["technician_display"]=frappe.db.get_value("User",tech,"full_name") or tech
    return out

@frappe.whitelist()
def get_component_webview_data(component_name):
    _component_webview_require_access()
    if not component_name: frappe.throw("Equipment Component is required.")
    if not frappe.db.exists("Equipment Component", component_name): frappe.throw("Equipment Component not found: "+str(component_name))
    component=frappe.get_doc("Equipment Component",component_name)
    fields=[
        "name","custom_requires_calibration","custom_parent_equipment","custom_customer","custom_branch",
        "custom_company_workshop","custom_component_group","custom_equipment_type","custom_make","custom_model",
        "custom_serial_number","custom_part_number","custom_status","custom_installation_date","custom_display_name",
        "custom_item","custom_commissioning_status","custom_commissioned_date","custom_last_commissioning_record",
        "custom_last_calibration_record","custom_last_calibration_date","custom_next_calibration_date",
        "custom_calibration_interval_months"
    ]
    c={f:component.get(f) for f in fields}
    parent=component.get("custom_parent_equipment"); eq=None
    if parent and frappe.db.exists("Installed Equipment",parent):
        eq=frappe.db.get_value("Installed Equipment",parent,["name","custom_asset_name","custom_display_name","custom_asset_id","custom_client_asset_code","custom_parent_customer","custom_branch"],as_dict=True)
    cust=component.get("custom_customer"); cust_display=(frappe.db.get_value("Customer",cust,"customer_name") if cust else None) or cust
    branch=component.get("custom_branch"); branch_display=branch; client_type=None; region=None; region_display=None
    if branch and frappe.db.exists("Client Branch",branch):
        bi=frappe.db.get_value("Client Branch",branch,["custom_branch","custom_site_type","custom_region"],as_dict=True) or {}
        branch_display=bi.get("custom_branch") or branch; client_type=bi.get("custom_site_type"); region=bi.get("custom_region")
        if region and frappe.db.exists("Region",region): region_display=frappe.db.get_value("Region",region,"custom_region_name") or region
    tickets=_component_get_tickets(component.name)
    return {
        "component":c,
        "context":{"customer_display":cust_display,"branch_display":branch_display,"client_type":client_type,"region":region,"region_display":region_display,"equipment":eq},
        "tickets":tickets,
        "service":_component_get_service_logs(component,tickets),
        "lifecycle":_component_get_lifecycle_logs(component),
        "config":_component_get_config_logs(component),
    }

