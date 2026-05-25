import frappe
from frappe.utils import today, getdate

no_cache = 1

def get_context(context):
    user = frappe.session.user
    selected_filter = frappe.form_dict.get("filter") or "today"

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

    all_mission_todos = frappe.get_all(
        "ToDo",
        filters={
            "allocated_to": user,
            "reference_type": "Tech Mission"
        },
        fields=["reference_name"],
        order_by="modified desc"
    )

    mission_names = list(set([
        t.reference_name for t in all_mission_todos if t.reference_name
    ]))

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
                "custom_planned_endtime"
            ],
            order_by="custom_planned_starttime desc"
        )

    today_date = getdate(today())

    today_missions = [
        m for m in missions
        if m.custom_planned_starttime
        and getdate(m.custom_planned_starttime) == today_date
    ]

    scheduled_missions = [
        m for m in missions
        if m.custom_mission_status == "Scheduled"
    ]

    ongoing_missions = [
        m for m in missions
        if m.custom_mission_status == "Ongoing"
    ]

    completed_missions = [
        m for m in missions
        if m.custom_mission_status in ["Completed", "Closed"]
    ]

    if selected_filter == "scheduled":
        visible_missions = scheduled_missions
    elif selected_filter == "ongoing":
        visible_missions = ongoing_missions
    elif selected_filter == "completed":
        visible_missions = completed_missions
    elif selected_filter == "todos":
        visible_missions = []
    else:
        visible_missions = today_missions

    context.selected_filter = selected_filter
    context.today_count = len(today_missions)
    context.scheduled_count = len(scheduled_missions)
    context.ongoing_count = len(ongoing_missions)
    context.completed_count = len(completed_missions)
    context.todo_count = len(open_todos)

    context.missions = visible_missions
    context.todos = open_todos
    context.selected_filter = selected_filter
