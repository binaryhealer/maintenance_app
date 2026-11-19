import frappe
from frappe.utils import now_datetime, flt, get_datetime


def _equipment_display(equipment_name):
    if not equipment_name:
        return {
            "name": None,
            "asset_name": None,
            "label": None,
            "serial_number": None,
            "location_status": None,
            "make": None,
            "model": None,
            "site_id": None,
        }

    if not frappe.db.exists(
        "Installed Equipment",
        equipment_name
    ):
        return {
            "name": equipment_name,
            "asset_name": equipment_name,
            "label": equipment_name,
            "serial_number": None,
            "location_status": None,
            "make": None,
            "model": None,
            "site_id": None,
        }

    equipment = frappe.get_doc(
        "Installed Equipment",
        equipment_name
    )

    asset_name = equipment.get("custom_asset_name") or equipment.name
    serial_number = (equipment.get("custom_asset_id") or "").strip()
    display_name = (equipment.get("custom_display_name") or "").strip()
    # Keep a friendly name while avoiding a duplicated serial number.
    label = display_name or asset_name
    if serial_number and serial_number.lower() not in label.lower():
        label = f"{label} - SN: {serial_number}"

    return {
        "name": equipment.name,
        "asset_name": asset_name,
        "label": label,
        "serial_number": serial_number,
        "location_status": equipment.get("custom_location_status") or "",
        "make": equipment.get("custom_make"),
        "model": equipment.get("custom_model"),
        "site_id": equipment.get("custom_site_id"),
    }


ALLOWED_STEPS = {
    "job",
    "actions",
    "work",
    "finish",
    "client",
    "checkout",
    "submit",
    "photos",
    "parts",
    "hse",
    "more",
    "plan",
}



def _get_mission_plan(mi):
    mission_name = mi.get("custom_parent_mission")

    result = {
        "mission_name": mission_name,
        "planned_start": None,
        "planned_end": None,
        "team": [],
        "mission_vehicle": None,
        "external_vehicle": None,
    }

    if not mission_name:
        return result

    if not frappe.db.exists(
        "Tech Mission",
        mission_name
    ):
        return result

    mission = frappe.get_doc(
        "Tech Mission",
        mission_name
    )

    result["planned_start"] = mission.get(
        "custom_planned_starttime"
    )

    result["planned_end"] = mission.get(
        "custom_planned_endtime"
    )

    result["mission_vehicle"] = mission.get(
        "custom_vehicle"
    )

    result["external_vehicle"] = mission.get(
        "custom_external_vehicle"
    )

    for row in (
        mission.get("custom_planned_team")
        or []
    ):
        technician = row.get(
            "custom_technician"
        )

        vehicle = row.get(
            "custom_assigned_vehicle"
        )

        if technician or vehicle:
            result["team"].append({
                "technician": technician,
                "vehicle": vehicle,
            })

    return result




def _get_sla_context(mi):
    result = {
        "status": mi.get("custom_sla_status"),
        "response_due": mi.get("custom_response_due"),
        "resolution_due": mi.get("custom_resolution_due"),
    }

    # Older MIs may not have the SLA snapshot populated.
    # Fall back to the Service Ticket without changing any data.
    if (
        not result["status"]
        and not result["response_due"]
        and not result["resolution_due"]
    ):
        ticket_name = mi.get("custom_service_ticket")

        if (
            ticket_name
            and frappe.db.exists(
                "Service Ticket",
                ticket_name
            )
        ):
            ticket = frappe.get_doc(
                "Service Ticket",
                ticket_name
            )

            result["status"] = ticket.get(
                "custom_sla_status"
            )

            result["response_due"] = ticket.get(
                "custom_response_due"
            )

            result["resolution_due"] = ticket.get(
                "custom_resolution_due"
            )

    return result



def _get_work_setup_options(mi):
    intervention_type = (
        mi.get("custom_intervention_type")
        or ""
    ).strip()

    result = {
        "fieldname": None,
        "label": None,
        "doctype": None,
        "current_value": None,
        "options": [],
    }

    mapping = {
        "Specialised Testing": {
            "fieldname": "custom_specialised_testing_type",
            "label": "Specialised Testing Type",
            "doctype": "Specialised Testing Type",
        },
        "General Installation": {
            "fieldname": "custom_general_installation_type",
            "label": "General Installation Type",
            "doctype": "General Installation Type",
        },
        "General Works": {
            "fieldname": "custom_general_work_type",
            "label": "General Work Type",
            "doctype": "General Works Type",
        },
    }

    config = mapping.get(
        intervention_type
    )

    if not config:
        return result

    result.update(config)

    result["current_value"] = mi.get(
        config["fieldname"]
    )

    if frappe.db.exists(
        "DocType",
        config["doctype"]
    ):
        result["options"] = [
            row.name
            for row in frappe.get_all(
                config["doctype"],
                fields=["name"],
                order_by="name asc",
                limit_page_length=500,
            )
        ]

    return result



def _get_swap_work_context(mi):
    result = {
        "enabled": False,
        "stage": mi.get("custom_swap_stage"),
        "equipment": _equipment_display(
            mi.get("custom_asset")
        ),
        "partner": _equipment_display(
            mi.get("custom_new_asset")
        ),
        "current_branch": mi.get("custom_branch"),
        "current_site": mi.get("custom_site_id"),
        "destination_branch": None,
        "destination_site": None,
        "route_reversed": False,
        "instruction": None,
    }

    if (
        mi.get("custom_intervention_type")
        != "Swap"
    ):
        return result

    result["enabled"] = True

    ticket_name = mi.get(
        "custom_service_ticket"
    )

    if (
        not ticket_name
        or not frappe.db.exists(
            "Service Ticket",
            ticket_name
        )
    ):
        return result

    ticket = frappe.get_doc(
        "Service Ticket",
        ticket_name
    )

    original_branch = (
        ticket.get("custom_client_branch")
        or ""
    )

    original_site = (
        ticket.get("custom_site_id")
        or ""
    )

    swap_branch = (
        ticket.get("custom_swap_branch")
        or ""
    )

    swap_site = (
        ticket.get("custom_swap_site_id")
        or ""
    )

    mission_name = mi.get(
        "custom_parent_mission"
    )

    route_reversed = False

    if (
        mission_name
        and frappe.db.exists(
            "Tech Mission",
            mission_name
        )
    ):
        route_reversed = bool(
            frappe.db.get_value(
                "Tech Mission",
                mission_name,
                "custom_swap_route_reversed"
            )
            or 0
        )

    result["route_reversed"] = (
        route_reversed
    )

    if route_reversed:
        first_branch = swap_branch
        first_site = swap_site

        second_branch = original_branch
        second_site = original_site

    else:
        first_branch = original_branch
        first_site = original_site

        second_branch = swap_branch
        second_site = swap_site

    stage = (
        mi.get("custom_swap_stage")
        or ""
    )

    if stage == "Same Site Exchange":
        result["instruction"] = (
            "Exchange the two equipment positions "
            "at this site. Both equipment remain "
            "installed and operational after the Swap."
        )

    elif stage == "Collection from Source":
        result["destination_branch"] = (
            second_branch
        )

        result["destination_site"] = (
            second_site
        )

        result["instruction"] = (
            "Collect the displayed equipment from "
            "this site for transport to the next "
            "Swap location."
        )

    elif stage == "Exchange at Swap Branch":
        result["destination_branch"] = (
            first_branch
        )

        result["destination_site"] = (
            first_site
        )

        result["instruction"] = (
            "Install the incoming equipment in this "
            "site's original position, then collect "
            "the outgoing partner equipment for "
            "transport to the final site."
        )

    elif stage == "Final Installation":
        result["destination_branch"] = (
            mi.get("custom_branch")
        )

        result["destination_site"] = (
            mi.get("custom_site_id")
        )

        result["instruction"] = (
            "Install the equipment in the final "
            "Swap position. This completes the "
            "physical Swap."
        )

    return result


