"""FDU structured readings stored on Calibration Record children.
No private JSON attachments are created by this module. Draft-only editing.
"""
import math
import frappe

# Numeric keys are compatible with the existing dynamically generated table UI.
COLUMNS = [
    ('1','Nozzle Number','Number','custom_nozzle_number'),
    ('2','Totaliser ID','Text','custom_totaliser_id'),
    ('3','Product','Text','custom_product'),
    ('4','Totaliser Before','Number','custom_totaliser_before'),
    ('5','Verification Slow','Number','custom_verification_slow'),
    ('6','Verification Fast','Number','custom_verification_fast'),
    ('7','Totaliser After','Number','custom_totaliser_after'),
    ('8','After Adjustment Slow','Number','custom_adjustment_slow'),
    ('9','After Adjustment Fast','Number','custom_adjustment_fast'),
    ('10','Original LMD Seal','Text','custom_lmd_seal'),
    ('11','New EMIMA Seal','Text','custom_emima_seal'),
]
NUMERIC={'1','4','5','6','7','8','9'}

def _topology(rec):
    try:
        from maintenance_app.fdu_calibration_layout import fdu_rows_for_equipment
    except ImportError:
        return []
    return fdu_rows_for_equipment(rec.custom_installed_equipment) or []

def _rows(rec):
    result=[]
    for item in rec.get('custom_fdu_readings') or []:
        row={}
        for key, label, typ, field in COLUMNS:
            value=item.get(field)
            row[key]='' if value is None else str(value)
        result.append(row)
    return result

def _draft_rows(rec):
    result=[]
    for item in _topology(rec):
        result.append({
            '1':str(item['number']), '2':item['totaliser'],
            '3':item['product'] or item['label'],
        })
    return result

def get_fdu_table(rec):
    rows=_rows(rec)
    if not rows:
        rows=_draft_rows(rec)
    return {
        'enabled':True,
        'title':'FDU Calibration Readings',
        'columns':[{'key':k,'label':label,'type':typ,'required':False} for k,label,typ,_ in COLUMNS],
        'rows':rows,
        'saved':bool(rec.get('custom_fdu_readings')),
        'readonly':bool(rec.docstatus != 0 or rec.get('custom_calibration_status') in ('Completed','Failed','Cancelled')),
        'storage':'DocType',
    }

def _value(value, key):
    if value is None or value=='':
        return None if key in NUMERIC else ''
    if isinstance(value,(dict,list,bool)):
        frappe.throw('Invalid value in FDU reading')
    raw=str(value).strip()
    if len(raw)>500:
        frappe.throw('FDU value exceeds 500 characters')
    if key in NUMERIC:
        try: number=float(raw)
        except ValueError: frappe.throw('Invalid number for '+next(label for k,label,_,_ in COLUMNS if k==key))
        if not math.isfinite(number): frappe.throw('FDU numbers must be finite')
        if key=='1':
            if not number.is_integer() or number<1:
                frappe.throw('Nozzle Number must be a positive whole number')
            return int(number)
        return number
    return raw

def save_fdu_table(rec, rows):
    if rec.docstatus != 0 or rec.get('custom_calibration_status') in ('Completed','Failed','Cancelled'):
        frappe.throw('Calibration Record is read-only')
    data=frappe.parse_json(rows) if isinstance(rows,str) else rows
    if not isinstance(data,list) or len(data)>100:
        frappe.throw('FDU table must have 0 to 100 rows')
    field_map={key:field for key,_,_,field in COLUMNS}
    topology=_topology(rec)
    topo_by_number={int(t['number']):t for t in topology}
    seen=set(); clean=[]
    for row in data:
        if not isinstance(row,dict) or set(row)-set(field_map):
            frappe.throw('Unknown FDU table field')
        values={field_map[k]:_value(row.get(k),k) for k in field_map}
        number=values['custom_nozzle_number']
        if number is None: frappe.throw('Enter the Nozzle Number on every row')
        if number in seen: frappe.throw('Duplicate Nozzle Number: '+str(number))
        seen.add(number)
        if number in topo_by_number:
            configured=topo_by_number[number]
            if values['custom_totaliser_id'] != configured['totaliser']:
                frappe.throw('Totaliser ID does not match nozzle '+str(number)+' equipment configuration')
            values['custom_nozzle_component']=configured['component']
        elif topo_by_number:
            frappe.throw('Nozzle '+str(number)+' is not configured on this FDU')
        if not values['custom_totaliser_id']:
            frappe.throw('Totaliser ID is required for nozzle '+str(number))
        clean.append(values)
    rec.set('custom_fdu_readings',[])
    for row in clean:
        rec.append('custom_fdu_readings',row)
    rec.custom_calibration_status='In Progress' if clean else 'Draft'
    rec.custom_overall_result='Not Completed'
    rec.save(ignore_permissions=True)  # MI write permission and ownership checked in caller
    return {'ok':True,'message':f'FDU readings saved to ERPNext ({len(clean)} nozzle rows).'}
