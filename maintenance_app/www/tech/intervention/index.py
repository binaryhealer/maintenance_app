import json
import re

import frappe
from frappe.utils import add_days, flt, get_datetime, now_datetime, today

no_cache = 1


def _has_field(doc, fieldname):
    return bool(doc.meta.has_field(fieldname))


def _set_if_field(doc, fieldname, value):
    if _has_field(doc, fieldname):
        doc.set(fieldname, value)


def _user_full_name(user):
    if not user:
        return ""
    return (
        frappe.db.get_value("User", user, "full_name")
        or user
    )



def _normalise_email(value):
    return (value or "").strip().lower()


def _unique_emails(values):
    result = []
    seen = set()

    for value in values or []:
        email = (value or "").strip()

        if not email:
            continue

        key = email.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(email)

    return result


def _get_mi_company(mi):
    """Resolve the Company used for Maintenance Email Profile lookup."""
    company = (mi.get("custom_company") or "").strip()
    if company:
        return company

    service_ticket = (mi.get("custom_service_ticket") or "").strip()
    if service_ticket:
        ticket_meta = frappe.get_meta("Service Ticket")
        for fieldname in ("custom_company", "company"):
            if ticket_meta.has_field(fieldname):
                company = (
                    frappe.db.get_value(
                        "Service Ticket",
                        service_ticket,
                        fieldname,
                    )
                    or ""
                ).strip()
                if company:
                    return company

    parent_mission = (mi.get("custom_parent_mission") or "").strip()
    if parent_mission:
        mission_meta = frappe.get_meta("Tech Mission")
        for fieldname in ("custom_company", "company"):
            if mission_meta.has_field(fieldname):
                company = (
                    frappe.db.get_value(
                        "Tech Mission",
                        parent_mission,
                        fieldname,
                    )
                    or ""
                ).strip()
                if company:
                    return company

    return ""


def _get_maintenance_email_profile(company, usage_key):
    """
    Return the active default Maintenance Email Profile for Company + Usage Key.

    The feature code knows only the stable usage key (for example
    technician_pwa). Administrators can change which profile is assigned
    to that usage without changing this code.
    """
    company = (company or "").strip()
    usage_key = (usage_key or "").strip()

    if not company or not usage_key:
        return None

    if not frappe.db.exists("DocType", "Maintenance Email Usage"):
        return None

    if not frappe.db.exists("DocType", "Maintenance Email Profile"):
        return None

    if not frappe.db.exists("DocType", "Maintenance Email Profile Usage"):
        return None

    usage = frappe.db.get_value(
        "Maintenance Email Usage",
        {
            "custom_usage_key": usage_key,
            "custom_active": 1,
        },
        "name",
    )

    if not usage:
        return None

    rows = frappe.get_all(
        "Maintenance Email Profile Usage",
        filters={
            "parenttype": "Maintenance Email Profile",
            "parentfield": "custom_usage_table",
            "custom_usage": usage,
            "custom_is_default": 1,
            "custom_active": 1,
        },
        fields=["parent", "idx"],
        order_by="idx asc",
        limit_page_length=100,
    )

    for row in rows:
        profile = frappe.get_doc(
            "Maintenance Email Profile",
            row.parent,
        )

        if not profile.get("custom_active"):
            continue

        if (profile.get("custom_company") or "").strip() != company:
            continue

        return profile

    return None


def _build_maintenance_email_identity(mi, usage_key):
    """
    Build sender/signature values for a maintenance email.

    If no configured profile is found, Frappe keeps using its default outgoing
    Email Account and the visible signature falls back to the Company name.
    """
    company = _get_mi_company(mi)
    profile = _get_maintenance_email_profile(company, usage_key)

    identity = {
        "company": company,
        "sender": None,
        "closing": "Kind regards,",
        "signature_name": company or "Support Team",
        "support_email": "",
        "support_phone": "",
        "footer": "",
        "profile": None,
    }

    if not profile:
        return identity

    sender_name = (profile.get("custom_sender_name") or "").strip()
    sender_email = (profile.get("custom_sender_email") or "").strip()

    if sender_email:
        identity["sender"] = (
            f"{sender_name} <{sender_email}>"
            if sender_name
            else sender_email
        )

    identity["closing"] = (
        profile.get("custom_email_closing")
        or identity["closing"]
    ).strip()

    identity["signature_name"] = (
        profile.get("custom_signature_name")
        or sender_name
        or company
        or identity["signature_name"]
    ).strip()

    identity["support_email"] = (
        profile.get("custom_support_email") or ""
    ).strip()

    identity["support_phone"] = (
        profile.get("custom_support_phone") or ""
    ).strip()

    identity["footer"] = (
        profile.get("custom_email_footer") or ""
    ).strip()

    identity["profile"] = profile.name

    return identity


def _html_text(value):
    """Escape plain text and preserve line breaks for HTML email output."""
    return frappe.utils.escape_html(value or "").replace("\n", "<br>")


def _get_contact_primary_email(contact_name):
    if not contact_name:
        return ""

    email = frappe.db.get_value(
        "Contact Email",
        {
            "parent": contact_name,
            "is_primary": 1,
        },
        "email_id",
    )

    if not email:
        email = frappe.db.get_value(
            "Contact Email",
            {
                "parent": contact_name,
            },
            "email_id",
            order_by="idx asc",
        )

    return (email or "").strip()


def _append_recipient_option(options, seen, email, label=None, source=None):
    email = (email or "").strip()
    if not email:
        return

    key = _normalise_email(email)
    if not key or key in seen:
        return

    seen.add(key)
    options.append({
        "email": email,
        "label": (label or email).strip(),
        "source": (source or "Contact").strip(),
    })


