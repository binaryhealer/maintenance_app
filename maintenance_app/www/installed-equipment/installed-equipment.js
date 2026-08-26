// ============================================================
// Internal Installed Equipment Web View
// Customer -> Client Type (Client Branch) -> Region (Client Branch) -> Branch -> Equipment
// ============================================================

var EQ = {
  state: {
    level: "customers",
    customerId: null,
    clientType: null,
    region: null,
    branchId: null,
    equipmentId: null
  },

  searchVal: "",
  categoryFilter: "All",
  activeTab: "overview",
  historyFilter: "all",
  historyFrom: "",
  historyTo: "",
  componentGroupFilter: "All",

  modalEq: null,
  modalComponentId: "",
  createdTicket: null,
  selectedTechnicians: [],
  technicianCache: [],

  cache: {
    customers: null,
    branches: {},
    regions: {},
    equipmentByBranch: {},
    logs: {},
    equipmentDetail: {}
  }
};

const IE_FIELDS = [
  "name",
  "custom_parent_customer",
  "custom_branch",
  "custom_asset_name",
  "custom_display_name",
  "custom_item_code",
  "custom_make",
  "custom_model",
  "custom_asset_category",
  "custom_asset_id",
  "custom_asset_type",
  "custom_site_id",
  "custom_equipment_template",
  "custom_client_type",
  "custom_next_maintenance_date",
  "custom_ownership",
  "custom_asset_status",
  "custom_operational_status",
  "custom_warranty",
  "custom_maint_frequency",
  "custom_warranty_period_years",
  "custom_coverage_type",
  "custom_client_asset_code",
  "custom_location_status",
  "custom_equipment_health",
  "custom_region",
  "custom_maintenance_contract",
  "custom_sla_rule",
  "custom_last_service_date",
  "custom_replaces_equipment",
  "custom_replaced_by_equipment",
  "custom_replacement_reason",
  "custom_replacement_date",
  "custom_commissioned_date",
  "custom_installed_date",
  "custom_installation_year",
  "custom_commissioning_status",
  "custom_last_calibration_date",
  "custom_next_calibration_date",
  "custom_last_calibration_record",
  "custom_last_commissioning_record",
  "custom_calibration_required"
];

const CAT_ICONS = {
  "Fuel Dispensing Unit": "⛽",
  "Fuel Storage Tanks & Ancillary": "🛢️",
  "Fuel Storage Tanks": "🛢️",
  "Compressor": "🔧",
  "Air Dial (Analog & Digital)": "💨",
  "Air Dial": "💨",
  "Safety & Fire Protection Systems": "🚒",
  "Electrical & Control Systems": "⚡",
  "Canopies & Lighting": "💡",
  "Signage & Customer Interfaces": "📺",
  "Drainage Systems": "🕳️"
};

const COV_MAP = {
  "Under AMC":      { cls: "cov-amc",      label: "Under AMC" },
  "Under Warranty": { cls: "cov-warranty", label: "Under Warranty" },
  "Billable":       { cls: "cov-billable", label: "Billable" },
  "Expired":        { cls: "cov-expired",  label: "Expired" },
  "Not Covered":    { cls: "cov-expired",  label: "Not Covered" },
  "Warranty":       { cls: "cov-warranty", label: "Warranty" },
  "AMC":            { cls: "cov-amc",      label: "AMC" },
  "None":           { cls: "cov-unknown",  label: "None" }
};

const TICKET_TYPE_BY_REQUEST_TYPE = {
  "Breakdown": [
    "Repair",
    "Service"
  ],

  "Maintenance Request": [
    "Preventive Maintenance",
    "Service",
    "Calibration",
    "Commissioning"
  ],

  "General Request": [
    "Installation",
    "Survey",
    "Training",
    "Audit",
    "Incident Investigation",
    "Asset Relocation",
    "Config Change",
    "Swap",
    "Loan",
    "Service",
    "Decommissioning",
    "Inspection",
    "Specialised Testing"
  ]
};


// ============================================================
// HELPERS
// ============================================================

