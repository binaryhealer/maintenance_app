import frappe
from frappe.utils import get_distance

@frappe.whitelist()
def check_geofence(ticket_id, user_lat, user_lon):
    doc = frappe.get_doc("HD Ticket", ticket_id)
    target_lat, target_lon = None, None

    # Logic to find the correct coordinates based on your Hybrid setup
    if doc.custom_location_type == "Branch":
        branch_coords = frappe.db.get_value("Client Branch", doc.custom_client_branch, 
                                          ["custom_latitude", "custom_longitude"], as_dict=1)
        target_lat = branch_coords.custom_latitude
        target_lon = branch_coords.custom_longitude
    
    else:
        # Fallback: Look for the Customer's Primary Address in ERPNext
        address_name = frappe.db.get_value("Dynamic Link", 
                                         {"link_doctype": "Customer", "link_name": doc.customer}, "parent")
        if address_name:
            addr = frappe.get_doc("Address", address_name)
            target_lat, target_lon = addr.latitude, addr.longitude

    if not target_lat or not target_lon:
        return {"allowed": False, "error": "No GPS coordinates found for this location."}

    # Calculate distance (500 meters = 0.5 km)
    dist = get_distance((target_lat, target_lon), (user_lat, user_lon))
    
    return {"allowed": dist <= 0.5, "distance": dist}
@frappe.whitelist()
def check_asset_health(asset_id):
    # Count tickets for this asset in the last 30 days
    thirty_days_ago = frappe.utils.add_days(frappe.utils.nowdate(), -30)
    
    ticket_count = frappe.db.count("HD Ticket", {
        "custom_target_asset": asset_id,
        "creation": [">", thirty_days_ago],
        "docstatus": ["<", 2] # Exclude cancelled tickets
    })

    status = "Healthy"
    color = "green"
    message = "Equipment is performing normally."

    if ticket_count >= 5:
        status = "LEMON ALERT"
        color = "red"
        message = f"CRITICAL: This asset has failed {ticket_count} times in 30 days!"
    elif ticket_count >= 3:
        status = "UNSTABLE"
        color = "orange"
        message = f"WARNING: This asset has been serviced {ticket_count} times recently."

    return {
        "status": status,
        "color": color,
        "message": message,
        "count": ticket_count
    }