def _contact_label(contact_name):
    if not contact_name:
        return ""

    values = frappe.db.get_value(
        "Contact",
        contact_name,
        ["first_name", "middle_name", "last_name", "full_name"],
        as_dict=True,
    ) or {}

    return (
        (values.get("full_name") or "").strip()
        or " ".join(
            value.strip()
            for value in [
                values.get("first_name") or "",
                values.get("middle_name") or "",
                values.get("last_name") or "",
            ]
            if value and value.strip()
        )
        or contact_name
    )


def _append_contact_rows(options, seen, rows, source):
    for row in rows or []:
        contact_name = (
            row.get("custom_contact")
            or row.get("contact")
            or row.get("name")
            or ""
        )
        email = (
            row.get("custom_email")
            or row.get("email")
            or row.get("email_id")
            or ""
        ).strip()

        if not email and contact_name:
            email = _get_contact_primary_email(contact_name)

        label = (
            row.get("custom_contact_name")
            or row.get("contact_name")
            or _contact_label(contact_name)
            or email
        )

        _append_recipient_option(
            options,
            seen,
            email,
            label=label,
            source=source,
        )


def _get_customer_linked_contacts(customer):
    """Return live Contact records linked to the Customer through Dynamic Link."""
    if not customer:
        return []

    contacts = frappe.db.sql(
        """
        SELECT DISTINCT c.name
        FROM `tabContact` c
        INNER JOIN `tabDynamic Link` dl
            ON dl.parent = c.name
           AND dl.parenttype = 'Contact'
        WHERE dl.link_doctype = 'Customer'
          AND dl.link_name = %(customer)s
        ORDER BY c.first_name, c.last_name, c.name
        """,
        {"customer": customer},
        as_dict=True,
    )

    result = []
    for row in contacts:
        contact_name = row.get("name")
        email = _get_contact_primary_email(contact_name)
        if email:
            result.append({
                "custom_contact": contact_name,
                "custom_contact_name": _contact_label(contact_name),
                "custom_email": email,
            })

    return result


def _get_system_user_recipient_rows():
    """All enabled System Users are valid internal recipients across companies."""
    rows = frappe.get_all(
        "User",
        filters={
            "enabled": 1,
            "user_type": "System User",
        },
        fields=["name", "email", "full_name"],
        order_by="full_name asc, name asc",
        limit_page_length=1000,
    )

    result = []
    for row in rows:
        email = (row.get("email") or row.get("name") or "").strip()
        if not email or "@" not in email:
            continue
        if row.get("name") in ("Guest", "Administrator"):
            continue

        result.append({
            "email": email,
            "label": (row.get("full_name") or row.get("name") or email).strip(),
            "source": "System User",
        })

    return result


def _get_mi_email_recipients_data(mi):
    """
    Build the approved recipient list and the automatic defaults.

    Defaults:
      TO = current MI applicant, falling back to Service Ticket applicant
      CC = live Client Branch contacts, excluding the TO applicant

    Allowed picker sources:
      Applicant + live Client Branch contacts + Customer/head-office contacts
      + all enabled System Users.
    """
    options = []
    seen = set()

    ticket = None
    if mi.get("custom_service_ticket"):
        ticket = frappe.get_doc(
            "Service Ticket",
            mi.get("custom_service_ticket"),
        )

    # Prefer the applicant stored on this MI. This matters for Additional MIs,
    # where the selected applicant can differ from the original ticket applicant.
    applicant_contact = (
        mi.get("custom_applicant")
        or (ticket.get("custom_applicant") if ticket else None)
        or ""
    )

    applicant_email = (
        (mi.get("custom_applicant_email") or "").strip()
        or (
            (ticket.get("custom_applicant_email") or "").strip()
            if ticket else ""
        )
        or _get_contact_primary_email(applicant_contact)
    )

    applicant_label = (
        _contact_label(applicant_contact)
        or applicant_email
        or "Applicant"
    )

    _append_recipient_option(
        options,
        seen,
        applicant_email,
        label=applicant_label,
        source="Applicant",
    )

    branch_name = (
        mi.get("custom_branch")
        or (ticket.get("custom_client_branch") if ticket else None)
        or ""
    )

    branch_rows = []
    live_head_office_rows = []

    # Live Client Branch is the source of truth for branch contacts.
    if branch_name and frappe.db.exists("Client Branch", branch_name):
        branch = frappe.get_doc("Client Branch", branch_name)

        for fieldname in (
            "custom_branch_contacts",
            "branch_contacts",
            "contacts",
        ):
            if branch.meta.has_field(fieldname):
                branch_rows = branch.get(fieldname) or []
                if branch_rows:
                    break

        for fieldname in (
            "custom_head_office_contacts",
            "head_office_contacts",
        ):
            if branch.meta.has_field(fieldname):
                live_head_office_rows = branch.get(fieldname) or []
                if live_head_office_rows:
                    break

    # Backward-compatible fallback for older records/sites.
    if not branch_rows:
        branch_rows = (
            mi.get("custom_branch_contacts")
            or (
                ticket.get("custom_branch_contacts")
                if ticket else []
            )
            or []
        )

    branch_emails = []
    for row in branch_rows:
        email = (
            row.get("custom_email")
            or row.get("email")
            or row.get("email_id")
            or ""
        ).strip()

        contact_name = (
            row.get("custom_contact")
            or row.get("contact")
            or ""
        )

        if not email and contact_name:
            email = _get_contact_primary_email(contact_name)

        if email:
            branch_emails.append(email)

    _append_contact_rows(
        options,
        seen,
        branch_rows,
        "Client Branch",
    )

    # Head-office/customer snapshot contacts carried by the MI/Ticket.
    head_office_rows = (
        live_head_office_rows
        or mi.get("custom_head_office_contacts")
        or (
            ticket.get("custom_head_office_contacts")
            if ticket else []
        )
        or []
    )

    _append_contact_rows(
        options,
        seen,
        head_office_rows,
        "Customer / Head Office",
    )

    customer = (
        mi.get("custom_parent_customer")
        or (ticket.get("custom_customer") if ticket else None)
        or ""
    )

    # Also add current Contacts linked directly to the Customer so the picker
    # does not depend only on snapshots copied when the ticket was created.
    _append_contact_rows(
        options,
        seen,
        _get_customer_linked_contacts(customer),
        "Customer / Head Office",
    )

    for user_row in _get_system_user_recipient_rows():
        _append_recipient_option(
            options,
            seen,
            user_row.get("email"),
            label=user_row.get("label"),
            source=user_row.get("source"),
        )

    applicant_key = _normalise_email(applicant_email)

    default_to = [applicant_email] if applicant_email else []
    default_cc = [
        email
        for email in _unique_emails(branch_emails)
        if _normalise_email(email) != applicant_key
    ]

    return {
        "to": default_to,
        "cc": default_cc,
        "options": options,
    }


