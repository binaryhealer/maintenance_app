import frappe
from frappe.utils import now_datetime, flt

@frappe.whitelist()
def tech_check_in(ticket_id, lat, lon):
    # 1. Geo-fencing Check (Logic we discussed)
    ticket = frappe.get_doc("HD Ticket", ticket_id)
    # [Insert distance calculation logic here as per previous chat]
    
    # 2. Add Row to 'Service Logs' Child Table
    # We use frappe.session.user directly as the 'tech'
    ticket.append("service_logs", {
        "tech": frappe.session.user,
        "check_in_time": now_datetime(),
        "check_in_lat_log": f"{lat}, {lon}"
    })
    
    ticket.save(ignore_permissions=True)
    return _("Check-in successful")
