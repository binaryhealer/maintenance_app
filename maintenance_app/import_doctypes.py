"""
Import Warranty DocTypes into Frappe
"""

import frappe

def import_doctypes():
    """Import Warranty DocTypes from JSON"""
    
    print("\n" + "="*60)
    print("IMPORTING WARRANTY DOCTYPES")
    print("="*60)
    
    # Step 1: Create Warranty License (child table)
    print("\n[1/6] Creating Warranty License (child table)...")
    try:
        warranty_license_data = {
            "custom": 1,
            "doctype": "DocType",
            "document_type": "",  
            "engine": "InnoDB",
            "field_order": [
                "custom_item_type",
                "custom_item_name",
                "custom_license_key",
                "col_break_dates",
                "custom_license_start_date",
                "custom_license_period_years",
                "custom_license_end_date",
                "custom_license_notes"
            ],
            "fields": [
                {
                    "fieldname": "custom_item_type",
                    "fieldtype": "Select",
                    "label": "Item Type",
                    "options": "Software License\nSupport Contract\nExtended Warranty\nOther",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_item_name",
                    "fieldtype": "Data",
                    "label": "Item Name",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_license_key",
                    "fieldtype": "Data",
                    "label": "License Key"
                },
                {
                    "fieldname": "col_break_dates",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "custom_license_start_date",
                    "fieldtype": "Date",
                    "label": "License Start Date",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_license_period_years",
                    "fieldtype": "Int",
                    "label": "License Period (Years)"
                },
                {
                    "fieldname": "custom_license_end_date",
                    "fieldtype": "Date",
                    "label": "License End Date",
                    "read_only": 1
                },
                {
                    "fieldname": "custom_license_notes",
                    "fieldtype": "Small Text",
                    "label": "Notes"
                }
            ],
            "is_submittable": 0,
            "istable": 1,  
            "module": "Maintenance",
            "name": "Warranty License",
            "owner": "Administrator",
            "sort_field": "creation",
            "sort_order": "DESC"
        }
        
        if frappe.db.exists("DocType", "Warranty License"):
            print("     ✓ Warranty License already exists")
        else:
            doc = frappe.get_doc(warranty_license_data)
            doc.insert(ignore_if_duplicate=True)
            frappe.db.commit()
            print("     ✓ Warranty License created!")
    
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        frappe.log_error(str(e), "Warranty License Import")
        return False
    
    # Step 2: Create Warranty (main table)
    print("\n[2/6] Creating Warranty DocType...")
    try:
        warranty_data = {
            "custom": 1,
            "doctype": "DocType",
            "document_type": "Document",
            "engine": "InnoDB",
            "autoname": "format:W-{MM}-{DD}-{######}",
            "show_in_module_section": "Document",
            "allow_import": 1,
            "allow_rename": 1,
            "quick_entry": 1,
            "editable_grid": 1,
            "field_order": [
                "warranty_details_section",
                "custom_warranty_title",
                "custom_customer",
                "custom_installed_equipment",
                "custom_branch",
                "col_break_dates",
                "custom_warranty_start_date",
                "custom_warranty_period_years",
                "custom_warranty_end_date",
                "custom_warranty_status",
                "coverage_details_tab",
                "custom_coverage_type",
                "custom_source",
                "custom_source_doctype",
                "custom_includes_parts",
                "custom_includes_labour",
                "custom_includes_transport",
                "col_break_coverage",
                "custom_coverage_notes",
                "custom_exclusions",
                "warranty_licenses_tab",
                "custom_warranty_licenses",
                "rma_tracking_tab",
                "custom_rma_number",
                "custom_rma_date",
                "custom_rma_reason",
                "col_break_rma",
                "custom_replacement_equipment",
                "custom_return_date",
                "custom_rma_status",
                "internal_tab",
                "custom_internal_notes",
                "custom_created_from_delivery_note"
            ],
            "fields": [
                {
                    "fieldname": "warranty_details_section",
                    "fieldtype": "Section Break",
                    "label": "Warranty Details"
                },
                {
                    "fieldname": "custom_warranty_title",
                    "fieldtype": "Data",
                    "label": "Warranty Title",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_customer",
                    "fieldtype": "Link",
                    "label": "Customer",
                    "options": "Customer",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_installed_equipment",
                    "fieldtype": "Link",
                    "label": "Installed Equipment",
                    "options": "Installed Equipment",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_branch",
                    "fieldtype": "Link",
                    "label": "Branch",
                    "options": "Client Branch"
                },
                {
                    "fieldname": "col_break_dates",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "custom_warranty_start_date",
                    "fieldtype": "Date",
                    "label": "Warranty Start Date",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_warranty_period_years",
                    "fieldtype": "Int",
                    "label": "Warranty Period (Years)",
                    "reqd": 1,
                    "default": 1
                },
                {
                    "fieldname": "custom_warranty_end_date",
                    "fieldtype": "Date",
                    "label": "Warranty End Date",
                    "read_only": 1
                },
                {
                    "fieldname": "custom_warranty_status",
                    "fieldtype": "Select",
                    "label": "Status",
                    "options": "Active\nExpired\nRMA Pending\nReplaced",
                    "default": "Active",
                    "reqd": 1
                },
                {
                    "fieldname": "coverage_details_tab",
                    "fieldtype": "Tab Break",
                    "label": "Coverage Details"
                },
                {
                    "fieldname": "custom_coverage_type",
                    "fieldtype": "Select",
                    "label": "Coverage Type",
                    "options": "Parts Only\nParts + Labour\nFull Coverage\nExtended",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_source",
                    "fieldtype": "Select",
                    "label": "Source",
                    "options": "Delivery Note\nManual Entry\nPurchased Separately",
                    "default": "Delivery Note"
                },
                {
                    "fieldname": "custom_source_doctype",
                    "fieldtype": "Link",
                    "label": "Source Document",
                    "options": "Delivery Note"
                },
                {
                    "fieldname": "custom_includes_parts",
                    "fieldtype": "Check",
                    "label": "Includes Parts"
                },
                {
                    "fieldname": "custom_includes_labour",
                    "fieldtype": "Check",
                    "label": "Includes Labour"
                },
                {
                    "fieldname": "custom_includes_transport",
                    "fieldtype": "Check",
                    "label": "Includes Transport"
                },
                {
                    "fieldname": "col_break_coverage",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "custom_coverage_notes",
                    "fieldtype": "Small Text",
                    "label": "Coverage Notes"
                },
                {
                    "fieldname": "custom_exclusions",
                    "fieldtype": "Small Text",
                    "label": "Exclusions"
                },
                {
                    "fieldname": "warranty_licenses_tab",
                    "fieldtype": "Tab Break",
                    "label": "License Sub-Items"
                },
                {
                    "fieldname": "custom_warranty_licenses",
                    "fieldtype": "Table",
                    "label": "Warranty Licenses",
                    "options": "Warranty License"
                },
                {
                    "fieldname": "rma_tracking_tab",
                    "fieldtype": "Tab Break",
                    "label": "RMA Tracking"
                },
                {
                    "fieldname": "custom_rma_number",
                    "fieldtype": "Data",
                    "label": "RMA Number"
                },
                {
                    "fieldname": "custom_rma_date",
                    "fieldtype": "Date",
                    "label": "RMA Date"
                },
                {
                    "fieldname": "custom_rma_reason",
                    "fieldtype": "Select",
                    "label": "RMA Reason",
                    "options": "Defect\nFailure\nUpgrade\nOther"
                },
                {
                    "fieldname": "col_break_rma",
                    "fieldtype": "Column Break"
                }
            ],
            "is_submittable": 0,
            "module": "Maintenance",
            "name": "Warranty",
            "naming_rule": "Expression",
            "owner": "Administrator",
            "permissions": [
                {
                    "create": 1,
                    "delete": 1,
                    "read": 1,
                    "role": "System Manager",
                    "write": 1
                },
                {
                    "create": 1,
                    "delete": 0,
                    "read": 1,
                    "role": "Maintenance Manager",
                    "write": 1
                }
            ], # FIXED: Cleaned up array block definition
            "search_fields": "custom_customer,custom_installed_equipment,custom_warranty_status",
            "sort_field": "creation",
            "sort_order": "DESC",
            "title_field": "custom_warranty_title",
            "track_changes": 1
        }
        
        if frappe.db.exists("DocType", "Warranty"):
            print("     ✓ Warranty already exists")
        else:
            doc = frappe.get_doc(warranty_data)
            doc.insert(ignore_if_duplicate=True)
            frappe.db.commit()
            print("     ✓ Warranty created!")
    
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        frappe.log_error(str(e), "Warranty Import")
        return False
    
    # Run Orchestrator for new tables
    if not create_warranty_coverage_item():
        return False
    
    if not create_warranty_addon():
        return False
    
    if not create_warranty_rma_record():
        return False
    
    print("\n" + "="*60)
    print("✓ SUCCESS - All DocTypes created safely!")
    print("="*60)
    return True


