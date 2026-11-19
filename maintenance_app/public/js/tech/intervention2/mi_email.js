(function () {
  "use strict";
  const panel = document.getElementById("tech2-mi-email-panel");
  if (!panel) return;
  const miName = panel.dataset.mi;
  const submitted = panel.dataset.submitted === "1";
  const state = {options: [], to: new Set(), cc: new Set(), loaded: false, busy: false};
  const el = id => document.getElementById(id);
  const norm = s => String(s || "").trim().toLowerCase();
  function status(message) {
    const node = el("tech2-mi-email-status");
    if (node) node.textContent = message || "";
  }
  function failureMessage(err) {
    if (!err) return "Request failed";
    const response = err.responseJSON || err.response || {};
    return response._server_messages || response.exception || err.message || "Request failed";
  }
  function api(method, args) {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      function execute() {
        if (window.frappe && typeof window.frappe.call === "function") {
          try {
            window.frappe.call({
              method: method, args: args,
              callback: function (r) {
                if (r && (r.exc || r.exc_type)) reject(new Error(r.exception || r.exc_type || "Server rejected request"));
                else resolve((r && r.message) || {});
              },
              error: function (r) { reject(new Error(failureMessage(r))); }
            });
          } catch (err) { reject(err); }
          return;
        }
        if (++attempts >= 60) { reject(new Error("Frappe API unavailable after page load")); return; }
        setTimeout(execute, 200);
      }
      execute();
    });
  }
  function labelFor(email) {
    const entry = state.options.find(o => norm(o.email) === norm(email));
    return entry ? (entry.label && entry.label !== entry.email ? entry.label + " <" + entry.email + ">" : entry.email) : email;
  }
  function render(kind) {
    const host = el("tech2-mi-email-" + kind);
    const input = el("tech2-mi-email-search-" + kind);
    if (!host || !input) return;
    let shell = host.parentElement;
    shell.classList.add("tech2-mi-email-picker");
    input.placeholder = kind === "to" ? "Search applicant, branch contact or system user" : "Search branch/customer contact or system user";
    const chipsId = "tech2-mi-email-chips-" + kind;
    let chips = el(chipsId);
    if (!chips) {
      chips = document.createElement("div");
      chips.id = chipsId;
      chips.className = "tech2-mi-email-chips";
      input.parentNode.insertBefore(chips, input);
    }
    chips.replaceChildren();
    Array.from(state[kind]).forEach(email => {
      const tag = document.createElement("span"); tag.className = "tech2-mi-email-chip";
      const name = document.createElement("span"); name.textContent = labelFor(email);
      const remove = document.createElement("button"); remove.type = "button";
      remove.className = "tech2-mi-email-chip-remove"; remove.textContent = "×";
      remove.setAttribute("aria-label", "Remove " + email);
      remove.addEventListener("click", () => { state[kind].delete(email); render("to"); render("cc"); });
      tag.appendChild(name); tag.appendChild(remove); chips.appendChild(tag);
    });
    host.replaceChildren();
    const query = norm(input.value);
    if (!state.loaded) { host.hidden = true; return; }
    const available = state.options.filter(o => !state.to.has(o.email) && !state.cc.has(o.email));
    const matching = available.filter(o => (norm(o.label) + " " + norm(o.email) + " " + norm(o.source)).includes(query));
    // Keep the menu closed until searched or focused. Show compact choices on focus.
    const shouldOpen = input === document.activeElement;
    host.hidden = !shouldOpen;
    if (!shouldOpen) return;
    if (!matching.length) {
      const empty = document.createElement("div"); empty.className = "tech2-mi-email-empty";
      empty.textContent = "No matching approved recipients"; host.appendChild(empty); return;
    }
    matching.slice(0, 30).forEach(o => {
      const option = document.createElement("button"); option.type = "button";
      option.className = "tech2-mi-email-option-row";
      const title = document.createElement("strong"); title.textContent = o.label || o.email;
      const subtitle = document.createElement("small"); subtitle.textContent = o.email + (o.source ? " · " + o.source : "");
      option.appendChild(title); option.appendChild(subtitle);
      option.addEventListener("mousedown", e => e.preventDefault());
      option.addEventListener("click", () => {
        state[kind].add(o.email);
        input.value = "";
        input.blur();
        render("to"); render("cc");
      });
      host.appendChild(option);
    });
  }
  async function load() {
    status("Loading approved recipients...");
    try {
      const data = await api("maintenance_app.www.tech.intervention.index.get_mi_email_recipients", {mi_name: miName});
      if (!Array.isArray(data.options)) throw new Error("Recipient service returned no approved recipient list");
      const emails = new Map();
      state.options = [];
      data.options.forEach(o => {
        if (!o || !o.email || typeof o.email !== "string") return;
        const key = norm(o.email);
        if (emails.has(key)) return;
        emails.set(key, o.email);
        state.options.push({label: String(o.label || o.email), email: o.email, source: String(o.source || "")});
      });
      (data.to || []).forEach(email => { if (emails.has(norm(email))) state.to.add(emails.get(norm(email))); });
      (data.cc || []).forEach(email => {
        const resolved = emails.get(norm(email));
        if (resolved && !state.to.has(resolved)) state.cc.add(resolved);
      });
      state.loaded = true;
      render("to"); render("cc");
      status("");
    } catch (err) {
      console.error("MI recipient loading failed", err);
      status("Cannot load approved recipients: " + failureMessage(err));
    }
  }
  // GMAO_COMBINED_MI_CAL_EMAIL_V1
  async function loadCalibrationCertificates() {
    const wrap = el("tech2-mi-email-cal-wrap");
    if (!wrap) return;
    const select = el("tech2-mi-email-cal-report");
    const note = el("tech2-mi-email-cal-note");
    try {
      const data = await api("maintenance_app.www.tech.intervention.index.get_mi_calibration_certificates", {mi_name: miName});
      const reports = Array.isArray(data.reports) ? data.reports : [];
      select.replaceChildren();
      reports.forEach(r => {
        const option = document.createElement("option");
        option.value = r.name;
        option.textContent = r.name + " — " + r.file_name;
        select.appendChild(option);
      });
      wrap.hidden = reports.length === 0;
      if (note) note.textContent = "Only submitted, signed certificates containing this MI can be sent.";
    } catch (err) {
      console.error("Calibration certificate lookup failed", err);
      wrap.hidden = true;
      status("Could not load Calibration Certificates: " + failureMessage(err));
    }
  }

  async function send() {
    if (!state.loaded) throw new Error("Approved recipients have not loaded");
    if (state.busy) throw new Error("Email send already in progress");
    if (!state.to.size) throw new Error("Select at least one To recipient");
    if (el("tech2-mi-email-cal-include")?.checked && !el("tech2-mi-email-cal-report")?.value) {
      throw new Error("Select a submitted Calibration Certificate first");
    }
    state.busy = true;
    status("Queueing MI report email...");
    try {
      const response = await api("maintenance_app.www.tech.intervention.index.send_mi_report", {
        mi_name: miName,
        recipients: JSON.stringify(Array.from(state.to)),
        cc: JSON.stringify(Array.from(state.cc)),
        send_photos: el("tech2-mi-email-photos")?.checked ? 1 : 0,
        calibration_report_name: el("tech2-mi-email-cal-include")?.checked
          ? (el("tech2-mi-email-cal-report")?.value || "") : ""
      });
      if (response.ok !== true) throw new Error(response.message || "Email was not queued");
      status("MI report" + (response.calibration_report ? " + Calibration Certificate" : "") +
        " queued for email. You can resend it later.");
      return response;
    } finally { state.busy = false; }
  }
  window.tech2EmailAfterSubmit = function (mi, done) {
    if (mi !== miName || !el("tech2-mi-email-on-submit")?.checked) { done(); return; }
    send().then(done).catch(err => {
      console.error(err);
      status("MI submitted, but email was not queued: " + failureMessage(err));
      // Stay on confirmation page so a technician can see and retry.
    });
  };
  const toggle = el("tech2-mi-email-on-submit");
  if (toggle) toggle.addEventListener("change", () => {
    const choices = el("tech2-mi-email-choices");
    if (choices) choices.hidden = !toggle.checked;
  });
  ["to", "cc"].forEach(kind => {
    const input = el("tech2-mi-email-search-" + kind);
    if (!input) return;
    input.setAttribute("autocomplete", "off");
    input.addEventListener("input", () => render(kind));
    input.addEventListener("focus", () => render(kind));
    input.addEventListener("blur", () => setTimeout(() => render(kind), 150));
  });
  const button = el("tech2-mi-email-send");
  if (button) button.addEventListener("click", () => {
    button.disabled = true;
    send().catch(err => { console.error(err); status("Email not queued: " + failureMessage(err)); })
      .finally(() => { button.disabled = false; });
  });
  const css = document.createElement("style");
  css.textContent = `
  .tech2-mi-email-picker { position:relative; min-width:0; }
  .tech2-mi-email-chips { display:flex; gap:5px; flex-wrap:wrap; margin:5px 0; }
  .tech2-mi-email-chip { display:inline-flex; align-items:center; gap:6px; padding:6px 10px; border:1px solid #d5e3ff; background:#edf4ff; color:#2046a0; border-radius:24px; font-size:13px; max-width:100%; overflow-wrap:anywhere; }
  .tech2-mi-email-chip-remove { appearance:none; border:0; background:none; color:inherit; font-size:17px; cursor:pointer; }
  .tech2-mi-email-options { max-height:260px; overflow:auto; border:1px solid #d9dfe8; border-radius:10px; padding:0; background:white; position:absolute; left:0; right:0; top:100%; z-index:25; box-shadow:0 8px 18px #0001; }
  .tech2-mi-email-options[hidden] { display:none!important; }
  .tech2-mi-email-option-row { display:block; text-align:left; width:100%; border:0; border-bottom:1px solid #edf0f4; padding:10px 12px; background:white; cursor:pointer; color:#1d2630; }
  .tech2-mi-email-option-row:hover, .tech2-mi-email-option-row:focus-visible { background:#f1f5fb; }
  .tech2-mi-email-option-row strong { display:block; font-size:14px; }
  .tech2-mi-email-option-row small { display:block; font-size:12px; color:#64748b; margin-top:3px; }
  .tech2-mi-email-empty { padding:12px; color:#64748b; }
  /* GMAO_COMPACT_RECIPIENT_CHIPS_V1 */
  .tech2-mi-email-picker {
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    align-content: center;
    gap: 6px;
    padding: 8px 12px !important;
    min-height: 48px;
    min-width: 0;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    background: #fff;
    box-sizing: border-box;
  }
  .tech2-mi-email-picker:focus-within {
    border-color: #2563eb;
    box-shadow: 0 0 0 2px #2563eb20;
  }
  .tech2-mi-email-picker .tech2-mi-email-chips {
    display: contents !important;
  }
  .tech2-mi-email-picker .tech2-mi-email-chip {
    flex: 0 1 auto;
    width: auto !important;
    max-width: 100%;
    white-space: normal;
    margin: 0 !important;
  }
  .tech2-mi-email-picker input[id^="tech2-mi-email-search-"] {
    flex: 1 1 180px !important;
    min-width: 120px !important;
    width: auto !important;
    max-width: 100%;
    min-height: 34px !important;
    padding: 4px 2px !important;
    margin: 0 !important;
    border: 0 !important;
    border-radius: 0 !important;
    outline: none !important;
    box-shadow: none !important;
    background: transparent !important;
  }
  .tech2-mi-email-picker .tech2-mi-email-options {
    top: calc(100% + 3px);
    left: 0;
    right: 0;
    width: 100%;
    flex: none;
    box-sizing: border-box;
  }

  `;
  document.head.appendChild(css);
  load();
  loadCalibrationCertificates();
})();
