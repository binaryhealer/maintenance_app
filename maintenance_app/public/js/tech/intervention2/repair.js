(function () {

    "use strict";

    function el(id) {
        return document.getElementById(id);
    }

    function showError(r) {
        let message = "Something went wrong.";

        if (r && r.message && typeof r.message === "string") {
            message = r.message;
        }

        if (r && r._server_messages) {
            try {
                const messages = JSON.parse(r._server_messages);

                if (messages && messages.length) {
                    const row = JSON.parse(messages[0]);

                    if (row && row.message) {
                        message = row.message;
                    }
                }
            } catch (e) {}
        }

        frappe.msgprint(message);
    }

    function setMessage(message) {
        const box = el("tech2-repair-message");

        if (!box) {
            return;
        }

        box.textContent = message || "";
    }

    function setBusy(busy) {
        const button = el("tech2-repair-continue");

        if (!button) {
            return;
        }

        button.disabled = !!busy;

        button.textContent = busy
            ? "Saving..."
            : "Continue to Finish Work";
    }

    function loadFaultTypes() {
        const select = el("tech2-repair-fault-type");

        if (!select) {
            return;
        }

        frappe.call({
            method: "frappe.client.get_list",

            args: {
                doctype: "Fault Type",
                fields: ["name"],
                limit_page_length: 500,
                order_by: "name asc"
            },

            callback: function (r) {

                const rows = r.message || [];

                select.innerHTML =
                    '<option value="">Select Fault Type</option>';

                rows.forEach(function (row) {

                    const option =
                        document.createElement("option");

                    option.value = row.name;
                    option.textContent = row.name;

                    if (
                        row.name
                        === window.TECH2_REPAIR_CURRENT_FAULT_TYPE
                    ) {
                        option.selected = true;
                    }

                    select.appendChild(option);
                });
            },

            error: showError
        });
    }

    window.tech2SaveRepairFaultType =
        function () {

            if (window.TECH2_REPAIR_SUBMITTED) {
                return;
            }

            const miName =
                window.TECH2_REPAIR_MI_NAME;

            const select =
                el("tech2-repair-fault-type");

            const faultType =
                select ? select.value : "";

            if (!faultType) {
                frappe.msgprint(
                    "Please select Fault Type."
                );
                return;
            }

            setBusy(true);
            setMessage("");

            frappe.call({
                method: "frappe.client.get",

                args: {
                    doctype: "Mission Intervention",
                    name: miName
                },

                callback: function (r) {

                    if (!r.message) {
                        setBusy(false);
                        setMessage(
                            "Could not load the intervention."
                        );
                        return;
                    }

                    const doc = r.message;

                    doc.custom_fault_type = faultType;

                    frappe.call({
                        method: "frappe.client.save",

                        args: {
                            doc: doc
                        },

                        callback: function () {

                            window.location.href =
                                "/tech/intervention2?name="
                                + encodeURIComponent(miName)
                                + "&step=finish";
                        },

                        error: function (r2) {
                            setBusy(false);
                            showError(r2);
                        }
                    });
                },

                error: function (r) {
                    setBusy(false);
                    showError(r);
                }
            });
        };

    document.addEventListener(
        "DOMContentLoaded",
        function () {

            if (
                el("tech2-repair-fault-type")
            ) {
                loadFaultTypes();
            }
        }
    );

})();