def create_warranty_coverage_item():
    """Create Warranty Coverage Item (child table)"""
    print("\n[3/6] Creating Warranty Coverage Item (child table)...")
    try:
        warranty_coverage_item_data = {
            "custom": 1,
            "doctype": "DocType",
            "document_type": "", # FIXED: Cannot be "Table"
            "engine": "InnoDB",
            "field_order": [
                "custom_item_code",
                "custom_coverage_type",
                "custom_item_name",
                "custom_quantity_limit",
                "custom_remarks"
            ],
            "fields": [
                {
                    "fieldname": "custom_item_code",
                    "fieldtype": "Data",
                    "label": "Item Code",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_coverage_type",
                    "fieldtype": "Select",
                    "label": "Coverage Type",
                    "options": "Parts\nLabour\nTransport\nPreventive\nRemote Support",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_item_name",
                    "fieldtype": "Data",
                    "label": "Item Name"
                },
                {
                    "fieldname": "custom_quantity_limit",
                    "fieldtype": "Data",
                    "label": "Quantity/Limit"
                },
                {
                    "fieldname": "custom_remarks",
                    "fieldtype": "Small Text",
                    "label": "Remarks"
                }
            ],
            "is_submittable": 0,
            "istable": 1,
            "module": "Maintenance",
            "name": "Warranty Coverage Item",
            "sort_field": "creation",
            "sort_order": "DESC"
        }
        
        if frappe.db.exists("DocType", "Warranty Coverage Item"):
            print("     ✓ Warranty Coverage Item already exists")
        else:
            doc = frappe.get_doc(warranty_coverage_item_data)
            doc.insert(ignore_if_duplicate=True)
            frappe.db.commit()
            print("     ✓ Warranty Coverage Item created!")
    
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        frappe.log_error(str(e), "Warranty Coverage Item Import")
        return False
    
    return True