def _get_report_email_defaults(mi):
    data = _get_mi_email_recipients_data(mi)
    return {
        "to": data.get("to") or [],
        "cc": data.get("cc") or [],
    }


def _parse_email_values(value):
    """Accept JSON arrays and common pasted separators, then normalise."""
    if not value:
        return []

    parsed = frappe.parse_json(value)

    if isinstance(parsed, str):
        parsed = [parsed]

    result = []
    for item in parsed or []:
        if not item:
            continue

        for email in re.split(r"[,;\n\r\t ]+", str(item)):
            email = email.strip()
            if email:
                result.append(email)

    return _unique_emails(result)


def _validate_mi_email_recipients(mi, to_list, cc_list):
    allowed_data = _get_mi_email_recipients_data(mi)
    allowed = {
        _normalise_email(row.get("email"))
        for row in allowed_data.get("options") or []
        if row.get("email")
    }

    invalid = [
        email
        for email in _unique_emails((to_list or []) + (cc_list or []))
        if _normalise_email(email) not in allowed
    ]

    if invalid:
        frappe.throw(
            "These email addresses are not in the approved recipient list: "
            + ", ".join(invalid)
        )

    to_keys = {_normalise_email(email) for email in to_list or []}
    clean_cc = [
        email
        for email in cc_list or []
        if _normalise_email(email) not in to_keys
    ]

    return _unique_emails(to_list), _unique_emails(clean_cc)


@frappe.whitelist()
def get_mi_email_recipients(mi_name):
    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    mi = frappe.get_doc("Mission Intervention", mi_name)
    mi.check_permission("read")

    return _get_mi_email_recipients_data(mi)


