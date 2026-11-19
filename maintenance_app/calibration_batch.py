"""Consolidated signed Calibration Reports. One report per technician-selected batch of MIs.

This module does not close MIs, TMs or STs, and does not update calibration dates.
"""
import base64
import hashlib
import json
import re

import frappe
from frappe.utils import now_datetime
from frappe.utils.file_manager import save_file

REPORT = 'Calibration Report'


def _link(doc, dt):
    vals = [doc.get(f.fieldname) for f in doc.meta.fields
            if f.fieldtype == 'Link' and f.options == dt and doc.get(f.fieldname)]
    vals = list(dict.fromkeys(vals))
    if len(vals) != 1:
        frappe.throw('Expected exactly one ' + dt + ' for intervention ' + doc.name)
    return vals[0]


def _equipment(mi):
    candidates = []
    if mi.meta.has_field('custom_asset') and mi.get('custom_asset'):
        candidates.append(mi.custom_asset)
    for f in mi.meta.fields:
        if f.fieldtype == 'Link' and f.options == 'Installed Equipment' and mi.get(f.fieldname):
            candidates.append(mi.get(f.fieldname))
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) != 1 or not frappe.db.exists('Installed Equipment', candidates[0]):
        frappe.throw('Each Calibration MI must identify exactly one main Installed Equipment: ' + mi.name)
    return candidates[0]


def _context(mi):
    return {'st': _link(mi, 'Service Ticket'), 'tm': _link(mi, 'Tech Mission'), 'equipment': _equipment(mi)}


def _read_mi(mi_name):
    mi = frappe.get_doc('Mission Intervention', mi_name)
    mi.check_permission('read')
    if mi.get('custom_intervention_type') != 'Calibration':
        frappe.throw('Only Calibration interventions can join a Calibration Report')
    return mi


def _require_current_user_is_technician(mi):
    # Use existing MI permissions and tech assignment controls; do not grant blanket report access.
    mi.check_permission('write')


def _active_member(mi_name):
    # Submitted reports and open reports both reserve a MI; cancelled reports do not.
    rows = frappe.db.sql('''
        SELECT parent FROM `tabCalibration Report Intervention`
        WHERE custom_mission_intervention=%s AND parenttype='Calibration Report'
        AND parentfield='custom_interventions'
    ''', (mi_name,), as_dict=True)
    for row in rows:
        status = frappe.db.get_value(REPORT, row.parent, 'docstatus')
        if status in (0, 1):
            return row.parent
    return None


def _report(name, write=False):
    doc = frappe.get_doc(REPORT, name)
    origin = _read_mi(doc.custom_origin_mi)
    ctx = _context(origin)
    if ctx['st'] != doc.custom_service_ticket or ctx['tm'] != doc.custom_tech_mission:
        frappe.throw('Calibration Report scope has changed')
    if write:
        _require_current_user_is_technician(origin)
    return doc


def _mi_records(mi_name):
    return frappe.get_all('Calibration Record',
                          filters={'custom_mission_intervention':mi_name},
                          fields=['name', 'docstatus', 'custom_calibration_status',
                                  'custom_overall_result', 'custom_installed_equipment',
                                  'custom_equipment_component'],
                          limit_page_length=1000, order_by='name asc')


def _check_complete(mi):
    if mi.docstatus != 1:
        frappe.throw('Submit the intervention before including it: ' + mi.name)
    records = [r for r in _mi_records(mi.name)
               if not (r.custom_calibration_status == 'Cancelled' and r.docstatus == 0)]
    if not records:
        frappe.throw('No calibration results found for ' + mi.name)
    for rec in records:
        if rec.custom_installed_equipment != _equipment(mi):
            frappe.throw('Calibration Record belongs to another equipment: ' + rec.name)
        if rec.docstatus != 1:
            frappe.throw('Submit Calibration Record before signing report: ' + rec.name)
        if rec.custom_calibration_status not in ('Completed', 'Failed'):
            frappe.throw('Calibration Record is not finalized: ' + rec.name)
        if rec.custom_overall_result not in ('Pass', 'Fail', 'Pass After Adjustment'):
            frappe.throw('Resolve incomplete calibration result: ' + rec.name)
    return records


