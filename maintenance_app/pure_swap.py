import frappe
from frappe.utils import now_datetime


SWAP_STAGES = {
    "Same Site Exchange",
    "Collection from Source",
    "Exchange at Swap Branch",
    "Final Installation",
}


def _set_if(doc, fieldname, value):
    if doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def _snapshot(equipment):
    return {
        "name": equipment.name,
        "customer": equipment.get("custom_parent_customer"),
        "branch": equipment.get("custom_branch"),
        "site_id": equipment.get("custom_site_id"),
        "asset_status": equipment.get("custom_asset_status"),
        "operational_status": equipment.get("custom_operational_status"),
        "location_status": equipment.get("custom_location_status"),
    }


def _get_context(mi):
    if not mi.get("custom_service_ticket"):
        frappe.throw("Service Ticket is required for a Swap intervention.")

    ticket = frappe.get_doc(
        "Service Ticket",
        mi.custom_service_ticket
    )

    if ticket.get("custom_ticket_type") != "Swap":
        frappe.throw(
            "Pure Swap processing requires Service Ticket Type = Swap."
        )

    current_name = ticket.get("custom_target_equipment")
    swap_name = ticket.get("custom_swap_equipment")

    if not current_name:
        frappe.throw("Current Equipment is missing on the Service Ticket.")

    if not swap_name:
        frappe.throw("Swap Equipment is missing on the Service Ticket.")

    if current_name == swap_name:
        frappe.throw(
            "Current Equipment and Swap Equipment cannot be the same."
        )

    current = frappe.get_doc(
        "Installed Equipment",
        current_name
    )

    swap = frappe.get_doc(
        "Installed Equipment",
        swap_name
    )

    customer = ticket.get("custom_customer")

    if (
        current.get("custom_parent_customer")
        and current.get("custom_parent_customer") != customer
    ):
        frappe.throw(
            "Current Equipment does not belong to the Service Ticket customer."
        )

    if (
        swap.get("custom_parent_customer")
        and swap.get("custom_parent_customer") != customer
    ):
        frappe.throw(
            "Swap Equipment must belong to the same customer."
        )

    original_branch = (
        ticket.get("custom_client_branch")
        or current.get("custom_branch")
    )

    original_site = (
        ticket.get("custom_site_id")
        or current.get("custom_site_id")
    )

    swap_branch = (
        ticket.get("custom_swap_branch")
        or swap.get("custom_branch")
    )

    swap_site = (
        ticket.get("custom_swap_site_id")
        or swap.get("custom_site_id")
    )

    if not swap_branch:
        frappe.throw("Swap Branch is required.")

    swap_type = ticket.get("custom_swap_type")
    if swap_type not in [
        "Permanent Swap",
        "Temporary Swap",
    ]:
        frappe.throw(
            "Swap Type must be Permanent Swap or Temporary Swap."
        )

    if not ticket.get("custom_swap_reason"):
        frappe.throw("Swap Reason is required.")

    return {
        "ticket": ticket,
        "current": current,
        "swap": swap,
        "customer": customer,
        "original_branch": original_branch,
        "original_site": original_site,
        "swap_branch": swap_branch,
        "swap_site": swap_site,
        "swap_type": swap_type,
        "reason": ticket.get("custom_swap_reason"),
        "same_site": original_branch == swap_branch,
    }


def _set_in_transit(equipment):
    _set_if(
        equipment,
        "custom_asset_status",
        "In Transit"
    )

    _set_if(
        equipment,
        "custom_operational_status",
        "Out of Service"
    )

    _set_if(
        equipment,
        "custom_location_status",
        "In Transit"
    )

    # Branch stays as the last confirmed customer site while travelling.
    # Slot is cleared because the equipment is no longer installed there.
    _set_if(
        equipment,
        "custom_site_id",
        None
    )

    equipment.save(ignore_permissions=True)


def _set_installed(equipment, branch, site_id):
    _set_if(
        equipment,
        "custom_branch",
        branch
    )

    _set_if(
        equipment,
        "custom_site_id",
        site_id
    )

    _set_if(
        equipment,
        "custom_asset_status",
        "Installed"
    )

    _set_if(
        equipment,
        "custom_operational_status",
        "Operational"
    )

    _set_if(
        equipment,
        "custom_location_status",
        "Client Site"
    )

    # IMPORTANT:
    # Do NOT change installed date, installation year,
    # serial number or equipment identity during a true Swap.

    equipment.save(ignore_permissions=True)


