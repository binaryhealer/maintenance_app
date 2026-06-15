"""
Import Warranty DocTypes into Frappe

Usage:
  bench execute maintenance_app.import_doctypes

This script creates:
  1. Warranty License (child table)
  2. Warranty (main DocType)
"""

import frappe
import json
import os

def import_doctypes():
    """Import Warranty DocTypes from JSON files"""
    
    # Get the base path
    base_path = os.path.dirname(__file__)
    
    # JSON file paths (relative to maintenance_app root)
    warranty_license_path = os.path.join(base_path, "doctype", "warranty_license", "warranty_license.json")
    warranty_path = os.path.join(base_path, "doctype", "warranty", "warranty.json")
    
    print("\n" + "="*60)
    print("IMPORTING WARRANTY DOCTYPES")
    print("="*60)
    
    # Step 1: Create Warranty License (must be first - child table)
    print("\n[1/2] Creating Warranty License (child table)...")
    try:
        with open(warranty_license_path, 'r') as f:
            warranty_license_data = json.load(f)
        
        # Check if already exists
        if frappe.db.exists("DocType", "Warranty License"):
            print("     ✓ Warranty License already exists, skipping...")
        else:
            warranty_license_doc = frappe.get_doc(warranty_license_data)
            warranty_license_doc.insert(ignore_if_duplicate=True)
            frappe.db.commit()
            print("     ✓ Warranty License created successfully!")
    
    except FileNotFoundError:
        print(f"     ✗ File not found: {warranty_license_path}")
        print("     Note: Make sure JSON files are in the correct locations")
        return False
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        return False
    
    # Step 2: Create Warranty (main table)
    print("\n[2/2] Creating Warranty (main DocType)...")
    try:
        with open(warranty_path, 'r') as f:
            warranty_data = json.load(f)
        
        # Check if already exists
        if frappe.db.exists("DocType", "Warranty"):
            print("     ✓ Warranty already exists, skipping...")
        else:
            warranty_doc = frappe.get_doc(warranty_data)
            warranty_doc.insert(ignore_if_duplicate=True)
            frappe.db.commit()
            print("     ✓ Warranty created successfully!")
    
    except FileNotFoundError:
        print(f"     ✗ File not found: {warranty_path}")
        return False
    except Exception as e:
        print(f"     ✗ Error: {str(e)}")
        return False
    
    # Step 3: Run migration
    print("\n[3/3] Running migration...")
    try:
        frappe.reload_doc("maintenance", "doctype", "warranty_license")
        frappe.reload_doc("maintenance", "doctype", "warranty")
        print("     ✓ Migration completed!")
    except Exception as e:
        print(f"     ✗ Migration error: {str(e)}")
        return False
    
    print("\n" + "="*60)
    print("✓ ALL DOCTYPES IMPORTED SUCCESSFULLY!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Go to Maintenance module")
    print("  2. You should now see 'Warranty' DocType")
    print("  3. Create your first warranty record")
    print("\n")
    
    return True


if __name__ == "frappe.desk.background_jobs":
    import_doctypes()