def get_context(context):
    mi_name = frappe.form_dict.get("name")

    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    if not frappe.db.exists("Mission Intervention", mi_name):
        frappe.throw("Mission Intervention not found.")

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    requested_step = (
        frappe.form_dict.get("step")
        or "job"
    ).strip().lower()

    if requested_step not in ALLOWED_STEPS:
        requested_step = "job"

    context.no_cache = 1
    context.mi = mi
    context.step = requested_step

    context.intervention_type = (
        mi.get("custom_intervention_type")
        or "Service"
    )

    context.equipment = _equipment_display(
        mi.get("custom_asset")
    )

    context.swap_equipment = _equipment_display(
        mi.get("custom_new_asset")
    )

    context.mission_plan = _get_mission_plan(
        mi
    )

    context.sla = _get_sla_context(
        mi
    )

    context.work_setup = _get_work_setup_options(
        mi
    )

    context.swap_work = _get_swap_work_context(
        mi
    )

    context.hse_rating_required = (
        _v2_hse_rating_required(mi)
    )

    context.actual_type_options = (
        _get_actual_type_options()
    )

    context.is_checked_in = bool(
        mi.get("custom_start_time")
    )

    context.has_outcome = bool(
        mi.get("custom_work_outcome")
    )

    context.client_confirmed = bool(
        mi.get("custom_client_signature_received")
        or mi.get("custom_client_signature")
    )

    context.is_checked_out = bool(
        mi.get("custom_end_time")
    )

    context.is_submitted = (
        int(mi.docstatus or 0) == 1
    )

    return context


def _set_if_field(doc, fieldname, value):
    if doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def _save_v2_gps(
    mi,
    prefix,
    latitude=None,
    longitude=None,
    accuracy=None,
):
    if latitude in (None, "") or longitude in (None, ""):
        return False

    _set_if_field(
        mi,
        f"custom_{prefix}_latitude",
        flt(latitude),
    )

    _set_if_field(
        mi,
        f"custom_{prefix}_longitude",
        flt(longitude),
    )

    if accuracy not in (None, ""):
        _set_if_field(
            mi,
            f"custom_{prefix}_accuracy",
            flt(accuracy),
        )

    return True


