(function () {
    "use strict";

    const SECTION_DEFINITIONS = [
        {
            id: "mi-section-overview",
            titles: ["Job Summary"]
        },
        {
            id: "mi-section-more",
            titles: ["More Details"]
        },
        {
            id: "mi-section-actions",
            titles: ["Actions"]
        },
        {
            id: "mi-section-parts",
            titles: ["Parts Used"]
        },
        {
            id: "mi-section-photos",
            titles: ["Photos & Attachments", "📸 Photos & Attachments"]
        },
        {
            id: "mi-section-hse",
            titles: ["HSE / Incidents", "⚠️ HSE / Incidents"]
        },
        {
            id: "mi-section-installation",
            titles: [
                "Equipment Installation",
                "General Installation"
            ]
        },
        {
            id: "mi-section-work",
            titles: ["Intervention Details"]
        }
    ];


    function normaliseText(value) {
        return (value || "")
            .replace(/\s+/g, " ")
            .trim();
    }


    function findSectionContainer(titleElement) {
        if (!titleElement) {
            return null;
        }

        let details = titleElement.closest("details");

        if (details) {
            return details;
        }

        /*
         * Some current PWA sections are plain div blocks instead of
         * accordions. Walk upward until we find a sensible card/container.
         */
        return (
            titleElement.closest(".mi-card") ||
            titleElement.parentElement
        );
    }


    function assignSectionIds() {
        const headings = Array.from(
            document.querySelectorAll(".section-title")
        );

        SECTION_DEFINITIONS.forEach(function (definition) {
            if (document.getElementById(definition.id)) {
                return;
            }

            const matchingHeading = headings.find(function (heading) {
                const text = normaliseText(
                    heading.textContent
                );

                return definition.titles.some(function (title) {
                    return text === title;
                });
            });

            if (!matchingHeading) {
                return;
            }

            const container = findSectionContainer(
                matchingHeading
            );

            if (container) {
                container.id = definition.id;
            }
        });
    }


    function updateAvailableNavigation() {
        document
            .querySelectorAll(".tech-nav-link[data-section]")
            .forEach(function (button) {

                const sectionId =
                    button.dataset.section;

                const target =
                    document.getElementById(sectionId);

                button.classList.toggle(
                    "is-hidden",
                    !target
                );
            });
    }


    function openAccordion(target) {
        if (
            target &&
            target.tagName &&
            target.tagName.toLowerCase() === "details"
        ) {
            target.open = true;
        }
    }


    function closeMobileNavigation() {
        const nav =
            document.getElementById("tech-side-nav");

        const backdrop =
            document.getElementById(
                "tech-nav-backdrop"
            );

        const button =
            document.getElementById(
                "tech-sections-button"
            );

        if (nav) {
            nav.classList.remove("is-open");
        }

        if (backdrop) {
            backdrop.classList.remove("is-open");
        }

        if (button) {
            button.setAttribute(
                "aria-expanded",
                "false"
            );
        }

        document.body.classList.remove(
            "tech-nav-open"
        );
    }


    function openMobileNavigation() {
        const nav =
            document.getElementById("tech-side-nav");

        const backdrop =
            document.getElementById(
                "tech-nav-backdrop"
            );

        const button =
            document.getElementById(
                "tech-sections-button"
            );

        if (nav) {
            nav.classList.add("is-open");
        }

        if (backdrop) {
            backdrop.classList.add("is-open");
        }

        if (button) {
            button.setAttribute(
                "aria-expanded",
                "true"
            );
        }

        document.body.classList.add(
            "tech-nav-open"
        );
    }


    function setActiveNavigation(sectionId) {
        document
            .querySelectorAll(".tech-nav-link")
            .forEach(function (button) {
                button.classList.toggle(
                    "active",
                    button.dataset.section === sectionId
                );
            });
    }


    function bindNavigationClicks() {
        document
            .querySelectorAll(".tech-nav-link[data-section]")
            .forEach(function (button) {

                button.addEventListener(
                    "click",
                    function () {
                        const target =
                            document.getElementById(
                                button.dataset.section
                            );

                        if (!target) {
                            return;
                        }

                        openAccordion(target);

                        target.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });

                        setActiveNavigation(
                            button.dataset.section
                        );

                        closeMobileNavigation();
                    }
                );
            });


        const openButton =
            document.getElementById(
                "tech-sections-button"
            );

        const closeButton =
            document.getElementById(
                "tech-nav-close"
            );

        const backdrop =
            document.getElementById(
                "tech-nav-backdrop"
            );


        if (openButton) {
            openButton.addEventListener(
                "click",
                openMobileNavigation
            );
        }

        if (closeButton) {
            closeButton.addEventListener(
                "click",
                closeMobileNavigation
            );
        }

        if (backdrop) {
            backdrop.addEventListener(
                "click",
                closeMobileNavigation
            );
        }
    }


    function initialiseScrollTracking() {
        const buttons = Array.from(
            document.querySelectorAll(
                ".tech-nav-link[data-section]:not(.is-hidden)"
            )
        );

        const sections = buttons
            .map(function (button) {
                return document.getElementById(
                    button.dataset.section
                );
            })
            .filter(Boolean);

        if (!sections.length) {
            return;
        }

        function updateActiveSection() {
            const position =
                window.scrollY + 140;

            let active = sections[0];

            sections.forEach(function (section) {
                if (
                    section.offsetTop <= position
                ) {
                    active = section;
                }
            });

            if (active && active.id) {
                setActiveNavigation(active.id);
            }
        }

        window.addEventListener(
            "scroll",
            updateActiveSection,
            { passive: true }
        );

        updateActiveSection();
    }


    function initialiseTechInterventionNavigation() {
        assignSectionIds();
        updateAvailableNavigation();
        bindNavigationClicks();
        initialiseScrollTracking();
    }


    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initialiseTechInterventionNavigation
        );
    }
    else {
        initialiseTechInterventionNavigation();
    }

})();
