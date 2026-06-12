import frappe
from frappe.utils import today, getdate, add_days, formatdate

no_cache = 1


def _safe_int(value):
    try:
        if value in [None, ""]:
            return None
        return int(value)
    except Exception:
        return None


def get_context(context):
    user = frappe.session.user
    selected_filter = frappe.form_dict.get("filter") or "today"
    selected_month = (frappe.form_dict.get("month") or "").strip()
    selected_year = (frappe.form_dict.get("year") or "").strip()

    open_todos = frappe.get_all(
        "ToDo",
        filters={
            "allocated_to": user,
            "status": "Open",
            "reference_type": "Tech Mission"
        },
        fields=["name", "reference_name", "description", "date"],
        order_by="date asc"
    )

    all_todos = frappe.get_all(
        "ToDo",
        filters={
            "allocated_to": user,
            "reference_type": "Tech Mission"
        },
        fields=["reference_name"]
    )

    # Do not rely only on ToDo.
    # Some missions may have no ToDo, or the ToDo may be closed/deleted.
    # Also include missions where this user is in the planned technician table.
    team_rows = frappe.get_all(
        "Planned Technicians",
        filters={
            "parenttype": "Tech Mission",
            "custom_technician": user
        },
        fields=["parent"]
    )

    mission_names = list(set(
        [t.reference_name for t in all_todos if t.reference_name] +
        [r.parent for r in team_rows if r.parent]
    ))

    missions = []
    if mission_names:
        missions = frappe.get_all(
            "Tech Mission",
            filters={"name": ["in", mission_names]},
            fields=[
                "name",
                "custom_parent_customer",
                "custom_branch",
                "custom_asset",
                "custom_mission_status",
                "custom_planned_starttime",
                "custom_planned_endtime",
                "modified"
            ],
            order_by="custom_planned_starttime asc"
        )

    today_date = getdate(today())
    upcoming_limit = getdate(add_days(today_date, 7))

    today_missions = [
        m for m in missions
        if m.custom_planned_starttime
        and getdate(m.custom_planned_starttime) == today_date
        and m.custom_mission_status not in ["Completed", "Closed", "Cancelled"]
    ]

    upcoming_missions = [
        m for m in missions
        if m.custom_planned_starttime
        and today_date < getdate(m.custom_planned_starttime) <= upcoming_limit
        and m.custom_mission_status not in ["Completed", "Closed", "Cancelled"]
    ]

    ongoing_missions = [
        m for m in missions
        if m.custom_mission_status == "Ongoing"
    ]

    unplanned_missions = [
        m for m in missions
        if not m.custom_planned_starttime
        and m.custom_mission_status not in ["Completed", "Closed", "Cancelled"]
    ]

    completed_missions_all = [
        m for m in missions
        if m.custom_mission_status in ["Completed", "Closed"]
    ]

    completed_missions = completed_missions_all

    selected_year_int = _safe_int(selected_year)
    selected_month_int = _safe_int(selected_month)

    if selected_year_int:
        completed_missions = [
            m for m in completed_missions
            if m.custom_planned_starttime
            and getdate(m.custom_planned_starttime).year == selected_year_int
        ]

    if selected_month_int:
        completed_missions = [
            m for m in completed_missions
            if m.custom_planned_starttime
            and getdate(m.custom_planned_starttime).month == selected_month_int
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
            m for m in missions
            if m.custom_planned_starttime
            and getdate(m.custom_planned_starttime) == day_date
            and m.custom_mission_status not in ["Completed", "Closed", "Cancelled"]
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