def _service_log(
    mi,
    equipment_name,
    before,
    after,
    note,
    moving=False,
):
    existing = frappe.db.exists(
        "Asset Service Log",
        {
            "custom_intervention_ref": mi.name,
            "custom_related_asset": equipment_name,
        }
    )

    if existing:
        return existing

    log = frappe.new_doc("Asset Service Log")

    _set_if(
        log,
        "custom_customer",
        mi.get("custom_parent_customer")
        or before.get("customer")
    )

    # The MI branch is where the technician performed this work.
    _set_if(
        log,
        "custom_branch",
        mi.get("custom_branch")
        or before.get("branch")
    )

    _set_if(
        log,
        "custom_related_asset",
        equipment_name
    )

    _set_if(
        log,
        "custom_intervention_type",
        "Swap"
    )

    _set_if(
        log,
        "custom_technician",
        mi.get("custom_technician")
        or frappe.session.user
    )

    _set_if(
        log,
        "custom_work_outcome",
        mi.get("custom_work_outcome")
    )

    _set_if(
        log,
        "custom_notes",
        note
    )

    _set_if(
        log,
        "custom_service_ticket",
        mi.get("custom_service_ticket")
    )

    _set_if(
        log,
        "custom_mission_ref",
        mi.get("custom_parent_mission")
    )

    _set_if(
        log,
        "custom_intervention_ref",
        mi.name
    )

    _set_if(
        log,
        "custom_service_date",
        mi.get("custom_start_time")
        or now_datetime()
    )

    _set_if(
        log,
        "custom_end_time",
        mi.get("custom_end_time")
        or now_datetime()
    )

    _set_if(
        log,
        "custom_duration",
        mi.get("custom_hours_worked") or 0
    )

    _set_if(
        log,
        "custom_asset_status_before",
        before.get("asset_status")
    )

    _set_if(
        log,
        "custom_asset_status_after",
        after.get("asset_status")
    )

    _set_if(
        log,
        "custom_operational_status_before",
        before.get("operational_status")
    )

    _set_if(
        log,
        "custom_operational_status_after",
        after.get("operational_status")
    )

    _set_if(
        log,
        "custom_previous_branch",
        before.get("branch")
    )

    _set_if(
        log,
        "custom_new_branch",
        after.get("branch")
    )

    _set_if(
        log,
        "custom_previous_site_id",
        before.get("site_id")
    )

    _set_if(
        log,
        "custom_new_site_id",
        after.get("site_id")
    )

    _set_if(
        log,
        "custom_swap_stage",
        mi.get("custom_swap_stage")
    )

    _set_if(
        log,
        "custom_equipment_being_moved",
        1 if moving else 0
    )

    log.insert(ignore_permissions=True)

    if log.docstatus == 0:
        log.submit()

    return log.name


