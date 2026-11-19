"""Read-only audit of Custom Field records on maintenance_app-owned DocTypes.

Generates an export of any record missing from its owning DocType JSON.
No database writes.
"""
import json
from pathlib import Path
import frappe


def audit_owned_extras():
    root=Path(frappe.get_app_path('maintenance_app'))/'doctype'
    owned={}
    for file in root.glob('*/*.json'):
        try:
            schema=json.loads(file.read_text(encoding='utf-8'))
        except (ValueError,OSError):
            continue
        if schema.get('name') and isinstance(schema.get('fields'),list):
            owned[schema['name']]={'path':str(file),'fields':{f.get('fieldname') for f in schema['fields']}}
    if not owned:
        raise RuntimeError(f'No maintenance_app doctypes found beneath {root}')
    props=['name','dt','fieldname','label','fieldtype','options','default',
           'insert_after','reqd','read_only','hidden','depends_on','fetch_from',
           'in_list_view','in_standard_filter']
    rows=frappe.get_all('Custom Field',filters={'dt':['in',sorted(owned)]},
                        fields=props,limit_page_length=10000,order_by='dt asc, fieldname asc')
    items=[]
    for row in rows:
        record=dict(row)
        record['in_doctype_json']=row.fieldname in owned[row.dt]['fields']
        record['doctype_json']=owned[row.dt]['path']
        items.append(record)
    site=frappe.local.site.replace('/','_')
    outfile=Path('/tmp')/f'maintenance_app_owned_extras_v4_{site}.json'
    outfile.write_text(json.dumps(items,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
    summary={
        'site':frappe.local.site,
        'app_owned_doctypes':len(owned),
        'custom_field_records_on_owned_doctypes':len(items),
        'records_missing_from_json':[r['dt']+'.'+r['fieldname'] for r in items if not r['in_doctype_json']],
        'records_already_in_json':[r['dt']+'.'+r['fieldname'] for r in items if r['in_doctype_json']],
        'report_file':str(outfile),
        'changed_database':False,
    }
    print(json.dumps(summary,indent=2))
    return summary
