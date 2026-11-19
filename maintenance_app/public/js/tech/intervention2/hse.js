(function () {

    "use strict";

    let incidentTypes = [];

    function el(id) {
        return document.getElementById(id);
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
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

    function severityClass(severity) {
        const value = (severity || "").toLowerCase();

        if (value === "low") return "is-low";
        if (value === "medium") return "is-medium";
        if (value === "high") return "is-high";
        if (value === "critical") return "is-critical";

        return "";
    }

    window.tech2LoadHSEIncidents = function () {

        const miName = window.TECH2_HSE_MI_NAME;
        const container = el("tech2-hse-incident-list");

        if (!miName || !container) {
            return;
        }

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Mission Intervention",
                name: miName
            },
            callback: function (r) {

                const doc = r.message || {};
                const incidents = doc.custom_incidents || [];

                container.innerHTML = "";

                if (!incidents.length) {
                    container.innerHTML =
                        '<div class="hse3-empty">'
                        + '<strong>No incident reported</strong>'
                        + '<span>No HSE incidents have been recorded '
                        + 'for this intervention.</span>'
                        + '</div>';
                    return;
                }

                incidents.forEach(function (row) {

                    const severity =
                        row.custom_severity || "-";

                    const photo = row.custom_photo
                        ? '<a class="hse3-photo" href="'
                            + escapeHtml(row.custom_photo)
                            + '" target="_blank">View photo</a>'
                        : "";

                    const investigation =
                        row.custom_requires_investigation
                            ? '<span class="hse3-investigate">'
                                + 'Requires investigation'
                                + '</span>'
                            : "";

                    const html =
                        '<div class="hse3-row">'
                        + '<div class="hse3-row-head">'
                        + '<div>'
                        + '<div class="hse3-date">'
                        + escapeHtml(
                            row.custom_incident_datetime || ""
                        )
                        + '</div>'
                        + '<div class="hse3-type">'
                        + escapeHtml(
                            row.custom_incident_type_name
                            || "Incident"
                        )
                        + '</div>'
                        + '</div>'
                        + '<span class="hse3-severity '
                        + severityClass(severity)
                        + '">'
                        + escapeHtml(severity)
                        + '</span>'
                        + '</div>'

                        + (investigation
                            ? '<div class="hse3-flags">'
                                + investigation
                                + '</div>'
                            : '')

                        + '<div class="hse3-detail">'
                        + '<span>Description</span>'
                        + '<p>'
                        + escapeHtml(
                            row.custom_description || "-"
                        )
                        + '</p>'
                        + '</div>'

                        + '<div class="hse3-detail">'
                        + '<span>Immediate action</span>'
                        + '<p>'
                        + escapeHtml(
                            row.custom_immediate_action || "-"
                        )
                        + '</p>'
                        + '</div>'

                        + photo
                        + '</div>';

                    container.insertAdjacentHTML(
                        "beforeend",
                        html
                    );
                });
            },
            error: showError
        });
    };


    function loadIncidentTypes(callback) {

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "HSE Incident Type",
                fields: [
                    "name",
                    "custom_incident_type_name",
                    "custom_default_severity",
                    "custom_requires_investigation_by_default"
                ],
                limit_page_length: 200
            },
            callback: function (r) {
                incidentTypes = r.message || [];

                if (callback) {
                    callback();
                }
            },
            error: showError
        });
    }


    function populateIncidentTypes() {

        const select = el("tech2-hse-incident-type");

        if (!select) {
            return;
        }

        select.innerHTML =
            '<option value="">Select incident type</option>';

        incidentTypes.forEach(function (row) {

            const option =
                document.createElement("option");

            option.value = row.name;

            option.textContent =
                row.custom_incident_type_name
                || row.name;

            option.setAttribute(
                "data-severity",
                row.custom_default_severity || ""
            );

            option.setAttribute(
                "data-investigation",
                row.custom_requires_investigation_by_default
                    ? "1"
                    : "0"
            );

            select.appendChild(option);
        });
    }


    window.tech2HSEIncidentTypeChange =
        function () {

            const select =
                el("tech2-hse-incident-type");

            const selected =
                select
                    ? select.options[select.selectedIndex]
                    : null;

            el("tech2-hse-severity").value =
                selected
                    ? (
                        selected.getAttribute(
                            "data-severity"
                        ) || ""
                    )
                    : "";

            el("tech2-hse-investigation").checked =
                selected
                    ? (
                        selected.getAttribute(
                            "data-investigation"
                        ) === "1"
                    )
                    : false;
        };


    window.tech2ShowHSEIncidentModal =
        function () {

            if (window.TECH2_HSE_MI_SUBMITTED) {
                frappe.msgprint(
                    "Submitted intervention incidents are locked."
                );
                return;
            }

            function openModal() {

                populateIncidentTypes();

                el("tech2-hse-incident-type").value = "";
                el("tech2-hse-severity").value = "";
                el("tech2-hse-investigation").checked = false;
                el("tech2-hse-description").value = "";
                el("tech2-hse-action").value = "";
                el("tech2-hse-photo").value = "";

                const dt =
                    frappe.datetime.now_datetime();

                el("tech2-hse-datetime").value =
                    dt
                        ? dt.replace(" ", "T").slice(0, 16)
                        : "";

                el("tech2-hse-modal").style.display =
                    "flex";
            }

            if (!incidentTypes.length) {
                loadIncidentTypes(openModal);
            } else {
                openModal();
            }
        };


    window.tech2CloseHSEIncidentModal =
        function () {

            const modal =
                el("tech2-hse-modal");

            if (modal) {
                modal.style.display = "none";
            }
        };


    function uploadIncidentPhoto(callback) {

        const input =
            el("tech2-hse-photo");

        const miName =
            window.TECH2_HSE_MI_NAME;

        if (
            !input
            || !input.files
            || !input.files.length
        ) {
            callback("");
            return;
        }

        const formData =
            new FormData();

        formData.append(
            "file",
            input.files[0]
        );

        formData.append(
            "is_private",
            "0"
        );

        formData.append(
            "doctype",
            "Mission Intervention"
        );

        formData.append(
            "docname",
            miName
        );

        formData.append(
            "folder",
            "Home/Attachments"
        );

        fetch(
            "/api/method/upload_file",
            {
                method: "POST",
                body: formData,
                headers: {
                    "X-Frappe-CSRF-Token":
                        frappe.csrf_token
                }
            }
        )
        .then(function (response) {
            return response.json();
        })
        .then(function (data) {

            if (data.exc) {
                frappe.msgprint(
                    "Incident photo upload failed."
                );
                callback("");
                return;
            }

            const url =
                data.message
                && data.message.file_url
                    ? data.message.file_url
                    : "";

            callback(url);
        })
        .catch(function () {

            frappe.msgprint(
                "Incident photo upload failed."
            );

            callback("");
        });
    }


    window.tech2SubmitHSEIncident =
        function () {

            if (window.TECH2_HSE_MI_SUBMITTED) {
                return;
            }

            const miName =
                window.TECH2_HSE_MI_NAME;

            const incidentType =
                el("tech2-hse-incident-type").value;

            const severity =
                el("tech2-hse-severity").value;

            const requiresInvestigation =
                el("tech2-hse-investigation").checked
                    ? 1
                    : 0;

            const incidentDatetime =
                el("tech2-hse-datetime").value;

            const description =
                el("tech2-hse-description").value;

            const immediateAction =
                el("tech2-hse-action").value;

            if (!incidentType) {
                frappe.msgprint(
                    "Please select incident type."
                );
                return;
            }

            if (
                !description
                || !description.trim()
            ) {
                frappe.msgprint(
                    "Please enter incident description."
                );
                return;
            }

            if (
                !immediateAction
                || !immediateAction.trim()
            ) {
                frappe.msgprint(
                    "Please enter immediate action taken."
                );
                return;
            }

            uploadIncidentPhoto(
                function (photoUrl) {

                    frappe.call({
                        method:
                            "frappe.client.get",

                        args: {
                            doctype:
                                "Mission Intervention",
                            name:
                                miName
                        },

                        freeze:
                            true,

                        freeze_message:
                            "Saving incident...",

                        callback:
                            function (r) {

                                if (!r.message) {
                                    return;
                                }

                                const doc =
                                    r.message;

                                if (!doc.custom_incidents) {
                                    doc.custom_incidents = [];
                                }

                                doc.custom_incidents.push({
                                    custom_incident_type_name:
                                        incidentType,

                                    custom_severity:
                                        severity,

                                    custom_incident_datetime:
                                        incidentDatetime
                                            ? incidentDatetime.replace(
                                                "T",
                                                " "
                                            )
                                            : frappe.datetime
                                                .now_datetime(),

                                    custom_description:
                                        description,

                                    custom_immediate_action:
                                        immediateAction,

                                    custom_requires_investigation:
                                        requiresInvestigation,

                                    custom_photo:
                                        photoUrl
                                });

                                frappe.call({
                                    method:
                                        "frappe.client.save",

                                    args: {
                                        doc: doc
                                    },

                                    callback:
                                        function () {

                                            frappe.show_alert({
                                                message:
                                                    "HSE incident saved",
                                                indicator:
                                                    "green"
                                            });

                                            window
                                                .tech2CloseHSEIncidentModal();

                                            window
                                                .tech2LoadHSEIncidents();
                                        },

                                    error:
                                        showError
                                });
                            },

                        error:
                            showError
                    });
                }
            );
        };


    document.addEventListener(
        "DOMContentLoaded",
        function () {

            if (
                el("tech2-hse-incident-list")
            ) {
                window.tech2LoadHSEIncidents();
            }
        }
    );

})();
