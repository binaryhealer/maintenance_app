(function () {
    "use strict";

    const pads = {};

    const signatureConfirmed = {
        client: false,
        tech: false
    };


    function normalise(data) {
        if (!data) {
            return "";
        }

        if (data.indexOf("data:image") === 0) {
            return data;
        }

        return "data:image/png;base64," + data;
    }


    function tech2RefreshSignatureButtons() {

        const clientButton =
            document.getElementById(
                "tech2-confirm-client-signature"
            );

        const techButton =
            document.getElementById(
                "tech2-confirm-tech-signature"
            );

        const signoffButton =
            document.getElementById(
                "tech2-save-confirmation"
            );


        if (clientButton) {
            clientButton.textContent =
                signatureConfirmed.client
                    ? "✓ Client Signature Confirmed"
                    : "Confirm Client Signature";
        }


        if (techButton) {
            techButton.textContent =
                signatureConfirmed.tech
                    ? "✓ Technician Signature Confirmed"
                    : "Confirm Technician Signature";
        }


        if (signoffButton) {
            signoffButton.disabled = !(
                signatureConfirmed.client
                && signatureConfirmed.tech
            );
        }
    }


    function setupPad(
        id,
        type,
        existing
    ) {

        const canvas =
            document.getElementById(id);

        if (!canvas) {
            return;
        }

        const ctx =
            canvas.getContext("2d");

        let drawing = false;
        let touched = false;


        function resize() {

            const rect =
                canvas.getBoundingClientRect();

            const ratio =
                Math.max(
                    window.devicePixelRatio || 1,
                    1
                );

            canvas.width =
                rect.width * ratio;

            canvas.height =
                rect.height * ratio;

            ctx.setTransform(
                ratio,
                0,
                0,
                ratio,
                0,
                0
            );

            ctx.lineWidth = 2;
            ctx.lineCap = "round";
            ctx.strokeStyle = "#111827";

            if (
                existing
                && !touched
            ) {
                const img =
                    new Image();

                img.onload =
                    function () {
                        ctx.drawImage(
                            img,
                            0,
                            0,
                            rect.width,
                            rect.height
                        );
                    };

                img.src =
                    normalise(existing);
            }
        }


        function point(event) {

            const rect =
                canvas.getBoundingClientRect();

            const e =
                event.touches?.length
                    ? event.touches[0]
                    : event;

            return {
                x:
                    e.clientX
                    - rect.left,

                y:
                    e.clientY
                    - rect.top
            };
        }


        function start(event) {

            event.preventDefault();

            drawing = true;

            const p =
                point(event);

            ctx.beginPath();

            ctx.moveTo(
                p.x,
                p.y
            );
        }


        function move(event) {

            if (!drawing) {
                return;
            }

            event.preventDefault();

            const p =
                point(event);

            ctx.lineTo(
                p.x,
                p.y
            );

            ctx.stroke();

            touched = true;

            /*
             * Any new stroke invalidates
             * previous confirmation.
             */
            signatureConfirmed[type] = false;

            tech2RefreshSignatureButtons();
        }


        function stop(event) {

            if (event) {
                event.preventDefault();
            }

            drawing = false;
        }


        resize();


        canvas.addEventListener(
            "mousedown",
            start
        );

        canvas.addEventListener(
            "mousemove",
            move
        );

        canvas.addEventListener(
            "mouseup",
            stop
        );

        canvas.addEventListener(
            "mouseleave",
            stop
        );

        canvas.addEventListener(
            "touchstart",
            start,
            { passive: false }
        );

        canvas.addEventListener(
            "touchmove",
            move,
            { passive: false }
        );

        canvas.addEventListener(
            "touchend",
            stop,
            { passive: false }
        );


        if (existing) {
            signatureConfirmed[type] =
                true;
        }


        pads[type] = {

            getData: function () {

                if (
                    !touched
                    && existing
                ) {
                    return existing;
                }

                if (!touched) {
                    return "";
                }

                return canvas.toDataURL(
                    "image/png"
                );
            },


            clear: function () {

                const rect =
                    canvas.getBoundingClientRect();

                ctx.clearRect(
                    0,
                    0,
                    rect.width,
                    rect.height
                );

                touched = false;
                existing = "";

                signatureConfirmed[type] =
                    false;

                tech2RefreshSignatureButtons();
            }
        };
    }


    window.tech2ConfirmSignature =
        function (type) {

            const pad =
                pads[type];

            if (!pad) {
                frappe.msgprint(
                    "Signature pad is not ready."
                );
                return;
            }

            const data =
                pad.getData();

            if (!data) {

                frappe.msgprint(
                    type === "client"
                        ? "Please capture the client signature first."
                        : "Please capture the technician signature first."
                );

                return;
            }


            signatureConfirmed[type] =
                true;

            tech2RefreshSignatureButtons();


            frappe.show_alert({
                message:
                    type === "client"
                        ? "Client signature confirmed"
                        : "Technician signature confirmed",

                indicator:
                    "green"
            });
        };


    window.tech2ClearSignature =
        function (type) {

            if (pads[type]) {
                pads[type].clear();
            }
        };


    function setupHseNA() {

        const checkbox =
            document.getElementById(
                "tech2-hse-na"
            );

        const reasonWrap =
            document.getElementById(
                "tech2-hse-na-reason-wrap"
            );

        const hseSelect =
            document.getElementById(
                "tech2-hse-score"
            );


        if (!checkbox) {
            return;
        }


        function refresh() {

            if (reasonWrap) {
                reasonWrap.style.display =
                    checkbox.checked
                        ? "block"
                        : "none";
            }

            if (hseSelect) {

                hseSelect.disabled =
                    checkbox.checked;

                if (checkbox.checked) {
                    hseSelect.value = "";
                }
            }
        }


        checkbox.addEventListener(
            "change",
            refresh
        );

        refresh();
    }


    window.tech2SaveClientConfirmation =
        function (miName) {

            const signatory =
                document
                    .getElementById(
                        "tech2-signatory-name"
                    )
                    ?.value.trim()
                || "";


            const quality =
                document
                    .getElementById(
                        "tech2-quality-score"
                    )
                    ?.value
                || "";


            const hse =
                document
                    .getElementById(
                        "tech2-hse-score"
                    )
                    ?.value
                || "";


            const remarks =
                document
                    .getElementById(
                        "tech2-customer-remarks"
                    )
                    ?.value
                || "";


            const hseNA =
                document
                    .getElementById(
                        "tech2-hse-na"
                    )
                    ?.checked
                ? 1
                : 0;


            const hseNAReason =
                document
                    .getElementById(
                        "tech2-hse-na-reason"
                    )
                    ?.value.trim()
                || "";


            const clientSignature =
                pads.client?.getData()
                || "";


            const techSignature =
                pads.tech?.getData()
                || "";


            if (!quality) {
                frappe.msgprint(
                    "Please complete Quality Rating."
                );
                return;
            }


            if (
                window.TECH2_HSE_REQUIRED
                && !hse
                && !hseNA
            ) {
                frappe.msgprint(
                    "Please complete HSE Rating or mark HSE Not Applicable."
                );
                return;
            }


            if (
                hseNA
                && !hseNAReason
            ) {
                frappe.msgprint(
                    "Please enter why HSE Rating is not applicable."
                );
                return;
            }


            if (!signatory) {
                frappe.msgprint(
                    "Please enter Client Signatory Name."
                );
                return;
            }


            if (!clientSignature) {
                frappe.msgprint(
                    "Please capture Client Signature."
                );
                return;
            }


            if (!signatureConfirmed.client) {
                frappe.msgprint(
                    "Please confirm Client Signature."
                );
                return;
            }


            if (!techSignature) {
                frappe.msgprint(
                    "Please capture Technician Signature."
                );
                return;
            }


            if (!signatureConfirmed.tech) {
                frappe.msgprint(
                    "Please confirm Technician Signature."
                );
                return;
            }


            frappe.call({
                method:
                    "maintenance_app.www.tech.intervention2.index.save_client_confirmation_v2",

                args: {
                    mi_name:
                        miName,

                    signatory_name:
                        signatory,

                    client_signature:
                        clientSignature,

                    tech_signature:
                        techSignature,

                    quality_score:
                        quality,

                    hse_score:
                        hse,

                    customer_remarks:
                        remarks,

                    hse_not_applicable:
                        hseNA,

                    hse_na_reason:
                        hseNAReason
                },

                freeze: true,

                freeze_message:
                    __(
                        "Confirming Client Sign-Off..."
                    ),

                callback: function (r) {

                    if (!r.message?.ok) {
                        return;
                    }

                    /*
                     * Stay on Client Confirmation.
                     * Reload shows confirmed sign-off
                     * and Submit button.
                     */
                    window.location.reload();
                }
            });
        };


    document.addEventListener(
        "DOMContentLoaded",
        function () {

            setupPad(
                "tech2-client-signature",
                "client",
                window
                    .TECH2_EXISTING_CLIENT_SIGNATURE
                    || ""
            );


            setupPad(
                "tech2-tech-signature",
                "tech",
                window
                    .TECH2_EXISTING_TECH_SIGNATURE
                    || ""
            );


            setupHseNA();

            tech2RefreshSignatureButtons();
        }
    );

})();
