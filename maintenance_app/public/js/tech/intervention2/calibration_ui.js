
(function () {
  const tests = document.getElementById("tech2-cal-tests");
  if (!tests) return;

  function decorate() {
    const cards = tests.querySelectorAll(".tech2-cal-test-card");

    cards.forEach(function (card, index) {
      if (card.dataset.foldReady) return;
      card.dataset.foldReady = "1";
      card.classList.add("tech2-collapsed");

      const heading = card.querySelector("h4, h5, strong");
      const name = heading
        ? heading.textContent.trim()
        : "Calibration Test " + (index + 1);

      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "tech2-cal-fold-btn";
      toggle.setAttribute("aria-expanded", "false");
      toggle.textContent = name + "  ▾";

      toggle.addEventListener("click", function () {
        const collapsed = card.classList.toggle("tech2-collapsed");
        toggle.setAttribute("aria-expanded", String(!collapsed));
        toggle.textContent = name + (collapsed ? "  ▾" : "  ▴");
      });

      card.insertBefore(toggle, card.firstChild);
    });

    if (cards.length && !tests.querySelector(".tech2-cal-fold-tools")) {
      const toolbar = document.createElement("div");
      toolbar.className = "tech2-cal-fold-tools";

      [["Expand All", false], ["Collapse All", true]].forEach(function (item) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-secondary";
        btn.textContent = item[0];

        btn.addEventListener("click", function () {
          tests.querySelectorAll(".tech2-cal-test-card").forEach(function (card) {
            card.classList.toggle("tech2-collapsed", item[1]);
            const toggle = card.querySelector(".tech2-cal-fold-btn");
            if (toggle) {
              toggle.setAttribute("aria-expanded", String(!item[1]));
              const label = toggle.textContent.replace(/\s+[▾▴]$/, "");
              toggle.textContent = label + (item[1] ? "  ▾" : "  ▴");
            }
          });
        });

        toolbar.appendChild(btn);
      });

      tests.insertBefore(toolbar, tests.firstChild);
    }
  }

  const observer = new MutationObserver(decorate);
  observer.observe(tests, {childList: true, subtree: true});
  decorate();
})();
