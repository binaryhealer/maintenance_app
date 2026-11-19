"""Template-driven generic calibration readings stored as Calibration Reading children.
This is DRAFT editing only; never finalizes results or updates calibration dates.
"""
import json
import math
import frappe

SLOTS = {
    'custom_target_label': 'Text',
    'custom_channel_id': 'Text',
    'custom_initial_counter': 'Number',
    'custom_final_counter': 'Number',
    'custom_reference_value': 'Number',
    'custom_before_a': 'Number',
    'custom_before_b': 'Number',
    'custom_after_a': 'Number',
    'custom_after_b': 'Number',
    'custom_reference_before': 'Text',
    'custom_reference_after': 'Text',
    'custom_generic_notes': 'Text',
 }
MAX_ROWS = 100


def _template(rec):
    return frappe.get_doc('Calibration Template', rec.custom_calibration_template)


def _mapping_from_template(template):
    result = []
    seen = set()
    for field in template.get('custom_field_mapping') or []:
        slot = field.get('custom_source_field')
        if slot not in SLOTS or slot in seen:
            frappe.throw('Invalid or duplicated calibration mapping field: ' + str(slot))
        seen.add(slot)
        label = (field.get('custom_display_label') or '').strip()
        if not label:
            frappe.throw('Display Label is required in Calibration Template mapping')
        kind = field.get('custom_value_type') or SLOTS[slot]
        if kind not in ('Text','Number'):
            frappe.throw('Unsupported mapped input type: ' + str(kind))
        result.append({
            'key':slot, 'label':label, 'type':kind,
            'unit':(field.get('custom_unit') or '').strip(),
            'required':bool(field.get('custom_required')),
            'help':field.get('custom_help') or '',
        })
    if not result:
        frappe.throw('Configure at least one row under Reading Field Mapping in Calibration Template')
    return result


def _columns(rec, template):
    snapshot = rec.get('custom_mapping_snapshot')
    if snapshot:
        try:
            columns = json.loads(snapshot)
        except (TypeError, ValueError):
            frappe.throw('Invalid saved Calibration field mapping snapshot')
        if not isinstance(columns,list) or not columns:
            frappe.throw('Invalid saved Calibration field mapping')
        return columns
    return _mapping_from_template(template)


def _rows(rec, columns):
    return [
        {column['key']: (row.get(column['key']) or '') for column in columns}
        for row in (rec.get('custom_calibration_readings') or [])
        if row.get('custom_generic_row')
    ]


def get_generic_table(rec):
    template = _template(rec)
    columns = _columns(rec, template)
    return {
        'enabled':True,
        'title':template.get('custom_table_title') or 'Calibration Measurements',
        'columns':columns, 'rows':_rows(rec, columns),
        'saved':bool(rec.get('custom_mapping_snapshot')),
        'storage':'Calibration Reading',
        'readonly':bool(rec.docstatus != 0 or rec.get('custom_calibration_status') in ('Completed','Failed','Cancelled')),
    }


def save_generic_table(rec, rows):
    if rec.docstatus != 0 or rec.get('custom_calibration_status') in ('Completed','Failed','Cancelled'):
        frappe.throw('Calibration Record is read-only')
    template = _template(rec)
    columns = _columns(rec, template)
    values = frappe.parse_json(rows) if isinstance(rows,str) else rows
    if not isinstance(values,list) or len(values)>MAX_ROWS:
        frappe.throw('Calibration table allows a maximum of 100 rows')
    allowed = {c['key'] for c in columns}
    clean = []
    for index, row in enumerate(values, start=1):
        if not isinstance(row,dict) or set(row)-allowed:
            frappe.throw('Unknown calibration column on row '+str(index))
        out = {'custom_generic_row':1, 'custom_test_point':'Mapped Test '+str(index), 'custom_result':'Not Tested'}
        for col in columns:
            value = row.get(col['key'], '')
            if isinstance(value,(list,dict,bool)):
                frappe.throw('Invalid measurement on row '+str(index))
            text = '' if value is None else str(value).strip()
            if len(text)>140:
                frappe.throw('Value is too long: '+col['label'])
            if col['type']=='Number' and text:
                try:
                    number = float(text)
                except ValueError:
                    frappe.throw('Number required for '+col['label']+' (row '+str(index)+')')
                if not math.isfinite(number):
                    frappe.throw('Finite number required for '+col['label'])
            out[col['key']] = text
        clean.append(out)
    # Preserve old standard readings; only replace rows belonging to generic form.
    original = [row.as_dict() for row in rec.get('custom_calibration_readings') or [] if not row.get('custom_generic_row')]
    rec.set('custom_calibration_readings',[])
    for row in original:
        # Avoid carrying child Document metadata/foreign parent IDs into new rows.
        cleaned = {k:v for k,v in row.items() if k not in (
            'name','doctype','parent','parenttype','parentfield','idx','docstatus','owner','creation','modified','modified_by'
        )}
        rec.append('custom_calibration_readings',cleaned)
    for row in clean:
        rec.append('custom_calibration_readings',row)
    if not rec.get('custom_mapping_snapshot'):
        rec.custom_mapping_snapshot = json.dumps(columns,ensure_ascii=False,separators=(',',':'))
    rec.custom_calibration_status = 'In Progress' if clean else 'Draft'
    rec.custom_overall_result = 'Not Completed'
    rec.save(ignore_permissions=True)  # caller checks MI write permissions and record ownership
    return {'ok':True,'message':'Saved '+str(len(clean))+' calibration row(s) in ERPNext.'}
