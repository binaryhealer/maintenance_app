# =========================
# ASSET SERVICE LOG
# =========================

existing_service_log = frappe.db.exists(
    "Asset Service Log",
    {
        "custom_intervention_ref": doc.name
    }
)

if not existing_service_log:

    service_log = frappe.new_doc("Asset Service Log")

    service_log.custom_customer = doc.custom_parent_customer
    service_log.custom_branch = doc.custom_branch
    service_log.custom_related_asset = doc.custom_asset

    service_log.custom_component_group = doc.get("custom_component_group")
    service_log.custom_component_item = doc.get("custom_component_item")
    service_log.custom_component_row_id = doc.get("custom_component_row_id")
    service_log.custom_component_serial = doc.get("custom_component_serial")
    service_log.custom_component_brand = doc.get("custom_component_brand")
    service_log.custom_component_model = doc.get("custom_component_model")

    service_log.custom_intervention_type = doc.custom_intervention_type or "Service"
    service_log.custom_technician = doc.custom_technician or frappe.session.user
    service_log.custom_work_outcome = doc.custom_work_outcome

    service_log.custom_notes = doc.custom_work_progress or doc.custom_description or ""

    service_log.custom_service_ticket = doc.custom_service_ticket
    service_log.custom_mission_ref = doc.custom_parent_mission
    service_log.custom_intervention_ref = doc.name

    service_log.custom_service_date = doc.custom_start_time
    service_log.custom_end_time = doc.custom_end_time
    service_log.custom_duration = doc.custom_hours_worked or 0

    service_log.insert(ignore_permissions=True)

    if service_log.docstatus == 0:
        service_log.submit()


# =========================
# CONFIG UPDATE LOG
# Source rows: MI Config Change Row
# Parent table field: custom_config_changes
# =========================

for row in doc.get("custom_config_changes") or []:

    if not row.get("custom_parameter") and not row.get("custom_new_value"):
        continue

    existing_config_log = frappe.db.exists(
    "Config Update Log",
    {
        "custom_service_ticket": doc.custom_service_ticket,
        "custom_parameter": row.get("custom_parameter"),
        "custom_new_value": row.get("custom_new_value")
    }

    )

    if existing_config_log:
        continue

    config_log = frappe.new_doc("Config Update Log")

    config_log.custom_customer = doc.custom_parent_customer
    config_log.custom_branch = doc.custom_branch
    config_log.custom_technician = doc.custom_technician or frappe.session.user
    config_log.custom_related_asset = doc.custom_asset

    config_log.custom_notes = row.get("custom_notes") or doc.custom_work_progress or ""

    config_log.custom_parameter = row.get("custom_parameter")
    config_log.custom_current_value = row.get("custom_current_value")
    config_log.custom_new_value = row.get("custom_new_value")

    config_log.custom_service_ticket = doc.custom_service_ticket
    config_log.custom_intervention = doc.name

    # Date comes from MI Config Change Row
    config_log.custom_datetime = row.get("custom_config_datetime") or frappe.utils.now_datetime()

    config_log.insert(ignore_permissions=True)

    if config_log.docstatus == 0:
        config_log.submit()
        
# =========================
# ASSET LIFECYCLE LOG
# =========================

lifecycle_event = None

if doc.custom_intervention_type == "Asset Relocation":
    lifecycle_event = "Asset Relocation"

elif doc.custom_intervention_type == "Swap":
    lifecycle_event = "Hardware Swap"

elif doc.custom_intervention_type == "Loan":

    if doc.custom_is_loan_return:
        lifecycle_event = "Return from Loan"
    else:
        lifecycle_event = "Temporary Loan"

elif doc.custom_intervention_type == "Retirement":
    lifecycle_event = "Retired"

elif doc.custom_intervention_type == "Disposal":
    lifecycle_event = "Scrapped"


