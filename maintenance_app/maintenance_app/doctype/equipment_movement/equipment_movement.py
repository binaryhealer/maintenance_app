import frappe
from frappe.model.document import Document

class EquipmentMovement(Document):
    def validate(self):
        if self.get("custom_applied"):
            frappe.throw("An applied Equipment Movement cannot be edited.")
