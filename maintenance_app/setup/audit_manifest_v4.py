"""Read-only preflight of ALL GMAO manifest entries on a Frappe v16 site.

Can be invoked with:
  bench --site dev.local execute maintenance_app.setup.audit_manifest_v4.preflight
No DB write is performed.
"""
import json
from pathlib import Path
import frappe


def preflight():
    path = Path(__file__).with_name('custom_fields.json')
    registry=json.loads(path.read_text(encoding='utf-8'))
    report={
        'site':frappe.local.site,
        'manifest_fields':sum(map(len,registry.values())),
        'missing_doctypes':[],
        'field_missing':[],
        'provided_by_meta':[],
        'definition_mismatch':[],
        'missing_external_anchors':[],
        'missing_link_target_doctypes':[],
        'missing_dynamic_link_fields':[],
        'prohibited_helpdesk_doctypes':[],
        'would_create_on_this_site':0,
    }
    for dt,fields in registry.items():
        if dt.startswith('HD '):
            report.setdefault('prohibited_helpdesk_doctypes',[]).append(dt)
            continue
        if not frappe.db.exists('DocType',dt):
            report['missing_doctypes'].append(dt)
            continue
        meta=frappe.get_meta(dt)
        own={x['fieldname'] for x in fields}
        for field in fields:
            name=field['fieldname']; key=dt+'.'+name
            actual=meta.get_field(name)
            if actual:
                report['provided_by_meta'].append(key)
                expected=(field['fieldtype'],field.get('options') or '')
                found=(actual.fieldtype,actual.get('options') or '')
                if found!=expected:
                    report['definition_mismatch'].append({'field':key,'expected':expected,'actual':found})
            else:
                report['field_missing'].append(key)
            anchor=field.get('insert_after')
            if anchor and anchor!='append' and anchor not in own and not meta.get_field(anchor):
                report['missing_external_anchors'].append({'field':key,'requested_anchor':anchor,'new_site_behavior':'append with warning'})
            if field['fieldtype'] in ('Table','Table MultiSelect','Link') and field.get('options'):
                target=field['options']
                if not frappe.db.exists('DocType',target):
                    report['missing_link_target_doctypes'].append({'field':key,'target':target})
            if field['fieldtype']=='Dynamic Link':
                target=field.get('options')
                if target not in own and not meta.get_field(target):
                    report['missing_dynamic_link_fields'].append({'field':key,'option_field':target})
    report['would_create_on_this_site']=len(report['field_missing'])
    report['status']='REVIEW' if any(report[k] for k in (
        'missing_doctypes','definition_mismatch','missing_external_anchors',
        'missing_link_target_doctypes','missing_dynamic_link_fields',
        'prohibited_helpdesk_doctypes')) else 'PRECHECK_OK'
    print(json.dumps(report,indent=2,default=str,ensure_ascii=False))
    return report
