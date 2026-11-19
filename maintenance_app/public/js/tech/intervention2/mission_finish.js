(function () {
    "use strict";

    function element(name) {
        return document.getElementById(name);
    }

    function addLine(container, value, bold) {
        const line = document.createElement("div");
        line.style.marginBottom = "8px";

        if (bold) {
            const strong = document.createElement("strong");
            strong.textContent = value;
            line.appendChild(strong);
        } else {
            line.textContent = value;
        }

        container.appendChild(line);
    }

    window.tech2ReviewMission = function () {
        const panel = element("tech2-mission-finish-panel");
        const result = element("tech2-mission-finish-result");
        const button = element("tech2-review-mission");

        if (!panel || !result || !button) {
            return;
        }

        const mission = panel.dataset.mission;

        if (!mission) {
            frappe.msgprint("No Tech Mission linked to this MI.");
            return;
        }

        button.disabled = true;
        result.style.display = "block";
        result.textContent = "Checking mission readiness...";

        frappe.call({
            method:
                "maintenance_app.mission_finalization."
                + "get_tech_mission_finish_readiness",
            args: {
                mission_name: mission
            },
            callback: function (response) {
                button.disabled = false;

                const data = response.message;
                result.replaceChildren();

                if (!data) {
                    addLine(result, "Unable to retrieve mission review.");
                    return;
                }

                addLine(result, "Mission: " + data.mission, true);

                addLine(
                    result,
                    "Submitted interventions: "
                    + data.submitted_mi_count
                );

                if (data.blockers && data.blockers.length) {
                    addLine(result, "Items requiring attention:", true);

                    data.blockers.forEach(function (item) {
                        addLine(result, "• " + item);
                    });
                }

                if (data.exceptions && data.exceptions.length) {
                    addLine(result, "Outstanding work:", true);

                    data.exceptions.forEach(function (item) {
                        addLine(
                            result,
                            "• " + item.equipment + " — "
                            + item.outcome + " (" + item.mi + ")"
                        );
                    });
                }

                if (data.ready_for_finish) {
                    addLine(
                        result,
                        "Ready for Finish Mission: "
                        + data.suggested_final_status,
                        true
                    );
                    const confirmButton =
                        document.createElement("button");

                    confirmButton.type = "button";
                    confirmButton.textContent = "Confirm Finish Mission";
                    confirmButton.className = "btn btn-primary";

                    confirmButton.style.cssText =
                        "display:inline-block;background:#2563eb;" +
                        "color:white;border:1px solid #2563eb;" +
                        "border-radius:8px;padding:12px 24px;" +
                        "font-weight:600;cursor:pointer;margin-top:12px;";

                    confirmButton.onclick = function () {
                        window.tech2ConfirmFinishMission(
                            mission, confirmButton
                        );
                    };

                    result.appendChild(confirmButton);
                } else {
                    addLine(
                        result,
                        "Mission cannot yet be finalized.",
                        true
                    );
                }
            },
            error: function () {
                button.disabled = false;
                result.textContent =
                    "Unable to check readiness. "
                    + "Verify technician access to this mission.";
            }
        });
    };

    window.tech2ConfirmFinishMission = function (mission, button) {
        if (!mission || !button || button.disabled) {
            return;
        }

        frappe.confirm(
            "Finish this Tech Mission? Once finalized, " +
            "no further interventions can be added to it. " +
            "Any unresolved customer work will remain on the " +
            "Service Ticket for RM follow-up.",
            function () {
                button.disabled = true;
                button.textContent = "Finalizing Mission...";

                frappe.call({
                    method:
                        "maintenance_app.mission_finalization." +
                        "finalize_tech_mission",
                    args: {
                        mission_name: mission
                    },
                    freeze: true,
                    freeze_message: "Finishing Tech Mission...",
                    callback: function (response) {
                        const data = response.message;

                        if (!data || !data.ok) {
                            button.disabled = false;
                            button.textContent =
                                "Confirm Finish Mission";
                            frappe.msgprint(
                                "Mission could not be finalized."
                            );
                            return;
                        }

                        frappe.msgprint({
                            title: "Mission Finalized",
                            message:
                                "Tech Mission " + data.mission +
                                " is now " + data.mission_status +
                                (data.hold_reason
                                    ? ". Reason: " + data.hold_reason
                                    : "."),
                            indicator: "green",
                            primary_action: {
                                label: "Return to Dashboard",
                                action: function () {
                                    window.location.href = "/tech";
                                }
                            }
                        });
                    },
                    error: function () {
                        button.disabled = false;
                        button.textContent =
                            "Confirm Finish Mission";
                    }
                });
            }
        );
    };

})();
