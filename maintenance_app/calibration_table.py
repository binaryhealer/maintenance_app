"""Private structured custom-table data for individual draft Calibration Records.
Does not alter Calibration Record or Calibration Reading schemas or update calibration dates.
"""
import json
import math

import frappe
from frappe.utils.file_manager import get_file, save_file
from maintenance_app.calibration_pwa import _mi, _get_pwa_records

FILE_NAME = 'gmao-calibration-table.json'


def _owned_record(mi_name, record_name, write=False):
    mi = _mi(mi_name, write=write)
    allowed = {r.name for r in _get_pwa_records(mi)}
    if record_name not in allowed:
        frappe.throw('Calibration record is not linked to this intervention', frappe.PermissionError)
    rec = frappe.get_doc('Calibration Record', record_name)
    if rec.get('custom_mission_intervention') != mi.name or not rec.get('custom_pwa_target_draft'):
        frappe.throw('Calibration record not editable from this intervention', frappe.PermissionError)
    if write and (rec.docstatus != 0 or rec.get('custom_calibration_status') in ('Completed', 'Failed', 'Cancelled')):
        frappe.throw('Calibration record is read-only')
    return rec


def _columns(template):
    result=[]
    for col in template.get('custom_table_columns') or []:
        label=(col.get('custom_column_label') or '').strip()
        result.append({'key':str(col.idx), 'label':label,
                       'type':col.get('custom_value_type') or 'Text',
                       'required':bool(col.get('custom_required'))})
    return result


def _file(rec):
    import re
    names = frappe.get_all(
        'File',
        filters={
            'attached_to_doctype': 'Calibration Record',
            'attached_to_name': rec.name,
            'is_private': 1,
        },
        fields=['name', 'file_name', 'file_url', 'creation'],
        order_by='creation desc, name desc',
        limit_page_length=0,
    )
    pattern = re.compile(r'^gmao-calibration-table[a-f0-9]*\\.json$')
    matches = [f for f in names if pattern.fullmatch(f.file_name or '')]
    return matches[0] if matches else None


def _read_json(rec):
    f=_file(rec)
    if not f: return None
    _, data=get_file(f.file_url)
    try:
        output=json.loads(data.decode('utf-8') if isinstance(data,bytes) else data)
    except (UnicodeError,ValueError,TypeError):
        frappe.throw('Saved calibration table attachment is invalid')
    if not isinstance(output,dict) or output.get('version')!=1:
        frappe.throw('Unknown calibration table format')
    return output


@frappe.whitelist()
def get_calibration_table(mi_name, record_name):
    rec=_owned_record(mi_name, record_name)
    if frappe.db.get_value('Calibration Template', rec.custom_calibration_template, 'custom_reading_layout') == 'Generic Mapped Readings':
        from maintenance_app.calibration_generic_readings import get_generic_table
        return get_generic_table(rec)
    if frappe.db.get_value('Calibration Template', rec.custom_calibration_template, 'custom_reading_layout') == 'FDU Readings':
        from maintenance_app.fdu_calibration_readings import get_fdu_table
        return get_fdu_table(rec)
    template=frappe.get_doc('Calibration Template',rec.custom_calibration_template)
    mode=template.get('custom_entry_format') or 'Standard Tests'
    if mode not in ('Custom Table','Both'):
        return {'enabled':False}
    saved=_read_json(rec)
    return {
        'enabled':True, 'title':template.get('custom_table_title') or 'Calibration Table',
        'columns':saved.get('columns') if saved else _columns(template),
        'rows':saved.get('rows') if saved else [],
        'saved':bool(saved),
        'readonly':bool(rec.docstatus or rec.get('custom_calibration_status') in ('Completed','Failed','Cancelled')),
    }


@frappe.whitelist()
def save_calibration_table(mi_name, record_name, rows):
    rec=_owned_record(mi_name, record_name,write=True)
    if frappe.db.get_value('Calibration Template', rec.custom_calibration_template, 'custom_reading_layout') == 'Generic Mapped Readings':
        from maintenance_app.calibration_generic_readings import save_generic_table
        return save_generic_table(rec, rows)
    if frappe.db.get_value('Calibration Template', rec.custom_calibration_template, 'custom_reading_layout') == 'FDU Readings':
        from maintenance_app.fdu_calibration_readings import save_fdu_table
        return save_fdu_table(rec, rows)
    template=frappe.get_doc('Calibration Template',rec.custom_calibration_template)
    if (template.get('custom_entry_format') or 'Standard Tests') not in ('Custom Table','Both'):
        frappe.throw('Template does not contain a calibration table')
    previous=_read_json(rec)
    columns=previous['columns'] if previous else _columns(template)
    values=frappe.parse_json(rows) if isinstance(rows,str) else rows
    if not isinstance(values,list) or len(values)>100:
        frappe.throw('Calibration table must contain at most 100 rows')
    keys={str(c['key']) for c in columns}
    clean=[]
    for row in values:
        if not isinstance(row,dict) or set(row)-keys:
            frappe.throw('Unknown calibration table column')
        entry={}
        for col in columns:
            key=str(col['key']); raw=row.get(key,'')
            if raw is None: raw=''
            if isinstance(raw,(dict,list,bool)):
                frappe.throw('Invalid calibration table value')
            value=str(raw).strip()
            if len(value)>500:
                frappe.throw('Calibration table value is too long')
            if col['type']=='Number' and value:
                try: n=float(value)
                except ValueError: frappe.throw('Number required for '+col['label'])
                if not math.isfinite(n): frappe.throw('Finite number required for '+col['label'])
            entry[key]=value
        # Allow draft, partially completed rows. Final validation comes later.
        clean.append(entry)
    payload={'version':1,'template':rec.custom_calibration_template,'columns':columns,'rows':clean}
    content=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(content)>150000:
        frappe.throw('Calibration table exceeds storage limit')
    # Preserve previous data until the new attachment is safely saved.
    save_file(FILE_NAME,content,'Calibration Record',rec.name,is_private=1)
    if rec.get('custom_calibration_status')=='Draft' and clean:
        rec.custom_calibration_status='In Progress'
        rec.custom_overall_result='Not Completed'
        rec.save(ignore_permissions=True)
    return {'ok':True,'message':'Calibration table draft saved ('+str(len(clean))+' rows).'}


@frappe.whitelist()
def save_calibration_table_with_result(mi_name, record_name, rows, result):
    """Atomically save generic measurement rows and the explicit overall result.

    The existing draft/MI ownership checks remain in _owned_record.
    A validation failure prevents a successful save/submit response.
    """
    if result not in ('Pass', 'Fail', 'Pass After Adjustment'):
        frappe.throw('Please select Overall Calibration Result.')
    rec = _owned_record(mi_name, record_name, write=True)
    if frappe.db.get_value('Calibration Template', rec.custom_calibration_template,
                           'custom_reading_layout') != 'Generic Mapped Readings':
        frappe.throw('Combined save is available for Generic Mapped Readings only')
    from maintenance_app.calibration_generic_readings import save_generic_table
    from maintenance_app.calibration_finalization import _check_generic
    # The generic helper handles mapping snapshots, row limits, numerical validation
    # and the existing Calibration Reading child rows.
    save_generic_table(rec, rows)
    rec.reload()
    _check_generic(rec)  # At least one row, required fields, and numbers.
    rec.custom_overall_result = result
    rec.custom_adjustment_performed = 1 if result == 'Pass After Adjustment' else 0
    rec.save(ignore_permissions=True)
    return {'ok': True, 'record': rec.name, 'result': result,
            'message': 'Calibration measurements and result saved.'}