function eqEscape(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function eqEscapeAttr(value) {
  return eqEscape(value);
}

function eqJs(value) {
  return String(value == null ? "" : value)
    .replace(/\\/g, "\\\\")
    .replace(/'/g, "\\'")
    .replace(/\r?\n/g, " ");
}

function eqUnique(values) {
  var seen = {};
  return values.filter(function(v) {
    var key = String(v || "").trim();
    if (!key || seen[key]) return false;
    seen[key] = true;
    return true;
  }).sort(function(a, b) {
    return String(a).localeCompare(String(b));
  });
}

function eqIsTruthy(value) {
  return value === 1
    || value === "1"
    || value === true
    || String(value || "").toLowerCase() === "yes"
    || String(value || "").toLowerCase() === "true";
}

function eqCall(method, args) {
  return new Promise(function(resolve, reject) {
    frappe.call({
      method: method,
      args: args || {},
      callback: function(r) {
        if (r && r.message !== undefined) {
          resolve(r.message);
        } else {
          reject("No response from " + method);
        }
      },
      error: function(err) {
        reject(err);
      }
    });
  });
}

function eqLoading() {
  var el = document.getElementById("eq-content");
  if (!el) return;
  el.innerHTML = '<div class="eq-loading"><div class="eq-spinner"></div>Loading…</div>';
}

function eqEmpty(icon, text) {
  return '<div class="eq-empty"><div class="eq-empty-icon">' + icon + '</div>' + eqEscape(text) + '</div>';
}

function eqParseDate(value) {
  if (!value) return null;

  var raw = String(value).trim();
  var dateOnly = raw.substring(0, 10);
  var parts = dateOnly.split("-");

  if (parts.length === 3) {
    var y = Number(parts[0]);
    var m = Number(parts[1]) - 1;
    var d = Number(parts[2]);
    if (!isNaN(y) && !isNaN(m) && !isNaN(d)) {
      return new Date(y, m, d, 12, 0, 0, 0);
    }
  }

  var parsed = new Date(raw);
  return isNaN(parsed.getTime()) ? null : parsed;
}

function eqToday() {
  var now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0, 0);
}

function eqFormatDate(value) {
  if (!value) return "—";

  var d = eqParseDate(value);
  if (!d) return eqEscape(value);

  var year = d.getFullYear();
  var month = String(d.getMonth() + 1).padStart(2, "0");
  var day = String(d.getDate()).padStart(2, "0");

  return year + "-" + month + "-" + day;
}

function eqFormatDateTime(value) {
  if (!value) return "—";

  var raw = String(value);
  var date = eqFormatDate(raw);
  var match = raw.match(/[ T](\d{2}:\d{2})/);

  return match ? date + " " + eqEscape(match[1]) : date;
}


function eqEquipmentAge(installedDate, installationYear) {
  var today = eqToday();

  // Full installed date has priority.
  if (installedDate) {
    var installed = eqParseDate(installedDate);

    if (installed) {
      var years = today.getFullYear() - installed.getFullYear();
      var months = today.getMonth() - installed.getMonth();

      if (today.getDate() < installed.getDate()) {
        months -= 1;
      }

      if (months < 0) {
        years -= 1;
        months += 12;
      }

      if (years < 0) return "—";

      if (years === 0) {
        return months + " month" + (months === 1 ? "" : "s");
      }

      if (months === 0) {
        return years + " year" + (years === 1 ? "" : "s");
      }

      return years + " year" + (years === 1 ? "" : "s")
        + " " + months + " month" + (months === 1 ? "" : "s");
    }
  }

  // When only a year is known, make it clear that age is approximate.
  var year = parseInt(installationYear, 10);

  if (!isNaN(year) && year > 1900 && year <= today.getFullYear()) {
    var approxYears = today.getFullYear() - year;

    if (approxYears === 0) {
      return "Less than 1 year";
    }

    return "Approx. " + approxYears + " year" + (approxYears === 1 ? "" : "s");
  }

  return "—";
}

function eqEquipmentAgeShort(installedDate, installationYear) {
  var today = eqToday();

  if (installedDate) {
    var installed = eqParseDate(installedDate);

    if (installed) {
      var years = today.getFullYear() - installed.getFullYear();
      var months = today.getMonth() - installed.getMonth();

      if (today.getDate() < installed.getDate()) {
        months -= 1;
      }

      if (months < 0) {
        years -= 1;
        months += 12;
      }

      if (years < 0) return "";

      if (years === 0) {
        return months + " mo";
      }

      return years + " yr" + (years === 1 ? "" : "s");
    }
  }

  var year = parseInt(installationYear, 10);

  if (!isNaN(year) && year > 1900 && year <= today.getFullYear()) {
    var approxYears = today.getFullYear() - year;
    return "~" + approxYears + " yr" + (approxYears === 1 ? "" : "s");
  }

  return "";
}


function eqDateStatus(value, futureLabel) {
  if (!value) {
    return { label: "Not Scheduled", cls: "eq-status-neutral", detail: "" };
  }

  var due = eqParseDate(value);
  if (!due) {
    return { label: "Not Scheduled", cls: "eq-status-neutral", detail: "" };
  }

  var days = Math.ceil((due.getTime() - eqToday().getTime()) / 86400000);

  if (days < 0) {
    var overdueDays = Math.abs(days);
    return {
      label: "Overdue",
      cls: "eq-status-bad",
      detail: overdueDays + " day" + (overdueDays === 1 ? "" : "s") + " overdue"
    };
  }

  if (days === 0) {
    return { label: "Due Today", cls: "eq-status-bad", detail: "Due today" };
  }

  if (days <= 30) {
    return {
      label: "Due Soon",
      cls: "eq-status-warn",
      detail: "Due in " + days + " day" + (days === 1 ? "" : "s")
    };
  }

  return {
    label: futureLabel || "Scheduled",
    cls: "eq-status-ok",
    detail: "Due in " + days + " days"
  };
}

function eqHealthStatus(value) {
  if (value === "Good") return { label: value, cls: "eq-status-ok" };
  if (value === "Warning") return { label: value, cls: "eq-status-warn" };
  if (value === "Critical") return { label: value, cls: "eq-status-bad" };
  return { label: value || "Unknown", cls: "eq-status-neutral" };
}

function eqOperationalStatus(value) {
  if (value === "Operational") return { label: value, cls: "eq-status-ok" };
  if (value === "Degraded" || value === "Awaiting Component") {
    return { label: value, cls: "eq-status-warn" };
  }
  if (value === "Out of Service") {
    return { label: value, cls: "eq-status-bad" };
  }
  return { label: value || "Not Set", cls: "eq-status-neutral" };
}

function eqStatusPill(state) {
  state = state || { label: "Not Set", cls: "eq-status-neutral", detail: "" };

  return '<span class="eq-status-pill ' + eqEscapeAttr(state.cls || "eq-status-neutral") + '">'
    + '<span class="eq-status-dot"></span>'
    + '<span>' + eqEscape(state.label || "Not Set") + '</span>'
    + (state.detail ? '<span class="eq-status-detail">· ' + eqEscape(state.detail) + '</span>' : '')
    + '</span>';
}

function eqSummaryCard(label, value, mono) {
  var display = value == null || value === "" ? "—" : value;
  return '<div class="eq-summary-card">'
    + '<div class="eq-summary-label">' + eqEscape(label) + '</div>'
    + '<div class="eq-summary-value' + (mono ? ' mono' : '') + '">' + display + '</div>'
    + '</div>';
}

function eqSummaryStatusCard(label, state) {
  return '<div class="eq-summary-card">'
    + '<div class="eq-summary-label">' + eqEscape(label) + '</div>'
    + '<div class="eq-summary-value">' + eqStatusPill(state) + '</div>'
    + '</div>';
}

function eqEquipmentLink(name) {
  if (!name) return "—";

  return '<a class="eq-detail-link" href="/app/installed-equipment/'
    + encodeURIComponent(name)
    + '" target="_blank">'
    + eqEscape(name)
    + '</a>';
}


function eqDocLink(doctype, name) {
  if (!name) return "—";

  var routes = {
    "Warranty": "warranty",
    "Maintenance Contract": "maintenance-contract",
    "SLA Rule": "sla-rule",
    "Calibration Record": "calibration-record",
    "Commissioning Record": "commissioning-record"
  };

  var route = routes[doctype] || String(doctype || "").toLowerCase().replaceAll(" ", "-");

  return '<a class="eq-detail-link" target="_blank" href="/app/'
    + route + '/'
    + encodeURIComponent(name)
    + '">'
    + eqEscape(name)
    + '</a>';
}


// ============================================================
// DATA
// Hierarchy source: Client Branch.custom_site_type + Client Branch.custom_region. Installed Equipment keeps its own custom_client_type field.
// Installed Equipment is loaded only after a site is selected.
// ============================================================

function eqLoadBranches(customerId) {
  if (EQ.cache.branches[customerId]) {
    return Promise.resolve(EQ.cache.branches[customerId]);
  }

  // First get the existing branch payload used by the original IE page
  // (branch labels, address, equipment count, etc.)
  var apiPromise = eqCall("maintenance_app.api.get_eq_branches", {
    customer: customerId
  }).catch(function() {
    return [];
  });

  // Separately read classification fields directly from Client Branch.
  // This makes Client Type and Region authoritative at branch/site level.
  var branchDocPromise = eqCall("frappe.client.get_list", {
    doctype: "Client Branch",
    fields: [
      "name",
      "custom_parent_customer",
      "custom_site_type",
      "custom_region",
      "custom_address"
    ],
    filters: {
      custom_parent_customer: customerId
    },
    order_by: "name asc",
    limit_page_length: 5000
  }).catch(function(err) {
    console.error("Could not read Client Branch classification fields", err);
    return [];
  });

  return Promise.all([apiPromise, branchDocPromise]).then(function(results) {
    var apiRows = results[0] || [];
    var branchDocs = results[1] || [];

    var apiMap = {};
    apiRows.forEach(function(row) {
      apiMap[row.name] = row;
    });

    var merged = branchDocs.map(function(doc) {
      var apiRow = apiMap[doc.name] || {};

      return {
        name: doc.name,
        branch_name: apiRow.branch_name || apiRow.custom_branch_name || doc.name,
        address: apiRow.address || apiRow.custom_address || doc.custom_address || "",
        equipment_count: apiRow.equipment_count || 0,
        custom_site_type: doc.custom_site_type || "",
        custom_region: doc.custom_region || ""
      };
    });

    // If the direct Client Branch query returned nothing, retain old API data
    // so the page still fails gracefully instead of becoming empty.
    if (!merged.length && apiRows.length) {
      merged = apiRows.map(function(row) {
        return {
          name: row.name,
          branch_name: row.branch_name || row.custom_branch_name || row.name,
          address: row.address || row.custom_address || "",
          equipment_count: row.equipment_count || 0,
          custom_site_type: row.custom_site_type || "",
          custom_region: row.custom_region || ""
        };
      });
    }

    EQ.cache.branches[customerId] = merged;
    return merged;
  });
}

function eqGetCustomerBranches() {
  return EQ.cache.branches[EQ.state.customerId] || [];
}


function eqLoadRegions() {
  var branches = eqGetCustomerBranches();

  var regionIds = eqUnique(
    branches
      .map(function(branch) {
        return branch.custom_region || "";
      })
      .filter(Boolean)
  );

  if (!regionIds.length) {
    EQ.cache.regions = {};
    return Promise.resolve(EQ.cache.regions);
  }

  if (!EQ.cache.regions || Array.isArray(EQ.cache.regions)) {
    EQ.cache.regions = {};
  }

  var missing = regionIds.filter(function(regionId) {
    return !EQ.cache.regions[regionId];
  });

  if (!missing.length) {
    return Promise.resolve(EQ.cache.regions);
  }

  return Promise.all(
    missing.map(function(regionId) {
      return eqCall("frappe.client.get", {
        doctype: "Region",
        name: regionId
      }).then(function(doc) {
        EQ.cache.regions[regionId] = {
          name: regionId,
          label: doc.custom_region_name || doc.region_name || doc.name
        };
      }).catch(function(err) {
        console.error("Could not resolve Region " + regionId, err);

        // Keep a cache entry so the page still works even if one Region
        // document cannot be read.
        EQ.cache.regions[regionId] = {
          name: regionId,
          label: regionId
        };
      });
    })
  ).then(function() {
    return EQ.cache.regions;
  });
}

function eqGetRegionLabel(regionId) {
  if (!regionId || regionId === "Unspecified") {
    return "Unspecified";
  }

  var map = EQ.cache.regions || {};
  var row = map[regionId];

  return row ? (row.label || row.name || regionId) : regionId;
}

function eqGetBranchLabel(branchId) {
  var branch = eqGetCustomerBranches().find(function(row) {
    return row.name === branchId;
  });

  return branch ? (branch.branch_name || branch.name) : (branchId || "Unknown Site");
}

function eqGetCustomerLabel(customerId) {
  var row = (EQ.cache.customers || []).find(function(customer) {
    return customer.name === customerId;
  });

  return row ? (row.customer_name || row.name) : (customerId || "Unknown Customer");
}

function eqLoadBranchEquipment(branchId) {
  if (EQ.cache.equipmentByBranch[branchId]) {
    return Promise.resolve(EQ.cache.equipmentByBranch[branchId]);
  }

  return eqCall("frappe.client.get_list", {
    doctype: "Installed Equipment",
    fields: IE_FIELDS,
    filters: {
      custom_parent_customer: EQ.state.customerId,
      custom_branch: branchId
    },
    order_by: "custom_asset_name asc",
    limit_page_length: 5000
  }).then(function(rows) {
    EQ.cache.equipmentByBranch[branchId] = rows || [];

    (rows || []).forEach(function(row) {
      if (row && row.name) {
        EQ.cache.equipmentDetail[row.name] = row;
      }
    });

    return EQ.cache.equipmentByBranch[branchId];
  });
}

function eqGetBranchEquipment() {
  return EQ.cache.equipmentByBranch[EQ.state.branchId] || [];
}

function eqGetEquipmentDetail(name) {
  if (EQ.cache.equipmentDetail[name]) {
    return Promise.resolve(EQ.cache.equipmentDetail[name]);
  }

  var cached = eqGetBranchEquipment().find(function(row) {
    return row.name === name;
  });

  if (cached) {
    EQ.cache.equipmentDetail[name] = cached;
    return Promise.resolve(cached);
  }

  return eqCall("frappe.client.get", {
    doctype: "Installed Equipment",
    name: name
  }).then(function(doc) {
    EQ.cache.equipmentDetail[name] = doc;
    return doc;
  });
}


// ============================================================
// NAVIGATION
// ============================================================

function eqGo(level, options) {
  options = options || {};

  if (level === "customers") {
    EQ.state = {
      level: "customers",
      customerId: null,
      clientType: null,
      region: null,
      branchId: null,
      equipmentId: null
    };
  }

  if (level === "client-types") {
    EQ.state.level = level;
    EQ.state.customerId = options.customerId || EQ.state.customerId;
    EQ.state.clientType = null;
    EQ.state.region = null;
    EQ.state.branchId = null;
    EQ.state.equipmentId = null;
  }

  if (level === "regions") {
    EQ.state.level = level;
    EQ.state.clientType = options.clientType || EQ.state.clientType;
    EQ.state.region = null;
    EQ.state.branchId = null;
    EQ.state.equipmentId = null;
  }

  if (level === "branches") {
    EQ.state.level = level;
    EQ.state.region = options.region || EQ.state.region;
    EQ.state.branchId = null;
    EQ.state.equipmentId = null;
  }

  if (level === "equipment") {
    EQ.state.level = level;
    EQ.state.branchId = options.branchId || EQ.state.branchId;
    EQ.state.equipmentId = null;
  }

  if (level === "detail") {
    EQ.state.level = level;
    EQ.state.equipmentId = options.equipmentId || EQ.state.equipmentId;
    EQ.activeTab = "overview";
    EQ.historyFilter = "all";
  }

  EQ.searchVal = "";
  EQ.categoryFilter = "All";

  var search = document.getElementById("eq-search");
  if (search) search.value = "";

  eqRender();
}

function eqOnSearch(value) {
  EQ.searchVal = String(value || "").toLowerCase();
  eqRender();
}

function eqSetCategoryFilter(category) {
  EQ.categoryFilter = category || "All";
  eqRenderEquipment();
}

function eqRender() {
  eqRenderBreadcrumb();

  // Once a customer is selected, the search is customer-wide.
  // It returns both Branch/Site matches and Equipment matches.
  if (EQ.state.customerId && EQ.searchVal) {
    eqRenderCustomerSearchResults();
    return;
  }

  switch (EQ.state.level) {
    case "customers":
      eqRenderCustomers();
      break;
    case "client-types":
      eqRenderClientTypes();
      break;
    case "regions":
      eqRenderRegions();
      break;
    case "branches":
      eqRenderBranches();
      break;
    case "equipment":
      eqRenderEquipment();
      break;
    case "detail":
      eqRenderDetail();
      break;
    default:
      eqGo("customers");
  }
}


// ============================================================
// BREADCRUMB
// ============================================================

function eqRenderBreadcrumb() {
  var el = document.getElementById("eq-breadcrumb");
  if (!el) return;

  var parts = [
    {
      label: "All Customers",
      action: "eqGo('customers')"
    }
  ];

  if (EQ.state.customerId) {
    var customer = (EQ.cache.customers || []).find(function(c) {
      return c.name === EQ.state.customerId;
    });

    parts.push({
      label: customer ? customer.customer_name : EQ.state.customerId,
      action: "eqGo('client-types',{customerId:'" + eqJs(EQ.state.customerId) + "'})"
    });
  }

  if (EQ.state.clientType) {
    parts.push({
      label: EQ.state.clientType,
      action: "eqGo('regions',{clientType:'" + eqJs(EQ.state.clientType) + "'})"
    });
  }

  if (EQ.state.region) {
    parts.push({
      label: eqGetRegionLabel(EQ.state.region),
      action: "eqGo('branches',{region:'" + eqJs(EQ.state.region) + "'})"
    });
  }

  if (EQ.state.branchId) {
    parts.push({
      label: eqGetBranchLabel(EQ.state.branchId),
      action: "eqGo('equipment',{branchId:'" + eqJs(EQ.state.branchId) + "'})"
    });
  }

  if (EQ.state.equipmentId) {
    var eq = EQ.cache.equipmentDetail[EQ.state.equipmentId]
      || eqGetBranchEquipment().find(function(row) {
        return row.name === EQ.state.equipmentId;
      });

    parts.push({
      label: eq ? (eq.custom_asset_name || eq.custom_display_name || eq.name) : EQ.state.equipmentId,
      action: null
    });
  }

  el.innerHTML = parts.map(function(p, index) {
    var isLast = index === parts.length - 1;

    if (isLast || !p.action) {
      return '<span class="bc-item current">' + eqEscape(p.label) + '</span>';
    }

    return '<span class="bc-item" onclick="' + p.action + '">'
      + eqEscape(p.label)
      + '</span><span class="bc-sep">›</span>';
  }).join("");
}


// ============================================================
// CUSTOMER
// ============================================================

function eqRenderCustomers() {
  var el = document.getElementById("eq-content");

  if (EQ.cache.customers) {
    eqBuildCustomerList(el, EQ.cache.customers);
    return;
  }

  eqLoading();

  eqCall("maintenance_app.api.get_eq_customers")
    .then(function(rows) {
      EQ.cache.customers = rows || [];
      eqBuildCustomerList(el, EQ.cache.customers);
    })
    .catch(function(err) {
      console.error(err);
      el.innerHTML = eqEmpty("⚠️", "Could not load customers.");
    });
}

function eqBuildCustomerList(el, customers) {
  var list = customers.filter(function(c) {
    var haystack = (
      (c.customer_name || "") + " "
      + (c.customer_group || "") + " "
      + (c.name || "")
    ).toLowerCase();

    return !EQ.searchVal || haystack.includes(EQ.searchVal);
  });

  var html = '<div class="eq-page-head">'
    + '<div>'
    + '<div class="eq-page-title">Installed Equipment</div>'
    + '<div class="eq-page-subtitle">Browse sites by customer, client type and region, then view installed equipment.</div>'
    + '</div>'
    + '</div>';

  html += '<div class="eq-level-label">Customers · ' + list.length + '</div>';
  html += '<div class="eq-customer-list">';

  if (!list.length) {
    html += eqEmpty("🔍", "No customers match your search.");
  } else {
    list.forEach(function(c) {
      html += '<div class="eq-customer-row" onclick="eqGo(\'client-types\',{customerId:\'' + eqJs(c.name) + '\'})">'
        + '<div class="eq-customer-avatar">🏢</div>'
        + '<div class="eq-customer-info">'
        + '<div class="eq-customer-name">' + eqEscape(c.customer_name || c.name) + '</div>'
        + '<div class="eq-customer-meta">'
        + eqEscape(c.customer_group || "")
        + (c.branch_count ? " · " + c.branch_count + " site(s)" : "")
        + '</div>'
        + '</div>'
        + (c.open_tickets
          ? '<span class="cov-badge cov-expired">' + eqEscape(c.open_tickets) + ' open</span>'
          : '')
        + '<span class="eq-customer-arrow">›</span>'
        + '</div>';
    });
  }

  html += '</div>';
  el.innerHTML = html;
}


// ============================================================
// CLIENT TYPE
// Derived from Client Branch.custom_site_type
// ============================================================

function eqRenderClientTypes() {
  var el = document.getElementById("eq-content");
  eqLoading();

  eqLoadBranches(EQ.state.customerId)
    .then(function(branches) {
      var values = eqUnique(branches.map(function(branch) {
        return branch.custom_site_type || "Unspecified";
      }));

      var list = values.filter(function(value) {
        return !EQ.searchVal || value.toLowerCase().includes(EQ.searchVal);
      });

      var html = '<div class="eq-page-head"><div>'
        + '<div class="eq-page-title">Client Type</div>'
        + '<div class="eq-page-subtitle">Select the client/site type.</div>'
        + '</div></div>';

      html += '<div class="eq-cards-grid">';

      if (!list.length) {
        html += eqEmpty("🧭", "No client types found on Client Branch.");
      } else {
        list.forEach(function(value) {
          var typeBranches = branches.filter(function(branch) {
            return (branch.custom_site_type || "Unspecified") === value;
          });

          html += '<div class="eq-card" onclick="eqGo(\'regions\',{clientType:\'' + eqJs(value) + '\'})">'
            + '<div class="eq-card-icon">🏷️</div>'
            + '<div class="eq-card-name">' + eqEscape(value) + '</div>'
            + '<div class="eq-card-sub">' + typeBranches.length + ' site' + (typeBranches.length === 1 ? '' : 's') + '</div>'
            + '</div>';
        });
      }

      html += '</div>';
      el.innerHTML = html;
      eqRenderBreadcrumb();
    })
    .catch(function(err) {
      console.error(err);
      el.innerHTML = eqEmpty("⚠️", "Could not load client types from Client Branch.");
    });
}


// ============================================================
// REGION
// Derived from Client Branch.custom_region
// ============================================================

function eqRenderRegions() {
  var el = document.getElementById("eq-content");
  eqLoading();

  eqLoadRegions().then(function() {
    var branches = eqGetCustomerBranches().filter(function(branch) {
      return (branch.custom_site_type || "Unspecified") === EQ.state.clientType;
    });

    var regionIds = eqUnique(branches.map(function(branch) {
      return branch.custom_region || "Unspecified";
    }));

    var regions = regionIds.map(function(regionId) {
      return {
        id: regionId,
        label: regionId === "Unspecified"
          ? "Unspecified"
          : eqGetRegionLabel(regionId)
      };
    });

    regions.sort(function(a, b) {
      return String(a.label).localeCompare(String(b.label));
    });

    regions = regions.filter(function(region) {
      var haystack = (region.label + " " + region.id).toLowerCase();
      return !EQ.searchVal || haystack.includes(EQ.searchVal);
    });

    var html = '<div class="eq-page-head"><div>'
      + '<div class="eq-page-title">Region</div>'
      + '<div class="eq-page-subtitle">' + eqEscape(EQ.state.clientType || "") + '</div>'
      + '</div></div>';

    html += '<div class="eq-cards-grid">';

    if (!regions.length) {
      html += eqEmpty("📍", "No regions found on Client Branch.");
    } else {
      regions.forEach(function(region) {
        var regionBranches = branches.filter(function(branch) {
          return (branch.custom_region || "Unspecified") === region.id;
        });

        html += '<div class="eq-card" onclick="eqGo(\'branches\',{region:\'' + eqJs(region.id) + '\'})">'
          + '<div class="eq-card-icon">📍</div>'
          + '<div class="eq-card-name">' + eqEscape(region.label) + '</div>'
          + '<div class="eq-card-sub">' + regionBranches.length + ' site' + (regionBranches.length === 1 ? '' : 's') + '</div>'
          + '</div>';
      });
    }

    html += '</div>';
    el.innerHTML = html;
    eqRenderBreadcrumb();
  }).catch(function(err) {
    console.error(err);
    el.innerHTML = eqEmpty("⚠️", "Could not load regions.");
  });
}


// ============================================================
// BRANCH / SITE
// Client Type + Region filters are applied to Client Branch records.
// ============================================================

function eqRenderBranches() {
  var el = document.getElementById("eq-content");
  eqLoading();

  eqLoadBranches(EQ.state.customerId)
    .then(function(branches) {
      var cards = branches.filter(function(branch) {
        return (branch.custom_site_type || "Unspecified") === EQ.state.clientType
          && (branch.custom_region || "Unspecified") === EQ.state.region;
      });

      cards = cards.filter(function(branch) {
        var haystack = (
          (branch.branch_name || "") + " "
          + (branch.address || "") + " "
          + (branch.name || "")
        ).toLowerCase();

        return !EQ.searchVal || haystack.includes(EQ.searchVal);
      });

      var html = '<div class="eq-page-head"><div>'
        + '<div class="eq-page-title">Branch / Site</div>'
        + '<div class="eq-page-subtitle">'
        + eqEscape(EQ.state.clientType || "")
        + ' · '
        + eqEscape(EQ.state.region || "")
        + '</div>'
        + '</div></div>';

      html += '<div class="eq-cards-grid">';

      if (!cards.length) {
        html += eqEmpty("🏪", "No sites match this client type and region.");
      } else {
        cards.forEach(function(branch) {
          html += '<div class="eq-card" onclick="eqGo(\'equipment\',{branchId:\'' + eqJs(branch.name) + '\'})">'
            + '<div class="eq-card-icon">🏪</div>'
            + '<div class="eq-card-name">' + eqEscape(branch.branch_name || branch.name) + '</div>'
            + '<div class="eq-card-sub">' + eqEscape(branch.address || "") + '</div>'
            + (branch.equipment_count
                ? '<div class="eq-card-sub">' + branch.equipment_count + ' equipment</div>'
                : '')
            + '</div>';
        });
      }

      html += '</div>';
      el.innerHTML = html;
      eqRenderBreadcrumb();
    })
    .catch(function(err) {
      console.error(err);
      el.innerHTML = eqEmpty("⚠️", "Could not load sites.");
    });
}


// ============================================================
// EQUIPMENT
// ============================================================

function eqRenderEquipment() {
  var el = document.getElementById("eq-content");
  eqLoading();

  eqLoadBranchEquipment(EQ.state.branchId)
    .then(function(rows) {
      var categories = ["All"].concat(eqUnique(rows.map(function(r) {
        return r.custom_asset_category || "Uncategorized";
      })));

      var list = rows.filter(function(r) {
        var category = r.custom_asset_category || "Uncategorized";

        if (EQ.categoryFilter !== "All" && category !== EQ.categoryFilter) {
          return false;
        }

        var haystack = (
          (r.custom_asset_name || "") + " "
          + (r.custom_display_name || "") + " "
          + (r.custom_make || "") + " "
          + (r.custom_model || "") + " "
          + (r.custom_asset_id || "") + " "
          + (r.custom_client_asset_code || "") + " "
          + (r.custom_site_id || "")
        ).toLowerCase();

        return !EQ.searchVal || haystack.includes(EQ.searchVal);
      });

      var html = '<div class="eq-page-head"><div>'
        + '<div class="eq-page-title">' + eqEscape(eqGetBranchLabel(EQ.state.branchId)) + '</div>'
        + '<div class="eq-page-subtitle">'
        + eqEscape(eqGetCustomerLabel(EQ.state.customerId))
        + ' · '
        + eqEscape(EQ.state.clientType || "")
        + ' · '
        + eqEscape(eqGetRegionLabel(EQ.state.region))
        + '</div>'
        + '</div></div>';

      html += '<div class="eq-filter-bar">';
      categories.forEach(function(category) {
        html += '<button class="eq-filter-btn'
          + (EQ.categoryFilter === category ? ' active' : '')
          + '" onclick="eqSetCategoryFilter(\'' + eqJs(category) + '\')">'
          + eqEscape(category)
          + '</button>';
      });
      html += '</div>';

      if (!list.length) {
        html += eqEmpty("🖥️", "No equipment matches the current filter.");
        el.innerHTML = html;
        return;
      }

      html += '<div class="eq-unit-grid">';

      list.forEach(function(eq) {
        var health = eq.custom_equipment_health || "Unknown";
        var hCls = health === "Good"
          ? "h-good"
          : health === "Warning"
            ? "h-warn"
            : health === "Critical"
              ? "h-crit"
              : "h-unk";

        var covKey = eq.custom_coverage_type || "";
        var cov = COV_MAP[covKey] || {
          cls: "cov-unknown",
          label: covKey || "Not Set"
        };

        var maintenanceState = eqDateStatus(eq.custom_next_maintenance_date, "Scheduled");
        var calibrationRequired = eqIsTruthy(eq.custom_calibration_required);
        var calibrationState = calibrationRequired
          ? eqDateStatus(eq.custom_next_calibration_date, "Valid")
          : null;

        html += '<div class="eq-unit-card" onclick="eqGo(\'detail\',{equipmentId:\'' + eqJs(eq.name) + '\'})">'
          + '<div class="eq-unit-header">'
          + '<div>'
          + '<div class="eq-unit-name">' + eqEscape(eq.custom_asset_name || eq.custom_display_name || eq.name) + '</div>'
          + '<div class="eq-unit-model">' + eqEscape(((eq.custom_make || "") + " " + (eq.custom_model || "")).trim() || "—") + '</div>'
          + '</div>'
          + '<div class="health-dot ' + hCls + '" title="' + eqEscapeAttr(health) + '"></div>'
          + '</div>'
          + '<div class="eq-unit-meta">'
          + (eq.custom_asset_id ? 'S/N ' + eqEscape(eq.custom_asset_id) + '<br>' : '')
          + (eq.custom_site_id ? eqEscape(eq.custom_site_id) + ' · ' : '')
          + eqEscape(eq.custom_asset_status || "—")
          + (eqEquipmentAgeShort(eq.custom_installed_date, eq.custom_installation_year)
              ? '<br>Age ' + eqEscape(eqEquipmentAgeShort(eq.custom_installed_date, eq.custom_installation_year))
              : '')
          + '</div>'
          + '<div class="eq-unit-alerts">'
          + eqUnitAlert("Maintenance", maintenanceState)
          + (calibrationRequired ? eqUnitAlert("Calibration", calibrationState) : '')
          + '</div>'
          + '<span class="cov-badge ' + cov.cls + '">' + eqEscape(cov.label) + '</span>'
          + '</div>';
      });

      html += '</div>';
      el.innerHTML = html;
    })
    .catch(function(err) {
      console.error(err);
      el.innerHTML = eqEmpty("⚠️", "Could not load equipment for this site.");
    });
}


function eqUnitAlert(label, state) {
  if (!state || !state.label) return "";

  return '<div class="eq-unit-alert">'
    + '<span class="eq-unit-alert-label">' + eqEscape(label) + '</span>'
    + '<span class="' + eqEscapeAttr(state.cls || "eq-status-neutral") + ' eq-unit-alert-value">'
    + eqEscape(state.label)
    + (state.detail ? ' · ' + eqEscape(state.detail) : '')
    + '</span>'
    + '</div>';
}



// ============================================================
// CUSTOMER-WIDE MIXED SEARCH
// Branch / Site matches + Equipment matches
// ============================================================

function eqLoadCustomerEquipment(customerId) {
  return eqLoadBranches(customerId)
    .then(function(branches) {
      return eqLoadRegions().then(function() {
        return branches;
      });
    })
    .then(function(branches) {
      if (!branches.length) return [];

      var jobs = branches.map(function(branch) {
        return eqLoadBranchEquipment(branch.name)
          .then(function(rows) {
            return (rows || []).map(function(eq) {
              return {
                equipment: eq,
                branchId: branch.name,
                branchName: branch.branch_name || branch.name,
                branchAddress: branch.address || "",
                clientType: branch.custom_site_type || "",
                regionId: branch.custom_region || "",
                regionName: eqGetRegionLabel(branch.custom_region)
              };
            });
          })
          .catch(function(err) {
            console.error("Could not load equipment for branch " + branch.name, err);
            return [];
          });
      });

      return Promise.all(jobs).then(function(groups) {
        return groups.reduce(function(all, group) {
          return all.concat(group);
        }, []);
      });
    });
}

function eqOpenCustomerSearchResult(equipmentId, clientType, regionId, branchId) {
  EQ.state.clientType = clientType || null;
  EQ.state.region = regionId || null;
  EQ.state.branchId = branchId || null;

  eqGo("detail", {
    equipmentId: equipmentId
  });
}

function eqOpenCustomerBranchResult(clientType, regionId, branchId) {
  EQ.state.clientType = clientType || null;
  EQ.state.region = regionId || null;
  EQ.state.branchId = branchId || null;
  EQ.state.equipmentId = null;
  EQ.state.level = "equipment";

  EQ.searchVal = "";
  EQ.categoryFilter = "All";

  var search = document.getElementById("eq-search");
  if (search) search.value = "";

  eqRender();
}

function eqRenderCustomerSearchResults() {
  var el = document.getElementById("eq-content");
  eqLoading();

  var query = EQ.searchVal;
  var customerId = EQ.state.customerId;

  Promise.all([
    eqLoadBranches(customerId).then(function(branches) {
      return eqLoadRegions().then(function() {
        return branches;
      });
    }),
    eqLoadCustomerEquipment(customerId)
  ])
    .then(function(results) {
      var branches = results[0] || [];
      var equipmentRecords = results[1] || [];

      var branchMatches = branches.filter(function(branch) {
        var regionName = eqGetRegionLabel(branch.custom_region);

        var haystack = (
          (branch.branch_name || "") + " "
          + (branch.name || "") + " "
          + (branch.address || "") + " "
          + (branch.custom_site_type || "") + " "
          + (regionName || "")
        ).toLowerCase();

        return haystack.includes(query);
      });

      var equipmentMatches = equipmentRecords.filter(function(record) {
        var eq = record.equipment;

        var haystack = (
          (eq.custom_asset_name || "") + " "
          + (eq.custom_display_name || "") + " "
          + (eq.custom_make || "") + " "
          + (eq.custom_model || "") + " "
          + (eq.custom_asset_id || "") + " "
          + (eq.custom_client_asset_code || "") + " "
          + (eq.custom_site_id || "") + " "
          + (eq.custom_asset_category || "") + " "
          + (record.branchName || "") + " "
          + (record.branchAddress || "") + " "
          + (record.clientType || "") + " "
          + (record.regionName || "")
        ).toLowerCase();

        return haystack.includes(query);
      });

      var total = branchMatches.length + equipmentMatches.length;

      var html = '<div class="eq-page-head"><div>'
        + '<div class="eq-page-title">Search Results</div>'
        + '<div class="eq-page-subtitle">'
        + eqEscape(eqGetCustomerLabel(customerId))
        + ' · '
        + total
        + ' result'
        + (total === 1 ? '' : 's')
        + ' for “'
        + eqEscape(query)
        + '”'
        + '</div>'
        + '</div></div>';

      if (!total) {
        html += eqEmpty("🔎", "No branch/site or equipment found for this customer.");
        el.innerHTML = html;
        return;
      }

      // -------------------------------------------------------
      // Branch / Site matches
      // -------------------------------------------------------
      if (branchMatches.length) {
        html += '<div class="eq-search-section">'
          + '<div class="eq-search-section-head">'
          + '<div class="eq-search-section-title">Branches / Sites</div>'
          + '<div class="eq-search-section-count">' + branchMatches.length + '</div>'
          + '</div>'
          + '<div class="eq-search-branch-grid">';

        branchMatches.forEach(function(branch) {
          var regionName = eqGetRegionLabel(branch.custom_region);

          html += '<div class="eq-search-branch-card" onclick="eqOpenCustomerBranchResult(\''
            + eqJs(branch.custom_site_type || "") + '\',\''
            + eqJs(branch.custom_region || "") + '\',\''
            + eqJs(branch.name) + '\')">'
            + '<div class="eq-search-branch-top">'
            + '<div>'
            + '<div class="eq-unit-name">'
            + eqEscape(branch.branch_name || branch.name)
            + '</div>'
            + '<div class="eq-search-result-path">'
            + eqEscape([
                branch.custom_site_type,
                regionName
              ].filter(Boolean).join(" · "))
            + '</div>'
            + '</div>'
            + '<div class="eq-search-open-label">Open Branch →</div>'
            + '</div>'
            + (branch.address
                ? '<div class="eq-search-branch-address">'
                  + eqEscape(branch.address)
                  + '</div>'
                : '')
            + '<div class="eq-search-branch-footer">'
            + eqEscape(String(branch.equipment_count || 0))
            + ' equipment'
            + '</div>'
            + '</div>';
        });

        html += '</div></div>';
      }

      // -------------------------------------------------------
      // Equipment matches
      // -------------------------------------------------------
      if (equipmentMatches.length) {
        html += '<div class="eq-search-section">'
          + '<div class="eq-search-section-head">'
          + '<div class="eq-search-section-title">Equipment</div>'
          + '<div class="eq-search-section-count">' + equipmentMatches.length + '</div>'
          + '</div>'
          + '<div class="eq-search-results-list">';

        equipmentMatches.forEach(function(record) {
          var eq = record.equipment;

          var health = eq.custom_equipment_health || "Unknown";
          var hCls = health === "Good"
            ? "h-good"
            : health === "Warning"
              ? "h-warn"
              : health === "Critical"
                ? "h-crit"
                : "h-unk";

          var covKey = eq.custom_coverage_type || "";
          var cov = COV_MAP[covKey] || {
            cls: "cov-unknown",
            label: covKey || "Not Set"
          };

          var maintenanceState = eqDateStatus(
            eq.custom_next_maintenance_date,
            "Scheduled"
          );

          var calibrationRequired = eqIsTruthy(
            eq.custom_calibration_required
          );

          var calibrationState = calibrationRequired
            ? eqDateStatus(eq.custom_next_calibration_date, "Valid")
            : null;

          var age = eqEquipmentAgeShort(
            eq.custom_installed_date,
            eq.custom_installation_year
          );

          html += '<div class="eq-search-result-card" onclick="eqOpenCustomerSearchResult(\''
            + eqJs(eq.name) + '\',\''
            + eqJs(record.clientType) + '\',\''
            + eqJs(record.regionId) + '\',\''
            + eqJs(record.branchId) + '\')">'

            + '<div class="eq-search-result-main">'
            + '<div class="eq-search-result-title-row">'
            + '<div>'
            + '<div class="eq-unit-name">'
            + eqEscape(eq.custom_asset_name || eq.custom_display_name || eq.name)
            + '</div>'
            + '<div class="eq-unit-model">'
            + eqEscape(
                ((eq.custom_make || "") + " " + (eq.custom_model || "")).trim()
                || "—"
              )
            + '</div>'
            + '</div>'
            + '<div class="health-dot ' + hCls + '" title="' + eqEscapeAttr(health) + '"></div>'
            + '</div>'

            + '<div class="eq-search-result-path">'
            + eqEscape(
                [record.clientType, record.regionName, record.branchName]
                  .filter(Boolean)
                  .join(" · ")
              )
            + '</div>'

            + '<div class="eq-unit-meta">'
            + (eq.custom_asset_id
                ? 'S/N ' + eqEscape(eq.custom_asset_id)
                : '')
            + (eq.custom_client_asset_code
                ? (eq.custom_asset_id ? ' · ' : '') + 'Tag ' + eqEscape(eq.custom_client_asset_code)
                : '')
            + ((eq.custom_asset_id || eq.custom_client_asset_code)
                ? '<br>'
                : '')
            + eqEscape(eq.custom_asset_status || "—")
            + (age ? ' · Age ' + eqEscape(age) : '')
            + '</div>'
            + '</div>'

            + '<div class="eq-search-result-side">'
            + eqUnitAlert("Maintenance", maintenanceState)
            + (calibrationRequired
                ? eqUnitAlert("Calibration", calibrationState)
                : '')
            + '<span class="cov-badge ' + cov.cls + '">'
            + eqEscape(cov.label)
            + '</span>'
            + '</div>'

            + '</div>';
        });

        html += '</div></div>';
      }

      el.innerHTML = html;
    })
    .catch(function(err) {
      console.error("Customer mixed search failed", err);
      el.innerHTML = eqEmpty(
        "⚠️",
        "Could not search branches/sites and equipment for this customer."
      );
    });
}


// ============================================================
// EQUIPMENT DETAIL
// ============================================================

function eqRenderDetail() {
  var el = document.getElementById("eq-content");
  eqLoading();

  eqGetEquipmentDetail(EQ.state.equipmentId)
    .then(function(eq) {
      EQ.cache.equipmentDetail[eq.name] = eq;
      eqBuildDetail(el, eq);
      eqRenderBreadcrumb();
    })
    .catch(function(err) {
      console.error(err);
      el.innerHTML = eqEmpty("⚠️", "Could not load equipment detail.");
    });
}

function eqBuildDetail(el, eq) {
  var health = eq.custom_equipment_health || "Unknown";
  var healthClass = health === "Good"
    ? "h-good"
    : health === "Warning"
      ? "h-warn"
      : health === "Critical"
        ? "h-crit"
        : "h-unk";

  var covKey = eq.custom_coverage_type || "";
  var cov = COV_MAP[covKey] || {
    cls: "cov-unknown",
    label: covKey || "Not Set"
  };

  var titleBits = [];
  if (eq.custom_make) titleBits.push(eq.custom_make);
  if (eq.custom_model) titleBits.push(eq.custom_model);

  var serialBits = [];
  if (eq.custom_asset_id) serialBits.push("S/N " + eq.custom_asset_id);
  if (eq.custom_client_asset_code) serialBits.push("Tag " + eq.custom_client_asset_code);
  if (eq.custom_site_id) serialBits.push(eq.custom_site_id);

  var contextBits = [
    EQ.state.clientType || "",
    eqGetRegionLabel(EQ.state.region),
    eqGetBranchLabel(EQ.state.branchId)
  ].filter(Boolean);

  var html = '<div class="eq-detail-wrap">'
    + '<div class="eq-detail-header">'
    + '<div>'
    + '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
    + '<div class="health-dot ' + healthClass + '"></div>'
    + '<div class="eq-detail-title">' + eqEscape(eq.custom_asset_name || eq.custom_display_name || eq.name)
    + (titleBits.length ? ' — ' + eqEscape(titleBits.join(" ")) : '')
    + '</div>'
    + '<span class="cov-badge ' + cov.cls + '">' + eqEscape(cov.label) + '</span>'
    + '</div>'
    + '<div class="eq-detail-context">'
    + '<div class="eq-detail-customer">' + eqEscape(eqGetCustomerLabel(EQ.state.customerId)) + '</div>'
    + '<div class="eq-detail-path">' + eqEscape(contextBits.join(" · ")) + '</div>'
    + '</div>'
    + '<div class="eq-detail-serial">'
    + eqEscape(serialBits.length ? serialBits.join(" · ") : eq.name)
    + '</div>'
    + '</div>'

    + '<div class="eq-detail-actions">'
    + '<button class="eq-btn eq-btn-primary" onclick="eqOpenTicketModal(\'' + eqJs(eq.name) + '\')">+ Open Ticket</button>'
    + '<a class="eq-btn eq-btn-ghost" href="/app/installed-equipment/' + encodeURIComponent(eq.name) + '">Open in Desk ↗</a>'
    + '</div>'
    + '</div>'

    + '<div class="eq-tabs-bar">'
    + eqTabButton("overview", "Overview")
    + eqTabButton("maintenance", "Maintenance")
    + eqTabButton("calibration", "Calibration")
    + eqTabButton("warranty", "Warranty")
    + eqTabButton("history", "History", "…")
    + eqTabButton("components", "Components", "…")
    + '</div>'

    + '<div class="eq-tab-panel' + (EQ.activeTab === "overview" ? ' active' : '') + '" id="eq-tab-overview">'
    + eqBuildOverviewTab(eq)
    + '</div>'

    + '<div class="eq-tab-panel' + (EQ.activeTab === "maintenance" ? ' active' : '') + '" id="eq-tab-maintenance">'
    + eqBuildMaintenanceTab(eq)
    + '</div>'

    + '<div class="eq-tab-panel' + (EQ.activeTab === "calibration" ? ' active' : '') + '" id="eq-tab-calibration">'
    + eqBuildCalibrationTab(eq)
    + '</div>'

    + '<div class="eq-tab-panel' + (EQ.activeTab === "warranty" ? ' active' : '') + '" id="eq-tab-warranty">'
    + eqBuildWarrantyTab(eq)
    + '</div>'

    + '<div class="eq-tab-panel' + (EQ.activeTab === "history" ? ' active' : '') + '" id="eq-tab-history">'
    + '<div class="eq-loading"><div class="eq-spinner"></div>Loading history…</div>'
    + '</div>'

    + '<div class="eq-tab-panel' + (EQ.activeTab === "components" ? ' active' : '') + '" id="eq-tab-components">'
    + '<div class="eq-loading"><div class="eq-spinner"></div>Loading components…</div>'
    + '</div>'

    + '</div>';

  el.innerHTML = html;

  eqLoadLogs(eq.name);
}

function eqTabButton(id, label, count) {
  return '<button class="eq-tab-btn'
    + (EQ.activeTab === id ? ' active' : '')
    + '" id="eq-tabbtn-' + id + '" onclick="eqSwitchTab(\'' + id + '\')">'
    + eqEscape(label)
    + (count ? ' <span class="eq-tab-count" id="eq-tabcount-' + id + '">' + count + '</span>' : '')
    + '</button>';
}

function eqSwitchTab(tab) {
  EQ.activeTab = tab;

  document.querySelectorAll(".eq-tab-btn").forEach(function(btn) {
    btn.classList.remove("active");
  });

  document.querySelectorAll(".eq-tab-panel").forEach(function(panel) {
    panel.classList.remove("active");
  });

  var btn = document.getElementById("eq-tabbtn-" + tab);
  var panel = document.getElementById("eq-tab-" + tab);

  if (btn) btn.classList.add("active");
  if (panel) panel.classList.add("active");
}

function eqBuildOverviewTab(eq) {
  var html = '<div class="eq-section-heading">Equipment Overview</div>'
    + '<div class="eq-summary-grid">'
    + eqSummaryCard("Equipment Status", eqEscape(eq.custom_asset_status || "—"))
    + eqSummaryStatusCard("Operational Status", eqOperationalStatus(eq.custom_operational_status))
    + eqSummaryStatusCard("Health", eqHealthStatus(eq.custom_equipment_health || "Unknown"))
    + eqSummaryCard("Ownership", eqEscape(eq.custom_ownership || "—"))
    + eqSummaryCard("Make", eqEscape(eq.custom_make || "—"))
    + eqSummaryCard("Model", eqEscape(eq.custom_model || "—"))
    + eqSummaryCard("Serial Number", eqEscape(eq.custom_asset_id || "—"), true)
    + eqSummaryCard("Client Asset Tag", eqEscape(eq.custom_client_asset_code || "—"), true)
    + eqSummaryCard("Site Position", eqEscape(eq.custom_site_id || "—"), true)
    + eqSummaryCard("Equipment Type", eqEscape(eq.custom_asset_type || "—"))
    + eqSummaryCard("Installed Date", eqFormatDate(eq.custom_installed_date))
    + eqSummaryCard("Installation Year", eq.custom_installation_year ? eqEscape(eq.custom_installation_year) : "—")
    + eqSummaryCard("Equipment Age", eqEscape(eqEquipmentAge(eq.custom_installed_date, eq.custom_installation_year)))
    + eqSummaryCard("Commissioned Date", eqFormatDate(eq.custom_commissioned_date))
    + eqSummaryCard("Commissioning Status", eqEscape(eq.custom_commissioning_status || "—"))
    + eqSummaryCard("Commissioning Record", eqDocLink("Commissioning Record", eq.custom_last_commissioning_record))
    + '</div>';

  var hasLifecycle = !!(
    eq.custom_replaces_equipment
    || eq.custom_replaced_by_equipment
    || eq.custom_replacement_reason
    || eq.custom_replacement_date
  );

  if (hasLifecycle) {
    html += '<div class="eq-subsection">'
      + '<div class="eq-section-heading">Lifecycle / Replacement</div>'
      + '<div class="eq-summary-grid">'
      + eqSummaryCard("Replaces Equipment", eqEquipmentLink(eq.custom_replaces_equipment))
      + eqSummaryCard("Replaced By Equipment", eqEquipmentLink(eq.custom_replaced_by_equipment))
      + eqSummaryCard("Replacement Date", eqFormatDate(eq.custom_replacement_date))
      + eqSummaryCard("Replacement Reason", eqEscape(eq.custom_replacement_reason || "—"))
      + '</div>'
      + '</div>';
  }

  return html;
}

function eqBuildMaintenanceTab(eq) {
  var state = eqDateStatus(eq.custom_next_maintenance_date, "Scheduled");

  return '<div class="eq-section-heading">Maintenance</div>'
    + '<div class="eq-summary-grid">'
    + eqSummaryCard("Last Service", eqFormatDate(eq.custom_last_service_date))
    + eqSummaryCard("Next Maintenance", eqFormatDate(eq.custom_next_maintenance_date))
    + eqSummaryStatusCard("Maintenance Status", state)
    + eqSummaryCard("Frequency", eqEscape(eq.custom_maint_frequency || "—"))
    + eqSummaryCard("Maintenance Contract", eqDocLink("Maintenance Contract", eq.custom_maintenance_contract))
    + eqSummaryCard("SLA Rule", eqDocLink("SLA Rule", eq.custom_sla_rule))
    + '</div>';
}

function eqBuildCalibrationTab(eq) {
  var required = eqIsTruthy(eq.custom_calibration_required);

  if (!required) {
    return '<div class="eq-section-heading">Calibration</div>'
      + '<div class="eq-panel-note">Calibration is not required for this equipment.</div>';
  }

  var state = eqDateStatus(eq.custom_next_calibration_date, "Valid");

  return '<div class="eq-section-heading">Calibration</div>'
    + '<div class="eq-summary-grid">'
    + eqSummaryCard("Calibration Required", "Yes")
    + eqSummaryCard("Last Calibration", eqFormatDateTime(eq.custom_last_calibration_date))
    + eqSummaryCard("Next Calibration", eqFormatDate(eq.custom_next_calibration_date))
    + eqSummaryStatusCard("Calibration Status", state)
    + eqSummaryCard("Last Calibration Record", eqDocLink("Calibration Record", eq.custom_last_calibration_record))
    + '</div>';
}

function eqBuildWarrantyTab(eq) {
  return '<div class="eq-section-heading">Warranty & Coverage</div>'
    + '<div class="eq-summary-grid">'
    + eqSummaryCard("Warranty", eqDocLink("Warranty", eq.custom_warranty))
    + eqSummaryCard(
        "Warranty Period",
        eq.custom_warranty_period_years
          ? eqEscape(eq.custom_warranty_period_years) + " year" + (Number(eq.custom_warranty_period_years) === 1 ? "" : "s")
          : "—"
      )
    + eqSummaryCard("Coverage Type", eqEscape(eq.custom_coverage_type || "—"))
    + '</div>';
}


// ============================================================
// LOGS / HISTORY / COMPONENTS
// ============================================================

function eqLoadLogs(eqName) {
  if (EQ.cache.logs[eqName]) {
    eqBuildHistoryAndComponents(EQ.cache.logs[eqName]);
    return;
  }

  eqCall("maintenance_app.api.get_eq_logs", {
    equipment: eqName
  }).then(function(data) {
    EQ.cache.logs[eqName] = data || {
      service: [],
      lifecycle: [],
      config: [],
      components: []
    };

    eqBuildHistoryAndComponents(EQ.cache.logs[eqName]);
  }).catch(function(err) {
    console.error(err);

    var history = document.getElementById("eq-tab-history");
    var components = document.getElementById("eq-tab-components");

    if (history) history.innerHTML = eqEmpty("⚠️", "Could not load history.");
    if (components) components.innerHTML = eqEmpty("⚠️", "Could not load components.");
  });
}

function eqBuildHistoryAndComponents(logs) {
  var historyCount = (logs.service || []).length
    + (logs.lifecycle || []).length
    + (logs.config || []).length;

  var histCount = document.getElementById("eq-tabcount-history");
  var compCount = document.getElementById("eq-tabcount-components");

  if (histCount) histCount.textContent = historyCount;
  if (compCount) compCount.textContent = (logs.components || []).length;

  var history = document.getElementById("eq-tab-history");
  var components = document.getElementById("eq-tab-components");

  if (history) history.innerHTML = eqBuildHistoryTab(logs);
  if (components) components.innerHTML = eqBuildComponents(logs.components || []);
}

function eqSetHistoryFilter(filter) {
  EQ.historyFilter = filter;
  eqRefreshHistoryPanel();
}

function eqSetHistoryDate(field, value) {
  if (field === "from") {
    EQ.historyFrom = value || "";
  } else if (field === "to") {
    EQ.historyTo = value || "";
  }

  eqRefreshHistoryPanel();
}

function eqClearHistoryDates() {
  EQ.historyFrom = "";
  EQ.historyTo = "";
  eqRefreshHistoryPanel();
}

function eqRefreshHistoryPanel() {
  var logs = EQ.cache.logs[EQ.state.equipmentId];
  var panel = document.getElementById("eq-tab-history");

  if (logs && panel) {
    panel.innerHTML = eqBuildHistoryTab(logs);
  }
}

function eqHistoryDateOnly(value) {
  if (!value) return "";

  var text = String(value).trim();

  // Frappe date/datetime values begin YYYY-MM-DD.
  var match = text.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match) return match[1];

  var parsed = new Date(text);
  if (isNaN(parsed.getTime())) return "";

  var year = parsed.getFullYear();
  var month = String(parsed.getMonth() + 1).padStart(2, "0");
  var day = String(parsed.getDate()).padStart(2, "0");

  return year + "-" + month + "-" + day;
}

