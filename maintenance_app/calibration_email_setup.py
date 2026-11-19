"""Install small recipient history field for combined MI and Calibration Report emails."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_calibration_email_fields():
    if not frappe.get_meta('Calibration Report').has_field('custom_recipients'):
        create_custom_fields({
            'Calibration Report': [{
                'fieldname': 'custom_recipients',
                'label': 'Recipients',
                'fieldtype': 'Small Text',
                'read_only': 1,
                'description': 'To and CC email addresses for which a signed certificate was queued',
            }],
        }, update=True)
    frappe.clear_cache(doctype='Calibration Report')
    return 'READY'
