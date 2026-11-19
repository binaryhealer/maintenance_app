(function () {
    "use strict";

    function el(id) {
        return document.getElementById(id);
    }


    window.tech2OutcomeChanged = function () {

        const outcome =
            el("tech2-work-outcome")?.value || "";

        const couldNotComplete =
            el("tech2-could-not-complete");

        const otherEquipmentWrap =
            el("tech2-other-equipment-wrap");

        if (otherEquipmentWrap) {
            otherEquipmentWrap.style.display =
                outcome === "Could Not Complete"
                    ? "block"
                    : "none";
        }

        const movement =
            el("tech2-swap-movement");

        const waitingClient =
            el("tech2-waiting-client");

        if (waitingClient) {
            waitingClient.style.display =
                outcome === "Waiting for Client"
                    ? "block"
                    : "none";
        }


        if (couldNotComplete) {
            couldNotComplete.style.display =
                outcome === "Could Not Complete"
                    ? "block"
                    : "none";
        }


        const showSwapMovement =
            window.TECH2_INTERVENTION_TYPE === "Swap"
            && outcome === "Continue Work"
            && [
                "Collection from Source",
                "Exchange at Swap Branch"
            ].includes(
                window.TECH2_SWAP_STAGE
            );

        if (movement) {
            movement.style.display =
                showSwapMovement
                    ? "block"
                    : "none";
        }


        window.tech2ExceptionActionChanged();
    };



    window.tech2CNCReasonChanged = function () {

        const reason =
            el("tech2-could-not-complete-reason")?.value
            || "";

        const planning =
            el("tech2-additional-planning");

        const rm =
            el("tech2-rm-attention");

        const mapping = {
            "Specialist Required": {
                planning: true,
                rm: true
            },
            "Different Technician Required": {
                planning: true,
                rm: true
            },
            "Required Tool / Equipment Unavailable": {
                planning: true,
                rm: true
            },
            "Unable to Access Equipment": {
                planning: true,
                rm: true
            },
            "Client / Site Access Issue": {
                planning: true,
                rm: true
            },
            "Unsafe to Continue": {
                planning: false,
                rm: true
            },
            "Wrong Equipment / Component": {
                planning: true,
                rm: true
            },
            "Move to Workshop Required": {
                planning: true,
                rm: true
            }
        };

        const values = mapping[reason];

        if (values) {
            if (planning) {
                planning.checked = values.planning;
            }

            if (rm) {
                rm.checked = values.rm;
            }
        } else if (reason !== "Other") {
            if (planning) {
                planning.checked = false;
            }

            if (rm) {
                rm.checked = false;
            }
        }

        window.tech2ExceptionActionChanged();
    };


    window.tech2ExceptionActionChanged =
        function () {

            const planning =
                !!el("tech2-additional-planning")?.checked;

            const rm =
                !!el("tech2-rm-attention")?.checked;

            const wrap =
                el("tech2-planning-note-wrap");

            if (wrap) {
                wrap.style.display =
                    planning || rm
                        ? "block"
                        : "none";
            }
        };


    window.tech2SaveWorkOutcome =
        function (miName) {

            const outcome =
                el("tech2-work-outcome")?.value || "";

            const workProgress =
                el("tech2-work-progress")?.value.trim()
                || "";

            const waitingClientReason =
                el("tech2-waiting-client-reason")
                    ?.value.trim() || "";

            const clientActionRequired =
                el("tech2-client-action-required")
                    ?.value.trim() || "";

            const otherEquipment =
                el("tech2-other-equipment")?.value || "";

            const couldReason =
                el(
                    "tech2-could-not-complete-reason"
                )?.value || "";

            const additionalPlanning =
                el("tech2-additional-planning")?.checked
                    ? 1
                    : 0;

            const rmAttention =
                el("tech2-rm-attention")?.checked
                    ? 1
                    : 0;

            const planningNote =
                el(
                    "tech2-planning-request-note"
                )?.value.trim()
                || "";

            const equipmentMoving =
                el(
                    "tech2-equipment-being-moved"
                )?.checked
                    ? 1
                    : 0;


            if (!outcome) {
                frappe.msgprint(
                    "Please select Work Outcome."
                );
                return;
            }


            if (!workProgress) {
                frappe.msgprint(
                    "Please enter Technical Progress Notes."
                );
                return;
            }


            if (
                outcome === "Waiting for Client"
                && !waitingClientReason
            ) {
                frappe.msgprint(
                    "Please explain why we are waiting for the client."
                );
                return;
            }

            if (
                outcome === "Waiting for Client"
                && !clientActionRequired
            ) {
                frappe.msgprint(
                    "Please explain what action is required from the client."
                );
                return;
            }

            if (
                outcome === "Could Not Complete"
                && !["Yes", "No"].includes(otherEquipment)
            ) {
                frappe.msgprint(
                    "Please confirm whether you have other equipment to work on."
                );
                return;
            }

            if (
                outcome === "Could Not Complete"
                && !couldReason
            ) {
                frappe.msgprint(
                    "Please select why the work could not be completed."
                );
                return;
            }


            if (
                outcome === "Could Not Complete"
                && (
                    additionalPlanning
                    || rmAttention
                )
                && !planningNote
            ) {
                frappe.msgprint(
                    "Please explain the action required from RM / Planning."
                );
                return;
            }


            const button =
                el("tech2-save-outcome");

            if (button) {
                button.disabled = true;
                button.textContent = "Saving...";
            }


            frappe.call({
                method:
                    "maintenance_app.www.tech.intervention2.index.save_work_outcome_v2",

                args: {
                    mi_name: miName,
                    outcome: outcome,
                    work_progress: workProgress,

                    waiting_client_reason:
                        waitingClientReason,

                    client_action_required:
                        clientActionRequired,

                    could_not_complete_reason:
                        couldReason,

                    other_equipment_to_work_on:
                        otherEquipment,

                    additional_planning_required:
                        additionalPlanning,

                    rm_attention_required:
                        rmAttention,

                    planning_request_note:
                        planningNote,

                    equipment_being_moved:
                        equipmentMoving
                },

                freeze: true,
                freeze_message:
                    __("Completing Work..."),

                callback: function (r) {

                    if (!r.message?.ok) {
                        if (button) {
                            button.disabled = false;
                            button.textContent =
                                "Complete Work";
                        }
                        return;
                    }

                    /*
                     * Work details are now saved.
                     *
                     * Complete the technical work stage through
                     * the shared backend method used by PWA /
                     * future mobile clients.
                     *
                     * This stamps custom_completed_time.
                     */
                    frappe.call({
                        method:
                            "maintenance_app.api." +
                            "complete_mission_intervention_work",

                        args: {
                            mi_name: miName
                        },

                        freeze: true,
                        freeze_message:
                            __("Completing Work..."),

                        callback: function (r2) {

                            if (!r2.message?.ok) {
                                if (button) {
                                    button.disabled = false;
                                    button.textContent =
                                        "Complete Work";
                                }
                                return;
                            }

                            frappe.show_alert({
                                message:
                                    __("Work completed"),
                                indicator: "green"
                            });

                            window.location.href =
                                "/tech/intervention2?name="
                                + encodeURIComponent(miName)
                                + "&step=checkout";
                        },

                        error: function () {
                            if (button) {
                                button.disabled = false;
                                button.textContent =
                                    "Complete Work";
                            }
                        }
                    });
                },

                error: function () {

                    if (button) {
                        button.disabled = false;
                        button.textContent =
                            "Complete Work";
                    }
                }
            });
        };


    document.addEventListener(
        "DOMContentLoaded",
        function () {
            window.tech2OutcomeChanged();
        }
    );

})();
