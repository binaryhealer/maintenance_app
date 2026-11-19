"""Service Ticket contact context -> Tech Mission notification snapshot.

- ST is the current contact context.
- TM.custom_notification_emails is created ONCE at TM insertion.
- Existing TM snapshots are not rebuilt during edits.
- Only material operational changes trigger subsequent email alerts.
- Sending is opt-in via site_config maintenance_tm_notifications_enabled=1.

Frappe doc_events handlers in hooks.py call the functions in this module.
"""

import html
import re

import frappe
from frappe.utils import cint, format_datetime, get_datetime

NOTIFICATION_FIELD = "custom_notification_emails"
ADDRESS_RE = re.compile(r"^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$")

WATCHED_FIELDS = {
    "custom_planned_starttime": "Planned Start",
    "custom_planned_endtime": "Planned End",
    "custom_mission_status": "Mission Status",
    "custom_external_vehicle": "External Vehicle",
    "custom_rm_attention_required": "RM Attention Required",
    "custom_rm_attention_reason": "RM Attention Reason",
    "custom_planning_required": "Additional Planning Required",
}
DATETIME_FIELDS = {"custom_planned_starttime", "custom_planned_endtime"}
CHECK_FIELDS = {"custom_rm_attention_required", "custom_planning_required"}


def _emails(value):
    """Parse comma, semicolon or whitespace-separated email addresses."""
    if not value:
        return []
    return [p.strip().lower() for p in re.split(r"[\s,;]+", str(value)) if p.strip()]


def unique_emails(values):
    """Normalize to lowercase, discard empty/invalid, preserve order."""
    result, seen = [], set()
    for value in values:
        for address in _emails(value):
            if ADDRESS_RE.fullmatch(address) and address not in seen:
                seen.add(address)
                result.append(address)
    return result


def _contact_emails(ticket, tablefield):
    return [row.get("custom_email") for row in (ticket.get(tablefield) or [])]


def recipients_from_ticket(ticket, mission=None):
    """Read ONLY ST records and the mission's own applicant email fallback."""
    addresses = [ticket.get("custom_applicant_email")]
    if not addresses[0] and mission:
        addresses[0] = mission.get("custom_applicant_email")

    addresses.extend(_contact_emails(ticket, "custom_branch_contacts"))
    addresses.extend(_contact_emails(ticket, "custom_head_office_contacts"))

    for row in ticket.get("custom_external_contacts") or []:
        if cint(row.get("custom_notify")):
            addresses.append(row.get("custom_email"))

    return unique_emails(addresses)


def validate_ticket_external_contacts(doc, method=None):
    """Guard against adding the same external Contact twice to one ticket."""
    seen = set()
    for row in doc.get("custom_external_contacts") or []:
        contact = row.get("custom_contact")
        if not contact:
            continue
        key = contact.casefold()
        if key in seen:
            frappe.throw(
                "ISP / External Contacts: Contact {0} is listed more than once.".format(
                    frappe.bold(contact)
                )
            )
        seen.add(key)
        if cint(row.get("custom_notify")) and not unique_emails([row.get("custom_email")]):
            frappe.throw(
                "ISP / External Contacts: Please enter a valid Email for "
                "notified Contact {0}.".format(contact)
            )


def snapshot_before_insert(doc, method=None):
    """Freeze recipients once, BEFORE TM is first inserted in the database."""
    if not doc.meta.has_field(NOTIFICATION_FIELD):
        return

    ticket_id = doc.get("custom_service_ticket")
    if ticket_id and frappe.db.exists("Service Ticket", ticket_id):
        ticket = frappe.get_doc("Service Ticket", ticket_id)
        addresses = recipients_from_ticket(ticket, doc)
    else:
        # A standalone TM may not have an ST; do not break its creation.
        addresses = unique_emails([doc.get("custom_applicant_email")])

    doc.set(NOTIFICATION_FIELD, "\n".join(addresses))


def on_mission_created(doc, method=None):
    """ERPNext's New Notification owns creation emails; legacy sender is fallback only."""
    if _standard_rule_enabled("GMAO - Tech Mission Created", "New"):
        return
    _queue_notification(doc, event="created", changes=[])


def _team_map(doc):
    mapping = {}
    for row in doc.get("custom_planned_team") or []:
        tech = (row.get("custom_technician") or "").strip()
        if tech:
            mapping[tech] = (row.get("custom_assigned_vehicle") or "").strip()
    return mapping


def _label_for_value(fieldname, value):
    if fieldname in CHECK_FIELDS:
        return "Yes" if cint(value) else "No"
    if fieldname in DATETIME_FIELDS and value:
        return format_datetime(value, "dd-MMM-yyyy HH:mm")
    return str(value).strip() if value not in (None, "") else "—"