def _lifecycle_log(
    mi,
    equipment_name,
    before,
    after,
    partner,
    swap_type,
    reason,
):
    existing = frappe.db.exists(
        "Asset Lifecycle Log",
        {
            "custom_intervention_ref": mi.name,
            "custom_related_asset": equipment_name,
            "custom_event": "Relocated",
        }
    )

    if existing:
        return existing

    log = frappe.new_doc("Asset Lifecycle Log")

    _set_if(
        log,
        "custom_customer",
        mi.get("custom_parent_customer")
        or after.get("customer")
        or before.get("customer")
    )

    _set_if(
        log,
        "custom_branch",
        after.get("branch")
    )

    _set_if(
        log,
        "custom_related_asset",
        equipment_name
    )

    _set_if(
        log,
        "custom_date",
        mi.get("custom_end_time")
        or mi.get("custom_start_time")
        or now_datetime()
    )

    _set_if(
        log,
        "custom_event",
        "Relocated"
    )

    _set_if(
        log,
        "custom_event_source",
        "Intervention"
    )

    _set_if(
        log,
        "custom_previous_branch",
        before.get("branch")
    )

    _set_if(
        log,
        "custom_new_branch",
        after.get("branch")
    )

    _set_if(
        log,
        "custom_previous_site_id",
        before.get("site_id")
    )

    _set_if(
        log,
        "custom_new_site_id",
        after.get("site_id")
    )

    _set_if(
        log,
        "custom_swap_partner",
        partner
    )

    _set_if(
        log,
        "custom_swap_type",
        swap_type
    )

    _set_if(
        log,
        "custom_new_asset",
        partner
    )

    _set_if(
        log,
        "custom_replacement_reason",
        reason
    )

    action = (
        str(swap_type)
        + " with "
        + str(partner)
        + ". "
        + "From "
        + str(before.get("branch") or "")
        + " / "
        + str(before.get("site_id") or "")
        + " to "
        + str(after.get("branch") or "")
        + " / "
        + str(after.get("site_id") or "")
        + ". Reason: "
        + str(reason or "")
    )

    _set_if(
        log,
        "custom_action_taken",
        action
    )

    _set_if(
        log,
        "custom_technician",
        mi.get("custom_technician")
        or frappe.session.user
    )

    _set_if(
        log,
        "custom_service_ticket",
        mi.get("custom_service_ticket")
    )

    _set_if(
        log,
        "custom_mission_ref",
        mi.get("custom_parent_mission")
    )

    _set_if(
        log,
        "custom_intervention_ref",
        mi.name
    )

    log.insert(ignore_permissions=True)

    if log.docstatus == 0:
        log.submit()

    return log.name


def _already_processed(mi):
    marker = "PURE_SWAP_PROCESSED:" + mi.name

    return frappe.db.exists(
        "Comment",
        {
            "reference_doctype": "Mission Intervention",
            "reference_name": mi.name,
            "comment_type": "Info",
            "content": marker,
        }
    )


def _mark_processed(mi):
    marker = "PURE_SWAP_PROCESSED:" + mi.name

    comment = frappe.new_doc("Comment")
    comment.comment_type = "Info"
    comment.reference_doctype = "Mission Intervention"
    comment.reference_name = mi.name
    comment.content = marker
    comment.insert(ignore_permissions=True)


def _configure_next_mi(
    next_mi,
    source_mi,
    context,
    stage,
    asset_name,
    partner_name,
    branch,
    site_id,
):
    _set_if(
        next_mi,
        "custom_branch",
        branch
    )

    _set_if(
        next_mi,
        "custom_site_id",
        site_id
    )

    _set_if(
        next_mi,
        "custom_asset",
        asset_name
    )

    _set_if(
        next_mi,
        "custom_new_asset",
        partner_name
    )

    _set_if(
        next_mi,
        "custom_primary_action",
        "Equipment Swap"
    )

    _set_if(
        next_mi,
        "custom_swap_stage",
        stage
    )

    # Keep the original ST Swap planning snapshot on every MI.
    # Execution direction may be reversed on the TM, but the ST plan
    # itself must not be rewritten.
    planned_swap_branch = (
        context["ticket"].get("custom_swap_branch")
        or context["swap_branch"]
    )
    planned_swap_site = (
        context["ticket"].get("custom_swap_site_id")
        or context["swap_site"]
    )

    _set_if(
        next_mi,
        "custom_swap_branch",
        planned_swap_branch
    )

    _set_if(
        next_mi,
        "custom_swap_site_id",
        planned_swap_site
    )

    _set_if(
        next_mi,
        "custom_swap_classification",
        context["swap_type"]
    )

    _set_if(
        next_mi,
        "custom_asset_change_reason",
        context["reason"]
    )

    _set_if(
        next_mi,
        "custom_equipment_being_moved",
        0
    )

    _set_if(
        next_mi,
        "custom_mi_purpose",
        "Follow-up"
    )

    _set_if(
        next_mi,
        "custom_previous_intervention",
        source_mi.name
    )

    previous_sequence = (
        source_mi.get("custom_follow_up_sequence")
        or 0
    )

    _set_if(
        next_mi,
        "custom_follow_up_sequence",
        int(previous_sequence) + 1
    )

    if stage in [
        "Exchange at Swap Branch",
        "Final Installation",
    ]:
        _set_if(
            next_mi,
            "custom_current_site_position",
            ""
        )
        _set_if(
            next_mi,
            "custom_replacement_site_position",
            site_id
        )


