"""Private, idempotent, signed consolidated Calibration Report PDF on parent ST.

Never sends email and never changes MI/Calibration Record statuses.
The existing MI PDF hook remains the owner of MI PDFs.
"""
import base64
import html
import json
import re

import frappe
from frappe.utils.file_manager import get_file, save_file
from frappe.utils.pdf import get_pdf


def _h(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def _safe_value(value):
    return '—' if value is None or value == '' else _h(value)


def _load_signature(report):
    url = report.get('custom_signature_file')
    if not url:
        frappe.throw('Signed Calibration Report has no signature file')
    found = frappe.get_all('File', filters={
        'attached_to_doctype': 'Calibration Report', 'attached_to_name': report.name,
        'file_url': url, 'is_private': 1,
    }, fields=['name', 'file_name'], limit_page_length=2)
    if len(found) != 1:
        frappe.throw('Report signature must be a private File attached to this Calibration Report')
    _, raw = get_file(url)
    if isinstance(raw, str):
        raw = raw.encode()
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) > 200_000:
        frappe.throw('Invalid report signature PNG')
    return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')


def _file_exists_on_st(ticket, report_name):
    # Stable, unique filename keyed to immutable report ID; content-hash suffix allowed.
    stem = 'Calibration-Report-' + report_name
    found = frappe.get_all('File', filters={
        'attached_to_doctype': 'Service Ticket', 'attached_to_name': ticket,
        'is_private': 1,
    }, fields=['name', 'file_name'], limit_page_length=0)
    return bool([row for row in found if row.file_name == stem + '.pdf'
                 or (row.file_name.startswith(stem + '-') and row.file_name.endswith('.pdf'))])


def _find_table(rec):
    from maintenance_app.calibration_table import _read_json
    return _read_json(rec)


def _table_html(data):
    columns = data.get('columns') or []
    rows = data.get('rows') or []
    if not columns:
        return ''
    head = '<tr>' + ''.join('<th>' + _h(c.get('label')) + '</th>' for c in columns) + '</tr>'
    body = ''.join('<tr>' + ''.join('<td>' + _safe_value(row.get(str(c.get('key')))) + '</td>'
                                  for c in columns) + '</tr>' for row in rows)
    if not rows:
        body = '<tr><td colspan="%d">No table rows recorded</td></tr>' % len(columns)
    return '<table class="readings"><thead>' + head + '</thead><tbody>' + body + '</tbody></table>'


def _standard_readings(rec):
    rows = rec.get('custom_calibration_readings') or []
    if not rows:
        return ''
    out = '<table class="readings"><thead><tr><th>Test</th><th>Before</th><th>After</th><th>Result</th><th>Remarks</th></tr></thead><tbody>'
    for r in rows:
        out += '<tr>' + ''.join('<td>' + _safe_value(r.get(field)) + '</td>' for field in (
            'custom_test_point','custom_before_reading','custom_after_reading','custom_result','custom_remarks')) + '</tr>'
    return out + '</tbody></table>'


def _equipment_label(code):
    return frappe.db.get_value('Installed Equipment', code, 'custom_asset_name') or code


def _component_label(code):
    if not code:
        return 'Complete equipment'
    return frappe.db.get_value('Equipment Component', code, 'custom_display_name') or code


