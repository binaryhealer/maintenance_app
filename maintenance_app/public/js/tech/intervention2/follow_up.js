(function () {

    "use strict";

    function el(id) {
        return document.getElementById(id);
    }

    function tomorrowLocalDate() {
        const now = new Date();
        now.setDate(now.getDate() + 1);

        const year = now.getFullYear();
        const month =
            String(now.getMonth() + 1).padStart(2, "0");
        const day =
            String(now.getDate()).padStart(2, "0");

        return year + "-" + month + "-" + day;
    }

    function setBusy(busy) {
        const button = el("tech2-create-follow-up");

        if (!button) {
            return;
        }

        button.disabled = !!busy;
        button.textContent = busy
            ? "Creating..."
            : "Create Follow-up MI";
    }

    window.tech2OpenFollowUpModal = function () {
        const modal = el("tech2-follow-up-modal");
        const date = el("tech2-follow-up-date");

        if (!modal) {
            return;
        }

        if (date && !date.value) {
            date.value = tomorrowLocalDate();
        }

        modal.style.display = "flex";
    };

    window.tech2CloseFollowUpModal = function () {
        const modal = el("tech2-follow-up-modal");

        if (modal) {
            modal.style.display = "none";
        }
    };

    window.tech2CreateFollowUpMI = function () {

        const sourceMi =
            window.TECH2_FOLLOW_UP_SOURCE_MI || "";

        const date =
            el("tech2-follow-up-date")?.value || "";

        const reason =
            el("tech2-follow-up-reason")?.value.trim() || "";

        if (!sourceMi) {
            frappe.msgprint(
                "Source intervention is missing."
            );
            return;
        }

        if (!date) {
            frappe.msgprint(
                "Please select the next planned work date."
            );
            return;
        }

        if (!reason) {
            frappe.msgprint(
                "Please enter the continuation reason or plan."
            );
            return;
        }

        setBusy(true);

        frappe.call({
            method:
                "maintenance_app.www.tech.intervention2.index."
                + "create_follow_up_mi_v2",

            args: {
                source_mi_name: sourceMi,
                follow_up_date: date,
                reason: reason
            },

            freeze: true,
            freeze_message:
                __("Creating follow-up MI..."),

            callback: function (r) {

                const result = r.message || {};

                if (!result.intervention) {
                    setBusy(false);
                    frappe.msgprint(
                        "The server did not return a follow-up MI."
                    );
                    return;
                }

                window.tech2CloseFollowUpModal();

                frappe.show_alert({
                    message:
                        result.created === false
                            ? __("Existing follow-up MI opened")
                            : __("Follow-up MI created"),
                    indicator: "green"
                });

                window.location.href =
                    "/tech/intervention2?name="
                    + encodeURIComponent(
                        result.intervention
                    )
                    + "&step=job";
            },

            error: function () {
                setBusy(false);
            }
        });
    };

    document.addEventListener(
        "DOMContentLoaded",
        function () {

            const date = el("tech2-follow-up-date");

            if (date && !date.value) {
                date.value = tomorrowLocalDate();
            }

            if (
                window.TECH2_AUTO_OPEN_FOLLOW_UP
                && el("tech2-follow-up-modal")
            ) {
                setTimeout(
                    window.tech2OpenFollowUpModal,
                    150
                );
            }
        }
    );

})();
