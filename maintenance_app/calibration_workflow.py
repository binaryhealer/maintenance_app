"""Guided Calibration workspace, draft measurements only.

Built on Stage 2's assigned-equipment and template filters. Never marks records
completed and never updates equipment or component calibration dates.
"""
import json
import math

import frappe
from frappe.utils import flt

from maintenance_app.calibration_pwa import (
    _mi, get_calibration_targets, _get_pwa_records,
    _previous_calibration_results,
)


def _required_flag(doc):
    return bool(frappe.utils.cint(doc.get('custom_requires_calibration')))


def _template_points(template_name, component=None):
    template = frappe.get_doc('Calibration Template', template_name)
    comp_type = None
    if component:
        comp_type = frappe.db.get_value('Equipment Component', component, 'custom_equipment_type')
    points = []
    for r in template.get('custom_test_points') or []:
        point_type = r.get('custom_component_type')
        if component and point_type and point_type != comp_type:
            continue
        if not component and point_type:
            continue
        points.append({
            'name': r.get('custom_test_point'),
            'instructions': r.get('custom_instructions') or '',
            'method': r.get('custom_evaluation_method') or 'Record Only',
            'expected': r.get('custom_expected_value'),
            'tolerance': r.get('custom_tolerance'),
            'minimum': r.get('custom_min_value'),
            'maximum': r.get('custom_max_value'),
            'unit': r.get('custom_unit') or '',
            'required': bool(r.get('custom_required')),
        })
    return points


@frappe.whitelist()
def get_calibration_workspace(mi_name):
    data = get_calibration_targets(mi_name)  # Enforces MI read permission.
    # GMAO_PARTIAL_CAL_CONTINUE_V1: derived from submitted records, never stored UI state.
    mi = _mi(mi_name)
    data['previous_calibrations'] = _previous_calibration_results(mi)
    for eq in data['equipment']:
        eq_doc = frappe.get_doc('Installed Equipment', eq['name'])
        eq['requires_calibration'] = bool(frappe.utils.cint(eq_doc.get('custom_calibration_required')))
        eq['default_template'] = eq_doc.get('custom_calibration_template') or ''
        for comp in eq['components']:
            comp_doc = frappe.get_doc('Equipment Component', comp['name'])
            comp['requires_calibration'] = _required_flag(comp_doc)
            comp['type'] = comp_doc.get('custom_equipment_type') or ''
    for r in data['records']:
        rec = frappe.get_doc('Calibration Record', r['name'])
        r['status'] = rec.get('custom_calibration_status')
        r['overall_result'] = rec.get('custom_overall_result') or 'Not Completed'
        r['readings'] = [
            {'name':x.get('custom_test_point'),
             'before':x.get('custom_before_reading'),
             'after':x.get('custom_after_reading'),
             'remarks':x.get('custom_remarks') or '',
             'result':x.get('custom_result') or 'Not Tested'}
            for x in (rec.get('custom_calibration_readings') or [])
        ]
        r['points'] = _template_points(r['template'], r.get('component') or None) if r['template'] else []
    return data


def _number(raw, title):
    if raw is None or raw == '':
        return None
    if isinstance(raw, bool):
        frappe.throw('Invalid numeric reading for ' + title)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        frappe.throw('Invalid numeric reading for ' + title)
    if not math.isfinite(value):
        frappe.throw('Reading must be finite for ' + title)
    return value


def _conforms(point, reading):
    if reading is None:
        return None
    mode = point['method']
    if mode == 'Record Only':
        return None
    if mode == 'Range':
        lo, hi = point['minimum'], point['maximum']
        if lo is None or hi is None:
            frappe.throw('Range limits missing from template test: ' + point['name'])
        return flt(lo) <= reading <= flt(hi)
    if mode == 'Absolute Tolerance':
        expected, tol = point['expected'], point['tolerance']
        if expected is None or tol is None or flt(tol) < 0:
            frappe.throw('Expected value/tolerance missing or invalid for: ' + point['name'])
        return abs(reading - flt(expected)) <= flt(tol) + 1e-9
    frappe.throw('Unsupported evaluation method for: ' + point['name'])