function eqBuildHistoryTab(logs) {
  var service = (logs.service || []).map(function(r) {
    return {
      type: "service",
      date: r.custom_service_date || r.custom_end_time || r.creation || "",
      event: r.custom_intervention_type || "Service",
      technician: r.custom_technician || "—",
      detail: r.custom_notes || r.custom_work_outcome || "—",
      ticket: r.custom_service_ticket || "",
      mi: r.custom_intervention_ref || ""
    };
  });

  var lifecycle = (logs.lifecycle || []).map(function(r) {
    return {
      type: "lifecycle",
      date: r.custom_date || r.creation || "",
      event: r.custom_event || "Lifecycle",
      technician: r.custom_technician || "—",
      detail: r.custom_action_taken || "—",
      ticket: r.custom_service_ticket || "",
      mi: ""
    };
  });

  var config = (logs.config || []).map(function(r) {
    return {
      type: "config",
      date: r.custom_config_datetime || r.creation || "",
      event: r.custom_parameter ? "Config · " + r.custom_parameter : "Config Change",
      technician: r.custom_technician || "—",
      detail: (r.custom_current_value || "—") + " → " + (r.custom_new_value || "—"),
      ticket: r.custom_service_ticket || "",
      mi: ""
    };
  });

  var rows = service.concat(lifecycle).concat(config);

  if (EQ.historyFilter !== "all") {
    rows = rows.filter(function(r) {
      return r.type === EQ.historyFilter;
    });
  }

  if (EQ.historyFrom || EQ.historyTo) {
    rows = rows.filter(function(r) {
      var rowDate = eqHistoryDateOnly(r.date);

      if (!rowDate) return false;
      if (EQ.historyFrom && rowDate < EQ.historyFrom) return false;
      if (EQ.historyTo && rowDate > EQ.historyTo) return false;

      return true;
    });
  }

  rows.sort(function(a, b) {
    return String(b.date || "").localeCompare(String(a.date || ""));
  });

  var html = '<div class="eq-history-toolbar">'
    + '<div class="eq-history-date-range">'
    + '<label><span>From</span><input type="date" value="' + eqEscapeAttr(EQ.historyFrom || "") + '" onchange="eqSetHistoryDate(\'from\', this.value)"></label>'
    + '<label><span>To</span><input type="date" value="' + eqEscapeAttr(EQ.historyTo || "") + '" onchange="eqSetHistoryDate(\'to\', this.value)"></label>'
    + '<button type="button" class="eq-history-clear" onclick="eqClearHistoryDates()">Clear</button>'
    + '</div>'
    + '<div class="eq-history-filters">'
    + eqHistoryFilterButton("all", "All")
    + eqHistoryFilterButton("service", "Service")
    + eqHistoryFilterButton("lifecycle", "Lifecycle")
    + eqHistoryFilterButton("config", "Config Changes")
    + '</div>'
    + '</div>';

  if (!rows.length) {
    return html + eqEmpty("📋", "No history found.");
  }

  html += '<div class="eq-table-wrap"><table class="eq-log-table">'
    + '<thead><tr>'
    + '<th>Date</th><th>Type</th><th>Event</th><th>Technician</th><th>Detail</th><th>Ticket</th><th>MI</th>'
    + '</tr></thead><tbody>';

  rows.forEach(function(r) {
    html += '<tr>'
      + '<td>' + eqEscape(r.date || "—") + '</td>'
      + '<td><span class="eq-event-pill">' + eqEscape(r.type) + '</span></td>'
      + '<td>' + eqEscape(r.event || "—") + '</td>'
      + '<td>' + eqEscape(r.technician || "—") + '</td>'
      + '<td>' + eqEscape(r.detail || "—") + '</td>'
      + '<td>' + eqDeskLink("Service Ticket", r.ticket) + '</td>'
      + '<td>' + eqDeskLink("Mission Intervention", r.mi) + '</td>'
      + '</tr>';
  });

  return html + '</tbody></table></div>';
}