def _equipment_display(equipment_name):
    if not equipment_name:
        return ""

    values = frappe.db.get_value(
        "Installed Equipment",
        equipment_name,
        [
            "custom_display_name",
            "custom_asset_name",
            "custom_client_asset_code",
            "custom_asset_id",
            "custom_make",
            "custom_model",
        ],
        as_dict=True,
    ) or {}

    return (
        values.get("custom_display_name")
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


def get_context(context):
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.local.flags.redirect_to = "/login"
        raise frappe.PermissionError("Not logged in")

    mi_name = frappe.form_dict.get("name")

    if not mi_name:
        frappe.throw("Mission Intervention missing.")

    mi = frappe.get_doc("Mission Intervention", mi_name)

    ticket_type = ""
    request_type = ""

    if mi.get("custom_service_ticket"):
        ticket_values = frappe.db.get_value(
            "Service Ticket",
            mi.custom_service_ticket,
            ["custom_ticket_type", "custom_request_type"],
            as_dict=True,
        ) or {}

        ticket_type = ticket_values.get("custom_ticket_type") or ""
        request_type = ticket_values.get("custom_request_type") or ""

    context.mi = mi
    context.page_title = "MI " + mi.name
    context.ticket_type = ticket_type
    context.request_type = request_type
    context.equipment_display = _equipment_display(mi.get("custom_asset"))
    context.technician_display = _user_full_name(
        mi.get("custom_technician")
    )
    context.current_user_full_name = _user_full_name(
        frappe.session.user
    )
    context.technician_signatory_display = _user_full_name(
        mi.get("custom_technician_signatory")
    )

    # Specialised Testing Type choices used by the PWA before Check In.
    context.specialised_testing_types = []
    if mi.get("custom_intervention_type") == "Specialised Testing":
        testing_meta = frappe.get_meta("Specialised Testing Type")
        filters = {}
        if testing_meta.has_field("custom_active"):
            filters["custom_active"] = 1

        context.specialised_testing_types = frappe.get_all(
            "Specialised Testing Type",
            filters=filters,
            fields=["name"],
            order_by="name asc",
            limit_page_length=500,
        )

    # General Installation Type choices used by the PWA before Check In.
    # Load all records without an Active filter.  The master field used for the
    # technician-facing label is custom_installation_type.
    context.general_installation_types = []
    if mi.get("custom_intervention_type") == "General Installation":
        installation_meta = frappe.get_meta("General Installation Type")

        fields = ["name"]
        if installation_meta.has_field("custom_installation_type"):
            fields.append("custom_installation_type")

        context.general_installation_types = frappe.get_all(
            "General Installation Type",
            fields=fields,
            order_by="custom_installation_type asc"
                if installation_meta.has_field("custom_installation_type")
                else "name asc",
            limit_page_length=500,
        )

    report_email_data = _get_mi_email_recipients_data(mi)

    context.report_email_to = ", ".join(
        report_email_data.get("to") or []
    )
    context.report_email_cc = ", ".join(
        report_email_data.get("cc") or []
    )
    context.report_email_options_json = json.dumps(
        report_email_data.get("options") or []
    )


@frappe.whitelist()
def create_follow_up_mi(
    source_mi_name,
    follow_up_date=None,
    reason=None,
):
    if not source_mi_name:
        frappe.throw("Source Mission Intervention is required.")

    source = frappe.get_doc(
        "Mission Intervention",
        source_mi_name,
    )

    if source.docstatus != 1:
        frappe.throw(
            "Submit the current intervention before creating a follow-up."
        )

    allowed_outcomes = [
        "Continue Work",
        "Waiting for Parts",
        "Waiting for Client",
        "Could Not Complete",
        "To Quote (Billable)",
    ]

    if source.get("custom_work_outcome") not in allowed_outcomes:
        frappe.throw(
            "A follow-up MI is only available for ongoing or waiting work."
        )

    if not source.get("custom_parent_mission"):
        frappe.throw("The intervention is not linked to a Tech Mission.")

    # Multiple draft MIs are valid under one Tech Mission.
    # Only prevent a duplicate follow-up for this same source MI when the
    # continuation-link field exists on this site.
    existing_draft = None
    mi_meta = frappe.get_meta("Mission Intervention")

    if mi_meta.has_field("custom_previous_intervention"):
        existing_draft = frappe.db.get_value(
            "Mission Intervention",
            {
                "custom_parent_mission": source.custom_parent_mission,
                "custom_previous_intervention": source.name,
                "docstatus": 0,
            },
            "name",
            order_by="creation desc",
        )

    if existing_draft:
        return {
            "created": False,
            "intervention": existing_draft,
            "message": "An open follow-up MI already exists for this work item.",
        }

    follow_up = frappe.new_doc("Mission Intervention")

    copy_fields = [
        "custom_service_ticket",
        "custom_parent_mission",
        "custom_parent_customer",
        "custom_branch",
        "custom_asset",
        "custom_parent_equipment",
        "custom_equipment_component",
        "custom_target_component_name",
        "custom_component_item",
        "custom_component_serial",
        "custom_component_brand",
        "custom_component_model",
        "custom_subject",
        "custom_intervention_type",
        "custom_specialised_testing_type",
        "custom_general_installation_type",
        "custom_service_type",
        "custom_priority",
        "custom_response_due",
        "custom_resolution_due",
        "custom_technician",
    ]

    for fieldname in copy_fields:
        if _has_field(follow_up, fieldname):
            follow_up.set(
                fieldname,
                source.get(fieldname),
            )

    # Keep General Installation follow-ups explicitly aligned with the source MI.
    # The subtype is copied when available, but a blank subtype remains editable
    # on the new draft MI before Check In.
    if source.get("custom_intervention_type") == "General Installation":
        _set_if_field(
            follow_up,
            "custom_intervention_type",
            "General Installation",
        )
        _set_if_field(
            follow_up,
            "custom_general_installation_type",
            source.get("custom_general_installation_type") or "",
        )

    _set_if_field(
        follow_up,
        "custom_mi_purpose",
        "Follow-up",
    )
    _set_if_field(
        follow_up,
        "custom_previous_intervention",
        source.name,
    )
    _set_if_field(
        follow_up,
        "custom_continuation_reason",
        reason or source.get("custom_work_progress") or "",
    )

    # A follow-up MI is a fresh work session.
    # Clear any DocType defaults / carried workflow state so the technician
    # must choose the outcome for this new visit.  In particular, some sites
    # default custom_work_outcome to "Work Completed", which caused follow-up
    # MIs to skip the outcome selector in the PWA.
    _set_if_field(follow_up, "custom_work_outcome", "")
    _set_if_field(follow_up, "custom_work_progress", "")
    _set_if_field(follow_up, "custom_start_time", None)
    _set_if_field(follow_up, "custom_start_date", None)
    _set_if_field(follow_up, "custom_end_time", None)
    _set_if_field(follow_up, "custom_completed_time", None)
    _set_if_field(follow_up, "custom_checkout_status", "Not Started")
    _set_if_field(follow_up, "custom_client_signature_received", 0)

    if _has_field(follow_up, "custom_follow_up_sequence"):
        previous_sequence = (
            source.get("custom_follow_up_sequence") or 0
        )
        follow_up.custom_follow_up_sequence = (
            int(previous_sequence) + 1
        )

    if reason and _has_field(follow_up, "custom_subject"):
        base_subject = source.get("custom_subject") or source.name
        follow_up.custom_subject = (
            f"Follow-up: {base_subject}"
        )

    if follow_up_date:
        follow_up_datetime = get_datetime(
            f"{follow_up_date} 08:00:00"
        )

        _set_if_field(
            follow_up,
            "custom_planned_starttime",
            follow_up_datetime,
        )
        _set_if_field(
            follow_up,
            "custom_planned_endtime",
            follow_up_datetime.replace(hour=17),
        )

    follow_up.insert(ignore_permissions=True)

    # Force the newly-created follow-up to remain a fresh work session even if
    # a DocType default / server-side hook writes a default outcome during insert.
    # The technician must explicitly choose the outcome for the follow-up.
    reset_values = {}

    if follow_up.meta.has_field("custom_work_outcome"):
        reset_values["custom_work_outcome"] = ""

    if follow_up.meta.has_field("custom_work_progress"):
        reset_values["custom_work_progress"] = ""

    if follow_up.meta.has_field("custom_start_time"):
        reset_values["custom_start_time"] = None

    if follow_up.meta.has_field("custom_start_date"):
        reset_values["custom_start_date"] = None

    if follow_up.meta.has_field("custom_end_time"):
        reset_values["custom_end_time"] = None

    if follow_up.meta.has_field("custom_completed_time"):
        reset_values["custom_completed_time"] = None

    if follow_up.meta.has_field("custom_checkout_status"):
        reset_values["custom_checkout_status"] = "Not Started"

    if reset_values:
        frappe.db.set_value(
            "Mission Intervention",
            follow_up.name,
            reset_values,
            update_modified=False,
        )

        for fieldname, value in reset_values.items():
            follow_up.set(fieldname, value)

    mission = frappe.get_doc(
        "Tech Mission",
        source.custom_parent_mission,
    )

    if follow_up_date:
        mission.custom_planned_starttime = get_datetime(
            f"{follow_up_date} 08:00:00"
        )
        mission.custom_planned_endtime = get_datetime(
            f"{follow_up_date} 17:00:00"
        )

    if mission.meta.has_field("custom_latest_intervention"):
        mission.custom_latest_intervention = follow_up.name

    if mission.meta.has_field("custom_open_work_remaining"):
        mission.custom_open_work_remaining = 1

    # Add the Follow-up MI to the Tech Mission live register immediately.
    # Creating a future follow-up must NOT restart the SLA clock.  The TM/ST
    # therefore remain On Hold until the technician actually checks in.
    live_row = None
    if mission.meta.has_field("custom_intervention_table"):
        for row in mission.get("custom_intervention_table") or []:
            if row.get("custom_intervention_reference") == follow_up.name:
                live_row = row
                break

        if live_row is None:
            live_row = mission.append("custom_intervention_table", {})

        live_values = {
            "custom_date": (
                follow_up.get("custom_planned_starttime")
                or frappe.utils.now_datetime()
            ),
            "custom_intervention_reference": follow_up.name,
            "custom_technician": follow_up.get("custom_technician"),
            "custom_hours": 0,
            "custom_status": "Draft",
            "custom_work_progress": "",
        }

        for fieldname, value in live_values.items():
            if live_row.meta.has_field(fieldname):
                live_row.set(fieldname, value)

    hold_reason_map = {
        "Continue Work": "Continue Work",
        "Waiting for Parts": "Waiting for Parts",
        "Waiting for Client": "Waiting for Client",
        "To Quote (Billable)": "To Quote",
        "Could Not Complete": "Could Not Complete",
    }
    hold_reason = hold_reason_map.get(
        source.get("custom_work_outcome"),
        "Continue Work",
    )

    if mission.meta.has_field("custom_mission_status"):
        mission.custom_mission_status = "On Hold"
    if mission.meta.has_field("custom_hold_reason"):
        mission.custom_hold_reason = hold_reason

    mission.save(ignore_permissions=True)

    if mission.get("custom_service_ticket"):
        ticket = frappe.get_doc(
            "Service Ticket",
            mission.custom_service_ticket,
        )
        if ticket.meta.has_field("custom_ticket_status"):
            ticket.custom_ticket_status = "On Hold"
        if ticket.meta.has_field("custom_hold_reason"):
            ticket.custom_hold_reason = hold_reason
        ticket.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "created": True,
        "intervention": follow_up.name,
    }