def _create_next_mi(
    source_mi,
    context,
    stage,
    asset_name,
    partner_name,
    branch,
    site_id,
):
    existing = frappe.db.get_value(
        "Mission Intervention",
        {
            "custom_parent_mission": source_mi.get(
                "custom_parent_mission"
            ),
            "custom_swap_stage": stage,
            "docstatus": ["<", 2],
        },
        "name",
        order_by="creation desc"
    )

    if existing:
        return existing

    mission = frappe.get_doc(
        "Tech Mission",
        source_mi.custom_parent_mission
    )

    from maintenance_app import api

    next_mi = frappe.new_doc(
        "Mission Intervention"
    )

    api._populate_mi_from_mission(
        next_mi,
        mission,
        asset_name
    )

    _configure_next_mi(
        next_mi,
        source_mi,
        context,
        stage,
        asset_name,
        partner_name,
        branch,
        site_id,
    )

    next_mi.insert(ignore_permissions=True)

    api._sync_mi_register_and_status(
        next_mi.name,
        save_mission=True
    )

    return next_mi.name



def _apply_tm_swap_route(mi, context):
    """
    Convert the original ST Swap pair into the execution pair.

    Normal:
        current A -> swap B

    Reversed:
        swap B -> current A

    The Service Ticket remains unchanged.
    """

    mission_name = mi.get("custom_parent_mission")

    if not mission_name:
        context["route_reversed"] = False
        return context

    mission = frappe.get_doc(
        "Tech Mission",
        mission_name
    )

    reversed_route = bool(
        mission.get("custom_swap_route_reversed")
        or 0
    )

    context = dict(context)
    context["route_reversed"] = reversed_route

    if not reversed_route:
        return context

    # Reverse execution roles only.
    # Do NOT modify the Service Ticket.
    (
        context["current"],
        context["swap"],
    ) = (
        context["swap"],
        context["current"],
    )

    (
        context["original_branch"],
        context["swap_branch"],
    ) = (
        context["swap_branch"],
        context["original_branch"],
    )

    (
        context["original_site"],
        context["swap_site"],
    ) = (
        context["swap_site"],
        context["original_site"],
    )

    return context


def _configure_initial_swap_mi(
    mi,
    context,
    reversed_route=False,
):
    """
    Configure the untouched first MI according to the TM execution route.
    """

    if reversed_route:
        first_asset = context["swap"].name
        partner_asset = context["current"].name
        branch = context["swap_branch"]
        site_id = context["swap_site"]
    else:
        first_asset = context["current"].name
        partner_asset = context["swap"].name
        branch = context["original_branch"]
        site_id = context["original_site"]

    _set_if(
        mi,
        "custom_branch",
        branch
    )

    _set_if(
        mi,
        "custom_site_id",
        site_id
    )

    _set_if(
        mi,
        "custom_asset",
        first_asset
    )

    _set_if(
        mi,
        "custom_new_asset",
        partner_asset
    )

    _set_if(
        mi,
        "custom_primary_action",
        "Equipment Swap"
    )

    _set_if(
        mi,
        "custom_swap_stage",
        (
            "Same Site Exchange"
            if context["same_site"]
            else "Collection from Source"
        )
    )

    # Original ST planning snapshot.
    _set_if(
        mi,
        "custom_swap_branch",
        context["ticket"].get("custom_swap_branch")
        or context["swap_branch"]
    )

    _set_if(
        mi,
        "custom_swap_site_id",
        context["ticket"].get("custom_swap_site_id")
        or context["swap_site"]
    )

    _set_if(
        mi,
        "custom_swap_classification",
        context["swap_type"]
    )

    _set_if(
        mi,
        "custom_asset_change_reason",
        context["reason"]
    )

    _set_if(
        mi,
        "custom_equipment_being_moved",
        0
    )

    _set_if(
        mi,
        "custom_mi_purpose",
        "Initial"
    )

    _set_if(
        mi,
        "custom_follow_up_sequence",
        0
    )


