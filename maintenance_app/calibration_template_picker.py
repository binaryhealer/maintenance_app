"""GMAO_CAL_TEMPLATE_PICKER_V1: component types actually calibrated within an Item Group.

This is a suggestion endpoint, NOT an authorization endpoint. Selection always
stores a component TYPE, never an individual customer's component record.
"""
import frappe


@frappe.whitelist()
def get_component_types(equipment_category=None, show_all=0):
    if not frappe.has_permission('Calibration Template', 'read'):
        frappe.throw('Not permitted to view Calibration Templates', frappe.PermissionError)
    if not frappe.has_permission('Installed Equipment', 'read'):
        frappe.throw('Not permitted to view Installed Equipment', frappe.PermissionError)
    if frappe.utils.cint(show_all):
        return frappe.get_list('Equipment Type', fields=['name'], order_by='name asc', limit_page_length=5000)
    if not equipment_category:
        return []
    # Use the actual Item Group category of Installed Equipment, not a new group.
    eq_names = frappe.get_list('Installed Equipment',
        filters={'custom_asset_category': equipment_category},
        pluck='name', limit_page_length=5000)
    if not eq_names:
        return []
    seen = set()
    # Installed Equipment Component can carry both the type and the calibration flag.
    for start in range(0, len(eq_names), 200):
        subset = eq_names[start:start+200]
        rows = frappe.get_all('Installed Equipment Component',
            filters={'parenttype':'Installed Equipment',
                     'parentfield':'custom_installed_components',
                     'parent':['in', subset]},
            fields=['parent','custom_equipment_type','custom_equipment_component',
                    'custom_requires_calibration'],
            limit_page_length=10000)
        component_ids = list({row.custom_equipment_component for row in rows if row.custom_equipment_component})
        masters = {}
        for p in range(0, len(component_ids), 200):
            for comp in frappe.get_all('Equipment Component',
                filters={'name':['in', component_ids[p:p+200]]},
                fields=['name','custom_parent_equipment','custom_equipment_type',
                        'custom_requires_calibration','custom_status'],
                limit_page_length=10000):
                masters[comp.name] = comp
        for row in rows:
            master = masters.get(row.custom_equipment_component)
            # A master component must actually belong to this Installed Equipment.
            if master and master.custom_parent_equipment != row.parent:
                continue
            if master and master.custom_status not in ('Installed', None, ''):
                continue
            required = bool(row.custom_requires_calibration or
                            (master and master.custom_requires_calibration))
            if not required:
                continue
            typ = (master.custom_equipment_type if master else None) or row.custom_equipment_type
            if typ:
                seen.add(typ)
    return [{'name':name} for name in sorted(seen)]