def _report_html(report):
    """Print submitted records only; cover each MI and all its component readings."""
    sig = _load_signature(report)
    parts = [
        '<html><head><meta charset="utf-8"><style>',
        '@page {size:A4 landscape; margin: 13mm;} body{font-family:DejaVu Sans,Arial,sans-serif;font-size:10px;color:#222}',
        'h1{font-size:19px;margin:0 0 5px} h2{font-size:14px;margin:16px 0 7px;border-bottom:1px solid #aaa;padding-bottom:5px}',
        'h3{font-size:11px;margin:12px 0 6px} .muted{color:#666}.meta{margin:8px 0 16px}.meta span{margin-right:18px}',
        'table{border-collapse:collapse;width:100%;} .readings{margin:7px 0 14px;table-layout:fixed}',
        'th,td{border:1px solid #aaa;padding:5px;overflow-wrap:anywhere;vertical-align:top}th{background:#f0f1f3;text-align:left}',
        '.equipment{page-break-inside:avoid;margin-bottom:12px}.signature{margin-top:22px;page-break-inside:avoid}',
        '.signature img{max-width:350px;max-height:110px;object-fit:contain;border-bottom:1px solid #333}',
        '</style></head><body>',
        '<h1>Consolidated Calibration Report</h1>',
        '<div class="meta"><span><b>Report:</b> '+_h(report.name)+'</span>',
        '<span><b>Service Ticket:</b> '+_h(report.custom_service_ticket)+'</span>',
        '<span><b>Tech Mission:</b> '+_h(report.custom_tech_mission)+'</span></div>',
        '<div class="meta"><span><b>Signed:</b> '+_safe_value(report.get('custom_signed_at'))+'</span>',
        '<span><b>Calibration measure:</b> '+_safe_value(report.get('custom_measure_jar_capacity_l'))+' L</span>',
        '<span><b>Jar ID:</b> '+_safe_value(report.get('custom_measure_jar_identifier'))+'</span></div>',
        '<p class="muted">Reported results may include failed calibration tests. The client signature acknowledges the recorded results, not that every test passed.</p>',
    ]
    if not report.get('custom_interventions'):
        frappe.throw('Calibration Report has no included interventions')
    for entry in report.custom_interventions:
        mi_name = entry.custom_mission_intervention
        eq = entry.custom_installed_equipment
        parts.append('<div class="equipment"><h2>'+_h(_equipment_label(eq))+' · MI '+_h(mi_name)+'</h2>')
        records = frappe.get_all('Calibration Record', filters={'custom_mission_intervention': mi_name},
            fields=['name','docstatus','custom_installed_equipment','custom_equipment_component',
                    'custom_calibration_template','custom_overall_result'], order_by='name asc', limit_page_length=1000)
        if not records:
            frappe.throw('No calibration records for MI '+mi_name)
        for row in records:
            if row.docstatus != 1 or row.custom_installed_equipment != eq:
                frappe.throw('Calibration Record must be submitted for correct equipment: '+row.name)
            rec = frappe.get_doc('Calibration Record', row.name)
            parts.append('<h3>'+_h(_component_label(row.custom_equipment_component))+
                         ' · '+_h(row.custom_calibration_template)+' · '+_h(row.custom_overall_result)+'</h3>')
            table = _find_table(rec)
            if table:
                parts.append(_table_html(table))
            parts.append(_standard_readings(rec))
        parts.append('</div>')
    parts += ['<div class="signature"><b>Client calibration acknowledgment</b><p>Representative: '+
              _h(report.custom_client_name)+'</p><img alt="Client calibration signature" src="'+sig+'"/></div>',
              '</body></html>']
    return ''.join(parts)


def queue_calibration_report_pdf_on_submit(doc):
    """Called from Calibration Report.on_submit: enqueue after commit."""
    if int(doc.docstatus or 0) != 1:
        return
    frappe.enqueue('maintenance_app.notifications.calibration_pdf_attachment.attach_submitted_calibration_pdf',
        queue='long', timeout=300, enqueue_after_commit=True,
        report_name=doc.name, job_name='gmao-cal-pdf-'+doc.name)


# GMAO_PRINT_FORMAT_PDF_ATTACHMENT_V1
@frappe.whitelist()
def attach_submitted_calibration_pdf(report_name):
    """Attach the submitted, signed report's own ERPNext Jinja Print Format to its ST.

    Safe to retry: a PDF attached to this ST with the stable report filename
    is not regenerated. Email handling, MI PDFs, and calibration outcomes are untouched.
    """
    report = frappe.get_doc('Calibration Report', report_name)
    if not frappe.flags.in_test and not frappe.local.flags.in_migrate and getattr(frappe.local, 'request', None):
        report.check_permission('read')
    if int(report.docstatus or 0) != 1:
        return 'SKIPPED_NOT_SUBMITTED'

    ticket = report.get('custom_service_ticket')
    if not ticket or not frappe.db.exists('Service Ticket', ticket):
        frappe.throw('Calibration Report has no valid parent Service Ticket')
    if _file_exists_on_st(ticket, report.name):
        return 'ALREADY_ATTACHED'

    print_format = 'GMAO Consolidated Calibration Certificate'
    if not frappe.db.exists('Print Format', print_format):
        frappe.throw('Missing Print Format: ' + print_format)
    pf = frappe.get_doc('Print Format', print_format)
    if pf.doc_type != 'Calibration Report':
        frappe.throw('Print Format is not assigned to Calibration Report: ' + print_format)

    # Use the SAME print template as ERPNext Print Preview; never build a
    # second certificate in Python. Explicit Chromium avoids wkhtmltopdf.
    # PDF creation is an automatic post-submit system action. A technician may
    # submit the report without having the "Print" role permission in Desk.
    # Elevate *only* while rendering this already-submitted report, and always
    # restore the original job user (including on exceptions).
    previous_user = frappe.session.user
    try:
        frappe.set_user('Administrator')
        pdf = frappe.get_print(
            'Calibration Report', report.name,
            print_format=print_format,
            as_pdf=True,
            pdf_generator='chrome',
        )
    finally:
        frappe.set_user(previous_user)
    if not isinstance(pdf, bytes) or not pdf.startswith(b'%PDF'):
        frappe.throw('Failed to generate consolidated Calibration Report PDF')

    save_file('Calibration-Report-' + report.name + '.pdf', pdf,
              dt='Service Ticket', dn=ticket, is_private=1)
    return 'ATTACHED'