function eqHistoryFilterButton(id, label) {
  return '<button class="eq-history-filter'
    + (EQ.historyFilter === id ? ' active' : '')
    + '" onclick="eqSetHistoryFilter(\'' + id + '\')">'
    + eqEscape(label)
    + '</button>';
}

function eqSetComponentGroupFilter(group) {
  EQ.componentGroupFilter = group || "All";

  var logs = EQ.cache.logs[EQ.state.equipmentId];
  var panel = document.getElementById("eq-tab-components");

  if (logs && panel) {
    panel.innerHTML = eqBuildComponents(logs.components || []);
  }
}

function eqBuildComponents(comps) {
  if (!comps.length) {
    return eqEmpty("🔩", "No components registered.");
  }

  var groups = [];
  comps.forEach(function(c) {
    var group = c.custom_component_group || c.custom_item_group || "Uncategorized";
    if (!groups.includes(group)) {
      groups.push(group);
    }
  });

  groups.sort(function(a, b) {
    return String(a).localeCompare(String(b));
  });

  if (EQ.componentGroupFilter !== "All" && !groups.includes(EQ.componentGroupFilter)) {
    EQ.componentGroupFilter = "All";
  }

  var filtered = comps.filter(function(c) {
    var group = c.custom_component_group || c.custom_item_group || "Uncategorized";
    return EQ.componentGroupFilter === "All" || group === EQ.componentGroupFilter;
  });

  var html = '<div class="eq-component-filter-wrap">'
    + '<label class="eq-component-filter-control">'
    + '<span class="eq-component-filter-label">Component Group</span>'
    + '<select onchange="eqSetComponentGroupFilter(this.value)">'
    + '<option value="All"' + (EQ.componentGroupFilter === "All" ? " selected" : "") + '>All Component Groups</option>';

  groups.forEach(function(group) {
    html += '<option value="' + eqEscapeAttr(group) + '"'
      + (EQ.componentGroupFilter === group ? " selected" : "")
      + '>' + eqEscape(group) + '</option>';
  });

  html += '</select></label></div>';

  if (!filtered.length) {
    return html + eqEmpty("🔩", "No components in this group.");
  }

  html += '<div class="eq-table-wrap"><table class="eq-log-table">'
    + '<thead><tr>'
    + '<th>Component</th><th>Group</th><th>Serial</th><th>Brand</th><th>Model</th><th>Status</th><th></th>'
    + '</tr></thead><tbody>';

  filtered.forEach(function(c) {
    var status = c.custom_status || "Installed";
    if (status === "Active") status = "Installed";

    var statusClass = status === "Installed"
      ? "cs-installed"
      : status === "Replaced"
        ? "cs-replaced"
        : "cs-other";

    var componentId = c.custom_equipment_component
      || c.equipment_component
      || c.component_id
      || c.custom_component_id
      || "";
    var label = c.custom_display_name
      || c.custom_equipment_type
      || c.custom_component_item
      || c.custom_component
      || componentId
      || "—";

    var group = c.custom_component_group || c.custom_item_group || "Uncategorized";

    html += '<tr>'
      + '<td>'
      + (componentId
          ? '<a class="eq-detail-link" href="/installed-equipment/component?name='
            + encodeURIComponent(componentId)
            + '">'
            + eqEscape(label)
            + '</a>'
          : eqEscape(label))
      + (componentId ? '<div style="font-family:var(--mono);font-size:9px;color:var(--text3);margin-top:3px">' + eqEscape(componentId) + '</div>' : '')
      + '</td>'
      + '<td>' + eqEscape(group) + '</td>'
      + '<td>' + eqEscape(c.custom_serial_number || "—") + '</td>'
      + '<td>' + eqEscape(c.custom_brand || "—") + '</td>'
      + '<td>' + eqEscape(c.custom_model || "—") + '</td>'
      + '<td><span class="eq-comp-status ' + statusClass + '">' + eqEscape(status) + '</span></td>'
      + '<td><button class="eq-btn eq-btn-ghost" onclick="eqOpenTicketModal(\'' + eqJs(EQ.state.equipmentId) + '\',\'' + eqJs(componentId) + '\')">Ticket</button></td>'
      + '</tr>';
  });

  return html + '</tbody></table></div>';
}