def create_warranty_addon():
    """Create Warranty Addon (child table)"""
    print("\n[4/6] Creating Warranty Addon (child table)...")
    try:
        warranty_addon_data = {
            "custom": 1,
            "doctype": "DocType",
            "document_type": "", # FIXED: Cannot be "Table"
            "engine": "InnoDB",
            "field_order": [
                "custom_addon_name",
                "custom_addon_code",
                "custom_addon_status",
                "custom_addon_notes"
            ],
            "fields": [
                {
                    "fieldname": "custom_addon_name",
                    "fieldtype": "Data",
                    "label": "Add-on Name",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_addon_code",
                    "fieldtype": "Data",
                    "label": "Add-on Code"
                },
                {
                    "fieldname": "custom_addon_status",
                    "fieldtype": "Select",
                    "label": "Status",
                    "options": "Active\nExpired\nCancelled"
                },
                {
                    "fieldname": "custom_addon_notes",
                    "fieldtype": "Small Text",
                    "label": "Notes"
                }
            ],
            "is_submittable": 0,
            "istable": 1,
            "module": "Maintenance",
            "name": "Warranty Addon",
            "sort_field": "creation",
            "sort_order": "DESC"
        }
        
        if frappe.db.exists("DocType", "Warranty Addon"):
            print("     ✓ Warranty Addon already exists")
        else:
            doc = frappe.get_doc(warranty_addon_data)
            doc.insert(ignore_if_duplicate=True)
            frappe.db.commit()
            print("     ✓ Warranty Addon created!")
    
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        frappe.log_error(str(e), "Warranty Addon Import")
        return False
    
    return True


