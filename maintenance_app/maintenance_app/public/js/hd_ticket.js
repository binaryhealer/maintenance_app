frappe.ui.form.on('HD Ticket', {
    refresh: function(frm) {
        // Clear to prevent duplicates
        frm.remove_custom_button(__('Tech Check-in'));

        if (frm.doc.status !== 'Closed') {
            // Add the button to the "Actions" menu
            frm.add_custom_button(__('Tech Check-in'), function() {
                
                frappe.show_alert({message: __('Processing...'), indicator: 'blue'});

                frappe.call({
                    method: "maintenance_app.maintenance_app.maintenance_app.api.tech_check_in",
                    args: {
                        ticket_id: frm.doc.name,
                        lat: 0,
                        lon: 0
                    },
                    callback: function(r) {
                        frappe.msgprint(__('Check-in Successful'));
                        frm.reload_doc();
                    }
                });
            }, __("Actions")); 
        }
    }
});