function eqDeskLink(doctype, name) {
  if (!name) return "—";

  var routeMap = {
    "Service Ticket": "service-ticket",
    "Mission Intervention": "mission-intervention",
    "Tech Mission": "tech-mission",
    "Asset Lifecycle Log": "asset-lifecycle-log",
    "Asset Service Log": "asset-service-log"
  };

  var route = routeMap[doctype] || String(doctype || "").toLowerCase().replaceAll(" ", "-");

  return '<a class="eq-log-link" target="_blank" href="/app/'
    + route + '/'
    + encodeURIComponent(name)
    + '">'
    + eqEscape(name)
    + '</a>';
}


// ============================================================
// TICKET MODAL
// ============================================================


function eqGetTicketTypesForRequestType(requestType) {
  var map = {
    "Breakdown": ["Repair", "Service"],
    "Maintenance Request": ["Preventive Maintenance", "Service", "Calibration", "Commissioning"],
    "General Request": ["Installation", "Survey", "Training", "Audit", "Incident Investigation", "Asset Relocation", "Config Change", "Swap", "Loan", "Service", "Decommissioning"]
  };
  return map[requestType] || [];
}

function eqUpdateTicketTypeOptions() {
  var requestSelect = document.getElementById("eq-ticket-request-type");
  var ticketSelect = document.getElementById("eq-ticket-type");
  if (!requestSelect || !ticketSelect) return;

  var types = eqGetTicketTypesForRequestType(requestSelect.value);
  var previous = ticketSelect.value;

  ticketSelect.innerHTML = types.map(function(type) {
    return '<option value="' + eqEscapeAttr(type) + '">' + eqEscape(type) + '</option>';
  }).join("");

  if (types.indexOf(previous) !== -1) {
    ticketSelect.value = previous;
  } else if (types.length) {
    ticketSelect.value = types[0];
  }
}

