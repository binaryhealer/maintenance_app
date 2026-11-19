"""Safe image embeds for the app-owned consolidated Calibration Report Print Format."""
import base64
import frappe


def calibration_signature_data_uri(report_name, fieldname):
    """Return PNG data URI only for a private signature attached to that report."""
    if fieldname not in ('custom_signature_file','custom_technician_signature_file'):
        return ''
    report = frappe.get_doc('Calibration Report', report_name)
    url = report.get(fieldname)
    if not url or not str(url).startswith('/private/files/'):
        return ''
    f_name = frappe.db.get_value('File', {'file_url': url}, 'name')
    if not f_name:
        return ''
    file_doc=frappe.get_doc('File', f_name)
    if (file_doc.attached_to_doctype != 'Calibration Report' or
        file_doc.attached_to_name != report.name or not file_doc.is_private):
        return ''
    content=file_doc.get_content()
    if not isinstance(content,bytes):
        content=content.encode()
    if not (100 <= len(content) <= 200000) or not content.startswith(b'\x89PNG\r\n\x1a\n'):
        return ''
    return 'data:image/png;base64,' + base64.b64encode(content).decode('ascii')
