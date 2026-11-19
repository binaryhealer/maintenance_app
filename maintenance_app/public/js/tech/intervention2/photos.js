(function () {

    "use strict";


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


    function isImageFile(file) {

        const name =
            (
                file.file_name
                || file.file_url
                || ""
            ).toLowerCase();

        return /\.(jpg|jpeg|png|gif|webp|bmp|heic|heif)(\?|$)/i
            .test(name);
    }


    function showUploadStatus(message) {

        const box =
            el("tech2-photo-upload-status");

        if (!box) {
            return;
        }

        box.textContent = message;
        box.style.display = "block";
    }


    function hideUploadStatus() {

        const box =
            el("tech2-photo-upload-status");

        if (!box) {
            return;
        }

        box.style.display = "none";
        box.textContent = "";
    }


    function showError(r) {

        let message =
            "Something went wrong.";

        if (
            r
            && r.message
            && typeof r.message === "string"
        ) {
            message = r.message;
        }

        if (r && r._server_messages) {

            try {

                const messages =
                    JSON.parse(
                        r._server_messages
                    );

                if (messages && messages.length) {

                    const row =
                        JSON.parse(messages[0]);

                    if (row && row.message) {
                        message = row.message;
                    }
                }

            } catch (e) {
                // Keep fallback message.
            }
        }

        frappe.msgprint(message);
    }


    window.tech2LoadPhotos =
        function () {

            const miName =
                window.TECH2_PHOTO_MI_NAME;

            const gallery =
                el("tech2-photo-gallery");

            if (!gallery || !miName) {
                return;
            }

            gallery.innerHTML =
                '<div class="tech2-muted">'
                + 'Loading attachments...'
                + '</div>';


            frappe.call({

                method:
                    "frappe.client.get_list",

                args: {

                    doctype:
                        "File",

                    filters: {
                        attached_to_doctype:
                            "Mission Intervention",

                        attached_to_name:
                            miName,

                        is_folder:
                            0
                    },

                    fields: [
                        "name",
                        "file_url",
                        "file_name",
                        "custom_private_for_client"
                    ],

                    limit_page_length:
                        100,

                    order_by:
                        "creation desc"
                },


                callback: function (r) {

                    const files =
                        r.message || [];

                    gallery.innerHTML = "";


                    if (!files.length) {

                        gallery.innerHTML =
                            '<div class="tech2-note">'
                            + 'No photos or files uploaded.'
                            + '</div>';

                        return;
                    }


                    files.forEach(
                        function (file) {

                            if (!file.file_url) {
                                return;
                            }


                            const isPrivate =
                                !!file.custom_private_for_client;

                            const submitted =
                                !!window
                                    .TECH2_PHOTO_MI_SUBMITTED;

                            const cardClass =
                                isPrivate
                                    ? "tech2-photo-card "
                                        + "tech2-photo-card-private"
                                    : "tech2-photo-card";

                            const checked =
                                isPrivate
                                    ? "checked"
                                    : "";

                            const disabled =
                                submitted
                                    ? "disabled"
                                    : "";

                            const state =
                                isPrivate
                                    ? "Internal only — "
                                        + "will not be emailed"
                                    : "Can be attached "
                                        + "to client email";


                            let preview = "";


                            if (isImageFile(file)) {

                                preview =
                                    '<a href="'
                                    + escapeHtml(
                                        file.file_url
                                    )
                                    + '" target="_blank">'
                                    + '<img class="'
                                    + 'tech2-photo-preview'
                                    + '" src="'
                                    + escapeHtml(
                                        file.file_url
                                    )
                                    + '" alt="'
                                    + escapeHtml(
                                        file.file_name
                                        || "Photo"
                                    )
                                    + '">'
                                    + '</a>';

                            } else {

                                preview =
                                    '<a class="'
                                    + 'tech2-photo-file-link'
                                    + '" href="'
                                    + escapeHtml(
                                        file.file_url
                                    )
                                    + '" target="_blank">'
                                    + '<span class="'
                                    + 'tech2-photo-file-icon'
                                    + '">📄</span>'
                                    + '<span>'
                                    + escapeHtml(
                                        file.file_name
                                        || "Attachment"
                                    )
                                    + '</span>'
                                    + '</a>';
                            }


                            const html =
                                '<div class="'
                                + cardClass
                                + '">'
                                + preview

                                + '<div class="'
                                + 'tech2-photo-info'
                                + '">'

                                + '<div class="'
                                + 'tech2-photo-name'
                                + '">'
                                + escapeHtml(
                                    file.file_name
                                    || file.name
                                )
                                + '</div>'

                                + '<label class="'
                                + 'tech2-photo-private-row'
                                + '">'

                                + '<input type="checkbox" '
                                + checked
                                + ' '
                                + disabled
                                + ' onchange="'
                                + 'tech2SetFilePrivateForClient('
                                + "'"
                                + escapeHtml(file.name)
                                + "',"
                                + 'this.checked'
                                + ')">'

                                + '<span>'
                                + 'Private for Client'
                                + '</span>'

                                + '</label>'

                                + '<div class="'
                                + 'tech2-photo-client-state'
                                + '">'
                                + state
                                + '</div>'

                                + '</div>'
                                + '</div>';


                            gallery.insertAdjacentHTML(
                                "beforeend",
                                html
                            );
                        }
                    );
                },


                error: function (r) {

                    gallery.innerHTML =
                        '<div class="tech2-note">'
                        + 'Could not load attachments.'
                        + '</div>';

                    showError(r);
                }
            });
        };


    window.tech2UploadSelectedFiles =
        function (input) {

            const miName =
                window.TECH2_PHOTO_MI_NAME;


            if (
                !miName
                || !input
                || !input.files
                || !input.files.length
            ) {
                return;
            }


            if (
                window.TECH2_PHOTO_MI_SUBMITTED
            ) {
                frappe.msgprint(
                    "Submitted interventions "
                    + "cannot accept new attachments."
                );

                input.value = "";
                return;
            }


            const files =
                Array.from(
                    input.files
                );

            let completed = 0;
            let failed = 0;


            showUploadStatus(
                "Uploading "
                + files.length
                + (
                    files.length === 1
                        ? " file..."
                        : " files..."
                )
            );


            files.forEach(
                function (file) {

                    const formData =
                        new FormData();

                    formData.append(
                        "file",
                        file
                    );

                    /*
                     * Frappe file storage privacy is separate
                     * from customer-facing attachment privacy.
                     */
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
                            method:
                                "POST",

                            body:
                                formData,

                            headers: {
                                "X-Frappe-CSRF-Token":
                                    frappe.csrf_token
                            }
                        }
                    )

                    .then(
                        function (response) {

                            if (!response.ok) {
                                throw new Error(
                                    "Upload failed"
                                );
                            }

                            return response.json();
                        }
                    )

                    .then(
                        function (data) {

                            if (data.exc) {
                                failed += 1;
                            } else {
                                completed += 1;
                            }
                        }
                    )

                    .catch(
                        function (error) {

                            console.error(
                                error
                            );

                            failed += 1;
                        }
                    )

                    .finally(
                        function () {

                            if (
                                completed + failed
                                !== files.length
                            ) {
                                showUploadStatus(
                                    "Uploaded "
                                    + completed
                                    + " of "
                                    + files.length
                                    + "..."
                                );

                                return;
                            }


                            input.value = "";

                            hideUploadStatus();

                            window.tech2LoadPhotos();


                            if (failed) {

                                frappe.msgprint(
                                    completed
                                    + " file(s) uploaded; "
                                    + failed
                                    + " failed."
                                );

                            } else {

                                frappe.show_alert({
                                    message:
                                        completed === 1
                                            ? "File uploaded"
                                            : completed
                                                + " files uploaded",
                                    indicator:
                                        "green"
                                });
                            }
                        }
                    );
                }
            );
        };


    window.tech2SetFilePrivateForClient =
        function (
            fileName,
            isPrivate
        ) {

            if (
                window.TECH2_PHOTO_MI_SUBMITTED
            ) {
                frappe.msgprint(
                    "Submitted intervention "
                    + "attachments are locked."
                );

                window.tech2LoadPhotos();
                return;
            }


            frappe.call({

                method:
                    "maintenance_app.www.tech."
                    + "intervention.index."
                    + "set_file_private_for_client",

                args: {
                    file_name:
                        fileName,

                    is_private:
                        isPrivate ? 1 : 0
                },

                freeze:
                    false,


                callback: function (r) {

                    if (
                        r.message
                        && r.message.ok === false
                    ) {
                        return;
                    }

                    frappe.show_alert({
                        message:
                            isPrivate
                                ? "Marked internal only"
                                : "File can be sent "
                                    + "to client",
                        indicator:
                            isPrivate
                                ? "orange"
                                : "green"
                    });

                    window.tech2LoadPhotos();
                },


                error: function (r) {

                    showError(r);

                    window.tech2LoadPhotos();
                }
            });
        };


    document.addEventListener(
        "DOMContentLoaded",
        function () {

            if (
                el("tech2-photo-gallery")
            ) {
                window.tech2LoadPhotos();
            }
        }
    );


})();