def _snapshot(report):
    """Immutable result manifest covered by the signature; hashes include attachments."""
    output = []
    for row in report.get('custom_interventions') or []:
        mi = _read_mi(row.custom_mission_intervention)
        if _context(mi)['st'] != report.custom_service_ticket or _context(mi)['tm'] != report.custom_tech_mission:
            frappe.throw('Intervention no longer matches report scope')
        if _equipment(mi) != row.custom_installed_equipment:
            frappe.throw('Equipment changed after report was assembled')
        records = _check_complete(mi)
        recs = []
        for brief in records:
            d = frappe.get_doc('Calibration Record', brief.name)
            frows = frappe.get_all('File', filters={'attached_to_doctype':'Calibration Record',
                'attached_to_name':d.name, 'is_private':1},
                fields=['file_name','content_hash','file_size'], order_by='name asc')
            readings = []
            for reading in d.get('custom_calibration_readings') or []:
                readings.append({f.fieldname: reading.get(f.fieldname) for f in reading.meta.fields
                                 if f.fieldname and not f.fieldname.startswith('_')})
            recs.append({'record':d.name, 'modified':str(d.modified),
                         'status':d.get('custom_calibration_status'),
                         'result':d.get('custom_overall_result'),
                         'component':d.get('custom_equipment_component'),
                         'readings':readings, 'files':[dict(x) for x in frows]})
        output.append({'mi':mi.name,'equipment':_equipment(mi),'records':recs})
    return output


def _digest(report):
    return hashlib.sha256(json.dumps(_snapshot(report),sort_keys=True,default=str,
                                     separators=(',',':')).encode()).hexdigest()


def _candidate(mi, origin):
    if mi.docstatus != 1 or mi.get('custom_intervention_type') != 'Calibration':
        return False
    try:
        ctx = _context(mi)
        return ctx['st']==origin['st'] and ctx['tm']==origin['tm']
    except Exception:
        return False


@frappe.whitelist()
def get_calibration_batch_workspace(mi_name):
    mi = _read_mi(mi_name)
    ctx = _context(mi)
    # Find all Calibration MIs for the same Tech Mission; filter again by ST.
    tm_field = next((f.fieldname for f in mi.meta.fields if f.fieldtype=='Link'
                     and f.options=='Tech Mission' and mi.get(f.fieldname)), None)
    if not tm_field:
        frappe.throw('MI Tech Mission link is unavailable')
    names = frappe.get_all('Mission Intervention', filters={tm_field:ctx['tm'],
                      'custom_intervention_type':'Calibration','docstatus':1},
                      pluck='name',limit_page_length=1000)
    candidates=[]
    for name in names:
        other = frappe.get_doc('Mission Intervention',name)
        if not other.has_permission('read') or not _candidate(other,ctx):
            continue
        owner = _active_member(name)
        eq = _equipment(other)
        candidates.append({'mi':name,'equipment':eq,
                           'equipment_label':frappe.db.get_value('Installed Equipment',eq,'custom_asset_name') or eq,
                           'report':owner,'eligible':not owner,
                           'finalized':bool(owner and frappe.db.get_value(REPORT,owner,'docstatus')==1)})
    drafts=[]
    reports=frappe.get_all(REPORT,filters={'custom_service_ticket':ctx['st'],
                    'custom_tech_mission':ctx['tm'],'docstatus':0},pluck='name',limit_page_length=100)
    for name in reports:
        try:
            r=_report(name)
            drafts.append({'name':r.name,'mis':[x.custom_mission_intervention for x in r.custom_interventions]})
        except frappe.PermissionError:
            pass
    return {'st':ctx['st'],'tm':ctx['tm'],'mi':mi.name,'candidates':candidates,'drafts':drafts}


