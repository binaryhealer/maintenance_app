(function () {
    "use strict";

    function setMessage(message) {
        const el =
            document.getElementById(
                "tech2-checkin-message"
            );

        if (el) {
            el.textContent = message || "";
        }
    }


    function setButtonBusy(isBusy) {
        const button =
            document.getElementById(
                "tech2-checkin-button"
            );

        if (!button) {
            return;
        }

        button.disabled = isBusy;

        button.textContent =
            isBusy
                ? "Checking In..."
                : "Check In";
    }


    function performCheckIn(
        miName,
        latitude,
        longitude,
        accuracy
    ) {
        setButtonBusy(true);
        setMessage("Saving Check In...");

        frappe.call({
            method:
                "maintenance_app.www.tech.intervention2.index.pwa_check_in_v2",

            args: {
                mi_name: miName,
                latitude: latitude || null,
                longitude: longitude || null,
                accuracy: accuracy || null
            },

            freeze: true,
            freeze_message: __("Checking In..."),

            callback: function (r) {
                setButtonBusy(false);

                if (!r.message || !r.message.ok) {
                    setMessage(
                        "Check In could not be completed."
                    );
                    return;
                }

                const gpsMessage =
                    r.message.gps_saved
                        ? "GPS captured."
                        : "Check In saved without GPS.";

                frappe.show_alert({
                    message:
                        __("Checked In successfully. " + gpsMessage),
                    indicator: "green"
                });

                window.location.href =
                    "/tech/intervention2?name="
                    + encodeURIComponent(miName)
                    + "&step=actions";
            },

            error: function () {
                setButtonBusy(false);

                setMessage(
                    "Check In was not completed."
                );

                frappe.show_alert({
                    message: __(
                        "Check In was not completed."
                    ),
                    indicator: "red"
                });
            }
        });
    }


    window.tech2CheckIn = function (miName) {

        if (!navigator.geolocation) {
            frappe.confirm(
                __(
                    "Location is not available on this device. Continue Check In without GPS?"
                ),
                function () {
                    performCheckIn(
                        miName,
                        null,
                        null,
                        null
                    );
                }
            );

            return;
        }

        setButtonBusy(true);
        setMessage("Getting current location...");

        navigator.geolocation.getCurrentPosition(

            function (position) {
                performCheckIn(
                    miName,
                    position.coords.latitude,
                    position.coords.longitude,
                    position.coords.accuracy
                );
            },

            function () {
                setButtonBusy(false);

                frappe.confirm(
                    __(
                        "Current location could not be obtained. Continue Check In without GPS?"
                    ),
                    function () {
                        performCheckIn(
                            miName,
                            null,
                            null,
                            null
                        );
                    },
                    function () {
                        setMessage(
                            "Check In cancelled."
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

})();