function eqOpenTicketModal(eqName, componentId) {
  eqGetEquipmentDetail(eqName).then(function(eq) {
    EQ.modalEq = eq;
    EQ.modalComponentId = componentId || "";
    EQ.createdTicket = null;
    EQ.selectedTechnicians = [];

    eqRenderSelectedTechnicians();

    var label = eq.custom_display_name || eq.custom_asset_name || eq.name;

    if (eq.custom_client_asset_code) {
      label += " · " + eq.custom_client_asset_code;
    }

    if (EQ.modalComponentId) {
      label += " · Component " + EQ.modalComponentId;
    }

    document.getElementById("eq-modal-eq-label").textContent = label;
    document.getElementById("eq-m-subject").value = "";
    document.getElementById("eq-m-description").value = "";
    document.getElementById("eq-m-req-type").value = "Breakdown";
    document.getElementById("eq-m-priority").value = "Normal";

    eqOnRequestTypeChange();
    eqLoadTechnicians();
    eqLoadApplicants(eq.name);

    document.getElementById("eq-modal-confirm").className = "eq-modal-confirm";
    document.getElementById("eq-modal-error").className = "eq-modal-error";
    document.getElementById("eq-modal-overlay").classList.add("open");
  }).catch(function(err) {
    console.error(err);
    eqShowModalError("Equipment details could not be loaded.");
  });
}