@frappe.whitelist()
def create_calibration_batch(mi_name):
    mi=_read_mi(mi_name)
    _require_current_user_is_technician(mi)
    ctx=_context(mi)
    doc=frappe.get_doc({'doctype':REPORT,'custom_service_ticket':ctx['st'],
                        'custom_tech_mission':ctx['tm'], 'custom_origin_mi':mi.name})
    doc.insert(ignore_permissions=True)
    return {'name':doc.name}


@frappe.whitelist()
def add_interventions_to_batch(report_name, mi_names):
    doc=_report(report_name,write=True)
    if doc.docstatus != 0 or doc.custom_signature_file:
        frappe.throw('A signed or submitted report cannot be changed')
    if isinstance(mi_names,str):
        mi_names=json.loads(mi_names)
    if not isinstance(mi_names,list) or not mi_names or len(mi_names)>100:
        frappe.throw('Select between 1 and 100 interventions')
    existing={r.custom_mission_intervention for r in doc.custom_interventions}
    for name in dict.fromkeys(mi_names):
        mi=_read_mi(name)
        _require_current_user_is_technician(mi)
        ctx=_context(mi)
        if ctx['st']!=doc.custom_service_ticket or ctx['tm']!=doc.custom_tech_mission:
            frappe.throw('Cannot mix Service Tickets or Tech Missions')
        _check_complete(mi)
        owner=_active_member(name)
        if owner and owner != doc.name:
            frappe.throw(name+' already belongs to '+owner)
        if name not in existing:
            doc.append('custom_interventions',{'custom_mission_intervention':name,
                         'custom_installed_equipment':ctx['equipment']})
    doc.save(ignore_permissions=True)
    return {'name':doc.name,'count':len(doc.custom_interventions)}


@frappe.whitelist()
def get_calibration_batch_preview(report_name):
    doc=_report(report_name)
    report=[]
    for r in doc.custom_interventions:
        mi=_read_mi(r.custom_mission_intervention)
        records=_mi_records(mi.name)
        detail=[]
        for x in records:
            rec=frappe.get_doc('Calibration Record',x.name)
            readings=[{'point':y.get('custom_test_point'), 'before':y.get('custom_before_reading'),
                       'after':y.get('custom_after_reading'),'result':y.get('custom_result')}
                      for y in rec.get('custom_calibration_readings') or []]
            table=None
            try:
                from maintenance_app.calibration_table import _read_json
                table=_read_json(rec)
            except ImportError:
                pass
            detail.append({'name':x.name,'component':x.custom_equipment_component,
                           'result':x.custom_overall_result,'readings':readings,
                           'table':table})
        report.append({'mi':mi.name,'equipment':r.custom_installed_equipment,
                       'records':detail})
    return {'name':doc.name,'docstatus':doc.docstatus,
            'measure_jar_capacity_l':doc.get('custom_measure_jar_capacity_l'),
            'measure_jar_identifier':doc.get('custom_measure_jar_identifier'),
            'signature':doc.custom_signature_file,
            'technician_name':frappe.db.get_value('User',frappe.session.user,'full_name') or frappe.session.user,
            'technician_user':frappe.session.user,'items':report}


