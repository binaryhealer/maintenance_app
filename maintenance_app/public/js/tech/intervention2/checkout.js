(function () {
    "use strict";


    function doCheckOut(
        miName,
        latitude,
        longitude,
        accuracy
    ) {
        frappe.call({
            method:
                "maintenance_app.www.tech.intervention2.index.pwa_check_out_v2",

            args: {
                mi_name: miName,
                latitude: latitude || null,
                longitude: longitude || null,
                accuracy: accuracy || null
            },

            freeze: true,
            freeze_message:
                __("Checking Out..."),

            callback: function (r) {

                if (!r.message?.ok) {
                    return;
                }

                window.location.reload();
            }
        });
    }


    window.tech2CheckOut =
        function (miName) {

            if (!navigator.geolocation) {
                doCheckOut(
                    miName,
                    null,
                    null,
                    null
                );

                return;
            }

            navigator.geolocation
                .getCurrentPosition(

                    function (position) {
                        doCheckOut(
                            miName,
                            position.coords.latitude,
                            position.coords.longitude,
                            position.coords.accuracy
                        );
                    },

                    function () {

                        frappe.confirm(
                            __(
                                "Location could not be obtained. Continue Check Out without GPS?"
                            ),
                            function () {
                                doCheckOut(
                                    miName,
                                    null,
                                    null,
                                    null
                                );
                            }
                        );
                    },

                    {
                        enableHighAccuracy: true,
                        timeout: 12000,
                        maximumAge: 30000
                    }
                );
        };



    window.tech2SubmitIntervention =
        function (miName) {

            const outcome =
                window.TECH2_SUBMIT_WORK_OUTCOME || "";

            let followUpDate = "";
            let followUpStartTime = "";
            let followUpEndTime = "";
            let followUpReason = "";

            if (outcome === "Continue Work") {

                const dateField =
                    document.getElementById(
                        "tech2-follow-up-date"
                    );

                const startField =
                    document.getElementById(
                        "tech2-follow-up-start-time"
                    );

                const endField =
                    document.getElementById(
                        "tech2-follow-up-end-time"
                    );

                const reasonField =
                    document.getElementById(
                        "tech2-follow-up-reason"
                    );

                followUpDate =
                    dateField ? dateField.value : "";

                followUpStartTime =
                    startField ? startField.value : "";

                followUpEndTime =
                    endField ? endField.value : "";

                followUpReason =
                    reasonField
                        ? reasonField.value.trim()
                        : "";

                if (!followUpDate) {
                    frappe.msgprint(
                        "Please select the Next Planned Work Date."
                    );
                    return;
                }

                if (!followUpStartTime) {
                    frappe.msgprint(
                        "Please select the Start Time."
                    );
                    return;
                }

                if (!followUpEndTime) {
                    frappe.msgprint(
                        "Please select the End Time."
                    );
                    return;
                }

                if (followUpEndTime <= followUpStartTime) {
                    frappe.msgprint(
                        "End Time must be after Start Time."
                    );
                    return;
                }

                if (!followUpReason) {
                    frappe.msgprint(
                        "Please enter the Continuation Reason / Plan."
                    );
                    return;
                }
            }

            frappe.confirm(
                __(
                    "Submit this intervention? You will not be able to edit it afterwards."
                ),

                function () {

                    const method =
                        outcome === "Continue Work"
                            ? "maintenance_app.www.tech.intervention2.index.submit_continue_work_v2"
                            : "maintenance_app.www.tech.intervention2.index.submit_intervention_v2";

                    const args = {
                        mi_name: miName
                    };

                    if (outcome === "Continue Work") {
                        args.follow_up_date =
                            followUpDate;

                        args.follow_up_start_time =
                            followUpStartTime;

                        args.follow_up_end_time =
                            followUpEndTime;

                        args.reason =
                            followUpReason;
                    }

                    frappe.call({
                        method: method,
                        args: args,

                        freeze: true,
                        freeze_message:
                            outcome === "Continue Work"
                                ? __("Submitting and planning follow-up...")
                                : __("Submitting Intervention..."),

                        callback: function (r) {

                            const result =
                                r.message || {};

                            if (!result.ok) {
                                frappe.msgprint(
                                    result.message
                                    || "Submission could not be completed."
                                );
                                return;
                            }

                            frappe.show_alert({
                                message:
                                    outcome === "Continue Work"
                                        ? __("Intervention submitted and follow-up planned")
                                        : __("Intervention submitted"),
                                indicator:
                                    "green"
                            });

                            const nextAfterEmail = function () {
                                if (outcome === "Continue Work" && result.follow_up_intervention) {
                                    window.location.href = "/tech/intervention2?name="
                                        + encodeURIComponent(result.follow_up_intervention) + "&step=job";
                                    return;
                                }
                                if (result.calibration_followup) {
                                    window.location.href = "/tech/intervention2?name="
                                        + encodeURIComponent(miName) + "&step=submit";
                                    return;
                                }
                                window.location.href = "/tech";
                            };
                            if (typeof window.tech2EmailAfterSubmit === "function") {
                                window.tech2EmailAfterSubmit(miName, nextAfterEmail);
                            } else {
                                nextAfterEmail();
                            }
                        },

                        error: function () {
                            frappe.msgprint(
                                "Submission failed. Please check the server error."
                            );
                        }
                    });
                }
            );
        };


})();


window.tech2SaveActualType =
    function (miName) {

        const field =
            document.getElementById(
                "tech2-actual-ticket-type"
            );

        const actualType =
            field?.value || "";

        if (!actualType) {
            frappe.msgprint(
                "Please select Actual Ticket Type."
            );
            return;
        }

        frappe.call({
            method:
                "maintenance_app.www.tech.intervention2.index.save_actual_ticket_type_v2",

            args: {
                mi_name: miName,
                actual_ticket_type:
                    actualType
            },

            freeze: true,

            freeze_message:
                __("Saving Actual Ticket Type..."),

            callback: function (r) {

                if (!r.message?.ok) {
                    return;
                }

                window.location.href =
                    "/tech/intervention2?name="
                    + encodeURIComponent(miName)
                    + "&step=client";
            }
        });
    };


window.tech2ActualTypeChoiceChanged =
    function () {

        const selected =
            document.querySelector(
                'input[name="tech2-ticket-type-correct"]:checked'
            );

        const wrap =
            document.getElementById(
                "tech2-actual-type-wrap"
            );

        if (!wrap) {
            return;
        }

        wrap.style.display =
            selected?.value === "no"
                ? "block"
                : "none";
    };


window.tech2ConfirmActualType =
    function (miName, currentType) {

        const selected =
            document.querySelector(
                'input[name="tech2-ticket-type-correct"]:checked'
            );

        if (!selected) {
            frappe.msgprint(
                "Please confirm whether the Ticket Type was correct."
            );
            return;
        }

        let actualType = currentType || "";

        if (selected.value === "no") {

            actualType =
                document
                    .getElementById(
                        "tech2-actual-ticket-type"
                    )
                    ?.value
                || "";

            if (!actualType) {
                frappe.msgprint(
                    "Please select the Actual Ticket Type."
                );
                return;
            }
        }

        frappe.call({
            method:
                "maintenance_app.www.tech.intervention2.index.save_actual_ticket_type_v2",

            args: {
                mi_name: miName,
                actual_ticket_type: actualType
            },

            freeze: true,

            freeze_message:
                __("Saving Actual Ticket Type..."),

            callback: function (r) {

                if (!r.message?.ok) {
                    return;
                }

                window.location.href =
                    "/tech/intervention2?name="
                    + encodeURIComponent(miName)
                    + "&step=client";
            }
        });
    };
