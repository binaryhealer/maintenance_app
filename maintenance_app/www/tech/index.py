import frappe
from frappe.utils import today, getdate, add_days, formatdate

no_cache = True


def _safe_int(value):
    try:
        if value in [None, ""]:
            return None
        return int(value)
    except Exception:
        return None


def _get_current_missions_for_user(user):
    """
    Return only Tech Missions where the logged-in user exists in the
    CURRENT custom_planned_team child table.

    Uses a direct SQL join instead of historical ToDos or a broad child-table
    lookup, so removed technicians disappear immediately after refresh.
    """

    return frappe.db.sql(
        """
        SELECT DISTINCT
            tm.name,
            tm.custom_parent_customer,
            tm.custom_branch,
            tm.custom_asset,
            tm.custom_target_component_name,
            tm.custom_parent_equipment,
            tm.custom_mission_status,
            tm.custom_planned_starttime,
            tm.custom_planned_endtime,
            tm.modified
        FROM `tabTech Mission` tm
        INNER JOIN `tabPlanned Technicians` pt
            ON pt.parent = tm.name
            AND pt.parenttype = 'Tech Mission'
            AND pt.parentfield = 'custom_planned_team'
        WHERE
            pt.custom_technician = %(user)s
        ORDER BY
            tm.custom_planned_starttime ASC,
            tm.modified DESC
        """,
        {"user": user},
        as_dict=True
    )




def _equipment_display(equipment_name):
    if not equipment_name:
        return ""

    meta = frappe.get_meta("Installed Equipment")
    title_field = meta.title_field

    fields = [
        "name",
        "custom_display_name",
        "custom_asset_name",
        "custom_client_asset_code",
        "custom_asset_id",
        "custom_make",
        "custom_model",
    ]

    # Use the actual Installed Equipment title field configured in Frappe.
    if title_field and title_field not in fields:
        fields.append(title_field)

    values = frappe.db.get_value(
        "Installed Equipment",
        equipment_name,
        fields,
        as_dict=True,
    ) or {}

    configured_title = (
        values.get(title_field)
        if title_field
        else None
    )

    return (
        configured_title
        or values.get("custom_display_name")
        or values.get("custom_asset_name")
        or values.get("custom_client_asset_code")
        or values.get("custom_asset_id")
        or " - ".join(
            [
                value
                for value in [
                    values.get("custom_make"),
                    values.get("custom_model"),
                ]
                if value
            ]
        )
        or equipment_name
    )

def _attach_interventions_to_missions(missions):
    """Attach every MI to its authorized Tech Mission for the technician dashboard."""
    mission_names = [m.name for m in missions if m.name]

    for mission in missions:
        mission.interventions = []

    if not mission_names:
        return

    for mission in missions:
        parent_equipment = (
            mission.get("custom_parent_equipment") or ""
        ).strip()

        # Older records may store the internal Installed Equipment ID
        # (for example SITE-ASSET-00170) in custom_parent_equipment.
        # Do not treat that as the readable display value.
        if parent_equipment.startswith("SITE-ASSET-"):
            parent_equipment = ""

        mission.equipment_display = (
            parent_equipment
            or mission.get("custom_target_component_name")
            or _equipment_display(mission.get("custom_asset"))
        )

    mi_meta = frappe.get_meta("Mission Intervention")
    fields = [
        "name",
        "custom_parent_mission",
        "docstatus",
        "custom_asset",
        "custom_target_component_name",
        "custom_subject",
        "custom_start_time",
        "custom_end_time",
        "custom_work_outcome",
        "creation",
    ]

    for optional_field in ["custom_mi_purpose", "custom_additional_mi"]:
        if mi_meta.has_field(optional_field):
            fields.append(optional_field)

    rows = frappe.get_all(
        "Mission Intervention",
        filters={"custom_parent_mission": ["in", mission_names]},
        fields=fields,
        order_by="creation asc",
        limit_page_length=1000,
    )

    by_mission = {name: [] for name in mission_names}

    for row in rows:
        purpose = (row.get("custom_mi_purpose") or "").strip()
        if not purpose:
            purpose = "Additional" if row.get("custom_additional_mi") else "Initial"

        if int(row.get("docstatus") or 0) == 2:
            live_status = "Cancelled"
        elif int(row.get("docstatus") or 0) == 1:
            live_status = "Submitted"
        elif row.get("custom_end_time"):
            live_status = "Checked Out"
        elif row.get("custom_start_time"):
            live_status = "Checked In"
        else:
            live_status = "Draft"

        row.purpose_label = purpose
        row.live_status = live_status
        by_mission.setdefault(row.custom_parent_mission, []).append(row)

    for mission in missions:
        parent_equipment = (
            mission.get("custom_parent_equipment") or ""
        ).strip()

        # Older records may store the internal Installed Equipment ID
        # (for example SITE-ASSET-00170) in custom_parent_equipment.
        # Do not treat that as the readable display value.
        if parent_equipment.startswith("SITE-ASSET-"):
            parent_equipment = ""

        mission.equipment_display = (
            parent_equipment
            or mission.get("custom_target_component_name")
            or _equipment_display(mission.get("custom_asset"))
        )

        mission.interventions = by_mission.get(
            mission.name,
            []
        )

        for intervention in mission.interventions:
            intervention.equipment_display = _equipment_display(
                intervention.get("custom_asset")
            )

