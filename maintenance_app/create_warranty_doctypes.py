"""
Create all Warranty DocTypes for Maintenance App
- Warranty License (child table)
- Warranty Coverage Items (child table)
- Warranty Add-ons (child table)
- Warranty RMA Records (child table)
- Warranty (main table)

Usage: bench execute maintenance_app.create_warranty_doctypes.create_all_doctypes
"""

import frappe

def create_all_doctypes():
    """Create all warranty-related DocTypes"""
    
    print("\n" + "="*70)
    print("CREATING WARRANTY DOCTYPES - MAINTENANCE APP")
    print("="*70)
    
    # ============================================================
    # CHILD TABLE 1: Warranty License
    # ============================================================
    print("\n[1/5] Creating Warranty License (child table)...")
    try:
        if frappe.db.exists("DocType", "Warranty License"):
            frappe.delete_doc("DocType", "Warranty License")
            print("     (Deleted existing)")
        
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Warranty License",
            "module": "Maintenance",
            "custom": 1,
            "istable": 1,
            "document_type": "Table",
            "engine": "InnoDB",
            "fields": [
                {"fieldname": "custom_item_type", "fieldtype": "Select", "label": "Item Type", "options": "Software License\nSupport Contract\nExtended Warranty\nOther", "reqd": 1},
                {"fieldname": "custom_item_name", "fieldtype": "Data", "label": "Item Name", "reqd": 1},
                {"fieldname": "custom_license_key", "fieldtype": "Data", "label": "License Key"},
                {"fieldname": "col_break_dates", "fieldtype": "Column Break"},
                {"fieldname": "custom_license_start_date", "fieldtype": "Date", "label": "License Start Date", "reqd": 1},
                {"fieldname": "custom_license_period_years", "fieldtype": "Int", "label": "License Period (Years)"},
                {"fieldname": "custom_license_end_date", "fieldtype": "Date", "label": "License End Date", "read_only": 1},
                {"fieldname": "custom_license_notes", "fieldtype": "Small Text", "label": "Notes"},
            ],
            "is_submittable": 0,
            "sort_field": "creation",
            "sort_order": "DESC"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("     ✓ Warranty License created!")
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        return False
    
    # ============================================================
    # CHILD TABLE 2: Warranty Coverage Items
    # ============================================================
    print("\n[2/5] Creating Warranty Coverage Items (child table)...")
    try:
        if frappe.db.exists("DocType", "Warranty Coverage Item"):
            frappe.delete_doc("DocType", "Warranty Coverage Item")
            print("     (Deleted existing)")
        
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Warranty Coverage Item",
            "module": "Maintenance",
            "custom": 1,
            "istable": 1,
            "document_type": "Table",
            "engine": "InnoDB",
            "fields": [
                {"fieldname": "custom_item_code", "fieldtype": "Data", "label": "Item Code", "reqd": 1},
                {"fieldname": "custom_coverage_type", "fieldtype": "Select", "label": "Coverage Type", "options": "Parts\nLabour\nTransport\nPreventive\nRemote Support", "reqd": 1},
                {"fieldname": "custom_item_name", "fieldtype": "Data", "label": "Item Name"},
                {"fieldname": "custom_quantity_limit", "fieldtype": "Data", "label": "Quantity/Limit"},
                {"fieldname": "custom_remarks", "fieldtype": "Small Text", "label": "Remarks"},
            ],
            "is_submittable": 0,
            "sort_field": "creation",
            "sort_order": "DESC"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("     ✓ Warranty Coverage Items created!")
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        return False
    
    # ============================================================
    # CHILD TABLE 3: Warranty Add-ons
    # ============================================================
    print("\n[3/5] Creating Warranty Add-ons (child table)...")
    try:
        if frappe.db.exists("DocType", "Warranty Addon"):
            frappe.delete_doc("DocType", "Warranty Addon")
            print("     (Deleted existing)")
        
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Warranty Addon",
            "module": "Maintenance",
            "custom": 1,
            "istable": 1,
            "document_type": "Table",
            "engine": "InnoDB",
            "fields": [
                {"fieldname": "custom_addon_name", "fieldtype": "Data", "label": "Add-on Name", "reqd": 1},
                {"fieldname": "custom_addon_code", "fieldtype": "Data", "label": "Add-on Code"},
                {"fieldname": "custom_addon_status", "fieldtype": "Select", "label": "Status", "options": "Active\nExpired\nCancelled"},
                {"fieldname": "custom_addon_notes", "fieldtype": "Small Text", "label": "Notes"},
            ],
            "is_submittable": 0,
            "sort_field": "creation",
            "sort_order": "DESC"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("     ✓ Warranty Add-ons created!")
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        return False
    
    # ============================================================
    # CHILD TABLE 4: Warranty RMA Records
    # ============================================================
    print("\n[4/5] Creating Warranty RMA Records (child table)...")
    try:
        if frappe.db.exists("DocType", "Warranty RMA Record"):
            frappe.delete_doc("DocType", "Warranty RMA Record")
            print("     (Deleted existing)")
        
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Warranty RMA Record",
            "module": "Maintenance",
            "custom": 1,
            "istable": 1,
            "document_type": "Table",
            "engine": "InnoDB",
            "fields": [
                {"fieldname": "custom_rma_number", "fieldtype": "Data", "label": "RMA Number", "reqd": 1},
                {"fieldname": "custom_rma_date", "fieldtype": "Date", "label": "RMA Date", "reqd": 1},
                {"fieldname": "custom_item_affected", "fieldtype": "Data", "label": "Item/Component Affected", "reqd": 1},
                {"fieldname": "custom_item_serial", "fieldtype": "Data", "label": "Item Serial Number"},
                {"fieldname": "custom_rma_reason", "fieldtype": "Select", "label": "RMA Reason", "options": "Defect\nFailure\nUpgrade\nOther"},
                {"fieldname": "col_break_description", "fieldtype": "Column Break"},
                {"fieldname": "custom_failure_description", "fieldtype": "Small Text", "label": "Failure Description"},
                {"fieldname": "custom_replacement_item", "fieldtype": "Data", "label": "Replacement Item"},
                {"fieldname": "custom_replacement_serial", "fieldtype": "Data", "label": "Replacement Serial"},
                {"fieldname": "col_break_return", "fieldtype": "Column Break"},
                {"fieldname": "custom_return_date", "fieldtype": "Date", "label": "Return Date"},
                {"fieldname": "custom_rma_status", "fieldtype": "Select", "label": "RMA Status", "options": "Open\nIn Transit\nReceived\nClosed\nDisputed"},
                {"fieldname": "custom_rma_notes", "fieldtype": "Small Text", "label": "Internal Notes"},
            ],
            "is_submittable": 0,
            "sort_field": "creation",
            "sort_order": "DESC"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("     ✓ Warranty RMA Records created!")
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        return False
    
    # ============================================================
    # MAIN TABLE: Warranty
    # ============================================================
    print("\n[5/5] Creating Warranty (main DocType)...")
    try:
        if frappe.db.exists("DocType", "Warranty"):
            frappe.delete_doc("DocType", "Warranty")
            print("     (Deleted existing)")
        
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Warranty",
            "module": "Maintenance",
            "custom": 1,
            "document_type": "Document",
            "engine": "InnoDB",
            "autoname": "format:W-{MM}-{DD}-{######}",
            "title_field": "custom_warranty_title",
            "quick_entry": 1,
            "allow_import": 1,
            "allow_rename": 1,
            "editable_grid": 1,
            "track_changes": 1,
            "fields": [
                # ====== DETAILS SECTION ======
                {"fieldname": "warranty_details_section", "fieldtype": "Section Break", "label": "Warranty Details"},
                {"fieldname": "custom_warranty_title", "fieldtype": "Data", "label": "Warranty Title", "reqd": 1},
                {"fieldname": "custom_customer", "fieldtype": "Link", "label": "Customer", "options": "Customer", "reqd": 1},
                {"fieldname": "custom_installed_equipment", "fieldtype": "Link", "label": "Installed Equipment", "options": "Installed Equipment", "reqd": 1},
                {"fieldname": "custom_branch", "fieldtype": "Link", "label": "Branch", "options": "Client Branch"},
                {"fieldname": "col_break_dates", "fieldtype": "Column Break"},
                {"fieldname": "custom_warranty_start_date", "fieldtype": "Date", "label": "Warranty Start Date", "reqd": 1},
                {"fieldname": "custom_warranty_period_years", "fieldtype": "Int", "label": "Warranty Period (Years)", "reqd": 1, "default": 1},
                {"fieldname": "custom_warranty_end_date", "fieldtype": "Date", "label": "Warranty End Date", "read_only": 1},
                {"fieldname": "custom_warranty_status", "fieldtype": "Select", "label": "Status", "options": "Active\nExpired\nRMA Pending\nReplaced", "default": "Active", "reqd": 1},
                {"fieldname": "col_break_source", "fieldtype": "Column Break"},
                {"fieldname": "custom_source", "fieldtype": "Select", "label": "Source", "options": "Delivery Note\nManual Entry\nPurchased Separately"},
                {"fieldname": "custom_source_doctype", "fieldtype": "Link", "label": "Source Document", "options": "Delivery Note"},
                
                # ====== COVERAGE ITEMS TAB ======
                {"fieldname": "coverage_items_tab", "fieldtype": "Tab Break", "label": "Coverage Items"},
                {"fieldname": "custom_warranty_coverage_items", "fieldtype": "Table", "label": "Coverage Items", "options": "Warranty Coverage Item"},
                
                # ====== ADD-ONS TAB ======
                {"fieldname": "addons_tab", "fieldtype": "Tab Break", "label": "Add-ons"},
                {"fieldname": "custom_warranty_addons", "fieldtype": "Table", "label": "Add-ons", "options": "Warranty Addon"},
                
                # ====== LICENSE SUB-ITEMS TAB ======
                {"fieldname": "warranty_licenses_tab", "fieldtype": "Tab Break", "label": "License Sub-Items"},
                {"fieldname": "custom_warranty_licenses", "fieldtype": "Table", "label": "Warranty Licenses", "options": "Warranty License"},
                
                # ====== RMA TRACKING TAB ======
                {"fieldname": "rma_tracking_tab", "fieldtype": "Tab Break", "label": "RMA Tracking"},
                {"fieldname": "custom_warranty_rma_records", "fieldtype": "Table", "label": "RMA Records", "options": "Warranty RMA Record"},
                
                # ====== INTERNAL TAB ======
                {"fieldname": "internal_tab", "fieldtype": "Tab Break", "label": "Internal"},
                {"fieldname": "custom_internal_notes", "fieldtype": "Small Text", "label": "Internal Notes"},
                {"fieldname": "custom_created_from_delivery_note", "fieldtype": "Data", "label": "Created From Delivery Note", "read_only": 1},
            ],
            "is_submittable": 0,
            "permissions": [
                {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
                {"role": "Maintenance Manager", "read": 1, "write": 1, "create": 1, "delete": 0},
            ],
            "search_fields": "custom_customer,custom_installed_equipment,custom_warranty_status",
            "sort_field": "creation",
            "sort_order": "DESC"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("     ✓ Warranty created!")
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        return False
    
    print("\n" + "="*70)
    print("✓ SUCCESS - All 5 Warranty DocTypes created!")
    print("="*70)
    print("\nDocTypes created:")
    print("  1. Warranty License (child table)")
    print("  2. Warranty Coverage Item (child table)")
    print("  3. Warranty Addon (child table)")
    print("  4. Warranty RMA Record (child table)")
    print("  5. Warranty (main table)")
    print("\nNext steps:")
    print("  1. bench --site dev.local clear-cache")
    print("  2. Go to Maintenance module → Warranty")
    print("  3. Create your first warranty\n")
    
    return True

if __name__ == "__main__":
    create_all_doctypes()
