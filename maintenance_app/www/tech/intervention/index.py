import json

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


def _get_report_email_defaults(service_ticket_name):
    """
    Email destination rule:
      To  = Service Ticket applicant email
      CC  = all other emails in Service Ticket branch contacts

    Applicant email is removed from CC to prevent duplication.
    """
    result = {
        "to": [],
        "cc": [],
    }

    if not service_ticket_name:
        return result

    ticket = frappe.get_doc(
        "Service Ticket",
        service_ticket_name,
    )

    applicant_email = (
        ticket.get("custom_applicant_email") or ""
    ).strip()

    # Fallback to the linked Contact when the snapshot email is empty.
    if (
        not applicant_email
        and ticket.get("custom_applicant")
    ):
        contact_email = frappe.db.get_value(
            "Contact Email",
            {
                "parent": ticket.custom_applicant,
                "is_primary": 1,
            },
            "email_id",
        )

        if not contact_email:
            contact_email = frappe.db.get_value(
                "Contact Email",
                {
                    "parent": ticket.custom_applicant,
                },
                "email_id",
                order_by="idx asc",
            )

        applicant_email = (
            contact_email or ""
        ).strip()

    if applicant_email:
        result["to"] = [applicant_email]

    branch_emails = []

    for row in (
        ticket.get("custom_branch_contacts") or []
    ):
        email = (row.get("custom_email") or "").strip()

        if email:
            branch_emails.append(email)

    applicant_key = _normalise_email(applicant_email)

    result["cc"] = [
        email
        for email in _unique_emails(branch_emails)
        if _normalise_email(email) != applicant_key
    ]

    return result


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

    report_email_defaults = _get_report_email_defaults(
        mi.get("custom_service_ticket")
    )

    context.report_email_to = ", ".join(
        report_email_defaults.get("to") or []
    )
    context.report_email_cc = ", ".join(
        report_email_defaults.get("cc") or []
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
        "Continue Work": "Follow-up Visit / Work to Continue",
        "Waiting for Parts": "Waiting for Parts",
        "Waiting for Client": "Waiting for Client",
        "To Quote (Billable)": "To Quote",
        "Could Not Complete": "Could Not Complete",
    }
    hold_reason = hold_reason_map.get(
        source.get("custom_work_outcome"),
        "Follow-up Visit / Work to Continue",
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
    field = frappe.get_meta("Mission Intervention").get_field("custom_intervention_type")
    if not field:
        frappe.throw("Mission Intervention field custom_intervention_type is missing.")

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

    # Reuse the same equipment/customer/branch contact filter already used elsewhere.
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
        frappe.throw("Selected Applicant is not valid for this customer/branch.")

    if intervention_type == "Specialised Testing":
        specialised_testing_type = (specialised_testing_type or "").strip()
        if not specialised_testing_type:
            frappe.throw("Specialised Testing Type is required.")
        if not frappe.db.exists("Specialised Testing Type", specialised_testing_type):
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

    intervention = (result or {}).get("intervention") if isinstance(result, dict) else None
    if not intervention:
        frappe.throw("Additional MI was created but no intervention reference was returned.")

    new_mi = frappe.get_doc("Mission Intervention", intervention)
    _set_if_field(new_mi, "custom_applicant", applicant)
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

    to_list = frappe.parse_json(recipients) if recipients else []
    cc_list = frappe.parse_json(cc) if cc else []

    if isinstance(to_list, str):
        to_list = [to_list]

    if isinstance(cc_list, str):
        cc_list = [cc_list]

    to_list = [
        email.strip()
        for email in to_list
        if email and email.strip()
    ]
    cc_list = [
        email.strip()
        for email in cc_list
        if email and email.strip()
    ]

    if not to_list:
        frappe.throw("At least one email recipient is required.")

    # Store only the TO-recipient names in custom_customer_remarks.
    # Example:
    #   julie@gotechmu.com, gerrard@gotechmu.com
    # becomes:
    #   julie, gerrard
    #
    # CC recipients are intentionally excluded.
    recipient_names = []
    seen_names = set()

    for email in to_list:
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
        <p>Kind regards,<br>GoTech</p>
    """

    frappe.sendmail(
        recipients=to_list,
        cc=cc_list,
        subject=subject,
        message=message,
        attachments=attachments,
        reference_doctype="Mission Intervention",
        reference_name=mi.name,
        now=False,
    )

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
