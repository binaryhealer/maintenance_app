"""Calibration PWA Stage 2: target selection and draft Calibration Records only.

Does NOT write readings, submit Calibration Records, or modify equipment due dates.
"""
import json

import frappe
from frappe.utils import now_datetime


def _mi(name, write=False):
    if not name:
        frappe.throw('Mission Intervention is required')
    mi = frappe.get_doc('Mission Intervention', name)
    mi.check_permission('write' if write else 'read')
    if write and mi.docstatus != 0:
        frappe.throw('Submitted intervention is read-only')
    return mi


def _link_to(doc, options):
    for field in doc.meta.fields:
        if field.fieldtype == 'Link' and field.options == options:
            value = doc.get(field.fieldname)
            if value:
                return value
    return None


def _assigned_equipment(mi):
    # Calibration targets are MI-scoped, NOT mission-scoped.
    # A TM may include multiple FDUs, but each MI works on its own FDU.
    equipment = mi.get('custom_asset')
    if not equipment:
        frappe.throw('Select the Installed Equipment on this intervention before calibration.')
    if not frappe.db.exists('Installed Equipment', equipment):
        frappe.throw('Installed Equipment does not exist: ' + str(equipment))

    mission_name = mi.get('custom_parent_mission') or _link_to(mi, 'Tech Mission')
    if mission_name:
        mission = frappe.get_doc('Tech Mission', mission_name)
        planned = [
            row.get('custom_equipment')
            for row in (mission.get('custom_target_equipments') or [])
            if row.get('custom_equipment')
        ]
        if not planned and mission.get('custom_target_equipment'):
            planned = [mission.get('custom_target_equipment')]
        if planned and equipment not in planned:
            frappe.throw('Intervention equipment is not among this mission\'s planned equipment: ' + str(equipment))
    return [equipment]


def _installed_components(eq):
    doc=frappe.get_doc('Installed Equipment',eq)
    names=[r.get('custom_equipment_component') for r in (doc.get('custom_installed_components') or []) if r.get('custom_equipment_component')]
    if not names:
        # Some installations use a permanent parent link rather than child rows.
        names=frappe.get_all('Equipment Component',filters={'custom_parent_equipment':eq,'custom_status':'Installed'},pluck='name')
    result=[]
    for n in dict.fromkeys(names):
        if not frappe.db.exists('Equipment Component',n):
            continue
        comp=frappe.get_doc('Equipment Component',n)
        if comp.get('custom_parent_equipment') != eq:
            continue
        result.append({'name':n,'label':comp.get('custom_display_name') or n,'group':comp.get('custom_component_group')})
    return result


def _templates(equipment, component=None):
    names=frappe.get_all('Calibration Template',filters={'custom_enabled':1},fields=['name','custom_template_name','custom_applicable_scope','custom_equipment_category','custom_calibrate_components','custom_table_component_type','custom_equipment_type','custom_component_group'],order_by='custom_template_name asc')
    eq_doc=frappe.get_doc('Installed Equipment',equipment)
    comp_doc=frappe.get_doc('Equipment Component',component) if component else None
    result=[]
    for item in names:
        # Primary classification: Installed Equipment's Item Group.
        if item.get('custom_equipment_category') != eq_doc.get('custom_asset_category'):
            continue
        # Simple template setup: complete equipment OR its components.
        if (item.get('custom_calibrate_components') == 'Yes') != bool(component):
            continue
        # Legacy optional restrictions remain supported, but are not required.
        if item.get('custom_equipment_type') and item.custom_equipment_type != eq_doc.get('custom_equipment_type'):
            continue
        if item.get('custom_component_group') and (not comp_doc or item.custom_component_group != comp_doc.get('custom_component_group')):
            continue
        if item.get('custom_table_component_type'):
            if not comp_doc or item.custom_table_component_type != comp_doc.get('custom_equipment_type'):
                continue
        # For component templates, show the template only when it contains
        # at least one test for this component type (or a generic test).
        if comp_doc:
            points=frappe.get_all('Calibration Template Item',
                filters={'parent':item.name,'parenttype':'Calibration Template'},
                fields=['custom_component_type'],limit_page_length=1000)
            component_type=comp_doc.get('custom_equipment_type')
            if points and not any(not x.custom_component_type or x.custom_component_type == component_type for x in points):
                continue
        result.append({'name':item.name,'label':item.get('custom_template_name') or item.name})
    return result


