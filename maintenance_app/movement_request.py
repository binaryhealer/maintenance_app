import frappe
from frappe import _
from frappe.utils import now_datetime

MANAGER_ROLES = {
    "Maintenance Manager",
    "TP Manager",
    "System Manager",
}

TRANSITIONS = {
    "Requested": {
        "Approve": "Approved",
        "Reject": "Rejected",
        "Cancel": "Cancelled",
    },
    "Approved": {
        "Mark Planned": "Planned",
        "Cancel": "Cancelled",
    },
    "Planned": {
        "Cancel": "Cancelled",
    },
}


@frappe.whitelist()
def change_movement_request_status(ticket, request_name, action):
    roles = set(frappe.get_roles(frappe.session.user))

    if not roles.intersection(MANAGER_ROLES):
        frappe.throw(
            _("You are not authorised to manage relocation requests."),
            frappe.PermissionError,
        )

    if not frappe.has_permission("Service Ticket", "write", ticket):
        frappe.throw(
            _("You do not have permission to modify this Service Ticket."),
            frappe.PermissionError,
        )

    rows = frappe.db.sql(
        """
        SELECT name, parent, parenttype, parentfield,
               custom_request_status,
               custom_movement_item_type,
               custom_equipment,
               custom_component,
               custom_destination_type,
               custom_destination_branch,
               custom_destination_workshop,
               custom_destination_warehouse,
               custom_destination_text
        FROM `tabService Ticket Movement Request`
        WHERE name = %s
        FOR UPDATE
        """,
        (request_name,),
        as_dict=True,
    )

    if not rows:
        frappe.throw(_("Movement Request not found."))

    row = rows[0]

    if (
        row.parent != ticket
        or row.parenttype != "Service Ticket"
        or row.parentfield != "custom_movement_requests"
    ):
        frappe.throw(_("Movement Request does not belong to this ticket."))

    current = row.custom_request_status or "Requested"
    permitted = TRANSITIONS.get(current, {})

    if action not in permitted:
        frappe.throw(
            _("Action {0} is not permitted from status {1}.").format(
                action, current
            )
        )

    if action == "Approve":
        if row.custom_movement_item_type not in ("Equipment", "Component"):
            frappe.throw(_("Select the movement item type."))

        if not row.custom_equipment:
            frappe.throw(_("Select the equipment."))

        if row.custom_movement_item_type == "Component" and not row.custom_component:
            frappe.throw(_("Select the component."))

        if not row.custom_destination_type:
            frappe.throw(_("Select the destination type."))

        required_destinations = {
            "Customer Branch": "custom_destination_branch",
            "Workshop": "custom_destination_workshop",
            "Company Warehouse": "custom_destination_warehouse",
            "Customer Warehouse": "custom_destination_warehouse",
            "Other Location": "custom_destination_text",
        }

        required_field = required_destinations.get(row.custom_destination_type)

        if required_field and not row.get(required_field):
            frappe.throw(_("Complete the destination details before approval."))

    new_status = permitted[action]

    values = {"custom_request_status": new_status}

    if action == "Approve":
        values["custom_approved_by"] = frappe.session.user
        values["custom_approved_on"] = now_datetime()

    frappe.db.set_value(
        "Service Ticket Movement Request",
        request_name,
        values,
        update_modified=False,
    )

    frappe.get_doc("Service Ticket", ticket).add_comment(
        "Comment",
        text=_("Movement Request {0}: {1} → {2} by {3}").format(
            request_name,
            current,
            new_status,
            frappe.session.user,
        ),
    )

    return {
        "request": request_name,
        "previous_status": current,
        "status": new_status,
    }


def validate_ticket_movement_requests(doc, method=None):
    """Prevent bypassing RM approval through ordinary Service Ticket saves."""

    rows = doc.get("custom_movement_requests") or []

    if doc.is_new():
        existing = {}
    else:
        existing = {
            row.name: row
            for row in frappe.get_all(
                "Service Ticket Movement Request",
                filters={
                    "parent": doc.name,
                    "parenttype": "Service Ticket",
                    "parentfield": "custom_movement_requests",
                },
                fields=[
                    "name",
                    "custom_request_status",
                    "custom_approved_by",
                    "custom_approved_on",
                ],
            )
        }

    for row in rows:
        saved = existing.get(row.name)

        if saved is None:
            if (row.custom_request_status or "Requested") != "Requested":
                frappe.throw(
                    _("New Movement Requests must start as Requested.")
                )
            if row.custom_approved_by or row.custom_approved_on:
                frappe.throw(
                    _("Approval information cannot be entered manually.")
                )
            continue

        if (row.custom_request_status or "Requested") != (
            saved.custom_request_status or "Requested"
        ):
            frappe.throw(
                _("Use Manage Movement Requests to change request status.")
            )

        if (
            row.custom_approved_by != saved.custom_approved_by
            or row.custom_approved_on != saved.custom_approved_on
        ):
            frappe.throw(
                _("Movement Request approval information is read-only.")
            )

    present_names = {row.name for row in rows}

    for name, saved in existing.items():
        if name not in present_names and saved.custom_request_status in (
            "Approved", "Planned", "Completed"
        ):
            frappe.throw(
                _("Approved, planned or completed Movement Requests cannot be deleted.")
            )
