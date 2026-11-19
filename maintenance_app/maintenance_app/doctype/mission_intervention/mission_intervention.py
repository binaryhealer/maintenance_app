# Copyright (c) 2026, Gotech Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MissionIntervention(Document):

    def before_insert(self):
        self._check_parent_mission_open()

    def validate(self):
        self._check_parent_mission_open()

    def before_submit(self):
        self._check_parent_mission_open()
        from maintenance_app.equipment_movement import validate_movement_before_mi_submit
        validate_movement_before_mi_submit(self)

    def _check_parent_mission_open(self):
        mission_name = self.get("custom_parent_mission")

        if not mission_name:
            return

        # Use the same parent-row lock as Finish Mission.
        # This serializes normal MI saves/submissions against
        # mission finalization.
        rows = frappe.db.sql(
            """
            SELECT custom_mission_status
            FROM `tabTech Mission`
            WHERE name = %s
            FOR UPDATE
            """,
            (mission_name,),
            as_dict=True,
        )

        if not rows:
            frappe.throw(
                "Linked Tech Mission does not exist: {0}"
                .format(mission_name)
            )

        status = rows[0].custom_mission_status

        if status in ("Completed", "Closed", "Cancelled"):
            frappe.throw(
                "Tech Mission {0} is {1}. "
                "No new or additional intervention work is allowed. "
                "Create a new Tech Mission from the Service Ticket."
                .format(mission_name, status)
            )
