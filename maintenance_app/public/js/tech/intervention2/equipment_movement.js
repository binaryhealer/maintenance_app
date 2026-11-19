(function () {
  'use strict';
  function initializeMovement() {
  const host = document.getElementById('tech2-eq-move');
  if (!host || !window.frappe || host.dataset.movementInitialized === '1') return;
  host.dataset.movementInitialized = '1';
  const mi = host.dataset.mi;
  const el = id => document.getElementById(id);
  const type = el('tech2-move-type'), picker = el('tech2-move-select'), text = el('tech2-move-text');
  const status = el('tech2-move-status'), save = el('tech2-move-save');
  let data = null;
  const isText = t => t === 'Customer Warehouse' || t === 'Other Location';
  const msg = s => { status.textContent = s; };
  function setOptions(rows) {
    picker.replaceChildren();
    const ph = document.createElement('option'); ph.value=''; ph.textContent='Select destination'; picker.appendChild(ph);
    (rows || []).forEach(row => {
      const opt = document.createElement('option'); opt.value=row.name;
      opt.textContent=row.name; picker.appendChild(opt);
    });
  }
  function changeType() {
    const t=type.value;
    picker.style.display=isText(t)?'none':'';
    text.style.display=isText(t)?'':'none';
    const key=({'Customer Branch':'branches','Workshop':'workshops','Company Warehouse':'warehouses'})[t];
    setOptions(data && key ? data[key] : []);
    if (t==='Customer Branch') el('tech2-move-custodian').value='Customer';
    if (t==='Workshop'||t==='Company Warehouse') el('tech2-move-custodian').value='Company';
  }
  type.addEventListener('change',changeType);
  frappe.call({method:'maintenance_app.equipment_movement.get_movement_setup',args:{mi_name:mi},
    callback:r=>{
      data=r.message;
      if (!data || !data.ok){msg('Could not load equipment movement.');return;}
      type.value=data.saved.destination_type||type.value||'Customer Branch';changeType();
      const t=type.value;
      if(isText(t))text.value=data.saved.destination_text||'';
      else picker.value=({'Customer Branch':data.saved.destination_branch,'Workshop':data.saved.destination_workshop,'Company Warehouse':data.saved.destination_warehouse})[t]||'';
      el('tech2-move-details').value=data.saved.destination_detail||'';
      el('tech2-move-reason').value=data.saved.reason||'';
      el('tech2-move-condition').value=data.saved.condition||'Unknown';
      el('tech2-move-disposition').value=data.saved.proposed_disposition||'Pending Assessment';
      el('tech2-move-custodian').value=data.saved.custodian||el('tech2-move-custodian').value;
      msg('Current location: '+(data.current_branch||data.location_status||'Unknown'));
    },error:()=>msg('Could not load movement destinations.')});
  save.addEventListener('click',()=>{
    const dest=isText(type.value)?text.value.trim():picker.value;
    const reason=el('tech2-move-reason').value.trim();
    if(!type.value||!dest||!reason){msg('Select destination and enter movement reason.');return;}
    save.disabled=true;msg('Saving movement...');
    frappe.call({method:'maintenance_app.equipment_movement.save_movement',args:{
      mi_name:mi,destination_type:type.value,destination:dest,
      details:el('tech2-move-details').value.trim(),reason,
      condition:el('tech2-move-condition').value,disposition:el('tech2-move-disposition').value,
      custodian:el('tech2-move-custodian').value},
      callback:r=>{save.disabled=false;if(r.message&&r.message.ok){location.href='/tech/intervention2?name='+encodeURIComponent(mi)+'&step=finish';}else msg('Movement was not saved.');},
      error:()=>{save.disabled=false;msg('Movement was not saved. Check destination and try again.');}});
  });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeMovement, {once: true});
  } else {
    initializeMovement();
  }
})();
