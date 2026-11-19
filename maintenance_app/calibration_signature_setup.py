"""One-time Print Format update after installing calibration two-signature upgrade."""
import re
import frappe

FORMAT = 'GMAO Consolidated Calibration Certificate'

def finalize_print_format():
    pf=frappe.get_doc('Print Format',FORMAT)
    if pf.doc_type!='Calibration Report':
        frappe.throw('Print Format belongs to another DocType')
    s=pf.html or ''
    if 'calibration_signature_data_uri(' in s:
        print('ALREADY CONFIGURED: Signature helpers in Print Format');return
    old_client='src="{{ frappe.get_url() }}{{ doc.custom_signature_file }}"'
    new_client='src="{{ calibration_signature_data_uri(doc.name, \'custom_signature_file\') }}"'
    if s.count(old_client)!=1:
        frappe.throw('STOP: Existing client image expression changed. Do not overwrite Print Format; share HTML for targeted edit')
    if s.count('Technician: __________________________')!=1 or s.count('<strong>Technician signature:</strong>')!=1:
        frappe.throw('STOP: Technician placeholder changed. Do not overwrite Print Format; share HTML for targeted edit')
    s=s.replace(old_client,new_client,1)
    s=s.replace('Technician: __________________________', "Technician: {{ doc.custom_technician_name or '—' }}",1)
    s=s.replace('<strong>Technician signature:</strong>', """<strong>Technician signature:</strong><div class="fdu-rule">
          {% if doc.custom_technician_signature_file %}<img class="fdu-sign-image" src="{{ calibration_signature_data_uri(doc.name, 'custom_technician_signature_file') }}" alt="Signed by technician">{% endif %}
          </div>""",1)
    # Remove original blank line after technician signature; other HTML untouched.
    s=s.replace('<div class="fdu-rule">&nbsp;</div>', '',1)
    pf.html=s
    pf.save(ignore_permissions=True)
    frappe.db.commit()
    print('SUCCESS: Print Format now embeds both private signatures; existing submitted Reports remain unchanged')