@frappe.whitelist()
def get_additional_mi_intervention_types():
    """Return live Select options from Mission Intervention.custom_intervention_type."""
    field = frappe.get_meta("Mission Intervention").get_field(
        "custom_intervention_type"
    )

    if not field:
        frappe.throw(
            "Mission Intervention field custom_intervention_type is missing."
        )

    return [
        value.strip()
        for value in (field.options or "").split("\n")
        if value.strip()
    ]


@frappe.whitelist()
def get_specialised_testing_types():
    meta = frappe.get_meta("Specialised Testing Type")
    filters = {}

    if meta.has_field("custom_active"):
        filters["custom_active"] = 1

    return frappe.get_all(
        "Specialised Testing Type",
        filters=filters,
        fields=["name"],
        order_by="name asc",
        limit_page_length=500,
    )


@frappe.whitelist()
def get_general_installation_types():
    """Return live General Installation Type master records for the PWA."""
    meta = frappe.get_meta("General Installation Type")
    fields = ["name"]

    if meta.has_field("custom_installation_type"):
        fields.append("custom_installation_type")

    return frappe.get_all(
        "General Installation Type",
        fields=fields,
        order_by=(
            "custom_installation_type asc"
            if meta.has_field("custom_installation_type")
            else "name asc"
        ),
        limit_page_length=500,
    )