if lifecycle_event:

    existing_lifecycle = frappe.db.exists(
        "Asset Lifecycle Log",
        {
            "custom_intervention_ref": doc.name,
            "custom_event": lifecycle_event
        }
    )

    if not existing_lifecycle:

        lifecycle_log = frappe.new_doc("Asset Lifecycle Log")

        lifecycle_log.custom_customer = doc.custom_parent_customer
        lifecycle_log.custom_branch = doc.custom_branch
        lifecycle_log.custom_related_asset = doc.custom_asset

        lifecycle_log.custom_date = (
            doc.custom_start_time
            or frappe.utils.now_datetime()
        )

        lifecycle_log.custom_event = lifecycle_event

        lifecycle_log.custom_to_branch = doc.custom_destination_branch

        lifecycle_log.custom_replacement_asset = doc.custom_replacement_asset
        lifecycle_log.custom_replacement_serial = doc.custom_replacement_serial
        lifecycle_log.custom_new_make = doc.custom_new_make
        lifecycle_log.custom_new_model = doc.custom_new_model

        lifecycle_log.custom_event_source = "Intervention"

        lifecycle_log.custom_action_taken = (
            doc.custom_work_progress
            or doc.custom_description
            or lifecycle_event
        )

        lifecycle_log.custom_technician = (
            doc.custom_technician
            or frappe.session.user
        )

        lifecycle_log.custom_service_ticket = doc.custom_service_ticket
        '''lifecycle_log.custom_billing_analysis = doc.custom_billing_analysis'''

        lifecycle_log.custom_mission_ref = doc.custom_parent_mission
        lifecycle_log.custom_intervention_ref = doc.name

        # GET PREVIOUS EQUIPMENT VALUES FROM INSTALLED EQUIPMENT

        if doc.custom_asset:

            asset_values = frappe.db.get_value(
                "Installed Equipment",
                doc.custom_asset,
                [
                    "custom_make",
                    "custom_model",
                    "custom_branch",
                    "custom_asset_id"
                ],
                as_dict=True
            )

            if asset_values:

                lifecycle_log.custom_previous_make = asset_values.custom_make
                lifecycle_log.custom_previous_model = asset_values.custom_model
                lifecycle_log.custom_from_branch = asset_values.custom_branch
                lifecycle_log.custom_previous_serial = asset_values.custom_asset_id

        lifecycle_log.insert(ignore_permissions=True)

        if lifecycle_log.docstatus == 0:
            lifecycle_log.submit()




        # =========================
        # UPDATE LAST SERVICE DATE
        # =========================

        if (
            doc.get("custom_asset")
            and doc.get("custom_work_outcome") == "Work Completed"
            and doc.get("custom_intervention_type") in [
                "Service",
                "Preventive Maintenance",
                "Calibration"
            ]
        ):

            frappe.db.set_value(
                "Installed Equipment",
                doc.custom_asset,
                "custom_last_service_date",
                (
                    doc.get("custom_end_time")
                    or doc.get("custom_start_time")
                    or frappe.utils.now_datetime()
                )
            )
        # =========================
        # UPDATE INSTALLED EQUIPMENT
        # AFTER RELOCATION
        # =========================

        if (
            doc.custom_intervention_type == "Asset Relocation"
            and doc.custom_asset
            and doc.custom_destination_branch
        ):

            frappe.db.set_value(
                "Installed Equipment",
                doc.custom_asset,
                "custom_branch",
                doc.custom_destination_branch
            )
    
            #=========================
            # component replacement  =
            #=========================
    
# =========================

# COMPONENT REPLACEMENT

# =========================

if str(doc.get("custom_component_replaced")) == "1":


    frappe.msgprint("Component Replacement Logic Running")

    if not doc.get("custom_asset"):
        frappe.throw("Equipment is required for component replacement.")

    if not doc.get("custom_component_row_id"):
        frappe.throw("Original component row is required.")

    if not doc.get("custom_new_component_item"):
        frappe.throw("New Component Item is required.")

        equipment = frappe.get_doc("Installed Equipment",doc.custom_asset)

        old_row = None

        for row in equipment.get("custom_installed_components") or []:
        if row.name == doc.custom_component_row_id:
            old_row = row
            break

            if not old_row:
                frappe.throw(
                    "Original component row not found on Installed Equipment."
                )

# Mark old component as replaced

            old_row.custom_status = "Replaced"

# Add new component

equipment.append("custom_installed_components", {
    "custom_component_item": doc.get("custom_new_component_item"),
    "custom_item_group": old_row.get("custom_item_group"),
    "custom_item_name": doc.get("custom_new_component_item"),
    "custom_serial_number": doc.get("custom_new_component_serial"),
    "custom_brand": doc.get("custom_new_component_brand"),
    "custom_model": doc.get("custom_new_component_model"),
    "custom_status": "Installed",
    "custom_notes": (
        doc.get("custom_component_replacement_reason")
        or ("Installed from MI " + doc.name)
    )
})

equipment.save(ignore_permissions=True)

# Lifecycle Log

lifecycle_log = frappe.new_doc("Asset Lifecycle Log")

lifecycle_log.custom_customer = doc.custom_parent_customer
lifecycle_log.custom_branch = doc.custom_branch
lifecycle_log.custom_related_asset = doc.custom_asset

lifecycle_log.custom_date = (
    doc.custom_start_time
    or frappe.utils.now_datetime()
)

lifecycle_log.custom_event = "Component Replaced"

lifecycle_log.custom_event_source = "Intervention"

lifecycle_log.custom_action_taken = (
    doc.get("custom_component_replacement_reason")
    or "Component Replaced"
)

lifecycle_log.custom_technician = (
    doc.custom_technician
    or frappe.session.user
)

lifecycle_log.custom_service_ticket = doc.custom_service_ticket
lifecycle_log.custom_mission_ref = doc.custom_parent_mission
lifecycle_log.custom_intervention_ref = doc.name

# Old Component

lifecycle_log.custom_component_item = (
    doc.get("custom_component_item")
)

lifecycle_log.custom_component_serial = (
    doc.get("custom_component_serial")
)

lifecycle_log.custom_component_brand = (
    doc.get("custom_component_brand")
)

lifecycle_log.custom_component_model = (
    doc.get("custom_component_model")
)

# New Component

lifecycle_log.custom_new_component_item = (
    doc.get("custom_new_component_item")
)

