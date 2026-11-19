# Copyright (c) 2026 and contributors
import frappe
from frappe.model.document import Document

class CalibrationTemplate(Document):
    def validate(self):
        fmt = self.get('custom_entry_format') or 'Standard Tests'
        if fmt not in ('Standard Tests', 'Custom Table', 'Both'):
            frappe.throw('Choose Standard Tests, Custom Table, or Both.')
        points = self.get('custom_test_points') or []
        columns = self.get('custom_table_columns') or []
        if fmt in ('Standard Tests', 'Both') and not points:
            frappe.throw('Add at least one calibration test point.')
        if fmt in ('Custom Table', 'Both') and not columns:
            frappe.throw('Add at least one table column.')
        if len(columns) > 24:
            frappe.throw('Maximum 24 calibration table columns.')
        seen = set()
        for col in columns:
            label = (col.get('custom_column_label') or '').strip()
            if not label:
                frappe.throw('Every table column needs a label.')
            key = label.casefold()
            if key in seen:
                frappe.throw('Duplicate table column: ' + label)
            seen.add(key)
            if col.get('custom_value_type') not in ('Text', 'Number'):
                frappe.throw('Select Text or Number for column ' + label)
        seen = set()
        for row in self.get("custom_test_points") or []:
            label = (row.get("custom_test_point") or "").strip()
            if not label:
                frappe.throw("Every calibration test point needs a name.")
            key = label.casefold()
            if key in seen:
                frappe.throw("Duplicate calibration test point: " + label)
            seen.add(key)
            mode = row.get("custom_evaluation_method") or "Absolute Tolerance"
            if mode == "Absolute Tolerance" and (row.get("custom_tolerance") or 0) < 0:
                frappe.throw("Tolerance must be zero or greater for " + label)
            if mode == "Range" and row.get("custom_min_value") is not None and row.get("custom_max_value") is not None:
                if row.custom_min_value > row.custom_max_value:
                    frappe.throw("Minimum must not exceed maximum for " + label)
        if (self.get("custom_calibration_interval_months") or 0) < 0:
            frappe.throw("Calibration interval cannot be negative.")
