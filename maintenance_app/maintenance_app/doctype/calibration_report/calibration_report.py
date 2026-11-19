from frappe.model.document import Document
from maintenance_app.calibration_batch import validate_report


class CalibrationReport(Document):
    def validate(self):
        validate_report(self)

    def before_submit(self):
        validate_report(self)

    def on_submit(self):
        from maintenance_app.notifications.calibration_pdf_attachment import queue_calibration_report_pdf_on_submit
        queue_calibration_report_pdf_on_submit(self)