lifecycle_log.custom_new_component_serial = (
    doc.get("custom_new_component_serial")
)

lifecycle_log.custom_new_component_brand = (
    doc.get("custom_new_component_brand")
)

lifecycle_log.custom_new_component_model = (
    doc.get("custom_new_component_model")
)

lifecycle_log.insert(ignore_permissions=True)

if lifecycle_log.docstatus == 0:
    lifecycle_log.submit()

# =========================
# PUSH MI PARTS TO SERVICE TICKET
# =========================

if doc.custom_service_ticket:

    ticket = frappe.get_doc("Service Ticket", doc.custom_service_ticket)

    for part in doc.get("custom_parts_table") or []:

        if not part.get("custom_item_code"):
            continue

        exists = False

        for row in ticket.get("custom_used_parts") or []:
            if (
                row.custom_mission_intervention == doc.name
                and row.custom_item_code == part.get("custom_item_code")
                and row.custom_warehouse == part.get("custom_warehouse")
            ):
                exists = True

        if exists:
            continue

        ticket.append("custom_used_parts", {
            "custom_item_code": part.get("custom_item_code"),
            "custom_item_name": part.get("custom_item_name"),
            "custom_brand": part.get("custom_brand"),
            "custom_qty": part.get("custom_qty") or 1,
            "custom_warehouse": part.get("custom_warehouse"),
            "custom_mission_intervention": doc.name,
            "custom_billed": 0
        })

    ticket.save(ignore_permissions=True)
    
# =========================
# PUSH MI PARTS + INTERVENTION HISTORY TO SERVICE TICKET
# =========================

if doc.get("custom_service_ticket"):

    ticket = frappe.get_doc("Service Ticket", doc.custom_service_ticket)
    ticket_changed = False

    # -------------------------
    # Push used parts
    # -------------------------

    for part in doc.get("custom_parts_table") or []:

        if not part.get("custom_item_code"):
            continue

        part_exists = False

        for row in ticket.get("custom_used_parts") or []:
            if (
                row.get("custom_mission_intervention") == doc.name
                and row.get("custom_item_code") == part.get("custom_item_code")
                and row.get("custom_warehouse") == part.get("custom_warehouse")
            ):
                part_exists = True
                break

        if part_exists:
            continue

        ticket.append("custom_used_parts", {
            "custom_item_code": part.get("custom_item_code"),
            "custom_item_name": part.get("custom_item_name"),
            "custom_brand": part.get("custom_brand"),
            "custom_qty": part.get("custom_qty") or 1,
            "custom_warehouse": part.get("custom_warehouse"),
            "custom_mission_intervention": doc.name,
            "custom_billed": 0
        })

        ticket_changed = True

    # -------------------------
    # Push intervention history
    # -------------------------

    history_exists = False

    for row in ticket.get("custom_intervention_history") or []:
        if row.get("custom_mission_intervention") == doc.name:
            history_exists = True
            break

    if not history_exists:
        ticket.append("custom_intervention_history", {
            "custom_mission_intervention": doc.name,
            "custom_equipment": doc.get("custom_asset"),
            "custom_work_outcome": doc.get("custom_work_outcome"),
            "custom_start_time": doc.get("custom_start_time"),
            "custom_end_time": doc.get("custom_end_time"),
            "custom_technician": doc.get("custom_technician"),
            "custom_source": "Mission Intervention"
        })

        ticket_changed = True

    if ticket_changed:
        ticket.save(ignore_permissions=True)

# =========================
# UPDATE MISSION + TICKET STATUS
# =========================

if doc.get("custom_parent_mission"):
    mission = frappe.get_doc("Tech Mission", doc.custom_parent_mission)

    outcome = doc.get("custom_work_outcome")

    mission.custom_mission_status = (
        "Completed" if outcome == "Work Completed" else "Ongoing"
    )

    mission.save(ignore_permissions=True)

    if mission.get("custom_service_ticket"):
        ticket = frappe.get_doc("Service Ticket", mission.custom_service_ticket)

        if outcome == "Work Completed":
            ticket.custom_ticket_status = "Resolved"
            ticket.custom_hold_reason = ""

        elif outcome == "Waiting for Parts":
            ticket.custom_ticket_status = "On Hold"
            ticket.custom_hold_reason = "Waiting for Parts"

        elif outcome == "Waiting for Client":
            ticket.custom_ticket_status = "On Hold"
            ticket.custom_hold_reason = "Waiting for Client"

        elif outcome == "Continue Work":
            ticket.custom_ticket_status = "On Hold"
            ticket.custom_hold_reason = "Continue Work"

        elif outcome == "Could Not Complete":
            ticket.custom_ticket_status = "On Hold"
            ticket.custom_hold_reason = "Could Not Complete"

        elif outcome == "To Quote (Billable)":
            ticket.custom_ticket_status = "On Hold"
            ticket.custom_hold_reason = "To Quote"

            if ticket.meta.has_field("custom_commercial_status"):
                ticket.custom_commercial_status = "To Quote"

        else:
            ticket.custom_ticket_status = "On Hold"
            ticket.custom_hold_reason = outcome or "Pending"

        ticket.save(ignore_permissions=True)