@frappe.whitelist()
def change_intervention_type_from_pwa(
    mi_name,
    intervention_type,
    specialised_testing_type=None,
    general_installation_type=None,
):
    """
    Change the actual intervention type while the MI is still Draft.

    The normal MI/Service Ticket submit logic remains responsible for writing
    the final type back to Service Ticket.custom_actual_ticket_type.
    """
    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    mi = frappe.get_doc("Mission Intervention", mi_name)
    mi.check_permission("write")

    if mi.docstatus != 0:
        frappe.throw("Intervention Type can only be changed on a draft intervention.")

    field = frappe.get_meta("Mission Intervention").get_field(
        "custom_intervention_type"
    )
    if not field:
        frappe.throw(
            "Mission Intervention field custom_intervention_type is missing."
        )

    allowed_types = [
        value.strip()
        for value in (field.options or "").split("\n")
        if value.strip()
    ]

    intervention_type = (intervention_type or "").strip()
    if not intervention_type or intervention_type not in allowed_types:
        frappe.throw("Please select a valid Intervention Type.")

    specialised_testing_type = (specialised_testing_type or "").strip()
    general_installation_type = (general_installation_type or "").strip()

    if intervention_type == "Specialised Testing":
        if not specialised_testing_type:
            frappe.throw("Specialised Testing Type is required.")

        if not frappe.db.exists(
            "Specialised Testing Type",
            specialised_testing_type,
        ):
            frappe.throw("Invalid Specialised Testing Type.")

        testing_meta = frappe.get_meta("Specialised Testing Type")
        if testing_meta.has_field("custom_active"):
            is_active = frappe.db.get_value(
                "Specialised Testing Type",
                specialised_testing_type,
                "custom_active",
            )
            if not is_active:
                frappe.throw("Selected Specialised Testing Type is inactive.")

        _set_if_field(
            mi,
            "custom_specialised_testing_type",
            specialised_testing_type,
        )
        _set_if_field(mi, "custom_general_installation_type", "")

    elif intervention_type == "General Installation":
        if not general_installation_type:
            frappe.throw("General Installation Type is required.")

        if not frappe.db.exists(
            "General Installation Type",
            general_installation_type,
        ):
            frappe.throw("Invalid General Installation Type.")

        _set_if_field(
            mi,
            "custom_general_installation_type",
            general_installation_type,
        )
        _set_if_field(mi, "custom_specialised_testing_type", "")

    else:
        # Clear subtype values that belong to a previous classification.
        _set_if_field(mi, "custom_specialised_testing_type", "")
        _set_if_field(mi, "custom_general_installation_type", "")

    mi.set("custom_intervention_type", intervention_type)
    mi.save()
    frappe.db.commit()

    return {
        "ok": True,
        "intervention": mi.name,
        "intervention_type": intervention_type,
        "specialised_testing_type": (
            mi.get("custom_specialised_testing_type") or ""
        ),
        "general_installation_type": (
            mi.get("custom_general_installation_type") or ""
        ),
    }


@frappe.whitelist()
def create_additional_mi_from_pwa(
    mission_name,
    asset_name,
    reason,
    subject,
    intervention_type,
    target_scope="Equipment",
    component_row_id=None,
    specialised_testing_type=None,
    applicant=None,
):
    """Create an Additional MI through the existing API, then apply PWA-only fields safely."""
    if not applicant:
        frappe.throw("Applicant is required.")

    get_applicants = frappe.get_attr(
        "maintenance_app.api.get_eq_applicants_for_equipment"
    )
    eligible_rows = get_applicants(asset_name) or []
    eligible = set()

    for row in eligible_rows:
        if isinstance(row, dict):
            value = (
                row.get("contact")
                or row.get("name")
                or row.get("custom_contact")
                or row.get("value")
            )
        else:
            value = str(row) if row else ""

        if value:
            eligible.add(value)

    if applicant not in eligible:
        frappe.throw(
            "Selected Applicant is not valid for this customer/branch."
        )

    if intervention_type == "Specialised Testing":
        specialised_testing_type = (
            specialised_testing_type or ""
        ).strip()

        if not specialised_testing_type:
            frappe.throw("Specialised Testing Type is required.")

        if not frappe.db.exists(
            "Specialised Testing Type",
            specialised_testing_type,
        ):
            frappe.throw("Invalid Specialised Testing Type.")
    else:
        specialised_testing_type = ""

    create_method = frappe.get_attr(
        "maintenance_app.api.create_additional_intervention_from_mission"
    )

    result = create_method(
        mission_name=mission_name,
        asset_name=asset_name,
        reason=reason,
        subject=subject,
        intervention_type=intervention_type,
        target_scope=target_scope,
        component_row_id=component_row_id,
    )

    intervention = (
        (result or {}).get("intervention")
        if isinstance(result, dict)
        else None
    )

    if not intervention:
        frappe.throw(
            "Additional MI was created but no intervention reference was returned."
        )

    new_mi = frappe.get_doc(
        "Mission Intervention",
        intervention,
    )

    _set_if_field(
        new_mi,
        "custom_applicant",
        applicant,
    )

    if intervention_type == "Specialised Testing":
        _set_if_field(
            new_mi,
            "custom_specialised_testing_type",
            specialised_testing_type,
        )

    new_mi.save(ignore_permissions=True)
    frappe.db.commit()

    return result


# -----------------------------------------------------------------------------
# PWA CHECK-IN / CHECK-OUT
# -----------------------------------------------------------------------------


def _get_pwa_mi_for_update(mi_name):
    """Return a writable draft Mission Intervention for the logged-in user."""
    if not frappe.session.user or frappe.session.user == "Guest":
        raise frappe.PermissionError("Please log in before updating an intervention.")

    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    mi = frappe.get_doc("Mission Intervention", mi_name)
    mi.check_permission("write")

    if mi.docstatus != 0:
        frappe.throw("Only a draft intervention can be checked in or checked out.")

    return mi


def _save_pwa_gps(mi, prefix, latitude=None, longitude=None, accuracy=None):
    """Save GPS values when both latitude and longitude were supplied."""
    if latitude in (None, "") or longitude in (None, ""):
        return False

    latitude_value = flt(latitude)
    longitude_value = flt(longitude)

    _set_if_field(mi, f"custom_{prefix}_latitude", latitude_value)
    _set_if_field(mi, f"custom_{prefix}_longitude", longitude_value)

    if accuracy not in (None, ""):
        _set_if_field(mi, f"custom_{prefix}_accuracy", flt(accuracy))

    return True