@frappe.whitelist()
def pwa_check_in_v2(
    mi_name,
    latitude=None,
    longitude=None,
    accuracy=None,
):
    """
    Technician PWA V2 Check In.

    Important:
    - Check In happens BEFORE subtype/work-detail selection.
    - No Specialised Testing Type requirement here.
    - No General Installation Type requirement here.
    """

    if (
        not frappe.session.user
        or frappe.session.user == "Guest"
    ):
        raise frappe.PermissionError(
            "Please log in before checking in."
        )

    if not mi_name:
        frappe.throw(
            "Mission Intervention is required."
        )

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if int(mi.docstatus or 0) != 0:
        frappe.throw(
            "Only a draft intervention can be checked in."
        )

    if mi.get("custom_start_time"):
        return {
            "ok": True,
            "already_checked_in": True,
            "intervention": mi.name,
            "checked_in_at": mi.get(
                "custom_start_time"
            ),
            "gps_saved": bool(
                mi.get("custom_checkin_latitude")
                and mi.get("custom_checkin_longitude")
            ),
        }

    checked_in_at = now_datetime()

    _set_if_field(
        mi,
        "custom_start_time",
        checked_in_at,
    )

    _set_if_field(
        mi,
        "custom_start_date",
        checked_in_at.date(),
    )

    _set_if_field(
        mi,
        "custom_checkout_status",
        "Checked In",
    )

    gps_saved = _save_v2_gps(
        mi,
        "checkin",
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    mi.save()

    # Keep TM/ST status and MI register aligned.
    try:
        sync_method = frappe.get_attr(
            "maintenance_app.api."
            "sync_mi_to_mission_register"
        )
        sync_method(mi.name)
    except Exception:
        # Fallback to the newer aggregate sync helper
        # if the older wrapper is not available.
        sync_method = frappe.get_attr(
            "maintenance_app.api."
            "_sync_mi_register_and_status"
        )
        sync_method(
            mi.name,
            save_mission=True,
        )

    frappe.db.commit()

    return {
        "ok": True,
        "intervention": mi.name,
        "checked_in_at": checked_in_at,
        "gps_saved": gps_saved,
    }



@frappe.whitelist()
def save_work_outcome_v2(
    mi_name,
    outcome,
    work_progress,
    could_not_complete_reason=None,
    additional_planning_required=0,
    rm_attention_required=0,
    planning_request_note=None,
    equipment_being_moved=0,
    waiting_client_reason=None,
    client_action_required=None,
    other_equipment_to_work_on=None,
):
    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if int(mi.docstatus or 0) != 0:
        frappe.throw(
            "Only a draft intervention can be updated."
        )

    if not mi.get("custom_start_time"):
        frappe.throw(
            "Please Check In before finishing the work."
        )

    allowed_outcomes = {
        "Work Completed",
        "Continue Work",
        "Waiting for Parts",
        "Waiting for Client",
        "To Quote (Billable)",
        "Could Not Complete",
        "False Call Out",
    }

    outcome = (outcome or "").strip()
    work_progress = (work_progress or "").strip()

    if outcome not in allowed_outcomes:
        frappe.throw("Please select a valid Work Outcome.")

    if not work_progress:
        frappe.throw(
            "Technical Progress Notes are required."
        )

    _set_if_field(
        mi,
        "custom_work_outcome",
        outcome
    )

    _set_if_field(
        mi,
        "custom_work_progress",
        work_progress
    )

    # ------------------------------------------------------
    # Waiting for Client
    # ------------------------------------------------------
    if outcome == "Waiting for Client":

        reason = (waiting_client_reason or "").strip()
        action = (client_action_required or "").strip()

        if not reason:
            frappe.throw(
                "Please explain why we are waiting for the client."
            )

        if not action:
            frappe.throw(
                "Please explain what action is required from the client."
            )

        for fieldname, value in {
            "custom_waiting_client_reason": reason,
            "custom_client_action_required": action,
        }.items():
            if not mi.meta.has_field(fieldname):
                frappe.throw(
                    "Missing Mission Intervention field: " + fieldname
                )
            mi.set(fieldname, value)

    else:
        # The technician changed to another Work Outcome.
        # Remove any draft Waiting for Client details.
        _set_if_field(
            mi,
            "custom_waiting_client_reason",
            ""
        )
        _set_if_field(
            mi,
            "custom_client_action_required",
            ""
        )

    # ------------------------------------------------------
    # Other equipment decision
    # ------------------------------------------------------
    if outcome == "Could Not Complete":

        decision = (
            other_equipment_to_work_on or ""
        ).strip()

        if decision not in ("Yes", "No"):
            frappe.throw(
                "Please confirm whether you have other equipment to work on."
            )

        if not mi.meta.has_field(
            "custom_other_equipment_to_work_on"
        ):
            frappe.throw(
                "Missing MI field: custom_other_equipment_to_work_on"
            )

        mi.set(
            "custom_other_equipment_to_work_on",
            decision
        )

    else:
        _set_if_field(
            mi,
            "custom_other_equipment_to_work_on",
            ""
        )

    # ------------------------------------------------------
    # Could Not Complete
    # ------------------------------------------------------
    if outcome == "Could Not Complete":

        reason = (
            could_not_complete_reason or ""
        ).strip()

        if not reason:
            frappe.throw(
                "Please select why the work could not be completed."
            )

        allowed_reasons = {
            "Specialist Required",
            "Different Technician Required",
            "Required Tool / Equipment Unavailable",
            "Unable to Access Equipment",
            "Client / Site Access Issue",
            "Unsafe to Continue",
            "Wrong Equipment / Component",
            "Move to Workshop Required",
            "Other",
        }

        if reason not in allowed_reasons:
            frappe.throw(
                "Invalid Could Not Complete reason."
            )

        planning_required = int(
            additional_planning_required or 0
        )

        rm_required = int(
            rm_attention_required or 0
        )

        note = (
            planning_request_note or ""
        ).strip()

        if (
            (planning_required or rm_required)
            and not note
        ):
            frappe.throw(
                "Please enter the action required from RM / Planning."
            )

        _set_if_field(
            mi,
            "custom_could_not_complete_reason",
            reason
        )

        _set_if_field(
            mi,
            "custom_additional_planning_required",
            planning_required
        )

        _set_if_field(
            mi,
            "custom_rm_attention_required",
            rm_required
        )

        _set_if_field(
            mi,
            "custom_planning_request_note",
            note
        )

    else:
        # Clear exception fields when they do not apply.
        _set_if_field(
            mi,
            "custom_could_not_complete_reason",
            ""
        )

        _set_if_field(
            mi,
            "custom_additional_planning_required",
            0
        )

        _set_if_field(
            mi,
            "custom_rm_attention_required",
            0
        )

        _set_if_field(
            mi,
            "custom_planning_request_note",
            ""
        )

    # ------------------------------------------------------
    # Pure Swap movement flag
    # ------------------------------------------------------
    if (
        mi.get("custom_intervention_type") == "Swap"
        and outcome == "Continue Work"
        and mi.get("custom_swap_stage") in [
            "Collection from Source",
            "Exchange at Swap Branch",
        ]
    ):
        _set_if_field(
            mi,
            "custom_equipment_being_moved",
            int(equipment_being_moved or 0)
        )
    else:
        _set_if_field(
            mi,
            "custom_equipment_being_moved",
            0
        )

    mi.save()
    frappe.db.commit()

    return {
        "ok": True,
        "intervention": mi.name,
        "outcome": outcome,
        "next_step": "client",
    }


@frappe.whitelist()
def save_work_setup_v2(
    mi_name,
    subtype=None,
):
    if not mi_name:
        frappe.throw(
            "Mission Intervention is required."
        )

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if int(mi.docstatus or 0) != 0:
        frappe.throw(
            "Only a draft intervention can be updated."
        )

    if not mi.get("custom_start_time"):
        frappe.throw(
            "Please Check In first."
        )

    intervention_type = (
        mi.get("custom_intervention_type")
        or ""
    ).strip()

    subtype = (
        subtype or ""
    ).strip()

    mapping = {
        "Specialised Testing": {
            "fieldname":
                "custom_specialised_testing_type",

            "doctype":
                "Specialised Testing Type",

            "label":
                "Specialised Testing Type",
        },

        "General Installation": {
            "fieldname":
                "custom_general_installation_type",

            "doctype":
                "General Installation Type",

            "label":
                "General Installation Type",
        },

        "General Works": {
            "fieldname":
                "custom_general_work_type",

            "doctype":
                "General Works Type",

            "label":
                "General Work Type",
        },
    }

    config = mapping.get(
        intervention_type
    )

    if config:
        if not subtype:
            frappe.throw(
                "Please select "
                + config["label"]
                + "."
            )

        if not frappe.db.exists(
            config["doctype"],
            subtype
        ):
            frappe.throw(
                "Invalid "
                + config["label"]
                + "."
            )

        _set_if_field(
            mi,
            config["fieldname"],
            subtype
        )

        mi.save()
        frappe.db.commit()

    return {
        "ok": True,
        "intervention": mi.name,
        "intervention_type":
            intervention_type,
        "subtype": subtype,
        "next_step": "work",
    }


@frappe.whitelist()
def save_client_confirmation_v2(
    mi_name,
    signatory_name,
    client_signature,
    tech_signature,
    quality_score=None,
    hse_score=None,
):
    if not mi_name:
        frappe.throw("Mission Intervention is required.")

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if int(mi.docstatus or 0) != 0:
        frappe.throw(
            "Only a draft intervention can be updated."
        )

    if not mi.get("custom_work_outcome"):
        frappe.throw(
            "Please save Work Outcome first."
        )

    if not mi.get("custom_work_progress"):
        frappe.throw(
            "Technical Progress Notes are required."
        )

    signatory_name = (
        signatory_name or ""
    ).strip()

    if not signatory_name:
        frappe.throw(
            "Client Signatory Name is required."
        )

    if not client_signature:
        frappe.throw(
            "Client Signature is required."
        )

    if not tech_signature:
        frappe.throw(
            "Technician Signature is required."
        )

    if (
        mi.get("custom_work_outcome")
        == "Work Completed"
    ):
        if not quality_score or not hse_score:
            frappe.throw(
                "Quality and HSE ratings are required "
                "for completed work."
            )

    signed_now = now_datetime()

    _set_if_field(
        mi,
        "custom_signatory_name",
        signatory_name
    )

    _set_if_field(
        mi,
        "custom_client_signature",
        client_signature
    )

    _set_if_field(
        mi,
        "custom_tech_signature",
        tech_signature
    )

    if quality_score not in (None, ""):
        _set_if_field(
            mi,
            "custom_quality_score",
            flt(quality_score)
        )

    if hse_score not in (None, ""):
        _set_if_field(
            mi,
            "custom_hse_score",
            flt(hse_score)
        )

    _set_if_field(
        mi,
        "custom_client_signature_received",
        1
    )

    _set_if_field(
        mi,
        "custom_client_signed_on",
        signed_now
    )

    _set_if_field(
        mi,
        "custom_client_signed_time",
        signed_now
    )

    _set_if_field(
        mi,
        "custom_technician_signatory",
        frappe.session.user
    )

    _set_if_field(
        mi,
        "custom_technician_signed_on",
        signed_now
    )

    _set_if_field(
        mi,
        "custom_checkout_status",
        "Client Signed"
    )

    mi.save()
    frappe.db.commit()

    return {
        "ok": True,
        "next_step": "checkout",
    }


@frappe.whitelist()
def pwa_check_out_v2(
    mi_name,
    latitude=None,
    longitude=None,
    accuracy=None,
):
    if not mi_name:
        frappe.throw(
            "Mission Intervention is required."
        )

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if int(mi.docstatus or 0) != 0:
        frappe.throw(
            "Only a draft intervention can be checked out."
        )

    if not mi.get("custom_start_time"):
        frappe.throw(
            "Please Check In first."
        )

    if mi.get("custom_end_time"):
        return {
            "ok": True,
            "already_checked_out": True,
            "checked_out_at":
                mi.get("custom_end_time"),
        }

    required = {
        "custom_work_outcome":
            "Work Outcome",
        "custom_work_progress":
            "Technical Progress Notes",
        "custom_signatory_name":
            "Client Signatory Name",
        "custom_client_signature":
            "Client Signature",
        "custom_tech_signature":
            "Technician Signature",
    }

    missing = [
        label
        for fieldname, label in required.items()
        if not mi.get(fieldname)
    ]

    if missing:
        frappe.throw(
            "Please complete before Check Out: "
            + ", ".join(missing)
        )

    if (
        mi.get("custom_work_outcome")
        == "Work Completed"
    ):
        rating_fields = {
            "custom_quality_score":
                "Quality Rating",
            "custom_hse_score":
                "HSE Rating",
        }

        missing_ratings = [
            label
            for fieldname, label
            in rating_fields.items()
            if not mi.get(fieldname)
        ]

        if missing_ratings:
            frappe.throw(
                "Please complete ratings: "
                + ", ".join(missing_ratings)
            )

    checked_out_at = now_datetime()

    _set_if_field(
        mi,
        "custom_end_time",
        checked_out_at
    )

    _set_if_field(
        mi,
        "custom_checkout_status",
        "Checked Out"
    )

    if not mi.get("custom_completed_time"):
        _set_if_field(
            mi,
            "custom_completed_time",
            checked_out_at
        )

    if mi.meta.has_field(
        "custom_hours_worked"
    ):
        start = get_datetime(
            mi.get("custom_start_time")
        )

        seconds = (
            checked_out_at - start
        ).total_seconds()

        if seconds > 0:
            mi.custom_hours_worked = round(
                seconds / 3600,
                2
            )

    gps_saved = _save_v2_gps(
        mi,
        "checkout",
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    mi.save()
    frappe.db.commit()

    return {
        "ok": True,
        "checked_out_at": checked_out_at,
        "gps_saved": gps_saved,
        "hours_worked":
            mi.get("custom_hours_worked"),
    }


@frappe.whitelist()
def submit_intervention_v2(mi_name):
    if not mi_name:
        frappe.throw(
            "Mission Intervention is required."
        )

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("submit")

    if int(mi.docstatus or 0) == 1:
        return {
            "ok": True,
            "already_submitted": True,
            "intervention": mi.name,
        }

    if int(mi.docstatus or 0) != 0:
        frappe.throw(
            "Only a draft intervention can be submitted."
        )

    if not mi.get("custom_end_time"):
        frappe.throw(
            "Please Check Out before submitting."
        )

    required = {
        "custom_work_outcome":
            "Work Outcome",
        "custom_work_progress":
            "Technical Progress Notes",
        "custom_signatory_name":
            "Client Signatory Name",
        "custom_client_signature":
            "Client Signature",
        "custom_tech_signature":
            "Technician Signature",
    }

    missing = [
        label
        for fieldname, label in required.items()
        if not mi.get(fieldname)
    ]

    if missing:
        frappe.throw(
            "Please complete before submission: "
            + ", ".join(missing)
        )

    if (
        mi.get("custom_work_outcome")
        == "Work Completed"
    ):
        if (
            not mi.get("custom_quality_score")
            or not mi.get("custom_hse_score")
        ):
            frappe.throw(
                "Quality and HSE ratings are required."
            )

    # Older MI / MI checked out before the V2 completion-time patch
    # may have custom_end_time but no custom_completed_time.
    # Existing Before Submit validation requires Completed Time
    # when Work Outcome = Work Completed.
    if (
        mi.get("custom_work_outcome") == "Work Completed"
        and not mi.get("custom_completed_time")
    ):
        if not mi.get("custom_end_time"):
            frappe.throw(
                "Please Check Out before submitting."
            )

        _set_if_field(
            mi,
            "custom_completed_time",
            mi.get("custom_end_time")
        )

        mi.save()

    _write_actual_execution_to_ticket(mi)

    mi.submit()

    frappe.db.commit()

    return {
        "ok": True,
        "intervention": mi.name,
        "submitted": True,
        "mission":
            mi.get("custom_parent_mission"),
        "ticket":
            mi.get("custom_service_ticket"),
    }



@frappe.whitelist()
def save_client_confirmation_v2(
    mi_name,
    signatory_name,
    client_signature,
    tech_signature,
    quality_score=None,
    hse_score=None,
):
    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if mi.docstatus != 0:
        frappe.throw(
            "Only a draft intervention can be updated."
        )

    if not mi.get("custom_work_outcome"):
        frappe.throw(
            "Please save Work Outcome first."
        )

    if not mi.get("custom_work_progress"):
        frappe.throw(
            "Technical Progress Notes are required."
        )

    signatory_name = (
        signatory_name or ""
    ).strip()

    if not signatory_name:
        frappe.throw(
            "Client Signatory Name is required."
        )

    if not client_signature:
        frappe.throw(
            "Client Signature is required."
        )

    if not tech_signature:
        frappe.throw(
            "Technician Signature is required."
        )

    if (
        mi.get("custom_work_outcome")
        == "Work Completed"
        and (
            not quality_score
            or not hse_score
        )
    ):
        frappe.throw(
            "Quality and HSE ratings are required "
            "for completed work."
        )

    signed_now = frappe.utils.now_datetime()

    _set_if_field(
        mi,
        "custom_signatory_name",
        signatory_name
    )

    _set_if_field(
        mi,
        "custom_client_signature",
        client_signature
    )

    _set_if_field(
        mi,
        "custom_tech_signature",
        tech_signature
    )

    if quality_score not in (None, ""):
        _set_if_field(
            mi,
            "custom_quality_score",
            frappe.utils.flt(quality_score)
        )

    if hse_score not in (None, ""):
        _set_if_field(
            mi,
            "custom_hse_score",
            frappe.utils.flt(hse_score)
        )

    _set_if_field(
        mi,
        "custom_client_signature_received",
        1
    )

    _set_if_field(
        mi,
        "custom_client_signed_on",
        signed_now
    )

    _set_if_field(
        mi,
        "custom_client_signed_time",
        signed_now
    )

    _set_if_field(
        mi,
        "custom_technician_signatory",
        frappe.session.user
    )

    _set_if_field(
        mi,
        "custom_technician_signed_on",
        signed_now
    )

    _set_if_field(
        mi,
        "custom_checkout_status",
        "Client Signed"
    )

    mi.save()

    frappe.db.commit()

    return {
        "ok": True,
        "next_step": "checkout"
    }


def _v2_hse_rating_required(mi):
    """
    TM is the live authority until MI submission.
    """
    mission = mi.get("custom_parent_mission")

    if (
        mission
        and frappe.db.exists("Tech Mission", mission)
    ):
        value = frappe.db.get_value(
            "Tech Mission",
            mission,
            "custom_hse_rating_required",
        )

        if value is not None:
            return bool(value)

    return True


@frappe.whitelist()
def pwa_check_out_v2(
    mi_name,
    latitude=None,
    longitude=None,
    accuracy=None,
):
    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if mi.docstatus != 0:
        frappe.throw(
            "Only a draft intervention can be checked out."
        )

    if not mi.get("custom_start_time"):
        frappe.throw(
            "Please Check In first."
        )

    if not mi.get("custom_work_outcome"):
        frappe.throw(
            "Please save Work Outcome first."
        )

    if not mi.get("custom_work_progress"):
        frappe.throw(
            "Technical Progress Notes are required."
        )

    if mi.get("custom_end_time"):

        # Repair older V2 checkouts where technical work
        # was completed but Completed Time was not saved.
        if (
            mi.get("custom_work_outcome") == "Work Completed"
            and not mi.get("custom_completed_time")
        ):
            _set_if_field(
                mi,
                "custom_completed_time",
                mi.get("custom_end_time")
            )

            mi.save()
            frappe.db.commit()

        return {
            "ok": True,
            "already_checked_out": True,
            "checked_out_at":
                mi.get("custom_end_time"),
            "completed_at":
                mi.get("custom_completed_time"),
        }

    checked_out_at = frappe.utils.now_datetime()

    _set_if_field(
        mi,
        "custom_end_time",
        checked_out_at
    )

    _set_if_field(
        mi,
        "custom_checkout_status",
        "Checked Out"
    )

    # Completed Time = technical completion time.
    # Only set when the work itself is completed.
    if mi.get("custom_work_outcome") == "Work Completed":
        _set_if_field(
            mi,
            "custom_completed_time",
            checked_out_at
        )
    else:
        _set_if_field(
            mi,
            "custom_completed_time",
            None
        )

    if mi.meta.has_field(
        "custom_hours_worked"
    ):
        start = frappe.utils.get_datetime(
            mi.get("custom_start_time")
        )

        seconds = (
            checked_out_at - start
        ).total_seconds()

        if seconds > 0:
            mi.custom_hours_worked = round(
                seconds / 3600,
                2
            )

    _save_v2_gps(
        mi,
        "checkout",
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    mi.save()
    frappe.db.commit()

    return {
        "ok": True,
        "checked_out_at": checked_out_at,
        "hours_worked":
            mi.get("custom_hours_worked"),
    }


@frappe.whitelist()
def save_client_confirmation_v2(
    mi_name,
    signatory_name,
    client_signature,
    tech_signature,
    quality_score=None,
    hse_score=None,
    customer_remarks=None,
    hse_not_applicable=0,
    hse_na_reason=None,
):
    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if mi.docstatus != 0:
        frappe.throw(
            "Only a draft intervention can be updated."
        )

    # Technical work must already be complete.
    if not mi.get("custom_end_time"):
        frappe.throw(
            "Please Check Out before Client Confirmation."
        )

    signatory_name = (
        signatory_name or ""
    ).strip()

    if not signatory_name:
        frappe.throw(
            "Client Signatory Name is required."
        )

    if not client_signature:
        frappe.throw(
            "Client Signature is required."
        )

    if not tech_signature:
        frappe.throw(
            "Technician Signature is required."
        )

    # Quality is mandatory for ALL outcomes.
    if not quality_score:
        frappe.throw(
            "Quality Rating is required."
        )

    hse_required = _v2_hse_rating_required(mi)
    hse_not_applicable = int(
        hse_not_applicable or 0
    )

    if hse_not_applicable:
        reason = (
            hse_na_reason or ""
        ).strip()

        if not reason:
            frappe.throw(
                "Please give a reason why HSE "
                "rating is not applicable."
            )

        _set_if_field(
            mi,
            "custom_hse_rating_not_applicable",
            1
        )

        _set_if_field(
            mi,
            "custom_hse_rating_na_reason",
            reason
        )

        _set_if_field(
            mi,
            "custom_hse_rating_na_by",
            frappe.session.user
        )

        _set_if_field(
            mi,
            "custom_hse_rating_na_on",
            frappe.utils.now_datetime()
        )

        # Clear any accidental previous rating.
        if mi.meta.has_field(
            "custom_hse_score"
        ):
            mi.custom_hse_score = None

    else:
        _set_if_field(
            mi,
            "custom_hse_rating_not_applicable",
            0
        )

        if hse_required and not hse_score:
            frappe.throw(
                "HSE Rating is required, or mark "
                "HSE Rating as Not Applicable."
            )

        if hse_score:
            _set_if_field(
                mi,
                "custom_hse_score",
                frappe.utils.flt(hse_score)
            )

    _set_if_field(
        mi,
        "custom_quality_score",
        frappe.utils.flt(quality_score)
    )

    _set_if_field(
        mi,
        "custom_customer_remarks",
        customer_remarks or ""
    )

    _set_if_field(
        mi,
        "custom_signatory_name",
        signatory_name
    )

    _set_if_field(
        mi,
        "custom_client_signature",
        client_signature
    )

    _set_if_field(
        mi,
        "custom_tech_signature",
        tech_signature
    )

    signed_now = frappe.utils.now_datetime()

    _set_if_field(
        mi,
        "custom_client_signature_received",
        1
    )

    # IMPORTANT:
    # This is client sign-off time,
    # NOT technician checkout time.
    _set_if_field(
        mi,
        "custom_client_signed_on",
        signed_now
    )

    _set_if_field(
        mi,
        "custom_client_signed_time",
        signed_now
    )

    _set_if_field(
        mi,
        "custom_technician_signatory",
        frappe.session.user
    )

    _set_if_field(
        mi,
        "custom_technician_signed_on",
        signed_now
    )

    mi.save()
    frappe.db.commit()

    return {
        "ok": True,
        "signed_on": signed_now,
        "hse_required": hse_required,
        "next_step": "submit",
    }


@frappe.whitelist()
def submit_intervention_v2(mi_name):
    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("submit")

    if mi.docstatus == 1:
        return {
            "ok": True,
            "already_submitted": True,
        }

    if mi.docstatus != 0:
        frappe.throw(
            "Only a draft intervention can be submitted."
        )

    if not mi.get("custom_end_time"):
        frappe.throw(
            "Please Check Out first."
        )

    required = {
        "custom_work_outcome":
            "Work Outcome",
        "custom_work_progress":
            "Technical Progress Notes",
        "custom_quality_score":
            "Quality Rating",
        "custom_signatory_name":
            "Client Signatory Name",
        "custom_client_signature":
            "Client Signature",
        "custom_tech_signature":
            "Technician Signature",
    }

    missing = [
        label
        for fieldname, label in required.items()
        if not mi.get(fieldname)
    ]

    if missing:
        frappe.throw(
            "Please complete before submission: "
            + ", ".join(missing)
        )

    if not mi.get(
        "custom_client_signature_received"
    ):
        frappe.throw(
            "Client Sign-Off has not been confirmed."
        )

    hse_required = _v2_hse_rating_required(mi)

    hse_na = bool(
        mi.get(
            "custom_hse_rating_not_applicable"
        )
    )

    if (
        hse_required
        and not hse_na
        and not mi.get("custom_hse_score")
    ):
        frappe.throw(
            "HSE Rating is required, or mark it "
            "as Not Applicable."
        )

    calibration_records = []
    if mi.get('custom_intervention_type') == 'Calibration':
        from maintenance_app.calibration_finalization import finalize_for_intervention
        calibration_records = finalize_for_intervention(mi)

        # Calibration Record After Submit scripts can save the linked MI.
        # Reload to keep their notes/links and prevent TimestampMismatchError.
        mi = frappe.get_doc("Mission Intervention", mi_name)
        mi.check_permission("submit")
        if mi.docstatus != 0:
            frappe.throw("The intervention changed status during calibration finalization.")

    mi.submit()
    frappe.db.commit()

    return {
        "ok": True,
        "submitted": True,
        "calibration_records": calibration_records,
        "intervention": mi.name,
        "mission":
            mi.get("custom_parent_mission"),
        "ticket":
            mi.get("custom_service_ticket"),
        "calibration_followup": bool(
            mi.get("custom_intervention_type") == "Calibration"
            or frappe.db.exists(
                "Calibration Record",
                {
                    "custom_mission_intervention": mi.name,
                    "custom_calibration_status": ["!=", "Cancelled"],
                },
            )
        ),
    }


def _get_actual_type_options():
    field = frappe.get_meta(
        "Mission Intervention"
    ).get_field(
        "custom_intervention_type"
    )

    if not field:
        return []

    return [
        x.strip()
        for x in (field.options or "").split("\n")
        if x.strip()
    ]


@frappe.whitelist()
def save_actual_ticket_type_v2(
    mi_name,
    actual_ticket_type,
):
    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    mi.check_permission("write")

    if mi.docstatus != 0:
        frappe.throw(
            "Only a draft intervention can be updated."
        )

    if not mi.get("custom_end_time"):
        frappe.throw(
            "Please Check Out first."
        )

    actual_ticket_type = (
        actual_ticket_type or ""
    ).strip()

    if not actual_ticket_type:
        frappe.throw(
            "Actual Ticket Type is required."
        )

    options = _get_actual_type_options()

    if actual_ticket_type not in options:
        frappe.throw(
            "Invalid Actual Ticket Type."
        )

    # MI remains the actual work record.
    mi.custom_intervention_type = (
        actual_ticket_type
    )

    mi.save()
    frappe.db.commit()

    return {
        "ok": True,
        "actual_ticket_type":
            actual_ticket_type,
    }


def _write_actual_execution_to_ticket(mi):
    """
    Write final actual execution values to the Service Ticket
    without changing the original requested/planned fields.
    """

    ticket_name = mi.get(
        "custom_service_ticket"
    )

    if not ticket_name:
        return

    if not frappe.db.exists(
        "Service Ticket",
        ticket_name
    ):
        return

    ticket = frappe.get_doc(
        "Service Ticket",
        ticket_name
    )

    # --------------------------------------------------
    # Actual Ticket Type
    # --------------------------------------------------

    if ticket.meta.has_field(
        "custom_actual_ticket_type"
    ):
        ticket.custom_actual_ticket_type = (
            mi.get("custom_intervention_type")
            or ""
        )

    # --------------------------------------------------
    # Actual Equipment
    # --------------------------------------------------

    if ticket.meta.has_field(
        "custom_actual_equipment"
    ):
        ticket.custom_actual_equipment = (
            mi.get("custom_asset")
            or ""
        )

    # --------------------------------------------------
    # Actual Component
    # --------------------------------------------------

    if ticket.meta.has_field(
        "custom_actual_component_item"
    ):
        actual_component = (
            mi.get(
                "custom_target_component_name"
            )
            or mi.get(
                "custom_component_item"
            )
            or ""
        )

        ticket.custom_actual_component_item = (
            actual_component
        )

    ticket.save(
        ignore_permissions=True
    )

#cat >> apps/maintenance_app/maintenance_app/www/tech/intervention2/index.py <<'PY'


def _get_actual_type_options():
    field = frappe.get_meta(
        "Mission Intervention"
    ).get_field(
        "custom_intervention_type"
    )

    if not field:
        return []

    return [
        x.strip()
        for x in (field.options or "").split("\n")
        if x.strip()
    ]





# === TECH2 EQUIPMENT IDENTITY PATCH START ===
# UI context only. Does not write to Mission Intervention or Installed Equipment.

_tech2_base_get_context = get_context


def _tech2_equipment_identity(mi):
    result = {
        "equipment_display": "",
        "site_id": "",
        "is_component_target": False,
        "component_display": "",
    }

    asset_name = (mi.get("custom_asset") or "").strip()

    if asset_name:
        try:
            equipment = frappe.get_doc("Installed Equipment", asset_name)
            meta = frappe.get_meta("Installed Equipment")

            title_field = (meta.title_field or "").strip()

            equipment_display = ""
            if title_field:
                equipment_display = (equipment.get(title_field) or "").strip()

            if not equipment_display:
                for fieldname in (
                    "custom_display_name",
                    "custom_asset_name",
                    "custom_client_asset_code",
                ):
                    if meta.has_field(fieldname):
                        equipment_display = (
                            equipment.get(fieldname) or ""
                        ).strip()
                        if equipment_display:
                            break

            result["equipment_display"] = equipment_display or equipment.name

            if meta.has_field("custom_site_id"):
                result["site_id"] = (
                    equipment.get("custom_site_id") or ""
                ).strip()

        except frappe.DoesNotExistError:
            result["equipment_display"] = asset_name

    component_target = bool(
        mi.get("custom_equipment_component")
        or mi.get("custom_parent_equipment")
    )

    result["is_component_target"] = component_target

    if component_target:
        result["component_display"] = (
            mi.get("custom_target_component_name") or ""
        ).strip()

    return result


def get_context(context):
    context = _tech2_base_get_context(context)

    mi = getattr(context, "mi", None)

    if mi:
        identity = _tech2_equipment_identity(mi)

        context.pwa_equipment_display = identity["equipment_display"]
        context.pwa_equipment_site_id = identity["site_id"]
        context.pwa_is_component_target = identity["is_component_target"]
        context.pwa_component_display = identity["component_display"]

    return context

# === TECH2 EQUIPMENT IDENTITY PATCH END ===

# === TECH2 COMPACT TOOLS CONTEXT START ===
# Read-only reference context for the technician Tools pages.

_tech2_tools_base_get_context = get_context


def _tech2_format_date(value):
    if not value:
        return ""
    try:
        return frappe.utils.formatdate(value, "dd MMM yyyy")
    except Exception:
        return str(value)


def _tech2_format_datetime(value):
    if not value:
        return ""
    try:
        return frappe.utils.format_datetime(value, "dd MMM yyyy HH:mm")
    except Exception:
        return str(value)


def _tech2_get_equipment_reference(mi):
    data = {
        "equipment": "",
        "site_id": "",
        "make": "",
        "model": "",
        "serial": "",
        "installed_date": "",
        "last_service_date": "",
        "next_maintenance_date": "",
        "asset_status": "",
        "operational_status": "",
        "component": "",
    }

    asset_name = (mi.get("custom_asset") or "").strip()

    if not asset_name:
        return data

    try:
        equipment = frappe.get_doc("Installed Equipment", asset_name)
        meta = frappe.get_meta("Installed Equipment")

        title_field = (meta.title_field or "").strip()
        display = ""

        if title_field:
            display = (equipment.get(title_field) or "").strip()

        if not display:
            for fieldname in (
                "custom_display_name",
                "custom_asset_name",
                "custom_client_asset_code",
            ):
                if meta.has_field(fieldname):
                    display = (equipment.get(fieldname) or "").strip()
                    if display:
                        break

        data["equipment"] = display or equipment.name

        field_map = {
            "site_id": "custom_site_id",
            "make": "custom_make",
            "model": "custom_model",
            "serial": "custom_asset_id",
            "asset_status": "custom_asset_status",
            "operational_status": "custom_operational_status",
        }

        for key, fieldname in field_map.items():
            if meta.has_field(fieldname):
                data[key] = equipment.get(fieldname) or ""

        if meta.has_field("custom_installed_date"):
            data["installed_date"] = _tech2_format_date(
                equipment.get("custom_installed_date")
            )

        if meta.has_field("custom_last_service_date"):
            data["last_service_date"] = _tech2_format_date(
                equipment.get("custom_last_service_date")
            )

        next_field = None
        for fieldname in (
            "custom_next_maintenance_date",
            "custom_next_maintenance",
        ):
            if meta.has_field(fieldname):
                next_field = fieldname
                break

        if next_field:
            data["next_maintenance_date"] = _tech2_format_date(
                equipment.get(next_field)
            )

    except frappe.DoesNotExistError:
        data["equipment"] = asset_name

    if (
        mi.get("custom_equipment_component")
        or mi.get("custom_parent_equipment")
    ):
        data["component"] = (
            mi.get("custom_target_component_name") or ""
        ).strip()

    return data


def _tech2_get_service_ticket_name(mi):
    for fieldname in (
        "custom_service_ticket",
        "custom_parent_ticket",
    ):
        value = (mi.get(fieldname) or "").strip()
        if value:
            return value

    mission_name = (mi.get("custom_parent_mission") or "").strip()

    if mission_name and frappe.db.exists("Tech Mission", mission_name):
        mission_meta = frappe.get_meta("Tech Mission")

        if mission_meta.has_field("custom_service_ticket"):
            return (
                frappe.db.get_value(
                    "Tech Mission",
                    mission_name,
                    "custom_service_ticket",
                )
                or ""
            )

    return ""


def _tech2_get_sla_reference(mi):
    data = {
        "service_ticket": "",
        "priority": "",
        "service_type": "",
        "ticket_type": "",
        "sla_status": "",
        "response_due": "",
        "resolution_due": "",
        "maintenance_contract": "",
        "sla_rule": "",
    }

    ticket_name = _tech2_get_service_ticket_name(mi)

    if not ticket_name:
        return data

    if not frappe.db.exists("Service Ticket", ticket_name):
        return data

    ticket = frappe.get_doc("Service Ticket", ticket_name)
    meta = frappe.get_meta("Service Ticket")

    data["service_ticket"] = ticket.name

    field_map = {
        "priority": "custom_priority",
        "service_type": "custom_service_type",
        "ticket_type": "custom_ticket_type",
        "sla_status": "custom_sla_status",
        "maintenance_contract": "custom_maintenance_contract",
        "sla_rule": "custom_sla_rule",
    }

    for key, fieldname in field_map.items():
        if meta.has_field(fieldname):
            data[key] = ticket.get(fieldname) or ""

    if meta.has_field("custom_response_due"):
        data["response_due"] = _tech2_format_datetime(
            ticket.get("custom_response_due")
        )

    if meta.has_field("custom_resolution_due"):
        data["resolution_due"] = _tech2_format_datetime(
            ticket.get("custom_resolution_due")
        )

    return data


def get_context(context):
    context = _tech2_tools_base_get_context(context)

    mi = getattr(context, "mi", None)

    if mi:
        context.pwa_equipment_details = _tech2_get_equipment_reference(mi)
        context.pwa_sla_info = _tech2_get_sla_reference(mi)

    return context

# === TECH2 COMPACT TOOLS CONTEXT END ===

# === TECH2 EXTRA TOOL ROUTES START ===
# Accept new read-only Tools pages even if the older base context
# still sanitizes unknown step values back to "job".

_tech2_extra_tool_routes_base_get_context = get_context


def get_context(context):
    context = _tech2_extra_tool_routes_base_get_context(context)

    requested_step = (
        frappe.form_dict.get("step") or ""
    ).strip()

    if requested_step in (
        "equipment",
        "sla",
    ):
        context.step = requested_step

    return context

# === TECH2 EXTRA TOOL ROUTES END ===

# === TECH2 SLA TARGET HOURS START ===

_tech2_sla_target_base_get_context = get_context


def _tech2_hour_label(value):
    if value in (None, ""):
        return ""

    try:
        number = float(value)
    except Exception:
        return str(value)

    if number.is_integer():
        number_text = str(int(number))
    else:
        number_text = str(number).rstrip("0").rstrip(".")

    return (
        number_text
        + " hour"
        + ("" if number == 1 else "s")
    )


def get_context(context):
    context = _tech2_sla_target_base_get_context(context)

    sla = getattr(context, "pwa_sla_info", None)

    if not isinstance(sla, dict):
        return context

    sla["response_target"] = ""
    sla["resolution_target"] = ""

    rule_name = (sla.get("sla_rule") or "").strip()

    if (
        rule_name
        and frappe.db.exists("SLA Rule", rule_name)
    ):
        rule = frappe.get_doc("SLA Rule", rule_name)
        rule_meta = frappe.get_meta("SLA Rule")

        if rule_meta.has_field("custom_response_time"):
            sla["response_target"] = _tech2_hour_label(
                rule.get("custom_response_time")
            )

        if rule_meta.has_field("custom_resolution_time"):
            sla["resolution_target"] = _tech2_hour_label(
                rule.get("custom_resolution_time")
            )

    context.pwa_sla_info = sla

    return context

# === TECH2 SLA TARGET HOURS END ===

# === TECH2 COMPONENT DETAILS CONTEXT START ===

_tech2_component_details_base_get_context = get_context


def _tech2_component_value(doc, meta, *fieldnames):
    for fieldname in fieldnames:
        if meta.has_field(fieldname):
            value = doc.get(fieldname)
            if value not in (None, ""):
                return value
    return ""


def _tech2_resolve_component_doc(mi):
    candidates = []

    for fieldname in (
        "custom_equipment_component",
        "custom_parent_equipment",
    ):
        value = (mi.get(fieldname) or "").strip()

        if value and value not in candidates:
            candidates.append(value)

    for candidate in candidates:
        if frappe.db.exists("Equipment Component", candidate):
            return frappe.get_doc(
                "Equipment Component",
                candidate
            )

    asset_name = (mi.get("custom_asset") or "").strip()
    target_name = (
        mi.get("custom_target_component_name")
        or ""
    ).strip()

    if asset_name and frappe.db.exists(
        "Installed Equipment",
        asset_name
    ):
        equipment = frappe.get_doc(
            "Installed Equipment",
            asset_name
        )

        for row in (
            equipment.get("custom_installed_components")
            or []
        ):
            component_name = (
                row.get("custom_equipment_component")
                or ""
            ).strip()

            if not component_name:
                continue

            row_display = (
                row.get("custom_display_name")
                or ""
            ).strip()

            row_item = (
                row.get("custom_component_item")
                or ""
            ).strip()

            if target_name and target_name not in (
                row_display,
                row_item,
                component_name,
            ):
                continue

            if frappe.db.exists(
                "Equipment Component",
                component_name
            ):
                return frappe.get_doc(
                    "Equipment Component",
                    component_name
                )

    return None


def _tech2_get_component_reference(mi):
    data = {
        "exists": False,
        "name": "",
        "display_name": "",
        "parent_equipment": "",
        "parent_equipment_display": "",
        "component_group": "",
        "equipment_type": "",
        "make": "",
        "model": "",
        "serial": "",
        "part_number": "",
        "item": "",
        "status": "",
        "installation_date": "",
        "commissioning_status": "",
        "commissioned_date": "",
        "requires_calibration": False,
        "last_calibration_date": "",
        "next_calibration_date": "",
        "calibration_interval_months": "",
    }

    component = _tech2_resolve_component_doc(mi)

    if not component:
        return data

    meta = frappe.get_meta("Equipment Component")

    data["exists"] = True
    data["name"] = component.name

    data["display_name"] = (
        _tech2_component_value(
            component,
            meta,
            "custom_display_name",
        )
        or (mi.get("custom_target_component_name") or "")
        or component.name
    )

    data["parent_equipment"] = _tech2_component_value(
        component,
        meta,
        "custom_parent_equipment",
    )

    data["component_group"] = _tech2_component_value(
        component,
        meta,
        "custom_component_group",
    )

    data["equipment_type"] = _tech2_component_value(
        component,
        meta,
        "custom_equipment_type",
    )

    data["make"] = _tech2_component_value(
        component,
        meta,
        "custom_make",
    )

    data["model"] = _tech2_component_value(
        component,
        meta,
        "custom_model",
    )

    data["serial"] = _tech2_component_value(
        component,
        meta,
        "custom_serial_number",
        "custom_serial",
    )

    data["part_number"] = _tech2_component_value(
        component,
        meta,
        "custom_part_number",
    )

    data["item"] = _tech2_component_value(
        component,
        meta,
        "custom_item",
    )

    data["status"] = _tech2_component_value(
        component,
        meta,
        "custom_status",
    )

    installation_date = _tech2_component_value(
        component,
        meta,
        "custom_installation_date",
    )

    if installation_date:
        data["installation_date"] = _tech2_format_date(
            installation_date
        )

    data["commissioning_status"] = _tech2_component_value(
        component,
        meta,
        "custom_commissioning_status",
    )

    commissioned_date = _tech2_component_value(
        component,
        meta,
        "custom_commissioned_date",
    )

    if commissioned_date:
        data["commissioned_date"] = _tech2_format_date(
            commissioned_date
        )

    data["requires_calibration"] = bool(
        _tech2_component_value(
            component,
            meta,
            "custom_requires_calibration",
        )
    )

    last_calibration_date = _tech2_component_value(
        component,
        meta,
        "custom_last_calibration_date",
    )

    if last_calibration_date:
        data["last_calibration_date"] = _tech2_format_date(
            last_calibration_date
        )

    next_calibration_date = _tech2_component_value(
        component,
        meta,
        "custom_next_calibration_date",
    )

    if next_calibration_date:
        data["next_calibration_date"] = _tech2_format_date(
            next_calibration_date
        )

    data["calibration_interval_months"] = (
        _tech2_component_value(
            component,
            meta,
            "custom_calibration_interval_months",
        )
    )

    parent_name = (
        data["parent_equipment"]
        or (mi.get("custom_asset") or "")
    ).strip()

    if parent_name and frappe.db.exists(
        "Installed Equipment",
        parent_name
    ):
        try:
            parent = frappe.get_doc(
                "Installed Equipment",
                parent_name
            )
            parent_meta = frappe.get_meta(
                "Installed Equipment"
            )

            title_field = (
                parent_meta.title_field
                or ""
            ).strip()

            parent_display = ""

            if title_field:
                parent_display = (
                    parent.get(title_field)
                    or ""
                ).strip()

            if not parent_display:
                for fieldname in (
                    "custom_display_name",
                    "custom_asset_name",
                    "custom_client_asset_code",
                ):
                    if parent_meta.has_field(fieldname):
                        parent_display = (
                            parent.get(fieldname)
                            or ""
                        ).strip()

                        if parent_display:
                            break

            data["parent_equipment_display"] = (
                parent_display
                or parent.name
            )

        except frappe.DoesNotExistError:
            pass

    return data


def get_context(context):
    context = _tech2_component_details_base_get_context(
        context
    )

    mi = getattr(context, "mi", None)

    if mi:
        context.pwa_component_details = (
            _tech2_get_component_reference(mi)
        )

    requested_step = (
        frappe.form_dict.get("step")
        or ""
    ).strip()

    if requested_step == "component":
        context.step = "component"

    return context

# === TECH2 COMPONENT DETAILS CONTEXT END ===

# === TECH2 CONTINUE WORK FOLLOW-UP START ===

@frappe.whitelist()
def create_follow_up_mi_v2(
    source_mi_name,
    planned_start=None,
    planned_end=None,
    reason=None,
):
    from maintenance_app.www.tech.intervention.index import (
        create_follow_up_mi,
    )

    source = frappe.get_doc(
        "Mission Intervention",
        source_mi_name,
    )

    result = create_follow_up_mi(
        source_mi_name=source_mi_name,
        planned_start=planned_start,
        planned_end=planned_end,
        reason=reason,
    ) or {}

    follow_up_name = result.get("intervention")
    if not follow_up_name:
        return result

    follow_up = frappe.get_doc(
        "Mission Intervention",
        follow_up_name,
    )

    fields_to_preserve = [
        "custom_intervention_type",
        "custom_service_type",
        "custom_specialised_testing_type",
        "custom_general_installation_type",
        "custom_general_work_type",
    ]

    changed = False

    for fieldname in fields_to_preserve:
        if (
            source.meta.has_field(fieldname)
            and follow_up.meta.has_field(fieldname)
        ):
            source_value = source.get(fieldname)

            if follow_up.get(fieldname) != source_value:
                follow_up.db_set(
                    fieldname,
                    source_value,
                    update_modified=False,
                )
                changed = True

    if changed:
        frappe.db.commit()

    result["actual_intervention_type"] = (
        source.get("custom_intervention_type")
    )
    result["actual_service_type"] = (
        source.get("custom_service_type")
    )

    return result

# === TECH2 CONTINUE WORK FOLLOW-UP END ===

# === TECH2 CONTINUE WORK SUBMIT START ===


@frappe.whitelist()
def submit_continue_work_v2(
    mi_name,
    follow_up_date,
    follow_up_start_time,
    follow_up_end_time,
    reason,
):
    from frappe.utils import get_datetime, now_datetime

    if not mi_name:
        frappe.throw(
            "Mission Intervention is required."
        )

    if not follow_up_date:
        frappe.throw(
            "Next Planned Work Date is required."
        )

    if not follow_up_start_time:
        frappe.throw(
            "Start Time is required."
        )

    if not follow_up_end_time:
        frappe.throw(
            "End Time is required."
        )

    if not reason:
        frappe.throw(
            "Continuation Reason / Plan is required."
        )

    new_start = get_datetime(
        f"{follow_up_date} {follow_up_start_time}:00"
    )

    new_end = get_datetime(
        f"{follow_up_date} {follow_up_end_time}:00"
    )

    if new_end <= new_start:
        frappe.throw(
            "End Time must be after Start Time."
        )

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name,
    )

    if mi.get("custom_work_outcome") != "Continue Work":
        frappe.throw(
            "This submit path is only for Continue Work."
        )

    if not mi.get("custom_parent_mission"):
        frappe.throw(
            "The intervention is not linked to a Tech Mission."
        )

    mission_name = mi.get(
        "custom_parent_mission"
    )

    mission_before = frappe.get_doc(
        "Tech Mission",
        mission_name,
    )

    previous_start = mission_before.get(
        "custom_planned_starttime"
    )

    previous_end = mission_before.get(
        "custom_planned_endtime"
    )

    # Submit the current MI.
    # Verify actual docstatus afterwards instead of depending
    # on submit_intervention_v2 returning {"ok": True}.
    if int(mi.docstatus or 0) != 1:
        submit_intervention_v2(
            mi_name=mi_name
        )

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name,
    )

    if int(mi.docstatus or 0) != 1:
        frappe.throw(
            "The current intervention was not submitted."
        )

    # Create/reuse follow-up through existing proven logic.
    follow_result = create_follow_up_mi_v2(
        source_mi_name=mi_name,
        planned_start=new_start,
        planned_end=new_end,
        reason=reason,
    ) or {}

    follow_up_name = follow_result.get(
        "intervention"
    )

    if not follow_up_name:
        frappe.throw(
            "The follow-up intervention could not be created."
        )

    follow_up = frappe.get_doc(
        "Mission Intervention",
        follow_up_name,
    )

    if follow_up.meta.has_field(
        "custom_planned_starttime"
    ):
        follow_up.db_set(
            "custom_planned_starttime",
            new_start,
            update_modified=False,
        )

    if follow_up.meta.has_field(
        "custom_planned_endtime"
    ):
        follow_up.db_set(
            "custom_planned_endtime",
            new_end,
            update_modified=False,
        )

    # Old follow-up logic may temporarily set TM to 08:00-17:00.
    # Re-load and apply the exact requested times.
    mission = frappe.get_doc(
        "Tech Mission",
        mission_name,
    )

    if mission.meta.has_field(
        "custom_change_history"
    ):
        history_meta = frappe.get_meta(
            "Tech Mission Schedule History"
        )

        history_values = {
            "custom_change_type":
                "Schedule Changed",
            "custom_previous_start":
                previous_start,
            "custom_previous_end":
                previous_end,
            "custom_change_reason":
                (
                    f"Continue Work from {mi.name}: "
                    f"{reason}"
                ),
            "custom_changed_on":
                now_datetime(),
            "custom_changed_by":
                frappe.session.user,
        }

        history_values = {
            key: value
            for key, value
            in history_values.items()
            if history_meta.has_field(key)
        }

        duplicate_filters = {
            "parent": mission.name,
            "parenttype": "Tech Mission",
            "parentfield": "custom_change_history",
        }

        if history_meta.has_field(
            "custom_change_type"
        ):
            duplicate_filters[
                "custom_change_type"
            ] = "Schedule Changed"

        if (
            previous_start
            and history_meta.has_field(
                "custom_previous_start"
            )
        ):
            duplicate_filters[
                "custom_previous_start"
            ] = previous_start

        existing_history = frappe.db.get_value(
            "Tech Mission Schedule History",
            duplicate_filters,
            "name",
        )

        if not existing_history:
            history_row = frappe.new_doc(
                "Tech Mission Schedule History"
            )

            history_row.parent = mission.name
            history_row.parenttype = (
                "Tech Mission"
            )
            history_row.parentfield = (
                "custom_change_history"
            )

            for fieldname, value in (
                history_values.items()
            ):
                history_row.set(
                    fieldname,
                    value,
                )

            history_row.db_insert()

    if mission.meta.has_field(
        "custom_planned_starttime"
    ):
        mission.custom_planned_starttime = (
            new_start
        )

    if mission.meta.has_field(
        "custom_planned_endtime"
    ):
        mission.custom_planned_endtime = (
            new_end
        )

    if mission.meta.has_field(
        "custom_mission_status"
    ):
        mission.custom_mission_status = (
            "On Hold"
        )

    if mission.meta.has_field(
        "custom_hold_reason"
    ):
        mission.custom_hold_reason = "Continue Work"

    if mission.meta.has_field(
        "custom_latest_intervention"
    ):
        mission.custom_latest_intervention = (
            follow_up_name
        )

    if mission.meta.has_field(
        "custom_open_work_remaining"
    ):
        mission.custom_open_work_remaining = 1

    mission.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "ok": True,
        "intervention":
            mi.name,
        "follow_up_intervention":
            follow_up_name,
        "follow_up_created":
            follow_result.get("created"),
        "planned_start":
            str(new_start),
        "planned_end":
            str(new_end),
        "message":
            "Intervention submitted and follow-up planned.",
    }

