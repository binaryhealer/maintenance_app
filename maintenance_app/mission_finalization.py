"""Shared GMAO Tech Mission finalization checks."""

import frappe


EXCEPTION_OUTCOMES = {
    "Could Not Complete": "Could Not Complete",
    "Waiting for Client": "Waiting for Client",
    "Waiting for Parts": "Waiting for Parts",
    "To Quote (Billable)": "To Quote",
}

KNOWN_OUTCOMES = set(EXCEPTION_OUTCOMES) | {
    "Work Completed",
    "Continue Work",
}


def _readiness(mission):
    """Read-only readiness evaluation. Never changes documents."""

    from maintenance_app.api import _planned_equipment_completion_state

    blockers = []

    status = mission.get("custom_mission_status") or ""

    if status in ("Completed", "Closed", "Cancelled"):
        blockers.append(
            "Tech Mission is already terminal: " + status
        )

    meta = frappe.get_meta("Mission Intervention")

    fields = [
        "name",
        "docstatus",
        "custom_asset",
        "custom_work_outcome",
    ]

    optional = [
        "custom_start_time",
        "custom_end_time",
        "custom_checkout_status",
        "custom_previous_intervention",
        "custom_other_equipment_to_work_on",
    ]

    fields.extend(
        field for field in optional if meta.has_field(field)
    )

    rows = frappe.get_all(
        "Mission Intervention",
        filters={
            "custom_parent_mission": mission.name,
        },
        fields=fields,
        order_by="creation asc",
        limit_page_length=1001,
    )

    if len(rows) > 1000:
        blockers.append(
            "Mission has too many interventions for this "
            "readiness check."
        )

    active = [
        row for row in rows
        if row.get("custom_checkout_status") != "Cancelled"
        and int(row.get("docstatus") or 0) != 2
    ]

    drafts = [
        row for row in active
        if int(row.get("docstatus") or 0) == 0
    ]

    submitted = [
        row for row in active
        if int(row.get("docstatus") or 0) == 1
    ]

    checked_in = [
        row for row in active
        if row.get("custom_start_time")
        and not row.get("custom_end_time")
    ]

    if not submitted:
        blockers.append(
            "No submitted interventions found."
        )

    if drafts:
        blockers.append(
            "Unfinished draft interventions: "
            + ", ".join(row["name"] for row in drafts[:10])
        )

    if checked_in:
        blockers.append(
            "Interventions with an active check-in: "
            + ", ".join(row["name"] for row in checked_in[:10])
        )

    followed_sources = {
        row.get("custom_previous_intervention")
        for row in active
        if row.get("custom_previous_intervention")
    }

    unfinished_continue = [
        row["name"] for row in submitted
        if row.get("custom_work_outcome") == "Continue Work"
        and row["name"] not in followed_sources
    ]

    if unfinished_continue:
        blockers.append(
            "Continue Work requires a follow-up intervention: "
            + ", ".join(unfinished_continue[:10])
        )

    unknown_outcomes = [
        row["name"] for row in submitted
        if (row.get("custom_work_outcome") or "").strip()
        not in KNOWN_OUTCOMES
    ]

    if unknown_outcomes:
        blockers.append(
            "Missing or unsupported Work Outcome: "
            + ", ".join(unknown_outcomes[:10])
        )

    # A successful linked follow-up resolves its ancestor exception,
    # but only when both interventions concern the same equipment.
    submitted_by_name = {
        row["name"]: row for row in submitted
    }

    resolved_exception_names = set()

    for completed in submitted:
        if completed.get("custom_work_outcome") != "Work Completed":
            continue

        equipment = completed.get("custom_asset")
        previous = completed.get("custom_previous_intervention")
        visited = set()

        while previous and previous not in visited:
            visited.add(previous)
            ancestor = submitted_by_name.get(previous)

            if not ancestor:
                break

            if ancestor.get("custom_asset") != equipment:
                break

            if ancestor.get("custom_work_outcome") in EXCEPTION_OUTCOMES:
                resolved_exception_names.add(previous)

            previous = ancestor.get("custom_previous_intervention")

    exceptions = [
        {
            "mi": row["name"],
            "equipment": row.get("custom_asset"),
            "outcome": row.get("custom_work_outcome"),
            "hold_reason": EXCEPTION_OUTCOMES[
                row.get("custom_work_outcome")
            ],
        }
        for row in submitted
        if row.get("custom_work_outcome") in EXCEPTION_OUTCOMES
        and row["name"] not in resolved_exception_names
    ]

    # Equipment is accounted for when it has a completed/
    # not-attended planning row, or a submitted MI recording
    # a final outcome. This does not imply successful repair.
    planned = _planned_equipment_completion_state(mission)
    outstanding_equipment = []

    for target in mission.get("custom_target_equipments") or []:
        target_status = (target.get("custom_status") or "").strip()
        equipment = target.get("custom_equipment")

        if target_status in ("Completed", "Not Attended"):
            continue

        attended = bool(equipment) and any(
            row.get("custom_asset") == equipment
            and row.get("custom_work_outcome") in (
                set(EXCEPTION_OUTCOMES) | {"Work Completed"}
            )
            for row in submitted
        )

        if not attended:
            outstanding_equipment.append(
                equipment or target.name
            )

    if outstanding_equipment:
        blockers.append(
            "Planned equipment not yet accounted for: "
            + ", ".join(outstanding_equipment[:10])
        )

    return {
        "mission": mission.name,
        "mission_status": status,
        "ready_for_finish": not bool(blockers),
        "blockers": blockers,
        "draft_mis": [row["name"] for row in drafts],
        "checked_in_mis": [row["name"] for row in checked_in],
        "submitted_mi_count": len(submitted),
        "exceptions": exceptions,
        "suggested_final_status": (
            "Closed" if exceptions else "Completed"
        ) if not blockers else None,
        "planned_equipment": planned,
        "multitech_attendance_check": "Not yet implemented",
    }