@frappe.whitelist()
def sign_and_submit_calibration_batch(report_name, client_name, signature_data, measure_jar_capacity_l=None, measure_jar_identifier=None, technician_signature_data=None):
    doc=_report(report_name,write=True)
    if doc.docstatus != 0 or doc.custom_signature_file:
        frappe.throw('This report is already signed or submitted')
    if not doc.custom_interventions:
        frappe.throw('Add completed interventions first')
    client_name=(client_name or '').strip()
    if not (2 <= len(client_name) <= 140):
        frappe.throw('Enter the client representative name')
    # Jar capacity is mandatory for this FDU signing workflow. Jar ID is optional.
    try:
        jar_capacity = float(measure_jar_capacity_l)
    except (TypeError, ValueError):
        frappe.throw('Enter a valid measuring jar capacity in litres')
    import math
    if not math.isfinite(jar_capacity) or not (0 < jar_capacity <= 100000):
        frappe.throw('Measuring jar capacity must be greater than zero')
    jar_identifier = str(measure_jar_identifier or '').strip()
    if len(jar_identifier) > 140:
        frappe.throw('Measuring jar ID must be at most 140 characters')
    # GMAO_CAL_TWO_SIGNATURES_V1: validate BOTH private PNG signatures.
    def decode_signature(value, label):
        if not isinstance(value,str) or len(value)>400000:
            frappe.throw(label+' signature is invalid or too large')
        match=re.fullmatch(r'data:image/png;base64,([A-Za-z0-9+/=]+)',value)
        if not match:
            frappe.throw(label+' signature must be a PNG image')
        try:
            data=base64.b64decode(match.group(1),validate=True)
        except Exception:
            frappe.throw('Invalid '+label+' signature image')
        if len(data)>200000 or len(data)<100 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
            frappe.throw('Please provide a valid '+label+' signature, maximum 200 KB')
        return data
    png=decode_signature(signature_data,'Client')
    technician_png=decode_signature(technician_signature_data,'Technician')
    technician_user=frappe.session.user
    if technician_user in ('Guest', 'Administrator'):
        frappe.throw('Sign in as the assigned technician before signing a certificate')
    technician_name=frappe.db.get_value('User',technician_user,'full_name') or technician_user
    # Repeat validation immediately before signing to avoid incomplete results.
    manifest=_snapshot(doc)
    digest=hashlib.sha256(json.dumps(manifest,sort_keys=True,default=str,
                  separators=(',',':')).encode()).hexdigest()
    doc.custom_measure_jar_capacity_l=jar_capacity
    doc.custom_measure_jar_identifier=jar_identifier
    doc.custom_client_name=client_name
    doc.custom_technician=technician_user
    doc.custom_technician_name=technician_name
    doc.custom_signing_version='2'
    doc.custom_signed_at=now_datetime()
    doc.custom_results_hash=digest
    doc.save(ignore_permissions=True)
    file_doc=save_file('calibration-signature-'+doc.name+'.png',png,REPORT,doc.name,is_private=1)
    tech_file=save_file('calibration-technician-signature-'+doc.name+'.png',technician_png,REPORT,doc.name,is_private=1)
    doc.custom_signature_file=file_doc.file_url
    doc.custom_technician_signature_file=tech_file.file_url
    doc.save(ignore_permissions=True)
    doc.flags.ignore_permissions = True
    doc.submit()
    return {'name':doc.name,'docstatus':doc.docstatus}


def validate_report(doc, method=None):
    seen=set()
    for r in doc.custom_interventions:
        if r.custom_mission_intervention in seen:
            frappe.throw('Duplicate intervention on Calibration Report')
        seen.add(r.custom_mission_intervention)
        mi=_read_mi(r.custom_mission_intervention)
        ctx=_context(mi)
        if ctx['st']!=doc.custom_service_ticket or ctx['tm']!=doc.custom_tech_mission:
            frappe.throw('The report must contain interventions from one ST and TM')
        if ctx['equipment']!=r.custom_installed_equipment:
            frappe.throw('Report equipment does not match MI')
        owner=_active_member(mi.name)
        if owner and owner!=doc.name:
            frappe.throw('Intervention is already on another Calibration Report: '+owner)
    if doc.docstatus==1:
        if not doc.custom_signature_file or not doc.custom_client_name or not doc.custom_results_hash:
            frappe.throw('Client signature and result snapshot are required to submit')
        if doc.get('custom_signing_version') == '2' and not (doc.get('custom_technician') and doc.get('custom_technician_name') and doc.get('custom_technician_signature_file')):
            frappe.throw('Technician identity and signature are required to submit')
        if _digest(doc)!=doc.custom_results_hash:
            frappe.throw('Calibration readings changed since signature capture')


def on_cancel_report(doc, method=None):
    # Existing signed report is retained for audit; a new report may group amended results.
    pass