def detect_important_changes(doc, previous):
    """Compare persisted values and actual team assignments, not row IDs."""
    changes = []
    for fieldname, label in WATCHED_FIELDS.items():
        before, after = previous.get(fieldname), doc.get(fieldname)
        if fieldname in CHECK_FIELDS:
            before, after = cint(before), cint(after)
        elif fieldname in DATETIME_FIELDS:
            before = get_datetime(before) if before else None
            after = get_datetime(after) if after else None
        if str(before or "") == str(after or ""):
            continue
        changes.append(
            (label, _label_for_value(fieldname, before), _label_for_value(fieldname, after))
        )

    old_team, new_team = _team_map(previous), _team_map(doc)
    added = sorted(set(new_team) - set(old_team))
    removed = sorted(set(old_team) - set(new_team))
    if added:
        changes.append(("Technician Added", "—", ", ".join(added)))
    if removed:
        changes.append(("Technician Removed", ", ".join(removed), "—"))
    for tech in sorted(set(old_team) & set(new_team)):
        if old_team[tech] != new_team[tech]:
            changes.append(
                (f"Assigned Vehicle ({tech})", old_team[tech] or "—", new_team[tech] or "—")
            )
    if added or removed:
        def summary(mapping):
            return ", ".join(
                f"{tech} ({vehicle})" if vehicle else tech
                for tech, vehicle in sorted(mapping.items())
            ) or "—"
        changes.append(("Team / Vehicle Assignments", summary(old_team), summary(new_team)))
    return changes


def _standard_rule_enabled(name, event):
    """Only an enabled ERPNext Notification of the intended event is eligible."""
    if not frappe.db.exists("Notification", name):
        return False
    return bool(frappe.db.get_value("Notification", name, "enabled")) and (
        frappe.db.get_value("Notification", name, "event") == event
    )


def _new_history_reason(doc, previous):
    current = doc.get("custom_change_history") or []
    past = previous.get("custom_change_history") or []
    if len(current) > len(past):
        return (current[-1].get("custom_change_reason") or "").strip()
    return ""


def on_mission_updated(doc, method=None):
    """One customer notification per save with meaningful TM changes only."""
    if doc.flags.get("gmao_suppress_customer_update_notification"):
        return

    previous = doc.get_doc_before_save()
    if not previous:
        return

    changes = detect_important_changes(doc, previous)
    if not changes:
        return

    if _standard_rule_enabled("GMAO - Tech Mission Updated", "Custom"):
        recipients = unique_emails([doc.get(NOTIFICATION_FIELD)])
        if not recipients:
            return
        # Capture event values NOW; the mission may change again before the worker runs.
        snapshot = {
            "ticket": doc.get("custom_service_ticket") or "",
            "customer": doc.get("custom_parent_customer") or "",
            "branch": doc.get("custom_branch") or "",
            "subject": doc.get("custom_subject") or "",
            "ticket_type": doc.get("custom_ticket_type") or "",
            "equipment": doc.get("custom_asset") or "",
            "component": doc.get("custom_target_component_name") or "",
            "reason": _new_history_reason(doc, previous),
        }
        frappe.enqueue(
            "maintenance_app.notifications.tech_mission.send_update_via_erpnext_notification",
            queue="short",
            enqueue_after_commit=True,
            mission_name=doc.name,
            changes=changes,
            recipients=recipients,
            snapshot=snapshot,
        )
        return

    # Legacy path remains gated by maintenance_tm_notifications_enabled=0.
    _queue_notification(doc, event="updated", changes=changes)


def send_update_via_erpnext_notification(mission_name, changes, recipients, snapshot):
    """Worker uses ERPNext's Notification editor, delivery, and Email Queue.

    Calling Notification.send directly here (rather than queue_send/evaluate_alert)
    is intentional: evaluate_alert reloads the document and discards transient
    old/new values. We have already queued this worker after transaction commit.
    """
    rule_name = "GMAO - Tech Mission Updated"
    if not _standard_rule_enabled(rule_name, "Custom"):
        return
    emails = unique_emails(recipients)
    if not emails:
        return
    alert = frappe.get_doc("Notification", rule_name)
    if alert.channel != "Email":
        return
    doc = frappe.get_doc("Tech Mission", mission_name)
    # Transient rendering context: these are NOT DocFields and are NEVER saved.
    doc.gmao_update_changes = [
        frappe._dict(label=label, before=before, after=after)
        for label, before, after in changes
    ]
    doc.gmao_update_details = frappe._dict(snapshot)
    doc.custom_notification_emails = "\n".join(emails)
    alert.send(doc)


