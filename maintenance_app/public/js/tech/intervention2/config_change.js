(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let busy = false;
  let editing = null;

  function encodeText(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  }
  function defaultDate() {
    const d = new Date();
    const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }
  function message(text, error) {
    const node = $("tech2-config-message");
    if (node) {
      node.textContent = text;
      node.style.color = error ? "#b42318" : "#16784a";
    }
    if (error && window.frappe?.msgprint) frappe.msgprint(text);
  }
  function setBusy(value) {
    busy = value;
    for (const id of ["tech2-config-save", "tech2-config-add"]) {
      const node = $(id);
      if (node) node.disabled = value;
    }
  }
  function readEditor() {
    const date = $("tech2-config-date")?.value || "";
    return {
      custom_parameter: $("tech2-config-parameter")?.value.trim() || "",
      custom_current_value: $("tech2-config-current")?.value.trim() || "",
      custom_new_value: $("tech2-config-new")?.value.trim() || "",
      custom_config_datetime: date ? date.replace("T", " ") + ":00" : "",
      custom_notes: $("tech2-config-notes")?.value.trim() || ""
    };
  }
  function fromSaved(node) {
    return {
      custom_parameter: node.querySelector(".tech2-config-saved-parameter")?.textContent || "",
      custom_current_value: node.querySelector(".tech2-config-saved-current")?.textContent || "",
      custom_new_value: node.querySelector(".tech2-config-saved-new")?.textContent || "",
      custom_config_datetime: node.querySelector(".tech2-config-saved-date")?.textContent.trim() || "",
      custom_notes: node.querySelector(".tech2-config-saved-notes")?.textContent || ""
    };
  }
  function savedRows() {
    return Array.from(document.querySelectorAll("#tech2-config-rows .tech2-config-row")).map(fromSaved);
  }
  function appendSaved(row) {
    const root = $("tech2-config-rows");
    const node = document.createElement("div");
    node.className = "tech2-config-row tech2-conditional-box";
    node.style.marginBottom = "10px";
    node.innerHTML = `
      <strong class="tech2-config-saved-parameter">${encodeText(row.custom_parameter)}</strong>
      <div>Current: <span class="tech2-config-saved-current">${encodeText(row.custom_current_value)}</span></div>
      <div>New: <span class="tech2-config-saved-new">${encodeText(row.custom_new_value)}</span></div>
      <small class="tech2-config-saved-date">${encodeText(row.custom_config_datetime)}</small>
      <div class="tech2-config-saved-notes">${encodeText(row.custom_notes)}</div>
      <button type="button" class="btn btn-default btn-sm" onclick="tech2ConfigEditSaved(this)">Edit</button>
      <button type="button" class="btn btn-default btn-sm" onclick="tech2ConfigRemoveSaved(window.TECH2_CONFIG_MI_NAME,this)">Remove</button>`;
    root.appendChild(node);
  }
  function renderRows(rows) {
    const root = $("tech2-config-rows");
    if (!root) return;
    root.innerHTML = "";
    rows.forEach(appendSaved);
    if ($("tech2-config-count")) $("tech2-config-count").textContent = String(rows.length);
  }
  function clearEditor() {
    for (const id of ["tech2-config-parameter", "tech2-config-current", "tech2-config-new", "tech2-config-notes"]) {
      if ($(id)) $(id).value = "";
    }
    if ($("tech2-config-date")) $("tech2-config-date").value = defaultDate();
    editing = null;
    if ($("tech2-config-add")) $("tech2-config-add").textContent = "Save Parameter & Add Another";
  }
  function persist(miName, rows, after) {
    if (busy) return;
    if (!rows.length) { message("Add at least one parameter first.", true); return; }
    if (!window.frappe || typeof frappe.call !== "function") {
      message("Saving is unavailable because the ERPNext client library has not loaded. Refresh the page.", true);
      return;
    }
    setBusy(true);
    message("Saving configuration changes...", false);
    frappe.call({
      method: "maintenance_app.www.tech.intervention2.index.save_config_changes_v2",
      args: {mi_name: miName, rows: JSON.stringify(rows)},
      callback: function (r) {
        setBusy(false);
        if (!r.message?.ok) { message("Configuration changes were not saved. Check the server error message.", true); return; }
        renderRows(rows);
        after();
      },
      error: function (err) {
        setBusy(false);
        const serverMessage = err?._server_messages || err?.responseJSON?.message || err?.message;
        message("Unable to save configuration changes. " + (serverMessage ? String(serverMessage).slice(0, 300) : "Check the browser console or Frappe error log."), true);
      }
    });
  }
  function collectWithEditor() {
    const rows = savedRows();
    const editor = readEditor();
    const hasInput = !!(editor.custom_parameter || editor.custom_current_value || editor.custom_new_value || editor.custom_notes);
    if (hasInput) {
      if (!editor.custom_parameter || !editor.custom_new_value) {
        message("Parameter and New Value are required.", true); return null;
      }
      if (!editor.custom_config_datetime) {
        message("Select the change date and time.", true); return null;
      }
      if (editing !== null) rows[editing] = editor;
      else rows.push(editor);
    }
    return rows;
  }
  window.tech2ConfigSaveAndAdd = function (miName) {
    const rows = collectWithEditor();
    if (rows === null) return;
    if (!($("tech2-config-parameter")?.value.trim())) {
      message("Enter a parameter before saving another.", true); return;
    }
    persist(miName, rows, () => { clearEditor(); message("Parameter saved. Add another when ready.", false); $("tech2-config-parameter")?.focus(); });
  };
  window.tech2SaveConfigChanges = function (miName) {
    const rows = collectWithEditor();
    if (rows === null) return;
    persist(miName, rows, () => {
      window.location.href = "/tech/intervention2?name=" + encodeURIComponent(miName) + "&step=finish";
    });
  };
  window.tech2ConfigEditSaved = function (button) {
    const node = button.closest(".tech2-config-row");
    const nodes = Array.from(document.querySelectorAll("#tech2-config-rows .tech2-config-row"));
    editing = nodes.indexOf(node);
    const row = fromSaved(node);
    for (const [field, id] of Object.entries({
      custom_parameter:"tech2-config-parameter", custom_current_value:"tech2-config-current",
      custom_new_value:"tech2-config-new", custom_notes:"tech2-config-notes"
    })) { if ($(id)) $(id).value = row[field]; }
    if ($("tech2-config-date")) $("tech2-config-date").value = row.custom_config_datetime.replace(" ", "T").slice(0,16) || defaultDate();
    if ($("tech2-config-add")) $("tech2-config-add").textContent = "Save Changes & Add Another";
    $("tech2-config-parameter")?.focus();
    message("Editing saved parameter. Save to apply changes.", false);
  };
  window.tech2ConfigRemoveSaved = function (miName, button) {
    const node = button.closest(".tech2-config-row");
    const rows = Array.from(document.querySelectorAll("#tech2-config-rows .tech2-config-row"));
    const index = rows.indexOf(node);
    const keep = savedRows().filter((_, i) => i !== index);
    if (!keep.length) { message("At least one parameter must remain. Edit it instead.", true); return; }
    persist(miName, keep, () => { clearEditor(); message("Parameter removed.", false); });
  };
  document.addEventListener("DOMContentLoaded", () => {
    const editor = $("tech2-config-edit");
    if (!editor) return;
    if ($("tech2-config-date") && !$("tech2-config-date").value) $("tech2-config-date").value = defaultDate();
    const save = $("tech2-config-save");
    if (save) window.TECH2_CONFIG_MI_NAME = save.dataset.miName || "";
    if (save) {
      const m = save.getAttribute("onclick")?.match(/tech2SaveConfigChanges\((.+)\)/);
      if (m) { try { window.TECH2_CONFIG_MI_NAME = JSON.parse(m[1]); } catch (_) {} }
    }
  });
})();