# GMAO_PARTIAL_CAL_CONTINUE_V1
# Read-only progress from submitted Calibration Records on earlier MIs in the
# same explicit Continue Work follow-up chain. Do not cross TMs or FDUs.
def _previous_calibration_results(mi):
    previous = mi.get('custom_previous_intervention')
    mission = mi.get('custom_parent_mission') or _link_to(mi, 'Tech Mission')
    equipment = mi.get('custom_asset')
    if not previous or not mission or not equipment:
        return {}

    ancestors = []
    seen = {mi.name}
    while previous:
        if previous in seen or len(ancestors) >= 30:
            frappe.throw('Invalid or excessively long Continue Work intervention chain')
        seen.add(previous)
        row = frappe.db.get_value('Mission Intervention', previous,
            ['custom_parent_mission', 'custom_asset', 'custom_previous_intervention',
             'custom_intervention_type', 'docstatus'], as_dict=True)
        if not row or row.custom_parent_mission != mission or row.custom_asset != equipment:
            frappe.throw('Continue Work source intervention belongs to another mission or equipment')
        if row.custom_intervention_type != 'Calibration' or int(row.docstatus) != 1:
            frappe.throw('Continue Work source must be a submitted Calibration MI')
        ancestors.append(previous)
        previous = row.custom_previous_intervention

    # Oldest-to-newest gives the latest completed attempt precedence.
    found = {}
    for name in reversed(ancestors):
        rows = frappe.get_all('Calibration Record',
            filters={'custom_mission_intervention': name, 'docstatus': 1,
                     'custom_installed_equipment': equipment},
            fields=['name', 'custom_equipment_component', 'custom_overall_result',
                    'custom_calibration_status'],
            order_by='creation asc', limit_page_length=1000)
        for rec in rows:
            if (rec.custom_calibration_status not in ('Completed', 'Failed')
                    or rec.custom_overall_result not in
                    ('Pass', 'Fail', 'Pass After Adjustment')):
                continue
            key = rec.custom_equipment_component or ''
            found[key] = {
                'mi': name, 'record': rec.name, 'result': rec.custom_overall_result,
                'completed': rec.custom_overall_result != 'Fail'
            }
    return found


def _get_pwa_records(mi):
    return frappe.get_all('Calibration Record',filters={'custom_mission_intervention':mi.name,'custom_pwa_target_draft':1},fields=['name','custom_installed_equipment','custom_equipment_component','custom_calibration_template','custom_calibration_status'],limit_page_length=1000)


@frappe.whitelist()
def get_calibration_targets(mi_name):
    mi=_mi(mi_name)
    allowed=_assigned_equipment(mi)
    rows=[]
    for eq in allowed:
        doc=frappe.get_doc('Installed Equipment',eq)
        comps=_installed_components(eq)
        for c in comps:
            c['templates']=_templates(eq,c['name'])
        rows.append({'name':eq,'label':doc.get('custom_display_name') or doc.get('custom_asset_name') or eq,'templates':_templates(eq),'components':comps})
    records=[]
    for r in _get_pwa_records(mi):
        if r.custom_calibration_status == 'Cancelled':
            continue
        if r.custom_installed_equipment not in allowed:
            continue
        records.append({'name':r.name,'equipment':r.custom_installed_equipment,'component':r.custom_equipment_component or '', 'template':r.custom_calibration_template})
    return {'equipment':rows,'records':records,'readonly':mi.docstatus != 0}