def get_context(context):
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.local.flags.redirect_to = "/login"
        raise frappe.PermissionError("Not logged in")

    user = frappe.session.user
    selected_filter = frappe.form_dict.get("filter") or "today"
    selected_month = (frappe.form_dict.get("month") or "").strip()
    selected_year = (frappe.form_dict.get("year") or "").strip()

    context.no_cache = 1

    # Current Tech Mission team is the only visibility source.
    missions = _get_current_missions_for_user(user)

    mission_names = [
        mission.name
        for mission in missions
        if mission.name
    ]

    _attach_interventions_to_missions(missions)

    mission_by_name = {
        mission.name: mission
        for mission in missions
    }

    # Only open ToDos belonging to missions where the user is still
    # currently assigned.
    open_todos = []

    if mission_names:
        open_todos = frappe.get_all(
            "ToDo",
            filters={
                "allocated_to": user,
                "status": "Open",
                "reference_type": "Tech Mission",
                "reference_name": ["in", mission_names]
            },
            fields=[
                "name",
                "reference_name",
                "description",
                "date"
            ],
            order_by="date asc"
        )

    # Display the live mission schedule, never an old ToDo date.
    for todo in open_todos:
        mission = mission_by_name.get(todo.reference_name)

        if mission:
            todo.mission_data = mission

        if mission and mission.custom_planned_starttime:
            todo.date = mission.custom_planned_starttime

    open_todos.sort(
        key=lambda row: (
            row.date is None,
            str(row.date or "")
        )
    )

    today_date = getdate(today())
    upcoming_limit = getdate(add_days(today_date, 7))

    excluded_statuses = [
        "Completed",
        "Closed",
        "Cancelled"
    ]

    today_missions = [
        mission
        for mission in missions
        if mission.custom_planned_starttime
        and getdate(mission.custom_planned_starttime) == today_date
        and mission.custom_mission_status not in excluded_statuses
    ]

    upcoming_missions = [
        mission
        for mission in missions
        if mission.custom_planned_starttime
        and today_date < getdate(
            mission.custom_planned_starttime
        ) <= upcoming_limit
        and mission.custom_mission_status not in excluded_statuses
    ]

    ongoing_missions = [
        mission
        for mission in missions
        if mission.custom_mission_status == "Ongoing"
    ]

    unplanned_missions = [
        mission
        for mission in missions
        if not mission.custom_planned_starttime
        and mission.custom_mission_status not in excluded_statuses
    ]

    completed_missions_all = [
        mission
        for mission in missions
        if mission.custom_mission_status in [
            "Completed",
            "Closed"
        ]
    ]

    completed_missions = completed_missions_all

    selected_year_int = _safe_int(selected_year)
    selected_month_int = _safe_int(selected_month)

    if selected_year_int:
        completed_missions = [
            mission
            for mission in completed_missions
            if mission.custom_planned_starttime
            and getdate(
                mission.custom_planned_starttime
            ).year == selected_year_int
        ]

    if selected_month_int:
        completed_missions = [
            mission
            for mission in completed_missions
            if mission.custom_planned_starttime
            and getdate(
                mission.custom_planned_starttime
            ).month == selected_month_int
        ]

    if selected_filter == "upcoming":
        visible_missions = upcoming_missions
    elif selected_filter == "ongoing":
        visible_missions = ongoing_missions
    elif selected_filter == "unplanned":
        visible_missions = unplanned_missions
    elif selected_filter == "completed":
        visible_missions = completed_missions
    elif selected_filter == "todos":
        visible_missions = []
    else:
        visible_missions = today_missions

    calendar_days = []

    for offset in range(0, 7):
        day_date = getdate(add_days(today_date, offset))

        day_missions = [
            mission
            for mission in missions
            if mission.custom_planned_starttime
            and getdate(
                mission.custom_planned_starttime
            ) == day_date
            and mission.custom_mission_status not in excluded_statuses
        ]

        calendar_days.append({
            "date": day_date,
            "label": formatdate(day_date, "dd-MMM"),
            "missions": day_missions
        })

    context.user = user
    context.selected_filter = selected_filter
    context.selected_month = selected_month
    context.selected_year = selected_year

    context.today_count = len(today_missions)
    context.upcoming_count = len(upcoming_missions)
    context.ongoing_count = len(ongoing_missions)
    context.unplanned_count = len(unplanned_missions)
    context.completed_count = len(completed_missions_all)
    context.todo_count = len(open_todos)

    context.missions = visible_missions
    context.todos = open_todos
    context.calendar_days = calendar_days