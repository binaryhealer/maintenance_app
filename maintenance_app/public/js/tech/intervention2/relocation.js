(function () {
  'use strict';
  const panel = document.getElementById('tech2-relocation-v1');
  if (!panel || !document.getElementById('tech2-reloc-save')) return;
  const mi = panel.dataset.mi;
  const get = (id) => document.getElementById(id);
  const type = get('tech2-reloc-type');
  const destSelect = get('tech2-reloc-select');
  const destText = get('tech2-reloc-text');
  const custodian = get('tech2-reloc-custodian');
  const save = get('tech2-reloc-save');
  const feedback = get('tech2-reloc-feedback');
  let data = null;

  // Wait for Frappe API initialization, as calibration.js does.
  function callWhenReady(options) {
    let tries = 0;

    function go() {
      if (window.frappe &&
          typeof window.frappe.call === 'function') {
        try {
          window.frappe.call(options);
        } catch (error) {
          if (typeof options.error === 'function') {
            options.error(error);
          } else {
            console.error('Relocation API error:', error);
          }
        }
        return;
      }

      if (++tries >= 60) {
        const error = new Error('Frappe API unavailable');

        if (typeof options.error === 'function') {
          options.error(error);
        } else {
          console.error(error);
        }
        return;
      }

      setTimeout(go, 200);
    }

    go();
  }

  const textTypes = ['Customer Warehouse', 'Other Location'];
  function message(value) { feedback.textContent = value; }
  function setOptions(select, rows, placeholder, labelKey) {
    select.replaceChildren();
    let empty = document.createElement('option');
    empty.value = ''; empty.textContent = placeholder; select.appendChild(empty);
    (rows || []).forEach((row) => {
      const option = document.createElement('option');
      option.value = typeof row === 'string' ? row : row.name;
      const name = typeof row === 'string' ? row : row.name;
      option.textContent = name + (row && typeof row === 'object' && row[labelKey] && row[labelKey] !== name ? ' — ' + row[labelKey] : '');
      select.appendChild(option);
    });
  }
  function destinationChanged() {
    const t = type.value;
    const isText = textTypes.includes(t);
    destSelect.style.display = isText ? 'none' : '';
    destText.style.display = isText ? '' : 'none';
    const config = {
      'Customer Branch': ['branches', 'Choose client branch', 'custom_branch'],
      'Workshop': ['workshops', 'Choose workshop', 'name'],
      'Company Warehouse': ['warehouses', 'Choose company warehouse', 'name']
    }[t];
    if (config && data) setOptions(destSelect, data[config[0]], config[1], config[2]);
    if (t === 'Customer Branch') custodian.value = 'Customer';
    if (t === 'Workshop' || t === 'Company Warehouse') custodian.value = 'Company';
  }
  type.addEventListener('change', destinationChanged);
  callWhenReady({
    method: 'maintenance_app.relocation_v1.get_relocation_setup_v2',
    args: {mi_name: mi},
    callback: (r) => {
      if (!r.message || !r.message.ok) { message('Unable to load relocation settings.'); return; }
      data = r.message;
      const conditionPicker = get('tech2-reloc-condition');
      setOptions(
        conditionPicker,
        [
          'Operational', 'Good', 'Degraded', 'Faulty',
          'Out of Service', 'Awaiting Component', 'Unknown'
        ],
        'Select equipment condition'
      );


      const slotLabel = get('tech2-reloc-details-label');
      const slotInput = get('tech2-reloc-details');
      const approvedType = data.saved.destination_type || '';

      const labels = {
        'Customer Branch': 'Site Position / Slot ID',
        'Workshop': 'Workshop Position / Location',
        'Company Warehouse': 'Storage Position / Location',
        'Customer Warehouse': 'Storage Position / Location',
        'Other Location': 'Location Details'
      };

      if (slotLabel) {
        slotLabel.textContent = labels[approvedType] || 'Location Details';
      }

      if (slotInput) {
        slotInput.placeholder = approvedType === 'Customer Branch'
          ? 'e.g. Rack 42U, U35-U37 or Island 1, P1'
          : 'e.g. Bay 3, Shelf B or Aisle 2, Rack 4';
      }
      if (data.approved_request) {
        const approvedType = data.saved.destination_type || '';
        const approvedDestination = data.saved.approved_destination || '';

        type.replaceChildren(new Option(approvedType, approvedType));
        type.value = approvedType;

        const isText = textTypes.includes(approvedType);

        destSelect.replaceChildren(
          new Option(approvedDestination, approvedDestination)
        );
        destSelect.value = approvedDestination;

        destText.value = approvedDestination;
        destSelect.style.display = isText ? 'none' : '';
        destText.style.display = isText ? '' : 'none';

        type.disabled = true;
        destSelect.disabled = true;
        destText.readOnly = true;
      } else {
        setOptions(type, data.destinations, 'Choose destination type');
        type.value = data.saved.destination_type || '';
        destinationChanged();
      }
      if (!data.approved_request) {
        const selected = ({'Customer Branch':data.saved.branch,'Workshop':data.saved.workshop,'Company Warehouse':data.saved.warehouse})[type.value];
        if (textTypes.includes(type.value)) destText.value = data.saved.details || '';
        else destSelect.value = selected || '';
      }
      if (data.approved_request) {
        const approved = data.saved.approved_destination || '';

        if (textTypes.includes(type.value)) {
          destText.value = approved;
        } else {
          if (approved && !Array.from(destSelect.options).some(o => o.value === approved)) {
            destSelect.add(new Option(approved, approved));
          }
          destSelect.value = approved;
        }

        type.disabled = true;
        destSelect.disabled = true;
        destText.readOnly = true;
        get('tech2-reloc-reason').readOnly = true;
      }

      if (!textTypes.includes(type.value)) get('tech2-reloc-details').value = data.saved.details || '';
      custodian.value = data.saved.custodian || custodian.value;
      get('tech2-reloc-condition').value = data.saved.condition || '';
      get('tech2-reloc-disposition').value = data.saved.disposition || 'Pending Assessment';
      get('tech2-reloc-reason').value = data.saved.reason || '';
      message('Current location: ' + (data.current_branch || data.location_status || 'Unspecified') + '. Ownership: ' + (data.ownership || 'Not recorded'));
    },
    error: () => message('Could not load destinations. Refresh and try again.')
  });
  save.addEventListener('click', () => {
    const destination = textTypes.includes(type.value) ? destText.value.trim() : destSelect.value;
    const reason = get('tech2-reloc-reason').value.trim();
    if (!type.value || !destination || !reason ) {
      message('Select a destination and custodian, and enter the movement reason.'); return;
    }
    save.disabled = true; message('Saving relocation...');
    callWhenReady({
      method:'maintenance_app.relocation_v1.save_relocation_v2',
      args:{mi_name:mi, destination_type:type.value, destination:destination,
            details:get('tech2-reloc-details').value.trim(), reason:reason,
            condition:get('tech2-reloc-condition').value,
            disposition:get('tech2-reloc-disposition').value,
            custodian:custodian.value},
      callback:(r) => {
        save.disabled = false;
        if (r.message && r.message.ok) {
          window.location.href = '/tech/intervention2?name=' + encodeURIComponent(mi) + '&step=finish';
        } else message('Relocation not saved. Check the error and try again.');
      },
      error:() => {save.disabled = false; message('Relocation could not be saved; check destination and try again.');}
    });
  });
})();