@frappe.whitelist()
def pwa_check_in(
    mi_name,
    latitude=None,
    longitude=None,
    accuracy=None,
    specialised_testing_type=None,
    general_installation_type=None,
):
    """Check into an MI from the technician PWA using server time."""
    mi = _get_pwa_mi_for_update(mi_name)

    if mi.get("custom_start_time"):
        frappe.throw("This intervention is already checked in.")

    if mi.get("custom_intervention_type") == "Specialised Testing":
        selected_testing_type = (
            specialised_testing_type
            or mi.get("custom_specialised_testing_type")
            or ""
        ).strip()

        if not selected_testing_type:
            frappe.throw(
                "Please select Specialised Testing Type before Check In."
            )

        if not frappe.db.exists(
            "Specialised Testing Type",
            selected_testing_type,
        ):
            frappe.throw("Invalid Specialised Testing Type.")

        _set_if_field(
            mi,
            "custom_specialised_testing_type",
            selected_testing_type,
        )

    if mi.get("custom_intervention_type") == "General Installation":
        selected_installation_type = (
            general_installation_type
            or mi.get("custom_general_installation_type")
            or ""
        ).strip()

        if not selected_installation_type:
            frappe.throw(
                "Please select General Installation Type before Check In."
            )

        if not frappe.db.exists(
            "General Installation Type",
            selected_installation_type,
        ):
            frappe.throw("Invalid General Installation Type.")

        _set_if_field(
            mi,
            "custom_general_installation_type",
            selected_installation_type,
        )

    checked_in_at = now_datetime()

    _set_if_field(mi, "custom_start_time", checked_in_at)
    _set_if_field(mi, "custom_start_date", checked_in_at.date())
    _set_if_field(mi, "custom_checkout_status", "Checked In")

    gps_saved = _save_pwa_gps(
        mi,
        "checkin",
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    mi.save()

    # Keep the Tech Mission live MI register and TM/ST aggregate status aligned.
    sync_method = frappe.get_attr(
        "maintenance_app.api.sync_mi_to_mission_register"
    )
    sync_method(mi.name)

    frappe.db.commit()

    return {
        "ok": True,
        "intervention": mi.name,
        "checked_in_at": checked_in_at,
        "gps_saved": gps_saved,
    }


@frappe.whitelist()
def pwa_check_out(mi_name, latitude=None, longitude=None, accuracy=None):
    """Check out of an MI from the technician PWA using server time."""
    mi = _get_pwa_mi_for_update(mi_name)

    if not mi.get("custom_start_time"):
        frappe.throw("Please Check In before checking out.")

    if mi.get("custom_end_time"):
        frappe.throw("This intervention is already checked out.")

    if not mi.get("custom_work_outcome") or not mi.get("custom_work_progress"):
        frappe.throw(
            "Please save Work Outcome and Technical Progress Notes before checking out."
        )

    required_confirmation = {
        "custom_signatory_name": "Client Signatory Name",
        "custom_client_signature": "Client Signature",
        "custom_tech_signature": "Technician Signature",
    }

    missing = [
        label
        for fieldname, label in required_confirmation.items()
        if _has_field(mi, fieldname) and not mi.get(fieldname)
    ]

    if missing:
        frappe.throw(
            "Please complete Client Confirmation before checking out: "
            + ", ".join(missing)
        )

    if mi.get("custom_work_outcome") == "Work Completed":
        rating_fields = {
            "custom_quality_score": "Quality Rating",
            "custom_hse_score": "HSE Rating",
        }
        missing_ratings = [
            label
            for fieldname, label in rating_fields.items()
            if _has_field(mi, fieldname) and not mi.get(fieldname)
        ]
        if missing_ratings:
            frappe.throw(
                "Please complete ratings for completed work: "
                + ", ".join(missing_ratings)
            )

    checked_out_at = now_datetime()

    _set_if_field(mi, "custom_end_time", checked_out_at)
    _set_if_field(mi, "custom_checkout_status", "Checked Out")

    if (
        mi.get("custom_work_outcome") == "Work Completed"
        and not mi.get("custom_completed_time")
    ):
        _set_if_field(mi, "custom_completed_time", checked_out_at)

    if _has_field(mi, "custom_hours_worked"):
        start_time = get_datetime(mi.get("custom_start_time"))
        elapsed_seconds = (checked_out_at - start_time).total_seconds()
        if elapsed_seconds > 0:
            mi.custom_hours_worked = round(elapsed_seconds / 3600, 2)

    gps_saved = _save_pwa_gps(
        mi,
        "checkout",
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    mi.save()

    # Checked-out state must appear immediately in the TM live MI register.
    sync_method = frappe.get_attr(
        "maintenance_app.api.sync_mi_to_mission_register"
    )
    sync_method(mi.name)

    frappe.db.commit()

    return {
        "ok": True,
        "intervention": mi.name,
        "checked_out_at": checked_out_at,
        "hours_worked": mi.get("custom_hours_worked"),
        "gps_saved": gps_saved,
    }


def _get_client_email_attachments(mi_name):
    """Return only MI files that are explicitly allowed to go to the client."""
    file_meta = frappe.get_meta("File")
    if not file_meta.has_field("custom_private_for_client"):
        frappe.throw(
            "File field custom_private_for_client is missing. "
            "Add the Private for Client checkbox before sending attachments."
        )

    rows = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Mission Intervention",
            "attached_to_name": mi_name,
            "is_folder": 0,
            "custom_private_for_client": 0,
        },
        fields=["name", "file_name"],
        order_by="creation asc",
        limit_page_length=100,
    )

    attachments = []
    for row in rows:
        file_doc = frappe.get_doc("File", row.name)

        # Defence in depth: never trust only the query filter for client privacy.
        if file_doc.get("custom_private_for_client"):
            continue

        try:
            content = file_doc.get_content()
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Could not attach MI file {file_doc.name}",
            )
            continue

        attachments.append({
            "fname": file_doc.file_name or file_doc.name,
            "fcontent": content,
        })

    return attachments