@frappe.whitelist()
def save_calibration_readings(mi_name, record_name, readings):
    mi = _mi(mi_name, write=True)
    if not record_name:
        frappe.throw('Calibration Record is required')
    record = frappe.get_doc('Calibration Record', record_name)
    if not record.get('custom_pwa_target_draft') or record.get('custom_mission_intervention') != mi.name:
        frappe.throw('Calibration Record is not an editable target of this intervention', frappe.PermissionError)
    if record.docstatus != 0 or record.get('custom_calibration_status') in ('Completed','Failed','Cancelled'):
        frappe.throw('Calibration Record is no longer editable')
    allowed = {r.name for r in _get_pwa_records(mi)}
    if record.name not in allowed:
        frappe.throw('Calibration target not found for this intervention', frappe.PermissionError)
    if not record.get('custom_calibration_template'):
        frappe.throw('Please select a calibration template first')
    rows = frappe.parse_json(readings) if isinstance(readings, str) else readings
    if not isinstance(rows, list) or len(rows) > 150:
        frappe.throw('Invalid calibration readings')
    points = _template_points(record.custom_calibration_template, record.get('custom_equipment_component'))
    names = [p['name'] for p in points]
    if len(names) != len(set(names)):
        frappe.throw('Duplicate test point names in calibration template')
    submitted = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('name') not in names:
            frappe.throw('Unknown calibration test point')
        if row['name'] in submitted:
            frappe.throw('Duplicate calibration test point')
        submitted[row['name']] = row
    record.set('custom_calibration_readings', [])
    count = 0
    for point in points:
        value = submitted.get(point['name'], {})
        before = _number(value.get('before'), point['name'])
        after = _number(value.get('after'), point['name'])
        reading = after if after is not None else before
        before_pass = _conforms(point, before)
        after_pass = _conforms(point, after)
        result_pass = _conforms(point, reading)
        if reading is None or point['method'] == 'Record Only':
            result = 'Not Tested'
        elif result_pass:
            result = 'Adjusted' if before_pass is False and after_pass is True else 'Pass'
        else:
            result = 'Fail'
        expected = point['expected']
        record.append('custom_calibration_readings', {
            'custom_test_point': point['name'],
            'custom_expected_value': expected,
            'custom_before_reading': before,
            'custom_after_reading': after,
            'custom_tolerance': point['tolerance'],
            'custom_unit': point['unit'],
            'custom_error_before': (before - flt(expected)) if before is not None and expected is not None else None,
            'error_after': (after - flt(expected)) if after is not None and expected is not None else None,
            'custom_result': result,
            'custom_remarks': (value.get('remarks') or '')[:1000],
        })
        if reading is not None:
            count += 1
    record.custom_calibration_status = 'In Progress' if count else 'Draft'
    record.custom_overall_result = 'Not Completed'
    record.save(ignore_permissions=True)  # MI permission + record ownership validated above.
    return {'ok': True, 'record': record.name,
            'message': 'Draft readings saved (' + str(count) + '/' + str(len(points)) + ' entered).'}


# GMAO_CAL_FINISH_READINGS_GATE_V1
@frappe.whitelist()
def check_calibration_finish_ready(mi_name):
    """Read-only preflight; identical record checks to MI submission.

    This is a UX gate on Finish Work. Actual MI submission continues to enforce
    finalize_for_intervention() server-side, so a crafted URL cannot submit
    missing calibration readings.
    """
    from maintenance_app.calibration_finalization import (
        _active_records, _validate,
    )
    mi = _mi(mi_name)  # MI read permission and ownership handled by existing helper
    if mi.get('custom_intervention_type') != 'Calibration':
        frappe.throw('This intervention is not a Calibration')
    records = _active_records(mi)
    if not records:
        frappe.throw('Select and save at least one calibration target before Finish Work.')
    for rec in records:
        _validate(rec, mi)
    return {'ok': True, 'count': len(records),
            'message': 'All selected calibration targets have saved readings and results.'}
