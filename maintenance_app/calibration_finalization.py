"""MI-scoped calibration finalization. No due-date updates, PDFs or emails here."""
import json
import math

import frappe
from frappe.utils import now_datetime

VALID_RESULTS = ('Pass', 'Fail', 'Pass After Adjustment')


def _active_records(mi):
    names = frappe.get_all(
        'Calibration Record',
        filters={'custom_mission_intervention': mi.name, 'custom_pwa_target_draft': 1},
        pluck='name', limit_page_length=1000,
    )
    active = []
    for name in names:
        record = frappe.get_doc('Calibration Record', name)
        if record.get('custom_calibration_status') == 'Cancelled' and record.docstatus == 0:
            continue
        active.append(record)
    return active


def _permission(mi, write=False):
    mi.check_permission('write' if write else 'read')
    if write and mi.docstatus != 0:
        frappe.throw('Only draft Mission Interventions can be edited')
    if mi.get('custom_intervention_type') != 'Calibration':
        frappe.throw('This intervention is not a Calibration')


@frappe.whitelist()
def set_calibration_overall_result(mi_name, record_name, result):
    mi = frappe.get_doc('Mission Intervention', mi_name)
    _permission(mi, write=True)
    if result not in VALID_RESULTS:
        frappe.throw('Choose Pass, Fail or Pass After Adjustment')
    names = {rec.name for rec in _active_records(mi)}
    if record_name not in names:
        frappe.throw('Calibration target does not belong to this intervention', frappe.PermissionError)
    record = frappe.get_doc('Calibration Record', record_name)
    if record.docstatus != 0:
        frappe.throw('This Calibration Record is already submitted')
    record.custom_overall_result = result
    if result == 'Pass After Adjustment':
        record.custom_adjustment_performed = 1
    record.save(ignore_permissions=True)
    return {'ok': True, 'record': record.name, 'result': result}


def _check_generic(record):
    from maintenance_app.calibration_generic_readings import _columns, _template
    columns = _columns(record, _template(record))
    rows = [r for r in (record.get('custom_calibration_readings') or [])
            if r.get('custom_generic_row')]
    if not rows:
        frappe.throw('Calibration ' + record.name + ': enter and save at least one measurement row')
    for i, row in enumerate(rows, 1):
        for col in columns:
            value = row.get(col['key'])
            text = '' if value is None else str(value).strip()
            if col.get('required') and not text:
                frappe.throw('Calibration ' + record.name + ', row ' + str(i)
                             + ': ' + col['label'] + ' is required')
            if text and col.get('type') == 'Number':
                try:
                    number = float(text)
                except (TypeError, ValueError):
                    frappe.throw('Calibration ' + record.name + ': invalid number in ' + col['label'])
                if not math.isfinite(number):
                    frappe.throw('Calibration ' + record.name + ': invalid finite number in ' + col['label'])


def _check_standard(record, template):
    from maintenance_app.calibration_workflow import _template_points
    points = _template_points(record.custom_calibration_template,
                              record.get('custom_equipment_component'))
    rows = [r for r in (record.get('custom_calibration_readings') or [])
            if not r.get('custom_generic_row')]
    by_name = {r.get('custom_test_point'): r for r in rows}
    if len(by_name) != len(rows):
        frappe.throw('Duplicate saved test points in ' + record.name)
    if not points:
        frappe.throw('Calibration ' + record.name + ': no standard tests configured')
    for p in points:
        r = by_name.get(p['name'])
        if p['required'] and (not r or
            (r.get('custom_before_reading') is None and r.get('custom_after_reading') is None)):
            frappe.throw('Calibration ' + record.name + ': required test missing: ' + p['name'])
        if r and r.get('custom_result') == 'Fail' and record.custom_overall_result == 'Pass':
            frappe.throw('Calibration ' + record.name + ': failed test cannot have overall Pass')
    if not rows:
        frappe.throw('Calibration ' + record.name + ': save the test readings first')


def _validate(record, mi):
    if record.docstatus != 0:
        frappe.throw('Calibration Record already submitted: ' + record.name)
    if record.get('custom_mission_intervention') != mi.name:
        frappe.throw('Calibration Record MI link mismatch: ' + record.name)
    if not mi.get('custom_asset') or record.get('custom_installed_equipment') != mi.get('custom_asset'):
        frappe.throw('Calibration Record equipment does not match MI: ' + record.name)
    if record.get('custom_overall_result') not in VALID_RESULTS:
        frappe.throw('Select overall Pass / Fail / Pass After Adjustment for ' + record.name)
    template_name = record.get('custom_calibration_template')
    if not template_name:
        frappe.throw('Calibration Template missing for ' + record.name)
    template = frappe.get_doc('Calibration Template', template_name)
    mode = template.get('custom_entry_format') or 'Standard Tests'
    layout = template.get('custom_reading_layout')
    if mode in ('Custom Table', 'Both'):
        if layout != 'Generic Mapped Readings':
            frappe.throw('Calibration ' + record.name
                         + ': automatic finalization currently requires Generic Mapped Readings; legacy tables are not supported')
        _check_generic(record)
    if mode in ('Standard Tests', 'Both'):
        _check_standard(record, template)
    if mode not in ('Custom Table', 'Both', 'Standard Tests'):
        frappe.throw('Unknown calibration entry format: ' + str(mode))


def finalize_for_intervention(mi):
    """Call only from active PWA submit handler, before mi.submit().

    Frappe owns the request transaction; do not commit here. A failure rolls back
    all Calibration Record submissions and the MI operation.
    """
    _permission(mi)
    records = _active_records(mi)
    if not records:
        frappe.throw('Select and save at least one Calibration target before submitting the MI')
    for record in records:
        _validate(record, mi)
    for record in records:
        record.custom_calibration_status = ('Failed' if record.custom_overall_result == 'Fail' else 'Completed')
        record.custom_completed_on = now_datetime()
        record.custom_technician = frappe.session.user
        record.save(ignore_permissions=True)
        record.submit()
    return [record.name for record in records]
