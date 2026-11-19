(function () {
    "use strict";

    function getSubtype() {
        const el =
            document.getElementById(
                "tech2-work-subtype"
            );

        return el
            ? (el.value || "").trim()
            : "";
    }


    window.tech2SaveWorkSetup =
        function (miName) {

            const subtype =
                getSubtype();

            if (
                window.TECH2_WORK_SETUP_REQUIRED
                && !subtype
            ) {
                frappe.msgprint(
                    "Please select the required work type."
                );

                return;
            }


            const button =
                document.getElementById(
                    "tech2-save-work-setup"
                );

            if (button) {
                button.disabled = true;
                button.textContent =
                    "Saving...";
            }


            frappe.call({
                method:
                    "maintenance_app.www.tech.intervention2.index.save_work_setup_v2",

                args: {
                    mi_name: miName,
                    subtype: subtype
                },

                freeze: true,
                freeze_message:
                    __("Saving Work Setup..."),

                callback: function (r) {

                    if (
                        !r.message
                        || !r.message.ok
                    ) {
                        if (button) {
                            button.disabled = false;
                            button.textContent =
                                "Save & Continue to Work";
                        }

                        return;
                    }

                    window.location.href =
                        "/tech/intervention2?name="
                        + encodeURIComponent(
                            miName
                        )
                        + "&step=work";
                },

                error: function () {

                    if (button) {
                        button.disabled = false;
                        button.textContent =
                            "Save & Continue to Work";
                    }
                }
            });
        };



    // =====================================================
    // COMMON SHORTCUT HELPERS
    // =====================================================

    function shortcutEl(id) {
        return document.getElementById(id);
    }


    function shortcutShowError(r) {
        let message = "Something went wrong.";

        if (r && r.message && typeof r.message === "string") {
            message = r.message;
        }

        if (r && r._server_messages) {
            try {
                const rows =
                    JSON.parse(r._server_messages);

                if (rows && rows.length) {
                    const parsed =
                        JSON.parse(rows[0]);

                    if (parsed && parsed.message) {
                        message = parsed.message;
                    }
                }
            } catch (e) {
                // Keep fallback message.
            }
        }

        frappe.msgprint(message);
    }


    function shortcutReloadActions() {
        window.location.href =
            "/tech/intervention2?name="
            + encodeURIComponent(
                window.TECH2_MI_NAME
            )
            + "&step=actions";
    }


    window.tech2OpenModal =
        function (id) {
            const modal = shortcutEl(id);

            if (modal) {
                modal.classList.add("is-open");
            }
        };


    window.tech2CloseModal =
        function (id) {
            const modal = shortcutEl(id);

            if (modal) {
                modal.classList.remove("is-open");
            }
        };


    function populateSelect(
        select,
        rows,
        valueGetter,
        labelGetter,
        placeholder
    ) {
        if (!select) {
            return;
        }

        select.innerHTML = "";

        if (placeholder) {
            const empty =
                document.createElement("option");

            empty.value = "";
            empty.textContent = placeholder;
            select.appendChild(empty);
        }

        (rows || []).forEach(function (row) {
            const value =
                valueGetter
                    ? valueGetter(row)
                    : row;

            if (!value) {
                return;
            }

            const option =
                document.createElement("option");

            option.value = value;
            option.textContent =
                labelGetter
                    ? labelGetter(row)
                    : value;

            select.appendChild(option);
        });
    }


    // =====================================================
    // CHANGE INTERVENTION TYPE
    // =====================================================

    window.tech2ShowChangeInterventionType =
        function () {

            const select =
                shortcutEl(
                    "tech2-change-type-select"
                );

            if (!select) {
                return;
            }

            select.innerHTML =
                '<option value="">'
                + 'Loading intervention types...'
                + '</option>';

            shortcutEl(
                "tech2-change-testing-wrap"
            ).style.display = "none";

            shortcutEl(
                "tech2-change-installation-wrap"
            ).style.display = "none";

            shortcutEl(
                "tech2-change-general-work-wrap"
            ).style.display = "none";

            window.tech2OpenModal(
                "tech2-change-type-modal"
            );

            frappe.call({
                method:
                    "maintenance_app.www.tech."
                    + "intervention.index."
                    + "get_additional_mi_intervention_types",

                callback: function (r) {

                    const rows =
                        r.message || [];

                    populateSelect(
                        select,
                        rows,
                        function (row) {
                            return row;
                        },
                        function (row) {
                            return row;
                        },
                        "Select intervention type"
                    );

                    select.value =
                        window
                            .TECH2_CURRENT_INTERVENTION_TYPE
                        || "";

                    window
                        .tech2ChangeTypeSelectionChanged(
                            true
                        );
                },

                error: shortcutShowError
            });
        };


    window.tech2ChangeTypeSelectionChanged =
        function (useCurrentValue) {

            const type =
                shortcutEl(
                    "tech2-change-type-select"
                )?.value || "";

            const testingWrap =
                shortcutEl(
                    "tech2-change-testing-wrap"
                );

            const installationWrap =
                shortcutEl(
                    "tech2-change-installation-wrap"
                );

            const generalWorkWrap =
                shortcutEl(
                    "tech2-change-general-work-wrap"
                );

            testingWrap.style.display =
                type === "Specialised Testing"
                    ? "block"
                    : "none";

            installationWrap.style.display =
                type === "General Installation"
                    ? "block"
                    : "none";

            generalWorkWrap.style.display =
                type === "General Works"
                    ? "block"
                    : "none";


            if (type === "Specialised Testing") {
                tech2LoadChangeTestingTypes(
                    useCurrentValue
                        ? window
                            .TECH2_CURRENT_SPECIALISED_TESTING_TYPE
                        : ""
                );
            }


            if (type === "General Installation") {
                tech2LoadChangeInstallationTypes(
                    useCurrentValue
                        ? window
                            .TECH2_CURRENT_GENERAL_INSTALLATION_TYPE
                        : ""
                );
            }


            if (type === "General Works") {
                tech2LoadChangeGeneralWorkTypes(
                    useCurrentValue
                        ? window
                            .TECH2_CURRENT_GENERAL_WORK_TYPE
                        : ""
                );
            }
        };


    function tech2LoadChangeTestingTypes(
        selectedValue
    ) {
        const select =
            shortcutEl(
                "tech2-change-testing-type"
            );

        select.innerHTML =
            '<option value="">'
            + 'Loading testing types...'
            + '</option>';

        frappe.call({
            method:
                "maintenance_app.www.tech."
                + "intervention.index."
                + "get_specialised_testing_types",

            callback: function (r) {

                populateSelect(
                    select,
                    r.message || [],
                    function (row) {
                        return row.name || row;
                    },
                    function (row) {
                        return row.name || row;
                    },
                    "Select testing type"
                );

                if (selectedValue) {
                    select.value =
                        selectedValue;
                }
            },

            error: shortcutShowError
        });
    }


    function tech2LoadChangeInstallationTypes(
        selectedValue
    ) {
        const select =
            shortcutEl(
                "tech2-change-installation-type"
            );

        select.innerHTML =
            '<option value="">'
            + 'Loading installation types...'
            + '</option>';

        frappe.call({
            method:
                "maintenance_app.www.tech."
                + "intervention.index."
                + "get_general_installation_types",

            callback: function (r) {

                populateSelect(
                    select,
                    r.message || [],
                    function (row) {
                        return row.name || row;
                    },
                    function (row) {
                        return (
                            row.custom_installation_type
                            || row.name
                            || row
                        );
                    },
                    "Select installation type"
                );

                if (selectedValue) {
                    select.value =
                        selectedValue;
                }
            },

            error: shortcutShowError
        });
    }


    function tech2LoadChangeGeneralWorkTypes(
        selectedValue
    ) {
        const select =
            shortcutEl(
                "tech2-change-general-work-type"
            );

        select.innerHTML =
            '<option value="">'
            + 'Loading work types...'
            + '</option>';

        frappe.call({
            method:
                "maintenance_app.www.tech."
                + "intervention.index."
                + "get_general_works_types",

            callback: function (r) {

                populateSelect(
                    select,
                    r.message || [],
                    function (row) {
                        return row.name || row;
                    },
                    function (row) {
                        return row.name || row;
                    },
                    "Select work type"
                );

                if (selectedValue) {
                    select.value =
                        selectedValue;
                }
            },

            error: shortcutShowError
        });
    }


    window.tech2SubmitChangeInterventionType =
        function () {

            const interventionType =
                shortcutEl(
                    "tech2-change-type-select"
                )?.value || "";

            const specialisedTestingType =
                shortcutEl(
                    "tech2-change-testing-type"
                )?.value || "";

            const generalInstallationType =
                shortcutEl(
                    "tech2-change-installation-type"
                )?.value || "";

            const generalWorkType =
                shortcutEl(
                    "tech2-change-general-work-type"
                )?.value || "";


            if (!interventionType) {
                frappe.msgprint(
                    "Please select Intervention Type."
                );
                return;
            }


            if (
                interventionType
                    === "Specialised Testing"
                && !specialisedTestingType
            ) {
                frappe.msgprint(
                    "Please select "
                    + "Specialised Testing Type."
                );
                return;
            }


            if (
                interventionType
                    === "General Installation"
                && !generalInstallationType
            ) {
                frappe.msgprint(
                    "Please select "
                    + "General Installation Type."
                );
                return;
            }


            if (
                interventionType
                    === "General Works"
                && !generalWorkType
            ) {
                frappe.msgprint(
                    "Please select "
                    + "General Work Type."
                );
                return;
            }


            frappe.call({
                method:
                    "maintenance_app.www.tech."
                    + "intervention.index."
                    + "change_intervention_type_from_pwa",

                args: {
                    mi_name:
                        window.TECH2_MI_NAME,

                    intervention_type:
                        interventionType,

                    specialised_testing_type:
                        specialisedTestingType,

                    general_installation_type:
                        generalInstallationType,

                    general_work_type:
                        generalWorkType
                },

                freeze: true,

                freeze_message:
                    __("Updating intervention type..."),

                callback: function (r) {

                    if (!r.message?.ok) {
                        return;
                    }

                    window.tech2CloseModal(
                        "tech2-change-type-modal"
                    );

                    frappe.show_alert({
                        message:
                            __("Intervention type updated"),
                        indicator: "green"
                    });

                    shortcutReloadActions();
                },

                error: shortcutShowError
            });
        };


    // =====================================================
    // CHANGE COMPONENT
    // =====================================================

    window.tech2ShowChangeComponent =
        function () {

            if (!window.TECH2_ASSET) {
                frappe.msgprint(
                    "No equipment is selected "
                    + "for this intervention."
                );
                return;
            }

            frappe.call({
                method:
                    "maintenance_app.api."
                    + "get_components_for_equipment_group",

                args: {
                    equipment_name:
                        window.TECH2_ASSET,

                    component_group: ""
                },

                freeze: true,

                freeze_message:
                    __("Loading installed components..."),

                callback: function (r) {

                    const rows =
                        r.message || [];

                    if (!rows.length) {
                        frappe.msgprint(
                            "No installed components "
                            + "were found for this equipment."
                        );
                        return;
                    }

                    const select =
                        shortcutEl(
                            "tech2-change-component-select"
                        );

                    populateSelect(
                        select,
                        rows,
                        function (row) {
                            return row.row_id;
                        },
                        function (row) {
                            let label =
                                row.component_item
                                || row.component_group
                                || row.row_id;

                            if (row.serial) {
                                label +=
                                    " - SN: "
                                    + row.serial;
                            }

                            return label;
                        }
                    );

                    shortcutEl(
                        "tech2-change-component-reason"
                    ).value = "";

                    window.tech2OpenModal(
                        "tech2-change-component-modal"
                    );
                },

                error: shortcutShowError
            });
        };


    window.tech2SubmitChangeComponent =
        function () {

            const componentRowId =
                shortcutEl(
                    "tech2-change-component-select"
                )?.value || "";

            const reason =
                shortcutEl(
                    "tech2-change-component-reason"
                )?.value.trim() || "";


            if (!componentRowId) {
                frappe.msgprint(
                    "Please select the actual component."
                );
                return;
            }


            if (!reason) {
                frappe.msgprint(
                    "Please enter the "
                    + "component correction reason."
                );
                return;
            }


            frappe.call({
                method:
                    "maintenance_app.api."
                    + "change_mi_component",

                args: {
                    mi_name:
                        window.TECH2_MI_NAME,

                    component_row_id:
                        componentRowId,

                    reason: reason
                },

                freeze: true,

                freeze_message:
                    __("Updating component..."),

                callback: function () {

                    window.tech2CloseModal(
                        "tech2-change-component-modal"
                    );

                    frappe.show_alert({
                        message:
                            __("Target component corrected"),
                        indicator: "green"
                    });

                    shortcutReloadActions();
                },

                error: shortcutShowError
            });
        };


    // =====================================================
    // CHANGE EQUIPMENT
    // =====================================================

    window.tech2ShowChangeEquipment =
        function () {

            if (!window.TECH2_BRANCH) {
                frappe.msgprint(
                    "No branch is available "
                    + "for this intervention."
                );
                return;
            }

            frappe.call({
                method:
                    "frappe.client.get_list",

                args: {
                    doctype:
                        "Installed Equipment",

                    filters: {
                        custom_branch:
                            window.TECH2_BRANCH
                    },

                    fields: [
                        "name",
                        "custom_asset_name",
                        "custom_display_name",
                        "custom_client_asset_code",
                        "custom_asset_id",
                        "custom_model"
                    ],

                    limit_page_length: 500
                },

                freeze: true,

                freeze_message:
                    __("Loading equipment..."),

                callback: function (r) {

                    const rows =
                        r.message || [];

                    if (!rows.length) {
                        frappe.msgprint(
                            "No equipment found "
                            + "for this branch."
                        );
                        return;
                    }

                    const select =
                        shortcutEl(
                            "tech2-change-equipment-select"
                        );

                    populateSelect(
                        select,
                        rows,
                        function (row) {
                            return row.name;
                        },
                        function (row) {
                            const values = [
                                row.custom_asset_name,
                                row.custom_display_name,
                                row.custom_client_asset_code,
                                row.custom_asset_id,
                                row.custom_model
                            ].filter(Boolean);

                            return values.join(" - ")
                                || row.name;
                        }
                    );

                    if (
                        window.TECH2_ASSET
                        && Array.from(
                            select.options
                        ).some(
                            function (option) {
                                return option.value
                                    === window.TECH2_ASSET;
                            }
                        )
                    ) {
                        select.value =
                            window.TECH2_ASSET;
                    }

                    shortcutEl(
                        "tech2-change-equipment-reason"
                    ).value = "";

                    window.tech2OpenModal(
                        "tech2-change-equipment-modal"
                    );
                },

                error: shortcutShowError
            });
        };


    window.tech2SubmitChangeEquipment =
        function () {

            const actualEquipment =
                shortcutEl(
                    "tech2-change-equipment-select"
                )?.value || "";

            const reason =
                shortcutEl(
                    "tech2-change-equipment-reason"
                )?.value.trim() || "";


            if (!actualEquipment) {
                frappe.msgprint(
                    "Please select equipment."
                );
                return;
            }


            if (!reason) {
                frappe.msgprint(
                    "Reason is required."
                );
                return;
            }


            frappe.call({
                method:
                    "maintenance_app.api."
                    + "change_mi_equipment",

                args: {
                    mi_name:
                        window.TECH2_MI_NAME,

                    actual_equipment:
                        actualEquipment,

                    reason: reason
                },

                freeze: true,

                freeze_message:
                    __("Changing equipment..."),

                callback: function () {

                    window.tech2CloseModal(
                        "tech2-change-equipment-modal"
                    );

                    frappe.show_alert({
                        message:
                            __("Equipment changed"),
                        indicator: "green"
                    });

                    shortcutReloadActions();
                },

                error: shortcutShowError
            });
        };


    // =====================================================
    // ADDITIONAL MI
    // =====================================================

    function tech2LoadBranchEquipment(
        callback
    ) {
        frappe.call({
            method:
                "frappe.client.get_list",

            args: {
                doctype:
                    "Installed Equipment",

                filters: {
                    custom_branch:
                        window.TECH2_BRANCH
                },

                fields: [
                    "name",
                    "custom_asset_name",
                    "custom_display_name",
                    "custom_client_asset_code",
                    "custom_asset_id",
                    "custom_model"
                ],

                limit_page_length: 500
            },

            callback: function (r) {

                const rows =
                    r.message || [];

                if (!rows.length) {
                    frappe.msgprint(
                        "No equipment found "
                        + "for this branch."
                    );
                    return;
                }

                const select =
                    shortcutEl(
                        "tech2-additional-equipment"
                    );

                populateSelect(
                    select,
                    rows,
                    function (row) {
                        return row.name;
                    },
                    function (row) {
                        const values = [
                            row.custom_asset_name,
                            row.custom_display_name,
                            row.custom_client_asset_code,
                            row.custom_asset_id,
                            row.custom_model
                        ].filter(Boolean);

                        return values.join(" - ")
                            || row.name;
                    }
                );

                if (callback) {
                    callback();
                }
            },

            error: shortcutShowError
        });
    }


    window.tech2ShowAdditionalMI =
        function () {

            if (!window.TECH2_PARENT_MISSION) {
                frappe.msgprint(
                    "This intervention is not "
                    + "linked to a Tech Mission."
                );
                return;
            }


            shortcutEl(
                "tech2-additional-target-scope"
            ).value = "Equipment";

            shortcutEl(
                "tech2-additional-component-wrap"
            ).style.display = "none";

            shortcutEl(
                "tech2-additional-component"
            ).innerHTML = "";

            shortcutEl(
                "tech2-additional-subject"
            ).value = "";

            shortcutEl(
                "tech2-additional-reason"
            ).value = "";

            shortcutEl(
                "tech2-additional-testing-wrap"
            ).style.display = "none";

            shortcutEl(
                "tech2-additional-general-work-wrap"
            ).style.display = "none";


            window.tech2OpenModal(
                "tech2-additional-mi-modal"
            );


            tech2LoadBranchEquipment(
                function () {

                    window
                        .tech2LoadAdditionalInterventionTypes();

                    window
                        .tech2LoadAdditionalApplicants();
                }
            );
        };


    window.tech2AdditionalEquipmentChanged =
        function () {

            window
                .tech2LoadAdditionalApplicants();

            if (
                shortcutEl(
                    "tech2-additional-target-scope"
                )?.value === "Component"
            ) {
                window
                    .tech2AdditionalTargetChanged();
            }
        };


    window.tech2AdditionalTargetChanged =
        function () {

            const asset =
                shortcutEl(
                    "tech2-additional-equipment"
                )?.value || "";

            const targetScope =
                shortcutEl(
                    "tech2-additional-target-scope"
                )?.value || "Equipment";

            const wrap =
                shortcutEl(
                    "tech2-additional-component-wrap"
                );

            const select =
                shortcutEl(
                    "tech2-additional-component"
                );


            if (targetScope !== "Component") {
                wrap.style.display = "none";
                select.innerHTML = "";
                return;
            }


            wrap.style.display = "block";

            select.innerHTML =
                '<option value="">'
                + 'Loading components...'
                + '</option>';


            if (!asset) {
                select.innerHTML =
                    '<option value="">'
                    + 'Select equipment first'
                    + '</option>';

                return;
            }


            frappe.call({
                method:
                    "maintenance_app.api."
                    + "get_additional_mi_components",

                args: {
                    equipment_name: asset
                },

                callback: function (r) {

                    const rows =
                        r.message || [];

                    populateSelect(
                        select,
                        rows,
                        function (row) {
                            return row.row_id;
                        },
                        function (row) {
                            return (
                                row.display_name
                                || row.equipment_component
                                || row.row_id
                            )
                            + (
                                row.serial
                                    ? " | " + row.serial
                                    : ""
                            );
                        },
                        "Select component"
                    );

                    if (!rows.length) {
                        select.innerHTML =
                            '<option value="">'
                            + 'No active components found'
                            + '</option>';
                    }
                },

                error: shortcutShowError
            });
        };


    window.tech2LoadAdditionalInterventionTypes =
        function () {

            const select =
                shortcutEl(
                    "tech2-additional-type"
                );

            select.innerHTML =
                '<option value="">'
                + 'Loading intervention types...'
                + '</option>';

            frappe.call({
                method:
                    "maintenance_app.www.tech."
                    + "intervention.index."
                    + "get_additional_mi_intervention_types",

                callback: function (r) {

                    const rows =
                        r.message || [];

                    populateSelect(
                        select,
                        rows,
                        function (row) {
                            return row;
                        },
                        function (row) {
                            return row;
                        },
                        "Select intervention type"
                    );

                    if (
                        rows.includes("Service")
                    ) {
                        select.value =
                            "Service";
                    }

                    window
                        .tech2AdditionalTypeChanged();
                },

                error: shortcutShowError
            });
        };


    window.tech2AdditionalTypeChanged =
        function () {

            const type =
                shortcutEl(
                    "tech2-additional-type"
                )?.value || "";

            const testingWrap =
                shortcutEl(
                    "tech2-additional-testing-wrap"
                );

            const generalWorkWrap =
                shortcutEl(
                    "tech2-additional-general-work-wrap"
                );

            testingWrap.style.display =
                type === "Specialised Testing"
                    ? "block"
                    : "none";

            generalWorkWrap.style.display =
                type === "General Works"
                    ? "block"
                    : "none";


            if (type === "Specialised Testing") {

                const select =
                    shortcutEl(
                        "tech2-additional-testing-type"
                    );

                select.innerHTML =
                    '<option value="">'
                    + 'Loading testing types...'
                    + '</option>';

                frappe.call({
                    method:
                        "maintenance_app.www.tech."
                        + "intervention.index."
                        + "get_specialised_testing_types",

                    callback: function (r) {

                        populateSelect(
                            select,
                            r.message || [],
                            function (row) {
                                return row.name || row;
                            },
                            function (row) {
                                return row.name || row;
                            },
                            "Select testing type"
                        );
                    },

                    error: shortcutShowError
                });

            } else {
                shortcutEl(
                    "tech2-additional-testing-type"
                ).innerHTML =
                    '<option value="">'
                    + 'Select testing type'
                    + '</option>';
            }


            if (type === "General Works") {

                const select =
                    shortcutEl(
                        "tech2-additional-general-work-type"
                    );

                select.innerHTML =
                    '<option value="">'
                    + 'Loading work types...'
                    + '</option>';

                frappe.call({
                    method:
                        "maintenance_app.www.tech."
                        + "intervention.index."
                        + "get_general_works_types",

                    callback: function (r) {

                        populateSelect(
                            select,
                            r.message || [],
                            function (row) {
                                return row.name || row;
                            },
                            function (row) {
                                return row.name || row;
                            },
                            "Select work type"
                        );
                    },

                    error: shortcutShowError
                });

            } else {
                shortcutEl(
                    "tech2-additional-general-work-type"
                ).innerHTML =
                    '<option value="">'
                    + 'Select work type'
                    + '</option>';
            }
        };


    window.tech2LoadAdditionalApplicants =
        function () {

            const asset =
                shortcutEl(
                    "tech2-additional-equipment"
                )?.value || "";

            const select =
                shortcutEl(
                    "tech2-additional-applicant"
                );

            if (!asset) {
                select.innerHTML =
                    '<option value="">'
                    + 'Select equipment first'
                    + '</option>';
                return;
            }


            select.innerHTML =
                '<option value="">'
                + 'Loading contacts...'
                + '</option>';


            frappe.call({
                method:
                    "maintenance_app.api."
                    + "get_eq_applicants_for_equipment",

                args: {
                    equipment_name: asset
                },

                callback: function (r) {

                    const rows =
                        r.message || [];

                    populateSelect(
                        select,
                        rows,

                        function (row) {
                            return (
                                row.contact
                                || row.name
                                || row.custom_contact
                                || row.value
                            );
                        },

                        function (row) {
                            return (
                                row.full_name
                                || row.contact_name
                                || row.custom_full_name
                                || row.label
                                || row.contact
                                || row.name
                                || row.value
                            );
                        },

                        "Select applicant"
                    );


                    if (!rows.length) {
                        select.innerHTML =
                            '<option value="">'
                            + 'No valid contacts found'
                            + '</option>';
                    }
                },

                error: shortcutShowError
            });
        };


    window.tech2SubmitAdditionalMI =
        function () {

            const asset =
                shortcutEl(
                    "tech2-additional-equipment"
                )?.value || "";

            const targetScope =
                shortcutEl(
                    "tech2-additional-target-scope"
                )?.value || "Equipment";

            const componentRowId =
                shortcutEl(
                    "tech2-additional-component"
                )?.value || "";

            const subject =
                shortcutEl(
                    "tech2-additional-subject"
                )?.value.trim() || "";

            const interventionType =
                shortcutEl(
                    "tech2-additional-type"
                )?.value || "";

            const specialisedTestingType =
                shortcutEl(
                    "tech2-additional-testing-type"
                )?.value || "";

            const generalWorkType =
                shortcutEl(
                    "tech2-additional-general-work-type"
                )?.value || "";

            const applicant =
                shortcutEl(
                    "tech2-additional-applicant"
                )?.value || "";

            const reason =
                shortcutEl(
                    "tech2-additional-reason"
                )?.value.trim() || "";


            if (!asset) {
                frappe.msgprint(
                    "Please select equipment."
                );
                return;
            }


            if (
                targetScope === "Component"
                && !componentRowId
            ) {
                frappe.msgprint(
                    "Please select the component "
                    + "to work on."
                );
                return;
            }


            if (!subject) {
                frappe.msgprint(
                    "Subject is required."
                );
                return;
            }


            if (!interventionType) {
                frappe.msgprint(
                    "Please select intervention type."
                );
                return;
            }


            if (
                interventionType
                    === "Specialised Testing"
                && !specialisedTestingType
            ) {
                frappe.msgprint(
                    "Please select "
                    + "Specialised Testing Type."
                );
                return;
            }


            if (
                interventionType === "General Works"
                && !generalWorkType
            ) {
                frappe.msgprint(
                    "Please select "
                    + "General Work Type."
                );
                return;
            }


            if (!applicant) {
                frappe.msgprint(
                    "Please select Applicant."
                );
                return;
            }


            if (!reason) {
                frappe.msgprint(
                    "Reason / work required "
                    + "is mandatory."
                );
                return;
            }


            frappe.call({
                method:
                    "maintenance_app.www.tech."
                    + "intervention.index."
                    + "create_additional_mi_from_pwa",

                args: {
                    mission_name:
                        window.TECH2_PARENT_MISSION,

                    asset_name:
                        asset,

                    reason:
                        reason,

                    subject:
                        subject,

                    intervention_type:
                        interventionType,

                    specialised_testing_type:
                        specialisedTestingType,

                    general_work_type:
                        generalWorkType,

                    applicant:
                        applicant,

                    target_scope:
                        targetScope,

                    component_row_id:
                        targetScope === "Component"
                            ? componentRowId
                            : null
                },

                freeze: true,

                freeze_message:
                    __("Creating additional MI..."),

                callback: function (r) {

                    const newMI =
                        r.message?.intervention;

                    if (!newMI) {
                        frappe.msgprint(
                            "Additional MI was created, "
                            + "but no intervention reference "
                            + "was returned."
                        );
                        return;
                    }

                    window.tech2CloseModal(
                        "tech2-additional-mi-modal"
                    );

                    frappe.show_alert({
                        message:
                            __("Additional MI created"),
                        indicator: "green"
                    });

                    window.location.href =
                        "/tech/intervention2?name="
                        + encodeURIComponent(newMI)
                        + "&step=job";
                },

                error: shortcutShowError
            });
        };



})();
