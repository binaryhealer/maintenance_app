"""Persist the submitted MI print PDF as a private ST attachment.

The technician-portal email code uses frappe.attach_print with print_format=None;
we use the same print mechanism, independently of whether an email is sent.
"""

import frappe
from frappe.utils.file_manager import save_file


def _get_parent_ticket(mi):
    ticket = mi.get("custom_service_ticket") or mi.get("custom_parent_ticket")
    if not ticket and mi.get("custom_parent_mission"):
        ticket = frappe.db.get_value(
            "Tech Mission", mi.get("custom_parent_mission"), "custom_service_ticket"
        )
    return ticket


def queue_mi_pdf_on_submit(doc, method=None):
    """Always schedule *after commit*, avoiding PDF work inside submission.

    If printing fails the MI remains submitted; the background job records an
    error and can be retried using attach_submitted_mi_pdf.
    """
    if int(doc.docstatus or 0) != 1:
        return
    if not _get_parent_ticket(doc):
        frappe.log_error(
            title="GMAO MI PDF: missing Service Ticket",
            message=f"Submitted MI {doc.name} has no linked Service Ticket or TM ticket.",
        )
        return
    frappe.enqueue(
        "maintenance_app.notifications.mi_report_attachment.attach_submitted_mi_pdf",
        queue="long",
        timeout=300,
        enqueue_after_commit=True,
        mi_name=doc.name,
        job_name=f"gmao-mi-pdf-{doc.name}",
    )


def attach_submitted_mi_pdf(mi_name):
    """Idempotent worker / manual retry: one private MI PDF per ST and MI."""
    mi = frappe.get_doc("Mission Intervention", mi_name)
    if int(mi.docstatus or 0) != 1:
        return "SKIPPED_NOT_SUBMITTED"
    ticket = _get_parent_ticket(mi)
    if not ticket or not frappe.db.exists("Service Ticket", ticket):
        frappe.log_error(
            title="GMAO MI PDF: invalid Service Ticket",
            message=f"MI {mi.name}: Service Ticket {ticket!r} was not found.",
        )
        return "SKIPPED_MISSING_TICKET"

    filename = f"MI-{mi.name}.pdf"
    # save_file may append a content-hash suffix to a filename already in use.
    # Accept either our exact name or that suffix on retries.
    existing_files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Service Ticket",
            "attached_to_name": ticket,
        },
        pluck="file_name",
        limit_page_length=0,
    )
    prefix = filename[:-4]
    if any(
        existing == filename or (
            existing.startswith(prefix + "-") and existing.endswith(".pdf")
        )
        for existing in existing_files
    ):
        return "ALREADY_ATTACHED"

    # The same format used for emailing MI reports in the technician portal.
    # Read the configured PDF engine instead of falling back
    # to wkhtmltopdf in the background worker.
    pdf_generator = frappe.db.get_single_value(
        "Print Settings", "pdf_generator"
    )
    if not pdf_generator:
        frappe.throw("Configure PDF Generator in Print Settings.")

    pdf = frappe.get_print(
        "Mission Intervention",
        mi.name,
        print_format=None,
        as_pdf=True,
        pdf_generator=pdf_generator,
    )
    if not pdf:
        frappe.throw(f"The MI print was empty for {mi.name}")

    save_file(
        fname=filename,
        content=pdf,
        dt="Service Ticket",
        dn=ticket,
        is_private=1,
    )
    return "ATTACHED"
