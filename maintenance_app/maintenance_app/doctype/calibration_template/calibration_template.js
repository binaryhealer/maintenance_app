// GMAO_CAL_TEMPLATE_PICKER_V1 — guided setup for non-technical supervisors.
frappe.ui.form.on('Calibration Template', {
  refresh(frm) {
    gmao_calibration_template_ui(frm);
    gmao_calibration_load_component_types(frm);
    frm.add_custom_button(__('Advanced Settings'), () => {
      frm.__gmao_calibration_advanced = !frm.__gmao_calibration_advanced;
      gmao_calibration_template_ui(frm);
    });
    if (frm.doc.custom_calibrate_components === 'Yes') {
      frm.add_custom_button(
        frm.__gmao_calibration_show_all ? __('Show only calibration-required types') : __('Show all component types'),
        () => {
          frm.__gmao_calibration_show_all = !frm.__gmao_calibration_show_all;
          gmao_calibration_load_component_types(frm);
          frm.refresh();
        }
      );
    }
  },
  custom_equipment_category(frm) {
    frm.__gmao_calibration_show_all = false;
    gmao_calibration_load_component_types(frm);
  },
  custom_entry_format(frm) { gmao_calibration_template_ui(frm); },
  custom_calibrate_components(frm) {
    const mode = frm.doc.custom_calibrate_components === 'Yes' ? 'Component' : 'Equipment';
    frm.set_value('custom_applicable_scope', mode);
    gmao_calibration_template_ui(frm);
    gmao_calibration_load_component_types(frm);
    frm.refresh();
  }
});

function gmao_calibration_template_ui(frm) {
  const format = frm.doc.custom_entry_format || 'Standard Tests';
  frm.toggle_display('custom_test_points', format === 'Standard Tests' || format === 'Both');
  frm.toggle_display('custom_table_title', format === 'Custom Table' || format === 'Both');
  frm.toggle_display('custom_table_component_type', (format === 'Custom Table' || format === 'Both') && frm.doc.custom_calibrate_components === 'Yes');
  frm.toggle_display('custom_table_columns', format === 'Custom Table' || format === 'Both');
  const advanced = !!frm.__gmao_calibration_advanced;
  ['custom_applicable_scope', 'custom_equipment_type', 'custom_component_group',
   'custom_reference_standard', 'custom_notes'].forEach(field => {
    if (frm.fields_dict[field]) frm.toggle_display(field, advanced);
  });
  const components = frm.doc.custom_calibrate_components === 'Yes';
  const table = frm.fields_dict.custom_test_points;
  if (table) {
    frm.set_df_property('custom_test_points', 'description', components
      ? __('Add tests for Pump, Nozzle, etc. Component Type shows only types marked for calibration in the selected Equipment Category. Use Show all component types for exceptions. Leave a test type blank for tests common to every component.')
      : __('Add tests for the complete equipment. Enter expected readings, tolerances and units if required.'));
    if (table.grid) {
      table.grid.update_docfield_property('custom_component_type', 'hidden', components ? 0 : 1);
      table.grid.refresh();
    }
  }
}

function gmao_calibration_load_component_types(frm) {
  const active = frm.doc.custom_calibrate_components === 'Yes';
  const category = frm.doc.custom_equipment_category || '';
  const token = (frm.__gmao_calibration_query_token || 0) + 1;
  frm.__gmao_calibration_query_token = token;
  frm.__gmao_calibration_component_types = [];
  // Frappe's child-table Link filter applies in grid rows and expanded row forms.
  frm.set_query('custom_component_type', 'custom_test_points', () => ({
    filters: [['Equipment Type', 'name', 'in',
      frm.__gmao_calibration_component_types.length
        ? frm.__gmao_calibration_component_types : ['__NO_MATCH__']]]
  }));
  if (!active || (!category && !frm.__gmao_calibration_show_all)) return;
  frappe.call({
    method: 'maintenance_app.calibration_template_picker.get_component_types',
    args: {equipment_category:category, show_all:frm.__gmao_calibration_show_all ? 1 : 0},
    callback(r) {
      if (token !== frm.__gmao_calibration_query_token) return;
      frm.__gmao_calibration_component_types = (r.message || []).map(x => x.name);
      if (frm.fields_dict.custom_test_points && frm.fields_dict.custom_test_points.grid) {
        frm.fields_dict.custom_test_points.grid.refresh();
      }
      if (!frm.__gmao_calibration_component_types.length) {
        frappe.show_alert({message: __('No calibration-required component types found for this category. Use Show all component types to define a new procedure.'), indicator:'orange'}, 6);
      }
    }
  });
}