# === TECH2 CONTINUE WORK SUBMIT END ===

# === TECH2 ACTUAL MI TYPE CONTEXT START ===
# The Service Ticket keeps the original requested ticket type.
# The technician PWA must display/work from the actual MI type.

_tech2_actual_type_base_get_context = get_context


def get_context(context):
    context = _tech2_actual_type_base_get_context(context)

    mi = getattr(context, "mi", None)

    if mi:
        actual_type = (
            mi.get("custom_intervention_type") or ""
        ).strip()

        if actual_type:
            context.intervention_type = actual_type

        context.is_submitted = (
            int(mi.docstatus or 0) == 1
        )

    return context

# === TECH2 ACTUAL MI TYPE CONTEXT END ===



@frappe.whitelist()
def save_config_changes_v2(mi_name, rows):
    """Save draft MI config rows; history is created by on_submit hook."""
    import json

    mi = frappe.get_doc("Mission Intervention", mi_name)
    mi.check_permission("write")
    if mi.docstatus != 0:
        frappe.throw("Only a draft intervention can be edited.")
    if mi.get("custom_intervention_type") != "Config Change":
        frappe.throw("This intervention is not a Config Change.")
    if not mi.get("custom_start_time"):
        frappe.throw("Check In before recording configuration changes.")

    if isinstance(rows, str):
        try:
            rows = json.loads(rows)
        except (ValueError, TypeError):
            frappe.throw("Invalid configuration change data.")

    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        frappe.throw("Enter between 1 and 100 configuration changes.")

    allowed = {
        "custom_parameter", "custom_current_value", "custom_new_value",
        "custom_notes", "custom_config_datetime"
    }
    cleaned = []
    for index, item in enumerate(rows, 1):
        if not isinstance(item, dict):
            frappe.throw(f"Row {index}: invalid configuration change.")
        record = {key: (str(item.get(key) or "").strip()) for key in allowed}
        if not record["custom_parameter"]:
            frappe.throw(f"Row {index}: Parameter is required.")
        if not record["custom_new_value"]:
            frappe.throw(f"Row {index}: New Value is required.")
        if record["custom_config_datetime"]:
            from frappe.utils import get_datetime
            try:
                record["custom_config_datetime"] = str(get_datetime(record["custom_config_datetime"]))
            except (TypeError, ValueError):
                frappe.throw(f"Row {index}: invalid date/time.")
        cleaned.append(record)

    mi.set("custom_config_changes", [])
    for record in cleaned:
        mi.append("custom_config_changes", record)
    mi.save()
    return {"ok": True, "count": len(cleaned), "intervention": mi.name}
