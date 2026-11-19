"""Install the legacy app-owned Custom Fields without mutating existing records.

These five fields already exist as ``Custom Field`` records on dev.local.
Keep them separate from DocType JSON until an explicit, data-safe metadata
conversion is planned. Fresh sites receive the fields automatically, while
existing sites retain their field records and data.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


MANIFEST = Path(__file__).with_name('owned_custom_fields.json')


def _read_manifest():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('owned_custom_fields.json must be an object keyed by DocType')
    seen = set()
    for dt, fields in data.items():
        if not isinstance(fields, list):
            raise ValueError(f'Expected an array of fields on {dt}')
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError(f'Invalid field definition on {dt}')
            name = field.get('fieldname')
            if not isinstance(name, str) or not name.startswith('custom_'):
                raise ValueError(f'Only custom_ fieldnames are managed here: {dt}.{name}')
            if not field.get('fieldtype') or not field.get('label'):
                raise ValueError(f'Missing fieldtype/label: {dt}.{name}')
            if (dt, name) in seen:
                raise ValueError(f'Duplicate field declaration: {dt}.{name}')
            seen.add((dt, name))
    if not seen:
        raise ValueError('App-owned Custom Field manifest is empty')
    return data


def _order_fields(dt, fields):
    remaining = list(fields)
    output = []
    while remaining:
        pending = {f['fieldname'] for f in remaining}
        ready = [f for f in remaining if f.get('insert_after') not in pending]
        if not ready:
            raise ValueError(f'Circular insert_after dependency for {dt}')
        output.extend(ready)
        picked = {f['fieldname'] for f in ready}
        remaining = [f for f in remaining if f['fieldname'] not in picked]
    return output


def _inventory():
    from maintenance_app.setup.install import _owned_doctypes

    registered = _read_manifest()
    owned = _owned_doctypes()
    planned = defaultdict(list)
    report = {
        'manifest_fields': sum(len(fs) for fs in registered.values()),
        'existing_custom_field': [],
        'provided_by_docfield': [],
        'missing_to_create': [],
        'mismatches': [],
        'unavailable_doctypes': [],
        'anchor_fallbacks': [],
    }
    for dt, fields in registered.items():
        if dt not in owned:
            raise ValueError(f'{dt} is not a canonical maintenance_app DocType; abort')
        if not frappe.db.exists('DocType', dt):
            report['unavailable_doctypes'].append(dt)
            continue
        ordered = _order_fields(dt, fields)
        manifest_names = {f['fieldname'] for f in ordered}
        meta = frappe.get_meta(dt)
        for field in ordered:
            key = f"{dt}.{field['fieldname']}"
            existing = frappe.db.get_value(
                'Custom Field', {'dt': dt, 'fieldname': field['fieldname']},
                ['fieldtype', 'options'], as_dict=True,
            )
            if existing:
                report['existing_custom_field'].append(key)
                actual = existing
            else:
                actual = meta.get_field(field['fieldname'])
                if actual:
                    report['provided_by_docfield'].append(key)
                else:
                    new_field = dict(field)
                    anchor = new_field.get('insert_after')
                    if anchor and anchor not in manifest_names and not meta.get_field(anchor):
                        # Layout fallback is for fresh installations with different
                        # base metadata; the exact fieldname and type are retained.
                        new_field['insert_after'] = 'append'
                        report['anchor_fallbacks'].append({
                            'field': key, 'original_anchor': anchor,
                        })
                    planned[dt].append(new_field)
                    report['missing_to_create'].append(key)
                    continue
            actual_type = actual.get('fieldtype') or ''
            actual_options = actual.get('options') or ''
            if actual_type != field['fieldtype'] or actual_options != (field.get('options') or ''):
                report['mismatches'].append({
                    'field': key,
                    'actual_type': actual_type, 'manifest_type': field['fieldtype'],
                    'actual_options': actual_options, 'manifest_options': field.get('options') or '',
                })
    return dict(planned), report


def verify_owned_custom_fields():
    """Read-only report; also safe to run before importing fixtures."""
    _, report = _inventory()
    print(json.dumps(report, indent=2, default=str))
    return report


def install_owned_custom_fields():
    """Create missing fields only; never overwrite/delete existing Custom Fields."""
    pending, report = _inventory()
    if report['unavailable_doctypes']:
        raise RuntimeError(f"Required GMAO DocTypes not installed: {report['unavailable_doctypes']}")
    if report['mismatches']:
        raise RuntimeError(f"Existing GMAO field definitions differ; review first: {report['mismatches']}")
    if pending:
        create_custom_fields(pending, update=False)
    print('maintenance_app owned Custom Fields:', len(report['missing_to_create']), 'new fields')
    return report