@frappe.whitelist()
def get_tech_mission_finish_readiness(mission_name):
    """Read-only preflight for Desk and future technician portal."""

    if not mission_name:
        frappe.throw("Tech Mission is required.")

    mission = frappe.get_doc("Tech Mission", mission_name)
    mission.check_permission("read")

    return _readiness(mission)



def _sync_service_ticket_mission_row(mission):
    """
    Synchronize the ST mission register from the actual TM.

    Only the matching child row is updated. This does not change
    the Service Ticket lifecycle, hold reason, or notifications.
    """
    ticket_name = mission.get("custom_service_ticket")

    if not ticket_name:
        return

    frappe.db.sql(
        """
        UPDATE `tabService Ticket Mission Row`
        SET custom_mission_status = %s
        WHERE parent = %s
          AND parenttype = 'Service Ticket'
          AND parentfield = 'custom_tech_missions'
          AND custom_tech_mission = %s
        """,
        (
            mission.get("custom_mission_status"),
            ticket_name,
            mission.name,
        ),
    )

@frappe.whitelist()
def finalize_tech_mission(mission_name):
    """
    Explicitly finish a Tech Mission.

    Phase 1:
    - Single-technician / existing MI attendance model.
    - Readiness rechecked after locking the mission.
    - TM Completed when no unresolved exception remains.
    - TM Closed when unresolved exception work remains.
    - ST On Hold when the latest TM closes with exceptions.
    - Successful TM does not yet auto-resolve ST.

    No explicit commit: Frappe owns the request transaction.
    """

    if not mission_name:
        frappe.throw("Tech Mission is required.")

    # Lock the parent mission to serialize finalization requests.
    locked = frappe.db.sql(
        """
        SELECT name
        FROM `tabTech Mission`
        WHERE name = %s
        FOR UPDATE
        """,
        (mission_name,),
        as_dict=True,
    )

    if not locked:
        frappe.throw("Tech Mission does not exist.")

    mission = frappe.get_doc("Tech Mission", mission_name)
    mission.check_permission("write")

    readiness = _readiness(mission)

    if not readiness["ready_for_finish"]:
        frappe.throw(
            "Cannot finish Tech Mission:\\n"
            + "\\n".join(readiness["blockers"])
        )

    # Until the reason field is verified, do not approve
    # Not Attended equipment silently.
    not_attended = [
        row.name
        for row in mission.get("custom_target_equipments") or []
        if (row.get("custom_status") or "").strip()
        == "Not Attended"
    ]

    if not_attended:
        frappe.throw(
            "Not Attended equipment requires a verified "
            "reason before Finish Mission can proceed: "
            + ", ".join(not_attended[:10])
        )

    exceptions = readiness["exceptions"]
    final_status = (
        "Closed" if exceptions else "Completed"
    )

    hold_reason = ""

    if exceptions:
        # Follow the established GMAO hold precedence.
        precedence = [
            "Waiting for Parts",
            "Waiting for Client",
            "To Quote",
            "Could Not Complete",
        ]

        for reason in precedence:
            if any(
                item["hold_reason"] == reason
                for item in exceptions
            ):
                hold_reason = reason
                break

    mission.custom_mission_status = final_status

    if mission.meta.has_field("custom_hold_reason"):
        mission.custom_hold_reason = hold_reason

    if mission.meta.has_field("custom_open_work_remaining"):
        mission.custom_open_work_remaining = 0

    # Preserve existing client-action summary and original
    # MI evidence. Those records remain authoritative.
    mission.save(ignore_permissions=True)

    ticket_status = None
    ticket_name = mission.get("custom_service_ticket")

    # Keep the ST Tech Missions child table aligned with
    # the authoritative Tech Mission status.
    _sync_service_ticket_mission_row(mission)

    if ticket_name and exceptions:
        # An older mission must not override a newer mission's
        # management of the same Service Ticket.
        newer_missions = frappe.get_all(
            "Tech Mission",
            filters={
                "custom_service_ticket": ticket_name,
                "creation": [">", mission.creation],
            },
            fields=["name"],
            limit_page_length=1,
        )

        if not newer_missions:
            ticket = frappe.get_doc(
                "Service Ticket", ticket_name
            )

            current_status = (
                ticket.get("custom_ticket_status") or ""
            )

            if current_status not in (
                "Closed", "Cancelled", "Resolved"
            ):
                if ticket.meta.has_field(
                    "custom_ticket_status"
                ):
                    ticket.custom_ticket_status = "On Hold"

                if ticket.meta.has_field(
                    "custom_hold_reason"
                ):
                    ticket.custom_hold_reason = hold_reason

                ticket.save(ignore_permissions=True)
                ticket_status = "On Hold"

    # A terminal mission no longer requires its assignment
    # ToDos to remain open.
    todos = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Tech Mission",
            "reference_name": mission.name,
            "status": ["!=", "Closed"],
        },
        pluck="name",
    )

    for todo_name in todos:
        frappe.db.set_value(
            "ToDo",
            todo_name,
            "status",
            "Closed",
            update_modified=False,
        )

    return {
        "ok": True,
        "mission": mission.name,
        "mission_status": final_status,
        "ticket": ticket_name,
        "ticket_status_updated": ticket_status,
        "hold_reason": hold_reason,
        "unresolved_exceptions": exceptions,
        "submitted_mi_count": readiness[
            "submitted_mi_count"
        ],
        "ticket_resolution_deferred": (
            final_status == "Completed"
        ),
    }