@frappe.whitelist()
def set_file_private_for_client(file_name, is_private=0):
    if not file_name:
        frappe.throw("File is required.")

    file_doc = frappe.get_doc("File", file_name)

    if file_doc.get("attached_to_doctype") != "Mission Intervention":
        frappe.throw("Only Mission Intervention attachments can be updated here.")

    mi_name = file_doc.get("attached_to_name")
    if not mi_name:
        frappe.throw("This file is not attached to a Mission Intervention.")

    mi = frappe.get_doc("Mission Intervention", mi_name)
    mi.check_permission("write")

    if not file_doc.meta.has_field("custom_private_for_client"):
        frappe.throw("File field custom_private_for_client is missing.")

    value = 1 if str(is_private).lower() in ("1", "true", "yes") else 0
    frappe.db.set_value(
        "File",
        file_doc.name,
        "custom_private_for_client",
        value,
        update_modified=False,
    )
    frappe.db.commit()

    return {
        "ok": True,
        "file": file_doc.name,
        "private_for_client": value,
    }


@frappe.whitelist()
def send_mi_report(
    mi_name,
    recipients,
    cc=None,
    send_photos=0,
):
    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name,
    )

    if mi.docstatus != 1:
        frappe.throw(
            "Submit the intervention before emailing the report."
        )

    to_list = _parse_email_values(recipients)
    cc_list = _parse_email_values(cc)

    if not to_list:
        frappe.throw("At least one email recipient is required.")

    # The technician may only send to the MI applicant, customer/branch contacts,
    # or enabled System Users. Enforce this on the server as well as in the UI.
    to_list, cc_list = _validate_mi_email_recipients(
        mi,
        to_list,
        cc_list,
    )

    # Store only the TO-recipient names in custom_customer_remarks.
    # Example:
    #   julie@gotechmu.com, gerrard@gotechmu.com
    # becomes:
    #   julie, gerrard
    #
    # CC recipients are intentionally excluded.
    recipient_names = []
    seen_names = set()

    for email in (to_list + cc_list):
        local_part = email.split("@", 1)[0].strip()

        if not local_part:
            continue

        key = local_part.lower()

        if key in seen_names:
            continue

        seen_names.add(key)
        recipient_names.append(local_part)

    customer_remarks = ", ".join(recipient_names)

    if mi.meta.has_field("custom_customer_remarks"):
        frappe.db.set_value(
            "Mission Intervention",
            mi.name,
            "custom_customer_remarks",
            customer_remarks,
            update_modified=False,
        )
        mi.custom_customer_remarks = customer_remarks

    # Generate the PDF after saving custom_customer_remarks so the same
    # report can display the current TO-recipient names.
    report_attachment = frappe.attach_print(
        "Mission Intervention",
        mi.name,
        print_format=None,
        file_name=f"{mi.name}.pdf",
    )

    attachments = [report_attachment]
    include_client_files = str(send_photos).lower() in ("1", "true", "yes")

    if mi.meta.has_field("custom_send_photos"):
        frappe.db.set_value(
            "Mission Intervention",
            mi.name,
            "custom_send_photos",
            1 if include_client_files else 0,
            update_modified=False,
        )
        mi.custom_send_photos = 1 if include_client_files else 0

    if include_client_files:
        attachments.extend(_get_client_email_attachments(mi.name))

    subject = (
        f"Intervention Report {mi.name}"
        f" - {mi.get('custom_parent_customer') or ''}"
    )

    email_identity = _build_maintenance_email_identity(
        mi,
        "technician_pwa",
    )

    signature_lines = [
        _html_text(email_identity.get("closing")),
        _html_text(email_identity.get("signature_name")),
    ]

    if email_identity.get("support_email"):
        signature_lines.append(
            _html_text(email_identity.get("support_email"))
        )

    if email_identity.get("support_phone"):
        signature_lines.append(
            _html_text(email_identity.get("support_phone"))
        )

    signature_html = "<br>".join(
        line for line in signature_lines if line
    )

    footer_html = ""
    if email_identity.get("footer"):
        footer_html = (
            f"<p>{_html_text(email_identity.get('footer'))}</p>"
        )

    message = f"""
        <p>Hello,</p>
        <p>Please find attached the intervention report
        <strong>{frappe.utils.escape_html(mi.name)}</strong>.</p>
        <p>
            <strong>Customer:</strong>
            {frappe.utils.escape_html(mi.get('custom_parent_customer') or '-')}<br>
            <strong>Branch:</strong>
            {frappe.utils.escape_html(mi.get('custom_branch') or '-')}<br>
            <strong>Outcome:</strong>
            {frappe.utils.escape_html(mi.get('custom_work_outcome') or '-')}
        </p>
        <p>{signature_html}</p>
        {footer_html}
    """

    sendmail_args = {
        "recipients": to_list,
        "cc": cc_list,
        "subject": subject,
        "message": message,
        "attachments": attachments,
        "reference_doctype": "Mission Intervention",
        "reference_name": mi.name,
        "now": False,
    }

    if email_identity.get("sender"):
        sendmail_args["sender"] = email_identity["sender"]

    frappe.sendmail(**sendmail_args)

    if mi.meta.has_field("custom_email_status"):
        frappe.db.set_value(
            "Mission Intervention",
            mi.name,
            "custom_email_status",
            "Queued",
            update_modified=False,
        )

    if mi.meta.has_field("custom_email_sent_by"):
        frappe.db.set_value(
            "Mission Intervention",
            mi.name,
            "custom_email_sent_by",
            frappe.session.user,
            update_modified=False,
        )

    frappe.db.commit()

    return {
        "ok": True,
        "status": "Queued",
        "recipients": to_list,
        "cc": cc_list,
        "send_photos": include_client_files,
        "client_attachment_count": max(len(attachments) - 1, 0),
    }