def _queue_notification(doc, event, changes):
    """No email until explicitly enabled for this site, after UAT."""
    if not cint(frappe.conf.get("maintenance_tm_notifications_enabled", 0)):
        return
    recipients = unique_emails([doc.get(NOTIFICATION_FIELD)])
    if not recipients:
        return

    # All args are primitive and serialize cleanly into the queue.
    payload = {
        "mission_name": doc.name,
        "notification_event": event,
        "recipients": recipients,
        "changes": changes,
        "ticket": doc.get("custom_service_ticket") or "",
        "customer": doc.get("custom_parent_customer") or "",
        "branch": doc.get("custom_branch") or "",
        "subject": doc.get("custom_subject") or "",
        "start": _label_for_value("custom_planned_starttime", doc.get("custom_planned_starttime")),
        "end": _label_for_value("custom_planned_endtime", doc.get("custom_planned_endtime")),
        "status": doc.get("custom_mission_status") or "",
        "team": _team_map(doc),
        "external_vehicle": doc.get("custom_external_vehicle") or "",
    }
    frappe.enqueue(
        "maintenance_app.notifications.tech_mission.send_notification",
        queue="short",
        enqueue_after_commit=True,
        **payload,
    )


def send_notification(mission_name, notification_event, recipients, changes, ticket, customer, branch,
                      subject, start, end, status, team, external_vehicle):
    """Background worker: render and queue an email; never sends a PDF."""
    def safe(value):
        return html.escape(str(value or "—"))

    heading = f"Tech Mission {mission_name} {'created' if notification_event == 'created' else 'updated'}"
    team_text = ", ".join(
        f"{user} ({vehicle})" if vehicle else user
        for user, vehicle in sorted((team or {}).items())
    ) or "—"

    items = [
        ("Tech Mission", mission_name),
        ("Service Ticket", ticket),
        ("Customer", customer),
        ("Branch", branch),
        ("Subject", subject),
        ("Planned Start", start),
        ("Planned End", end),
        ("Assigned Technicians / Vehicles", team_text),
        ("External Vehicle", external_vehicle),
        ("Mission Status", status),
    ]
    details = "".join(
        f"<tr><th align='left' style='padding:5px 14px 5px 0'>{safe(label)}</th>"
        f"<td>{safe(value)}</td></tr>" for label, value in items
    )
    change_html = ""
    if changes:
        change_rows = "".join(
            f"<tr><td>{safe(label)}</td><td>{safe(old)}</td><td>{safe(new)}</td></tr>"
            for label, old, new in changes
        )
        change_html = (
            "<h3>Changes</h3><table border='1' cellspacing='0' cellpadding='7'>"
            "<tr><th>Field</th><th>Old</th><th>New</th></tr>"
            + change_rows + "</table>"
        )

    message = (
        f"<p>{safe(heading)}</p>"
        + change_html
        + "<h3>Mission details</h3><table>" + details + "</table>"
        + "<p>This is an automated Tech Mission notification.</p>"
    )
    frappe.sendmail(
        recipients=unique_emails(recipients),
        subject=heading,
        message=message,
    )


# Editable Notification record. It is installed disabled, and only when missing.
# User modifications in ERPNext are never overwritten by subsequent migrations.
def ensure_tm_updated_notification():
    name = "GMAO - Tech Mission Updated"
    if frappe.db.exists("Notification", name):
        return "EXISTS"

    message = """{% set details = doc.get('gmao_update_details') or {} %}
{% set change_rows = doc.get('gmao_update_changes') or [] %}
<p>Dear Customer,</p>
<p>There has been a change to the technical mission for your service request.</p>
<p><strong>Tech Mission:</strong> {{ doc.name }}</p>
<p><strong>Service Ticket:</strong> {{ details.ticket or '-' }}</p>
<p><strong>Customer:</strong> {{ details.customer or '-' }}</p>
<p><strong>Branch:</strong> {{ details.branch or '-' }}</p>
<p><strong>Subject:</strong> {{ details.subject or '-' }}</p>
{% if details.ticket_type %}<p><strong>Ticket Type:</strong> {{ details.ticket_type }}</p>{% endif %}
{% if details.equipment %}<p><strong>Equipment:</strong> {{ details.equipment }}</p>{% endif %}
{% if details.component %}<p><strong>Target Component:</strong> {{ details.component }}</p>{% endif %}
<h3>Changes</h3>
<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse">
<tr><th align="left">Field</th><th align="left">Previous</th><th align="left">Updated</th></tr>
{% for change in change_rows %}
<tr><td>{{ change.label }}</td><td>{{ change.before }}</td><td>{{ change.after }}</td></tr>
{% endfor %}
</table>
{% if details.reason %}
<p><strong>Reason:</strong> {{ details.reason }}</p>
{% endif %}
<p>Kind regards,<br>GoTech Technical Support</p>"""
    frappe.get_doc({
        "doctype": "Notification",
        "name": name,
        "subject": "Tech Mission {{ doc.name }} Updated",
        "document_type": "Tech Mission",
        "channel": "Email",
        "event": "Custom",
        "enabled": 0,
        "message_type": "HTML",
        "message": message,
        "attach_print": 0,
        "send_to_all_assignees": 0,
        "recipients": [
            {"receiver_by_document_field": "custom_notification_emails"}
        ],
    }).insert(ignore_permissions=True)
    return "CREATED_DISABLED"
