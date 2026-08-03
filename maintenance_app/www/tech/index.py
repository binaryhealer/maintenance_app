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
