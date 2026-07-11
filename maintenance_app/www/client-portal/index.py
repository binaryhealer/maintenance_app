import frappe

def get_context(context):
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.local.flags.redirect_to = "/login"
        raise frappe.PermissionError("Not logged in")

    current_user = frappe.session.user
    user_fullname = frappe.db.get_value("User", current_user, "full_name") or "User"

    contact_name = frappe.db.get_value(
        "Contact Email",
        {"email_id": current_user},
        "parent"
    )

    customer_name = None
    contact_scope = None
    contact_branch = None

    if contact_name:
        customer_name = frappe.db.get_value(
            "Dynamic Link",
            {
                "parent": contact_name,
                "parenttype": "Contact",
                "link_doctype": "Customer"
            },
            "link_name"
        )

        contact_scope = frappe.db.get_value(
            "Contact",
            contact_name,
            "custom_contact_scope"
        )

        contact_branch = frappe.db.get_value(
            "Contact",
            contact_name,
            "custom_client_branch"
        )

    internal_roles = [
        "System Manager",
        "Administrator",
        "Maintenance Manager",
        "Maintenance Supervisor"
    ]

    user_roles = frappe.get_roles(current_user)

    if not customer_name:
        if not any(r in user_roles for r in internal_roles):
            frappe.throw(
                "Your user is not linked to a customer account. Please contact support.",
                frappe.PermissionError
            )

    if customer_name and contact_scope == "Branch Level" and not contact_branch:
        frappe.throw(
            "Branch Level contact has no Client Branch assigned.",
            frappe.PermissionError
        )

    equipment_list = []

    if customer_name:
        equipment_filters = {
            "custom_parent_customer": customer_name
        }

        if contact_scope == "Branch Level":
            equipment_filters["custom_branch"] = contact_branch

        equipment_list = frappe.get_all(
            "Installed Equipment",
            filters=equipment_filters,
            fields=[
                "name",
                "custom_branch",
                "custom_asset_name",
                "custom_asset_category",
                "custom_model",
                "custom_asset_status",
                "custom_equipment_health",
                "custom_last_service_date",
                "custom_next_maintenance_date"
            ],
            order_by="custom_asset_category, custom_asset_name"
        )

        for eq in equipment_list:
            try:
                child_rows = frappe.db.get_values(
                    "Installed Equipment Component",
                    filters={
                        "parent": eq["name"],
                        "parenttype": "Installed Equipment",
                        "parentfield": "custom_installed_components"
                    },
                    fieldname=[
                        "name",
                        "custom_component_group",
                        "custom_display_name",
                        "custom_brand",
                        "custom_model",
                        "custom_serial_number",
                        "custom_status"
                    ],
                    as_dict=True
                ) or []

                components = []

                for row in child_rows:
                    components.append({
                        "name": row.get("name"),
                        "custom_component_group": row.get("custom_component_group") or "General",
                        "custom_display_name": (
                            row.get("custom_display_name")
                            or row.get("custom_item_name")
                            or "Unnamed Part"
                        ),
                        "custom_brand": row.get("custom_brand") or "-",
                        "custom_model": row.get("custom_model") or "-",
                        "custom_serial_number": row.get("custom_serial_number") or "N/A",
                        "custom_status": row.get("custom_status") or "Installed"
                    })

                eq["components"] = components

            except Exception as e:
                frappe.log_error(
                    f"Portal cache compilation failure for asset {eq.get('name')}: {str(e)}"
                )
                eq["components"] = []

    context.update({
        "user": current_user,
        "user_full_name": user_fullname,
        "customer_company": customer_name,
        "contact_scope": contact_scope,
        "contact_branch": contact_branch,
        "preloaded_equipment": equipment_list
    })

    context.no_header = 1
    context.no_sidebar = 1

    return context