@frappe.whitelist()
def set_pure_swap_route(
    mission_name,
    reversed_route=0,
    reason=None,
):
    """
    RM action for changing which Swap site is visited first.

    Allowed only before physical Swap movement has started.
    """

    if not mission_name:
        frappe.throw("Tech Mission is required.")

    reason = (reason or "").strip()

    if not reason:
        frappe.throw(
            "Swap Route Change Reason is required."
        )

    mission = frappe.get_doc(
        "Tech Mission",
        mission_name
    )

    if mission.get("custom_ticket_type") != "Swap":
        frappe.throw(
            "Swap route can only be changed on a Swap Tech Mission."
        )

    if mission.get("custom_mission_status") in [
        "Completed",
        "Closed",
        "Cancelled",
    ]:
        frappe.throw(
            "Completed or cancelled missions cannot have their Swap route changed."
        )

    ticket_name = mission.get(
        "custom_service_ticket"
    )

    if not ticket_name:
        frappe.throw(
            "Service Ticket is missing from the Tech Mission."
        )

    ticket = frappe.get_doc(
        "Service Ticket",
        ticket_name
    )

    current_name = ticket.get(
        "custom_target_equipment"
    )
    swap_name = ticket.get(
        "custom_swap_equipment"
    )

    if not current_name or not swap_name:
        frappe.throw(
            "Both Swap equipment are required on the Service Ticket."
        )

    current = frappe.get_doc(
        "Installed Equipment",
        current_name
    )

    swap = frappe.get_doc(
        "Installed Equipment",
        swap_name
    )

    original_branch = (
        ticket.get("custom_client_branch")
        or current.get("custom_branch")
    )

    original_site = (
        ticket.get("custom_site_id")
        or current.get("custom_site_id")
    )

    swap_branch = (
        ticket.get("custom_swap_branch")
        or swap.get("custom_branch")
    )

    swap_site = (
        ticket.get("custom_swap_site_id")
        or swap.get("custom_site_id")
    )

    if original_branch == swap_branch:
        frappe.throw(
            "Same-site Swap does not require route reversal."
        )

    # No submitted Swap MI may exist.
    submitted = frappe.db.exists(
        "Mission Intervention",
        {
            "custom_parent_mission": mission.name,
            "custom_intervention_type": "Swap",
            "docstatus": 1,
        }
    )

    if submitted:
        frappe.throw(
            "Swap route cannot be changed after physical Swap work has been submitted."
        )

    draft_rows = frappe.get_all(
        "Mission Intervention",
        filters={
            "custom_parent_mission": mission.name,
            "docstatus": 0,
        },
        fields=[
            "name",
            "custom_start_time",
            "custom_checkout_status",
        ],
        order_by="creation asc",
    )

    active_drafts = [
        row
        for row in draft_rows
        if (
            row.get("custom_checkout_status")
            or ""
        ).strip() != "Cancelled"
    ]

    # A checked-in MI means physical execution has already started.
    for row in active_drafts:
        if row.get("custom_start_time"):
            frappe.throw(
                "Swap route cannot be changed after the technician has checked in."
            )

    if len(active_drafts) > 1:
        frappe.throw(
            "More than one active Draft MI exists. Please review the mission before changing the Swap route."
        )

    reversed_route = bool(int(reversed_route or 0))

    _set_if(
        mission,
        "custom_swap_route_reversed",
        1 if reversed_route else 0
    )

    _set_if(
        mission,
        "custom_swap_route_change_reason",
        reason
    )

    _set_if(
        mission,
        "custom_swap_route_changed_by",
        frappe.session.user
    )

    _set_if(
        mission,
        "custom_swap_route_changed_on",
        now_datetime()
    )

    mission.save(ignore_permissions=True)

    context = {
        "ticket": ticket,
        "current": current,
        "swap": swap,
        "original_branch": original_branch,
        "original_site": original_site,
        "swap_branch": swap_branch,
        "swap_site": swap_site,
        "swap_type": ticket.get("custom_swap_type"),
        "reason": ticket.get("custom_swap_reason"),
        "same_site": original_branch == swap_branch,
    }

    from maintenance_app import api

    # Reconfigure existing untouched first MI, or create it now.
    if active_drafts:
        first_mi = frappe.get_doc(
            "Mission Intervention",
            active_drafts[0].name
        )

        _configure_initial_swap_mi(
            first_mi,
            context,
            reversed_route=reversed_route,
        )

        first_mi.save(
            ignore_permissions=True
        )

    else:
        first_mi = frappe.new_doc(
            "Mission Intervention"
        )

        # Populate normal TM references/team/company first.
        api._populate_mi_from_mission(
            first_mi,
            mission,
            (
                swap.name
                if reversed_route
                else current.name
            ),
        )

        _configure_initial_swap_mi(
            first_mi,
            context,
            reversed_route=reversed_route,
        )

        first_mi.insert(
            ignore_permissions=True
        )

    api._sync_mi_register_and_status(
        first_mi.name,
        save_mission=True,
    )

    # Audit trail on the TM.
    route_text = (
        "Swap execution route reversed. Start from "
        + str(
            swap_branch
            if reversed_route
            else original_branch
        )
        + ". Reason: "
        + reason
    )

    mission.add_comment(
        "Info",
        route_text
    )

    frappe.db.commit()

    return {
        "ok": True,
        "mission": mission.name,
        "intervention": first_mi.name,
        "reversed": reversed_route,
        "start_branch": (
            swap_branch
            if reversed_route
            else original_branch
        ),
        "start_equipment": (
            swap.name
            if reversed_route
            else current.name
        ),
    }