function eqCloseModal() {
  document.getElementById("eq-modal-overlay").classList.remove("open");
  EQ.modalEq = null;
  EQ.modalComponentId = "";
  EQ.createdTicket = null;
  EQ.selectedTechnicians = [];
  eqRenderSelectedTechnicians();
}

function eqOnRequestTypeChange() {
  var requestType = document.getElementById("eq-m-req-type").value;
  var select = document.getElementById("eq-m-ticket-type");
  var options = TICKET_TYPE_BY_REQUEST_TYPE[requestType] || ["Service"];

  select.innerHTML = "";

  options.forEach(function(value) {
    var option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function eqLoadTechnicians() {
  frappe.call({
    method: "maintenance_app.api.get_maintenance_technicians",
    args: {
      doctype: "User",
      txt: "",
      searchfield: "name",
      start: 0,
      page_len: 100,
      filters: {}
    },
    callback: function(r) {
      EQ.technicianCache = (r.message || []).map(function(row) {
        if (Array.isArray(row)) {
          return {
            name: row[0] || "",
            full_name: row[1] || row[0] || ""
          };
        }

        return {
          name: row.name || "",
          full_name: row.full_name || row.name || ""
        };
      }).filter(function(user) {
        return !!user.name;
      });

      eqRenderSelectedTechnicians();
      eqRenderTechnicianSuggestions();
    },
    error: function() {
      EQ.technicianCache = [];
      eqRenderTechnicianSuggestions();
    }
  });
}

function eqTechnicianLabel(user) {
  if (!user) return "";
  var fullName = user.full_name || user.name || "";

  if (user.name && fullName !== user.name) {
    return fullName + " (" + user.name + ")";
  }

  return fullName;
}

function eqTechnicianInitials(user) {
  var label = (user.full_name || user.name || "?").trim();
  var parts = label.split(/\s+/).filter(Boolean);

  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();

  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

function eqRenderSelectedTechnicians() {
  var el = document.getElementById("eq-tech-tags");
  if (!el) return;

  el.innerHTML = (EQ.selectedTechnicians || []).map(function(user) {
    return '<span class="eq-picker-tag">'
      + eqEscape(eqTechnicianLabel(user))
      + '<button type="button" onclick="eqRemoveTechnician(\'' + eqJs(user.name) + '\')">×</button>'
      + '</span>';
  }).join("");
}

function eqRenderTechnicianSuggestions() {
  var input = document.getElementById("eq-tech-search");
  var dropdown = document.getElementById("eq-tech-suggestions");

  if (!input || !dropdown) return;

  var q = (input.value || "").toLowerCase().trim();

  var selected = {};
  (EQ.selectedTechnicians || []).forEach(function(user) {
    selected[user.name] = true;
  });

  var matches = (EQ.technicianCache || []).filter(function(user) {
    if (!user || !user.name || selected[user.name]) return false;

    var label = ((user.full_name || "") + " " + (user.name || "")).toLowerCase();

    return !q || label.includes(q);
  }).slice(0, 8);

  if (!matches.length) {
    dropdown.innerHTML = '<div class="eq-picker-empty">'
      + (q ? "No matching technician" : "No technician available")
      + '</div>';
    dropdown.classList.add("open");
    return;
  }

  dropdown.innerHTML = matches.map(function(user) {
    return '<div class="eq-picker-option" onclick="eqAddTechnician(\'' + eqJs(user.name) + '\')">'
      + '<div class="eq-picker-avatar">' + eqEscape(eqTechnicianInitials(user)) + '</div>'
      + '<div>' + eqEscape(eqTechnicianLabel(user)) + '</div>'
      + '</div>';
  }).join("");

  dropdown.classList.add("open");
}

function eqAddTechnician(userName) {
  var user = (EQ.technicianCache || []).find(function(row) {
    return row.name === userName;
  });

  if (!user) return;

  if (!(EQ.selectedTechnicians || []).some(function(row) {
    return row.name === user.name;
  })) {
    EQ.selectedTechnicians.push(user);
  }

  var input = document.getElementById("eq-tech-search");
  if (input) input.value = "";

  eqRenderSelectedTechnicians();
  eqRenderTechnicianSuggestions();

  if (input) input.focus();
}

function eqRemoveTechnician(userName) {
  EQ.selectedTechnicians = (EQ.selectedTechnicians || []).filter(function(user) {
    return user.name !== userName;
  });

  eqRenderSelectedTechnicians();
  eqRenderTechnicianSuggestions();
}

function eqTechSearchKeydown(event) {
  if (event.key === "Enter") {
    event.preventDefault();

    var first = document.querySelector("#eq-tech-suggestions .eq-picker-option");
    if (first) first.click();
  }

  if (event.key === "Backspace") {
    var input = document.getElementById("eq-tech-search");

    if (input && !input.value && EQ.selectedTechnicians.length) {
      EQ.selectedTechnicians.pop();
      eqRenderSelectedTechnicians();
      eqRenderTechnicianSuggestions();
    }
  }

  if (event.key === "Escape") {
    var dropdown = document.getElementById("eq-tech-suggestions");
    if (dropdown) dropdown.classList.remove("open");
  }
}

function eqGetSelectedTechnicians() {
  return (EQ.selectedTechnicians || []).map(function(user) {
    return user.name;
  }).filter(Boolean);
}

function eqLoadApplicants(eqName) {
  var select = document.getElementById("eq-m-applicant");
  if (!select) return;

  select.innerHTML = '<option value="">No applicant selected</option>';

  frappe.call({
    method: "maintenance_app.api.get_eq_applicants_for_equipment",
    args: {
      equipment_name: eqName
    },
    callback: function(r) {
      (r.message || []).forEach(function(contact) {
        var option = document.createElement("option");
        option.value = contact.name;
        option.textContent = contact.label || contact.name;
        select.appendChild(option);
      });
    },
    error: function() {
      select.innerHTML = '<option value="">Could not load contacts</option>';
    }
  });
}

function eqOpenInDesk() {
  if (EQ.createdTicket) {
    window.location.href = "/app/service-ticket/" + encodeURIComponent(EQ.createdTicket);
    return;
  }

  if (!EQ.modalEq) return;

  var subject = document.getElementById("eq-m-subject").value.trim()
    || ("Service Request - " + (EQ.modalEq.custom_display_name || EQ.modalEq.custom_asset_name || EQ.modalEq.name));

  frappe.route_options = {
    custom_target_equipment: EQ.modalEq.name,
    custom_subject: subject,
    custom_customer: EQ.modalEq.custom_parent_customer || "",
    custom_client_branch: EQ.modalEq.custom_branch || "",
    custom_request_type: document.getElementById("eq-m-req-type").value,
    custom_ticket_type: document.getElementById("eq-m-ticket-type").value,
    custom_priority: document.getElementById("eq-m-priority").value,
    custom_applicant: document.getElementById("eq-m-applicant").value || ""
  };

  // Component field is only populated if the Service Ticket doctype supports it.
  if (EQ.modalComponentId) {
    frappe.route_options.custom_equipment_component = EQ.modalComponentId;
  }

  window.location.href = "/app/service-ticket/new-service-ticket-1";
}

function eqSubmitTicket() {
  if (!EQ.modalEq) return;

  var subject = document.getElementById("eq-m-subject").value.trim();

  if (!subject) {
    document.getElementById("eq-m-subject").focus();
    eqShowModalError("Subject is required.");
    return;
  }

  var btn = document.getElementById("eq-btn-create-ticket");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Creating…";
  }

  frappe.call({
    method: "maintenance_app.api.create_service_ticket_from_equipment",
    args: {
      equipment_name: EQ.modalEq.name,

      // The backend should now interpret this as the permanent
      // Equipment Component document ID (COMP-xxxxx).
      component_row_id: EQ.modalComponentId || "",

      request_type: document.getElementById("eq-m-req-type").value,
      ticket_type: document.getElementById("eq-m-ticket-type").value,
      subject: subject,
      priority: document.getElementById("eq-m-priority").value,
      description: document.getElementById("eq-m-description").value,
      technicians: JSON.stringify(eqGetSelectedTechnicians()),
      applicant: document.getElementById("eq-m-applicant").value || ""
    },
    callback: function(r) {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Create Ticket";
      }

      if (r && r.message && r.message.ticket) {
        EQ.createdTicket = r.message.ticket;

        var coverage = r.message.coverage || {};
        var serviceType = r.message.service_type || "Billable";

        eqShowModalConfirm(
          "✓ Ticket " + r.message.ticket + " created.\n"
          + "Equipment: " + (EQ.modalEq.custom_display_name || EQ.modalEq.custom_asset_name || EQ.modalEq.name) + "\n"
          + (EQ.modalComponentId ? "Component: " + EQ.modalComponentId + "\n" : "")
          + "Service Type: " + serviceType + "\n"
          + (coverage.message || "")
        );

        EQ.cache.customers = null;
      } else {
        eqShowModalError("Ticket was created but no ticket reference was returned.");
      }
    },
    error: function(err) {
      console.error(err);

      if (btn) {
        btn.disabled = false;
        btn.textContent = "Create Ticket";
      }

      eqShowModalError("Failed to create ticket. Please try again.");
    }
  });
}

function eqShowModalConfirm(message) {
  var confirm = document.getElementById("eq-modal-confirm");
  var error = document.getElementById("eq-modal-error");

  confirm.textContent = message;
  confirm.className = "eq-modal-confirm show";
  error.className = "eq-modal-error";
}

function eqShowModalError(message) {
  var error = document.getElementById("eq-modal-error");
  var confirm = document.getElementById("eq-modal-confirm");

  if (error) {
    error.textContent = message;
    error.className = "eq-modal-error show";
  }

  if (confirm) {
    confirm.className = "eq-modal-confirm";
  }
}



// ============================================================
// RESPONSIVE SIDEBAR
// ============================================================

function eqIsMobileLayout() {
  return window.matchMedia("(max-width: 900px)").matches;
}

function eqOpenMobileMenu() {
  var sidebar = document.querySelector(".eq-sidebar");
  var backdrop = document.getElementById("eq-mobile-backdrop");
  var button = document.getElementById("eq-mobile-menu-btn");

  if (!sidebar) return;

  sidebar.classList.add("mobile-open");

  if (backdrop) {
    backdrop.classList.add("open");
  }

  if (button) {
    button.classList.add("open");
    button.setAttribute("aria-expanded", "true");
  }

  document.body.classList.add("eq-mobile-menu-open");
}

function eqCloseMobileMenu() {
  var sidebar = document.querySelector(".eq-sidebar");
  var backdrop = document.getElementById("eq-mobile-backdrop");
  var button = document.getElementById("eq-mobile-menu-btn");

  if (sidebar) {
    sidebar.classList.remove("mobile-open");
  }

  if (backdrop) {
    backdrop.classList.remove("open");
  }

  if (button) {
    button.classList.remove("open");
    button.setAttribute("aria-expanded", "false");
  }

  document.body.classList.remove("eq-mobile-menu-open");
}

function eqToggleMobileMenu() {
  var sidebar = document.querySelector(".eq-sidebar");

  if (!sidebar) return;

  if (sidebar.classList.contains("mobile-open")) {
    eqCloseMobileMenu();
  } else {
    eqOpenMobileMenu();
  }
}

function eqHandleResponsiveMenu() {
  if (!eqIsMobileLayout()) {
    eqCloseMobileMenu();
  }
}


function eqOpenEquipmentFromUrl(equipmentName) {
  if (!equipmentName) return Promise.resolve(false);

  return eqCall("frappe.client.get", {
    doctype: "Installed Equipment",
    name: equipmentName
  }).then(function(eq) {
    if (!eq || !eq.name) return false;

    EQ.state.customerId = eq.custom_parent_customer || null;
    EQ.state.branchId = eq.custom_branch || null;
    EQ.state.equipmentId = eq.name;
    EQ.state.level = "detail";
    EQ.activeTab = "overview";
    EQ.historyFilter = "all";
    EQ.historyFrom = "";
    EQ.historyTo = "";
    EQ.componentGroupFilter = "All";
    EQ.searchVal = "";
    EQ.categoryFilter = "All";

    EQ.cache.equipmentDetail[eq.name] = eq;

    if (!EQ.state.customerId || !EQ.state.branchId) {
      eqRender();
      return true;
    }

    return eqLoadBranches(EQ.state.customerId)
      .then(function(branches) {
        var branch = (branches || []).find(function(row) {
          return row.name === EQ.state.branchId;
        });

        if (branch) {
          EQ.state.clientType = branch.custom_site_type || null;
          EQ.state.region = branch.custom_region || null;
        }

        return eqLoadRegions();
      })
      .then(function() {
        eqRender();
        return true;
      });
  }).catch(function(err) {
    console.error("Could not open equipment from URL", err);
    return false;
  });
}

// ============================================================
// INITIALIZE
// ============================================================

frappe.ready(function() {
  var directEquipment = new URLSearchParams(window.location.search).get("equipment");

  if (directEquipment) {
    eqOpenEquipmentFromUrl(directEquipment).then(function(opened) {
      if (!opened) {
        eqGo("customers");
      }
    });
    return;
  }

  eqGo("customers");
});

document.addEventListener("click", function(event) {
  var picker = document.getElementById("eq-tech-picker");
  var dropdown = document.getElementById("eq-tech-suggestions");

  if (!picker || !dropdown) return;

  if (!picker.contains(event.target)) {
    dropdown.classList.remove("open");
  }
});

document.querySelectorAll(".eq-sidebar .eq-nav-item").forEach(function(link) {
  link.addEventListener("click", function() {
    if (eqIsMobileLayout()) {
      eqCloseMobileMenu();
    }
  });
});

window.addEventListener("resize", eqHandleResponsiveMenu);

document.addEventListener("keydown", function(event) {
  if (event.key === "Escape") {
    eqCloseMobileMenu();
  }
});