def create_warranty_rma_record():
    """Create Warranty RMA Record (child table)"""
    print("\n[5/6] Creating Warranty RMA Record (child table)...")
    try:
        warranty_rma_record_data = {
            "custom": 1,
            "doctype": "DocType",
            "document_type": "", # FIXED: Cannot be "Table"
            "engine": "InnoDB",
            "field_order": [
                "custom_rma_number",
                "custom_rma_date",
                "custom_item_affected",
                "custom_item_serial",
                "custom_rma_reason",
                "col_break_description",
                "custom_failure_description",
                "custom_replacement_item",
                "custom_replacement_serial",
                "col_break_return",
                "custom_return_date",
                "custom_rma_status",
                "custom_rma_notes"
            ],
            "fields": [
                {
                    "fieldname": "custom_rma_number",
                    "fieldtype": "Data",
                    "label": "RMA Number",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_rma_date",
                    "fieldtype": "Date",
                    "label": "RMA Date",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_item_affected",
                    "fieldtype": "Data",
                    "label": "Item/Component Affected",
                    "reqd": 1
                },
                {
                    "fieldname": "custom_item_serial",
                    "fieldtype": "Data",
                    "label": "Item Serial Number"
                },
                {
                    "fieldname": "custom_rma_reason",
                    "fieldtype": "Select",
                    "label": "RMA Reason",
                    "options": "Defect\nFailure\nUpgrade\nOther"
                },
                {
                    "fieldname": "col_break_description",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "custom_failure_description",
                    "fieldtype": "Small Text",
                    "label": "Failure Description"
                },
                {
                    "fieldname": "custom_replacement_item",
                    "fieldtype": "Data",
                    "label": "Replacement Item"
                },
                {
                    "fieldname": "custom_replacement_serial",
                    "fieldtype": "Data",
                    "label": "Replacement Serial"
                },
                {
                    "fieldname": "col_break_return",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "custom_return_date",
                    "fieldtype": "Date",
                    "label": "Return Date"
                },
                {
                    "fieldname": "custom_rma_status",
                    "fieldtype": "Select",
                    "label": "RMA Status",
                    "options": "Open\nIn Transit\nReceived\nClosed\nDisputed"
                },
                {
                    "fieldname": "custom_rma_notes",
                    "fieldtype": "Small Text",
                    "label": "Internal Notes"
                }
            ],
            "is_submittable": 0,
            "istable": 1,
            "module": "Maintenance",
            "name": "Warranty RMA Record",
            "sort_field": "creation",
            "sort_order": "DESC"
        }
        
        if frappe.db.exists("DocType", "Warranty RMA Record"):
            print("     ✓ Warranty RMA Record already exists")
        else:
            doc = frappe.get_doc(warranty_rma_record_data)
            doc.insert(ignore_if_duplicate=True)
            frappe.db.commit()
            print("     ✓ Warranty RMA Record created!")
    
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        frappe.log_error(str(e), "Warranty RMA Record Import")
        return False
    
    return True


if __name__ == "__main__":
    import_doctypes()