@frappe.whitelist()
def process_pure_equipment_swap_on_submit(mi_name):
    if not mi_name:
        frappe.throw(
            "Mission Intervention is required."
        )

    mi = frappe.get_doc(
        "Mission Intervention",
        mi_name
    )

    if int(mi.docstatus or 0) != 1:
        frappe.throw(
            "Pure Swap processing requires a submitted Mission Intervention."
        )

    if mi.get("custom_intervention_type") != "Swap":
        return {
            "ok": True,
            "applied": False,
            "reason": "Not a Swap intervention.",
        }

    if _already_processed(mi):
        return {
            "ok": True,
            "applied": False,
            "already_processed": True,
        }

    context = _get_context(mi)

    # The ST contains the original Swap plan.
    # TM may reverse only the execution direction.
    context = _apply_tm_swap_route(
        mi,
        context
    )

    current = context["current"]
    swap = context["swap"]

    stage = (
        mi.get("custom_swap_stage")
        or (
            "Same Site Exchange"
            if context["same_site"]
            else "Collection from Source"
        )
    )

    if stage not in SWAP_STAGES:
        frappe.throw(
            "Invalid Pure Swap stage: "
            + str(stage)
        )

    # ======================================================
    # SAME SITE:
    # both equipments exchange slots in one completed MI.
    # ======================================================
    if stage == "Same Site Exchange":

        if mi.get("custom_work_outcome") != "Work Completed":
            frappe.throw(
                "Same-site Swap must use Work Outcome = Work Completed."
            )

        before_current = _snapshot(current)
        before_swap = _snapshot(swap)

        if before_current.get("asset_status") != "Installed":
            frappe.throw(
                "Current Equipment must be Installed before same-site Swap."
            )

        if before_swap.get("asset_status") != "Installed":
            frappe.throw(
                "Swap Equipment must be Installed before same-site Swap."
            )

        _set_installed(
            current,
            before_swap.get("branch"),
            before_swap.get("site_id")
        )

        _set_installed(
            swap,
            before_current.get("branch"),
            before_current.get("site_id")
        )

        after_current = _snapshot(current)
        after_swap = _snapshot(swap)

        _service_log(
            mi,
            current.name,
            before_current,
            after_current,
            (
                "Equipment swapped with "
                + swap.name
                + " within the same site."
            ),
            moving=False,
        )

        _service_log(
            mi,
            swap.name,
            before_swap,
            after_swap,
            (
                "Equipment swapped with "
                + current.name
                + " within the same site."
            ),
            moving=False,
        )

        _lifecycle_log(
            mi,
            current.name,
            before_current,
            after_current,
            swap.name,
            context["swap_type"],
            context["reason"],
        )

        _lifecycle_log(
            mi,
            swap.name,
            before_swap,
            after_swap,
            current.name,
            context["swap_type"],
            context["reason"],
        )

    # ======================================================
    # CROSS BRANCH - MI 1
    # Collect A at source branch.
    # ======================================================
    elif stage == "Collection from Source":

        if mi.get("custom_work_outcome") != "Continue Work":
            frappe.throw(
                "Collection stage must use Work Outcome = Continue Work."
            )

        if not int(
            mi.get("custom_equipment_being_moved") or 0
        ):
            frappe.throw(
                "Please tick Equipment Being Moved before submitting the collection MI."
            )

        before_current = _snapshot(current)

        if before_current.get("asset_status") != "Installed":
            frappe.throw(
                "Current Equipment must be Installed before collection."
            )

        _set_in_transit(current)

        after_current = _snapshot(current)

        _service_log(
            mi,
            current.name,
            before_current,
            after_current,
            (
                "Collected from "
                + str(context["original_branch"] or "")
                + " / "
                + str(context["original_site"] or "")
                + " for transport to "
                + str(context["swap_branch"] or "")
                + "."
            ),
            moving=True,
        )

        _create_next_mi(
            mi,
            context,
            "Exchange at Swap Branch",
            current.name,
            swap.name,
            context["swap_branch"],
            context["swap_site"],
        )

    # ======================================================
    # CROSS BRANCH - MI 2
    # Install A at Branch B / collect B for Branch A.
    # ======================================================
    elif stage == "Exchange at Swap Branch":

        if mi.get("custom_work_outcome") != "Continue Work":
            frappe.throw(
                "Exchange stage must use Work Outcome = Continue Work."
            )

        if not int(
            mi.get("custom_equipment_being_moved") or 0
        ):
            frappe.throw(
                "Please tick Equipment Being Moved because the outgoing Swap Equipment is leaving this site."
            )

        before_current = _snapshot(current)
        before_swap = _snapshot(swap)

        if before_current.get("asset_status") != "In Transit":
            frappe.throw(
                "Current Equipment must be In Transit before installation at the Swap Branch."
            )

        if before_swap.get("asset_status") != "Installed":
            frappe.throw(
                "Swap Equipment must still be Installed before the exchange."
            )

        _set_installed(
            current,
            context["swap_branch"],
            context["swap_site"]
        )

        _set_in_transit(swap)

        after_current = _snapshot(current)
        after_swap = _snapshot(swap)

        _service_log(
            mi,
            current.name,
            before_current,
            after_current,
            (
                "Installed at "
                + str(context["swap_branch"] or "")
                + " / "
                + str(context["swap_site"] or "")
                + " as part of equipment Swap."
            ),
            moving=False,
        )

        _service_log(
            mi,
            swap.name,
            before_swap,
            after_swap,
            (
                "Collected from "
                + str(context["swap_branch"] or "")
                + " / "
                + str(context["swap_site"] or "")
                + " for transport to "
                + str(context["original_branch"] or "")
                + "."
            ),
            moving=True,
        )

        # Current equipment has now completed its relocation.
        _lifecycle_log(
            mi,
            current.name,
            {
                **before_current,
                "branch": context["original_branch"],
                "site_id": context["original_site"],
            },
            after_current,
            swap.name,
            context["swap_type"],
            context["reason"],
        )

        _create_next_mi(
            mi,
            context,
            "Final Installation",
            swap.name,
            current.name,
            context["original_branch"],
            context["original_site"],
        )

    # ======================================================
    # CROSS BRANCH - MI 3
    # Install B at Branch A. Swap is physically complete.
    # ======================================================
    elif stage == "Final Installation":

        if mi.get("custom_work_outcome") != "Work Completed":
            frappe.throw(
                "Final Installation must use Work Outcome = Work Completed."
            )

        before_swap = _snapshot(swap)

        if before_swap.get("asset_status") != "In Transit":
            frappe.throw(
                "Swap Equipment must be In Transit before final installation."
            )

        _set_installed(
            swap,
            context["original_branch"],
            context["original_site"]
        )

        after_swap = _snapshot(swap)

        _service_log(
            mi,
            swap.name,
            before_swap,
            after_swap,
            (
                "Installed at "
                + str(context["original_branch"] or "")
                + " / "
                + str(context["original_site"] or "")
                + ". Equipment Swap completed."
            ),
            moving=False,
        )

        _lifecycle_log(
            mi,
            swap.name,
            {
                **before_swap,
                "branch": context["swap_branch"],
                "site_id": context["swap_site"],
            },
            after_swap,
            current.name,
            context["swap_type"],
            context["reason"],
        )

    _mark_processed(mi)

    # Do not commit here.
    # MI submission, IE updates and logs must remain one atomic transaction.

    return {
        "ok": True,
        "applied": True,
        "stage": stage,
    }
