(function () {
    "use strict";

    function openMenu() {
        const nav =
            document.getElementById("tech2-nav");

        const backdrop =
            document.getElementById(
                "tech2-nav-backdrop"
            );

        if (nav) {
            nav.classList.add("open");
        }

        if (backdrop) {
            backdrop.classList.add("open");
        }
    }


    function closeMenu() {
        const nav =
            document.getElementById("tech2-nav");

        const backdrop =
            document.getElementById(
                "tech2-nav-backdrop"
            );

        if (nav) {
            nav.classList.remove("open");
        }

        if (backdrop) {
            backdrop.classList.remove("open");
        }
    }


    document.addEventListener(
        "DOMContentLoaded",
        function () {

            const openButton =
                document.getElementById(
                    "tech2-menu-button"
                );

            const closeButton =
                document.getElementById(
                    "tech2-nav-close"
                );

            const backdrop =
                document.getElementById(
                    "tech2-nav-backdrop"
                );


            if (openButton) {
                openButton.addEventListener(
                    "click",
                    openMenu
                );
            }

            if (closeButton) {
                closeButton.addEventListener(
                    "click",
                    closeMenu
                );
            }

            if (backdrop) {
                backdrop.addEventListener(
                    "click",
                    closeMenu
                );
            }
        }
    );

})();