@frappe.whitelist()
def save_calibration_targets(mi_name, targets):
    mi=_mi(mi_name,write=True)
    targets=frappe.parse_json(targets) if isinstance(targets,str) else targets
    if not isinstance(targets,list):
        frappe.throw('Expected list of calibration targets')
    if len(targets)>100:
        frappe.throw('Too many calibration targets')
    allowed=set(_assigned_equipment(mi))
    if not allowed:
        frappe.throw('No assigned equipment found for this intervention')
    # GMAO_PARTIAL_CAL_CONTINUE_V1: protected prior calibration on linked MIs.
    previous_results = _previous_calibration_results(mi)
    choices={}
    for target in targets:
        if not isinstance(target,dict):
            frappe.throw('Invalid calibration target')
        eq=target.get('equipment')
        comp=target.get('component') or ''
        template=target.get('template')
        if eq not in allowed:
            frappe.throw('Equipment is not assigned to this mission: ' + str(eq))
        if comp and comp not in {c['name'] for c in _installed_components(eq)}:
            frappe.throw('Component is not installed on selected equipment: ' + str(comp))
        available={x['name'] for x in _templates(eq,comp or None)}
        if template not in available:
            frappe.throw('Invalid or inactive calibration template for target')
        key=(eq,comp)
        older = previous_results.get(comp)
        if older and older['completed']:
            frappe.throw('Already calibrated in ' + older['mi'] +
                ' (' + older['record'] + '). Do not repeat this component on the follow-up MI.')
        # Previous Fail is eligible for deliberate retesting; it stays in history.
        if key in choices:
            frappe.throw('Duplicate calibration target: ' + str(key))
        choices[key]=template
    existing={}
    for row in _get_pwa_records(mi):
        if row.custom_installed_equipment not in allowed:
            # Do not silently delete or cancel older mis-scoped records.
            # Those must be reviewed separately if they exist.
            if row.custom_calibration_status != 'Cancelled':
                frappe.throw('Existing calibration record ' + row.name +
                    ' belongs to a different FDU. Review this record before saving MI calibration targets.')
            continue
        k=(row.custom_installed_equipment,row.custom_equipment_component or '')
        if k in existing:
            frappe.throw('Duplicate PWA Calibration Records exist for ' + str(k) + '. Resolve them before saving.')
        existing[k]=row
    mission_name=_link_to(mi,'Tech Mission')
    ticket_name=_link_to(mi,'Service Ticket') or mi.get('custom_service_ticket')
    count=0
    for key,template in choices.items():
        eq, comp=key
        item=existing.get(key)
        if item:
            rec=frappe.get_doc('Calibration Record',item.name)
            if rec.docstatus != 0 or rec.get('custom_calibration_status') in ('Completed','Failed'):
                frappe.throw('Cannot edit completed calibration: ' + rec.name)
        else:
            rec=frappe.new_doc('Calibration Record')
            rec.custom_calibration_title='Calibration - ' + (comp or eq)
            rec.custom_calibration_date=now_datetime()
            rec.custom_mission_intervention=mi.name
            rec.custom_tech_mission=mission_name
            rec.custom_service_ticket=ticket_name
            rec.custom_customer=mi.get('custom_customer')
            rec.custom_branch=mi.get('custom_client_branch')
            rec.custom_installed_equipment=eq
            rec.custom_equipment_component=comp or None
            rec.custom_pwa_target_draft=1
            rec.custom_calibration_status='Draft'
        rec.custom_calibration_template=template
        if rec.get('custom_calibration_status') == 'Cancelled':
            rec.custom_calibration_status='Draft'
        rec.save(ignore_permissions=True) if not rec.is_new() else rec.insert(ignore_permissions=True)
        count+=1
    for key,row in existing.items():
        if key not in choices and row.custom_calibration_status not in ('Cancelled','Completed','Failed'):
            rec=frappe.get_doc('Calibration Record',row.name)
            if rec.docstatus == 0:
                if rec.get('custom_calibration_readings'):
                    frappe.throw('Cannot deselect target with saved readings: ' + rec.name)
                rec.custom_calibration_status='Cancelled'
                rec.save(ignore_permissions=True)
    return {'ok':True,'count':count,'message':str(count)+' calibration target(s) saved as draft records.'}
