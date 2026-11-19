"""ST notification recipients and three editable status-change ERPNext rules.

Notifications are created disabled. Existing administrator edits are never overwritten.
"""

import frappe

from maintenance_app.notifications.tech_mission import (
    recipients_from_ticket,
)

FIELDNAME = "custom_notification_emails"


def refresh_ticket_notification_emails(doc, method=None):
    """Build current ST customer/external recipients before every document save.

    Unlike TM's historical snapshot, ST recipients reflect the ticket's live
    contact configuration. This runs in the same save transaction as a status
    change, so the Notification sees the current list.
    """
    if not doc.meta.has_field(FIELDNAME):
        return
    recipients = recipients_from_ticket(doc)
    doc.set(FIELDNAME, "\n".join(recipients))


def ensure_st_status_notifications():
    """Install ST recipient field and editable Notification records (disabled)."""
    # This Custom Field is installed by setup/owned_custom_fields.json,
    # as part of after_install / after_migrate. Do not create a second,
    # differently managed schema definition here.
    meta_field = frappe.get_meta("Service Ticket").get_field(FIELDNAME)
    if not meta_field:
        raise RuntimeError(
            "Service Ticket.custom_notification_emails is missing. "
            "Run maintenance_app.setup.owned_fields.install_owned_custom_fields first."
        )
    if meta_field.fieldtype != "Small Text" or (meta_field.options or "") != "Email":
        raise RuntimeError(
            "Service Ticket.custom_notification_emails definition differs from manifest; "
            "review before creating notifications."
        )

    specs = [
        ("GMAO - Service Ticket Resolved", "Resolved", "has been resolved"),
        ("GMAO - Service Ticket Closed", "Closed", "has been closed"),
    ]
    for name, status, wording in specs:
        if frappe.db.exists("Notification", name):
            print("NOTIFICATION_EXISTS:", name)
            continue
        message = f"""<p>Dear Customer,</p>
<p>Your service request <strong>{wording}</strong>.</p>
<p><strong>Service Ticket:</strong> {{{{ doc.name }}}}</p>
<p><strong>Subject:</strong> {{{{ doc.get('custom_subject') or '-' }}}}</p>
<p><strong>Customer:</strong> {{{{ doc.get('custom_customer') or '-' }}}}</p>
<p><strong>Branch:</strong> {{{{ doc.get('custom_client_branch') or '-' }}}}</p>
<p><strong>Ticket Type:</strong> {{{{ doc.get('custom_ticket_type') or '-' }}}}</p>
<p><strong>Status:</strong> {{{{ doc.custom_ticket_status }}}}</p>
<p>Kind regards,<br>Technical Support Team<br>{{{{ doc.get('custom_company') or '' }}}}</p>"""
        frappe.get_doc({
            "doctype": "Notification",
            "name": name,
            "subject": f"Service Ticket {{{{ doc.name }}}} - {status}",
            "document_type": "Service Ticket",
            "channel": "Email",
            "event": "Value Change",
            "value_changed": "custom_ticket_status",
            "condition": f'doc.custom_ticket_status == "{status}"',
            "enabled": 0,
            "message_type": "HTML",
            "message": message,
            "attach_print": 0,
            "send_to_all_assignees": 0,
            "recipients": [{"receiver_by_document_field": FIELDNAME}],
        }).insert(ignore_permissions=True)
        print("CREATED_DISABLED:", name)

    # Waiting for Client is the On Hold status combined with its Hold Reason.
    # The custom on_update hook handles changes to either field without duplicates.
    name = AWAITING_CLIENT_RULE
    if frappe.db.exists("Notification", name):
        print("NOTIFICATION_EXISTS:", name)
    else:
        # Kept disabled until MI Work Outcome / Remote Session / Workshop Repair
        # action requests are mapped into the email template.
        message = """<p>Dear Customer,</p>
<p>We are awaiting your response or confirmation before proceeding with your service request.</p>
<p><strong>Service Ticket:</strong> {{ doc.name }}</p>
<p><strong>Subject:</strong> {{ doc.get('custom_subject') or '-' }}</p>
<p><strong>Customer:</strong> {{ doc.get('custom_customer') or '-' }}</p>
<p><strong>Branch:</strong> {{ doc.get('custom_client_branch') or '-' }}</p>
<p><strong>Ticket Type:</strong> {{ doc.get('custom_ticket_type') or '-' }}</p>
<p><strong>Status:</strong> On Hold – Waiting for Client</p>
<p>Please reply with the information or approval requested by our team.</p>
<p>Kind regards,<br>Technical Support Team<br>{{ doc.get('custom_company') or '' }}</p>"""
        frappe.get_doc({
            "doctype": "Notification",
            "name": name,
            "subject": "Action Required - Service Ticket {{ doc.name }} Awaiting Client",
            "document_type": "Service Ticket",
            "channel": "Email",
            "event": "Custom",
            "enabled": 0,
            "message_type": "HTML",
            "message": message,
            "attach_print": 0,
            "send_to_all_assignees": 0,
            "recipients": [{"receiver_by_document_field": FIELDNAME}],
        }).insert(ignore_permissions=True)
        print("CREATED_DISABLED:", name)

    return "ST_NOTIFICATION_SETUP_COMPLETE"


# In the current ST schema the combination below represents "Awaiting Client".
AWAITING_CLIENT_RULE = "GMAO - Service Ticket Awaiting Client"


def on_ticket_updated_check_awaiting_client(doc, method=None):
    """Queue exactly one customer alert when ENTERING Waiting for Client."""
    if doc.get("custom_ticket_status") != "On Hold":
        return
    if doc.get("custom_hold_reason") != "Waiting for Client":
        return
    previous = doc.get_doc_before_save()
    if not previous:
        return
    if (previous.get("custom_ticket_status") == "On Hold"
            and previous.get("custom_hold_reason") == "Waiting for Client"):
        return  # No repeat notification on routine saves.
    if not frappe.db.exists("Notification", AWAITING_CLIENT_RULE):
        return
    if not frappe.db.get_value("Notification", AWAITING_CLIENT_RULE, "enabled"):
        return
    emails = recipients_from_ticket(doc)
    if not emails:
        return
    frappe.enqueue(
        "maintenance_app.notifications.service_ticket.send_awaiting_client_notification",
        queue="short", enqueue_after_commit=True,
        ticket_name=doc.name, recipient_snapshot=emails,
    )


def send_awaiting_client_notification(ticket_name, recipient_snapshot):
    """Deliver using the editable ERPNext Custom Notification template."""
    if not frappe.db.exists("Notification", AWAITING_CLIENT_RULE):
        return "MISSING_RULE"
    rule = frappe.get_doc("Notification", AWAITING_CLIENT_RULE)
    if not rule.enabled or rule.channel != "Email" or rule.event != "Custom":
        return "RULE_NOT_ENABLED"
    if not frappe.db.exists("Service Ticket", ticket_name):
        return "MISSING_TICKET"
    ticket = frappe.get_doc("Service Ticket", ticket_name)
    # Preserve the actual recipients at the transition, not at job execution.
    ticket.set(FIELDNAME, "\n".join(recipient_snapshot))
    rule.send(ticket)
    return "QUEUED"
