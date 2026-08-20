var CP={name:null,data:null,tab:"overview",technicianCache:[],selectedTechnicians:[],createdTicket:null};
function cpCall(m,a){return new Promise((res,rej)=>frappe.call({method:m,args:a||{},callback:r=>res(r.message),error:rej}));}
function e(v){if(v==null)return"";return String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");}
function cpJs(v){
  return String(v==null?"":v)
    .replace(/\\/g,"\\\\")
    .replace(/'/g,"\\'")
    .replace(/\r/g,"\\r")
    .replace(/\n/g,"\\n");
}
function p(n){return new URLSearchParams(location.search).get(n)}
function fd(v){if(!v)return"—";let m=String(v).match(/^(\d{4})-(\d{2})-(\d{2})/);return m?m[3]+"/"+m[2]+"/"+m[1]:e(v)}
function fdt(v){return v?e(String(v).replace("T"," ").slice(0,16)):"—"}
function truth(v){return v===1||v==="1"||v===true||v==="true"}
function age(v){if(!v)return"—";let d=new Date(String(v).slice(0,10)+"T00:00:00"),t=new Date();t.setHours(0,0,0,0);if(isNaN(d))return"—";let y=t.getFullYear()-d.getFullYear(),m=t.getMonth()-d.getMonth();if(t.getDate()<d.getDate())m--;if(m<0){y--;m+=12}if(y<0)return"—";if(y===0)return m+" month"+(m===1?"":"s");if(m===0)return y+" year"+(y===1?"":"s");return y+" year"+(y===1?"":"s")+" "+m+" month"+(m===1?"":"s")}
function ds(v){if(!v)return{label:"Not Scheduled",cls:"neutral",detail:""};let d=new Date(String(v).slice(0,10)+"T00:00:00"),t=new Date();t.setHours(0,0,0,0);let n=Math.ceil((d-t)/86400000);if(n<0)return{label:"Overdue",cls:"bad",detail:Math.abs(n)+" days overdue"};if(n===0)return{label:"Due Today",cls:"bad",detail:"Due today"};if(n<=30)return{label:"Due Soon",cls:"warn",detail:"Due in "+n+" days"};return{label:"Valid",cls:"ok",detail:"Due in "+n+" days"}}
function pill(t,c){return'<span class="cp-pill cp-pill-'+c+'">'+e(t||"—")+'</span>'}
function info(l,v){return'<div class="cp-info-card"><div class="cp-info-label">'+e(l)+'</div><div class="cp-info-value">'+(v||"—")+'</div></div>'}
function doc(dt,n){if(!n)return"—";return'<a class="cp-link" target="_blank" href="/app/'+encodeURIComponent(dt.toLowerCase().replace(/ /g,"-"))+'/'+encodeURIComponent(n)+'">'+e(n)+'</a>'}
function empty(i,t){return'<div class="cp-empty"><div class="cp-empty-icon">'+i+'</div><div>'+e(t)+'</div></div>'}
function render(){let c=CP.data.component,ctx=CP.data.context||{},eq=ctx.equipment||{};document.getElementById("cp-breadcrumb-name").textContent=c.custom_display_name||c.name;let sc="neutral";if(["Installed","Repaired"].includes(c.custom_status))sc="ok";if(["Faulty","Under Repair"].includes(c.custom_status))sc="warn";if(["Retired","Scrapped","Lost"].includes(c.custom_status))sc="bad";let title=c.custom_display_name||c.custom_equipment_type||c.name,cl=[ctx.customer_display,ctx.client_type,ctx.region_display,ctx.branch_display].filter(Boolean).join(" · ");let h='<section class="cp-hero"><div class="cp-hero-main"><a class="cp-back-link" href="/installed-equipment">← Back to Installed Equipment</a><div class="cp-title-row"><div><h1>'+e(title)+'</h1><div class="cp-component-id">'+e(c.name)+'</div></div>'+pill(c.custom_status||"Not Set",sc)+'</div><div class="cp-context">'+e(cl||"No current site context")+'</div><div class="cp-hero-meta">'+(c.custom_serial_number?'<span>S/N '+e(c.custom_serial_number)+'</span>':'')+(c.custom_part_number?'<span>Part '+e(c.custom_part_number)+'</span>':'')+(c.custom_component_group?'<span>'+e(c.custom_component_group)+'</span>':'')+'</div></div><div class="cp-hero-actions"><button class="cp-btn cp-btn-primary" onclick="openTicket()">+ Open Ticket</button><a class="cp-btn cp-btn-ghost" target="_blank" href="/app/equipment-component/'+encodeURIComponent(c.name)+'">Open in Desk</a></div></section>';if(c.custom_parent_equipment){let q=eq.custom_display_name||eq.custom_asset_name||c.custom_parent_equipment;h+='<section class="cp-parent-strip"><div><span class="cp-parent-label">Parent Equipment</span><a class="cp-parent-equipment-link" href="/installed-equipment?equipment='+encodeURIComponent(c.custom_parent_equipment)+'"><strong>'+e(q)+'</strong></a><span class="cp-mono-small">'+e(c.custom_parent_equipment)+'</span></div><a class="cp-btn cp-btn-small cp-btn-ghost" href="/installed-equipment?equipment='+encodeURIComponent(c.custom_parent_equipment)+'">View Equipment</a></section>'}let tabs=[["overview","Overview"],["component-info","Component Info"],["calibration","Calibration"],["lifecycle","Lifecycle"],["service","Service History"],["config","Config Changes"],["tickets","Tickets"]];h+='<div class="cp-tabs">';tabs.forEach(t=>h+='<button class="cp-tab'+(CP.tab===t[0]?' active':'')+'" onclick="setTab(\''+t[0]+'\')">'+t[1]+'</button>');h+='</div><section class="cp-panel">'+buildTab()+'</section>';document.getElementById("cp-content").innerHTML=h}
function setTab(t){CP.tab=t;render()}
function buildTab(){let c=CP.data.component;
if(CP.tab==="overview")return'<div class="cp-section-title">Component Overview</div><div class="cp-info-grid">'+info("Component ID",e(c.name))+info("Display Name",e(c.custom_display_name||"—"))+info("Component Group",e(c.custom_component_group||"—"))+info("Equipment Type",e(c.custom_equipment_type||"—"))+info("Make",e(c.custom_make||"—"))+info("Model",e(c.custom_model||"—"))+info("Serial Number",e(c.custom_serial_number||"—"))+info("Part Number",e(c.custom_part_number||"—"))+'</div>';
if(CP.tab==="component-info"){let ctx=CP.data.context||{},eq=ctx.equipment||{},eqLabel=eq.custom_display_name||eq.custom_asset_name||c.custom_parent_equipment||"—";return'<div class="cp-section-title">Component Info</div><div class="cp-subsection-title">Status & Inventory</div><div class="cp-info-grid">'+info("Status",e(c.custom_status||"—"))+info("ERPNext Item",doc("Item",c.custom_item))+'</div><div class="cp-subsection-title">Installation</div><div class="cp-info-grid">'+info("Installation Date",fd(c.custom_installation_date))+info("Component Age",e(age(c.custom_installation_date)))+'</div><div class="cp-subsection-title">Commissioning</div><div class="cp-info-grid">'+info("Commissioning Status",e(c.custom_commissioning_status||"—"))+info("Commissioned Date",fd(c.custom_commissioned_date))+info("Last Commissioning Record",doc("Commissioning Record",c.custom_last_commissioning_record))+'</div><div class="cp-subsection-title">Current Location</div><div class="cp-info-grid">'+info("Parent Equipment",e(eqLabel))+info("Customer",e(ctx.customer_display||c.custom_customer||"—"))+info("Branch / Site",e(ctx.branch_display||c.custom_branch||"—"))+info("Company Workshop",e(c.custom_company_workshop||"—"))+'</div>'}
if(CP.tab==="calibration"){if(!truth(c.custom_requires_calibration))return empty("✓","Calibration is not required for this component.");let s=ds(c.custom_next_calibration_date);return'<div class="cp-section-title">Calibration</div><div class="cp-cal-status cp-cal-'+s.cls+'"><strong>'+e(s.label)+'</strong><span>'+e(s.detail)+'</span></div><div class="cp-info-grid">'+info("Last Calibration Date",fd(c.custom_last_calibration_date))+info("Next Calibration Date",fd(c.custom_next_calibration_date))+info("Calibration Interval",c.custom_calibration_interval_months?e(c.custom_calibration_interval_months+" months"):"—")+info("Last Calibration Record",doc("Calibration Record",c.custom_last_calibration_record))+'</div>'}
if(CP.tab==="lifecycle")return lifecycle();
if(CP.tab==="service")return service();
if(CP.tab==="config")return config();
if(CP.tab==="tickets")return tickets();
return""}
function lifecycle(){let r=CP.data.lifecycle||[];if(!r.length)return empty("↻","No component lifecycle events found.");let h='<div class="cp-section-title">Lifecycle History</div><div class="cp-timeline">';r.forEach(x=>h+='<div class="cp-timeline-row"><div class="cp-timeline-date">'+fd(x.custom_date||x.creation)+'</div><div class="cp-timeline-body"><div class="cp-timeline-title">'+e(x.custom_event||"Lifecycle Event")+'</div><div class="cp-timeline-meta">'+e([x.custom_event_source,x.technician_display||x.custom_technician].filter(Boolean).join(" · "))+'</div>'+(x.custom_action_taken?'<div class="cp-timeline-note">'+e(x.custom_action_taken)+'</div>':'')+'</div></div>');return h+'</div>'}
function service(){let r=CP.data.service||[];if(!r.length)return empty("🛠","No service history found for this component.");let h='<div class="cp-section-title">Service History</div><div class="cp-table-wrap"><table class="cp-table"><thead><tr><th>Date</th><th>Type</th><th>Technician</th><th>Outcome</th><th>Ticket</th><th>Intervention</th></tr></thead><tbody>';r.forEach(x=>h+='<tr><td>'+fdt(x.custom_end_time||x.creation)+'</td><td>'+e(x.custom_intervention_type||"—")+'</td><td>'+e(x.technician_display||x.custom_technician||"—")+'</td><td>'+e(x.custom_work_outcome||"—")+'</td><td>'+doc("Service Ticket",x.custom_service_ticket)+'</td><td>'+doc("Mission Intervention",x.custom_intervention_ref)+'</td></tr>');return h+'</tbody></table></div>'}
function config(){let r=CP.data.config||[];if(!r.length)return empty("⚙","No component-specific configuration changes found.");let h='<div class="cp-section-title">Configuration Changes</div><div class="cp-table-wrap"><table class="cp-table"><thead><tr><th>Date</th><th>Parameter</th><th>Previous</th><th>New</th><th>Technician</th></tr></thead><tbody>';r.forEach(x=>h+='<tr><td>'+fdt(x.custom_config_datetime||x.creation)+'</td><td>'+e(x.custom_parameter||"—")+'</td><td>'+e(x.custom_current_value||"—")+'</td><td>'+e(x.custom_new_value||"—")+'</td><td>'+e(x.technician_display||x.custom_technician||"—")+'</td></tr>');return h+'</tbody></table></div>'}
function tickets(){let r=CP.data.tickets||[];if(!r.length)return empty("🎫","No Service Tickets are linked to this component.");let h='<div class="cp-section-title">Component Tickets</div><div class="cp-table-wrap"><table class="cp-table"><thead><tr><th>Ticket</th><th>Date</th><th>Subject</th><th>Priority</th><th>Status</th></tr></thead><tbody>';r.forEach(x=>h+='<tr><td>'+doc("Service Ticket",x.name)+'</td><td>'+fd(x.custom_opening_date||x.creation)+'</td><td>'+e(x.custom_subject||"—")+'</td><td>'+e(x.custom_priority||"—")+'</td><td>'+e(x.custom_ticket_status||"—")+'</td></tr>');return h+'</tbody></table></div>'}

function cpGetTicketTypesForRequestType(requestType){
  var map={
    "Breakdown":["Repair","Service"],
    "Maintenance Request":["Preventive Maintenance","Service","Calibration","Commissioning"],
    "General Request":["Installation","Survey","Training","Audit","Incident Investigation","Asset Relocation","Config Change","Swap","Loan","Service","Decommissioning"]
  };
  return map[requestType]||[];
}

function cpUpdateTicketTypeOptions(){
  var requestSelect=document.getElementById("cp-ticket-request-type");
  var ticketSelect=document.getElementById("cp-ticket-type");
  if(!requestSelect||!ticketSelect)return;

  var types=cpGetTicketTypesForRequestType(requestSelect.value);
  var previous=ticketSelect.value;

  ticketSelect.innerHTML=types.map(function(type){
    return '<option value="'+e(type)+'">'+e(type)+'</option>';
  }).join("");

  if(types.indexOf(previous)!==-1){
    ticketSelect.value=previous;
  }else if(types.length){
    ticketSelect.value=types[0];
  }
}

function cpLoadTechnicians(){
  cpCall("maintenance_app.api.get_technicians",{}).then(function(rows){
    CP.technicianCache=rows||[];
    cpRenderSelectedTechnicians();
    cpRenderTechnicianSuggestions();
  }).catch(function(err){
    console.error("Could not load technicians",err);
    CP.technicianCache=[];
    cpRenderTechnicianSuggestions();
  });
}

function cpTechnicianLabel(user){
  if(!user)return "";
  var fullName=user.full_name||user.name||"";
  if(user.name&&fullName!==user.name)return fullName+" ("+user.name+")";
  return fullName;
}

function cpTechnicianInitials(user){
  var label=(user.full_name||user.name||"?").trim();
  var parts=label.split(/\s+/).filter(Boolean);
  if(!parts.length)return "?";
  if(parts.length===1)return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0)+parts[parts.length-1].charAt(0)).toUpperCase();
}

function cpRenderSelectedTechnicians(){
  var el=document.getElementById("cp-tech-tags");
  if(!el)return;

  el.innerHTML="";

  (CP.selectedTechnicians||[]).forEach(function(user){
    var tag=document.createElement("span");
    tag.className="cp-picker-tag";

    var label=document.createElement("span");
    label.textContent=cpTechnicianLabel(user);

    var remove=document.createElement("button");
    remove.type="button";
    remove.textContent="×";
    remove.setAttribute("data-remove-user",user.name||"");
    remove.setAttribute("aria-label","Remove "+cpTechnicianLabel(user));

    tag.appendChild(label);
    tag.appendChild(remove);
    el.appendChild(tag);
  });
}

function cpRenderTechnicianSuggestions(){
  var input=document.getElementById("cp-tech-search");
  var dropdown=document.getElementById("cp-tech-suggestions");
  if(!input||!dropdown)return;

  var q=(input.value||"").toLowerCase().trim();
  var selected={};

  (CP.selectedTechnicians||[]).forEach(function(user){
    selected[user.name]=true;
  });

  var matches=(CP.technicianCache||[]).filter(function(user){
    if(!user||!user.name||selected[user.name])return false;

    var label=((user.full_name||"")+" "+(user.name||"")).toLowerCase();
    return !q||label.includes(q);
  }).slice(0,8);

  dropdown.innerHTML="";

  if(!matches.length){
    var empty=document.createElement("div");
    empty.className="cp-picker-empty";
    empty.textContent=q?"No matching technician":"No technician available";
    dropdown.appendChild(empty);
    dropdown.classList.add("open");
    return;
  }

  matches.forEach(function(user){
    var option=document.createElement("div");
    option.className="cp-picker-option";
    option.setAttribute("data-tech-user",user.name);

    var avatar=document.createElement("div");
    avatar.className="cp-picker-avatar";
    avatar.textContent=cpTechnicianInitials(user);

    var label=document.createElement("div");
    label.textContent=cpTechnicianLabel(user);

    option.appendChild(avatar);
    option.appendChild(label);
    dropdown.appendChild(option);
  });

  dropdown.classList.add("open");
}

function cpAddTechnician(userName){
  var user=(CP.technicianCache||[]).find(function(row){
    return row.name===userName;
  });

  if(!user)return;

  if(!(CP.selectedTechnicians||[]).some(function(row){
    return row.name===user.name;
  })){
    CP.selectedTechnicians.push(user);
  }

  var input=document.getElementById("cp-tech-search");
  if(input)input.value="";

  cpRenderSelectedTechnicians();
  cpRenderTechnicianSuggestions();

  if(input)input.focus();
}

function cpRemoveTechnician(userName){
  CP.selectedTechnicians=(CP.selectedTechnicians||[]).filter(function(user){
    return user.name!==userName;
  });

  cpRenderSelectedTechnicians();
  cpRenderTechnicianSuggestions();
}

function cpTechSearchKeydown(event){
  if(event.key==="Enter"){
    event.preventDefault();
    var first=document.querySelector("#cp-tech-suggestions .cp-picker-option");
    if(first)first.click();
  }

  if(event.key==="Backspace"){
    var input=document.getElementById("cp-tech-search");
    if(input&&!input.value&&CP.selectedTechnicians.length){
      CP.selectedTechnicians.pop();
      cpRenderSelectedTechnicians();
      cpRenderTechnicianSuggestions();
    }
  }

  if(event.key==="Escape"){
    var dropdown=document.getElementById("cp-tech-suggestions");
    if(dropdown)dropdown.classList.remove("open");
  }
}

function cpGetSelectedTechnicians(){
  return (CP.selectedTechnicians||[]).map(function(user){
    return user.name;
  }).filter(Boolean);
}

function cpLoadApplicants(equipmentName){
  var select=document.getElementById("cp-ticket-applicant");
  if(!select)return;

  select.innerHTML='<option value="">No applicant selected</option>';

  cpCall("maintenance_app.api.get_eq_applicants_for_equipment",{
    equipment_name:equipmentName
  }).then(function(rows){
    (rows||[]).forEach(function(contact){
      var option=document.createElement("option");
      option.value=contact.name;
      option.textContent=contact.label||contact.name;
      select.appendChild(option);
    });
  }).catch(function(err){
    console.error("Could not load applicants",err);
    select.innerHTML='<option value="">Could not load contacts</option>';
  });
}


function cpShowModalConfirm(message){
  var el=document.getElementById("cp-modal-confirm");
  if(!el)return;
  el.textContent=message||"";
  el.classList.add("show");
}
function cpClearModalConfirm(){
  var el=document.getElementById("cp-modal-confirm");
  if(!el)return;
  el.textContent="";
  el.classList.remove("show");
}
function cpShowModalError(message){
  var el=document.getElementById("cp-modal-error");
  if(!el)return;
  el.textContent=message||"";
  el.classList.add("show");
}
function cpClearModalError(){
  var el=document.getElementById("cp-modal-error");
  if(!el)return;
  el.textContent="";
  el.classList.remove("show");
}
function cpOpenCreatedTicketInDesk(){
  if(!CP.createdTicket)return;
  window.location.href="/app/service-ticket/"+encodeURIComponent(CP.createdTicket);
}

function openTicket(){let c=CP.data.component;if(!c.custom_parent_equipment){frappe.msgprint("This component is not currently installed on an Installed Equipment record.");return}CP.selectedTechnicians=[];cpRenderSelectedTechnicians();document.getElementById("cp-ticket-target").textContent=(c.custom_display_name||c.name)+" · "+c.name;document.getElementById("cp-ticket-subject").value="Service Request - "+(c.custom_display_name||c.custom_equipment_type||c.name);document.getElementById("cp-ticket-description").value="";document.getElementById("cp-ticket-modal").style.display="flex";cpUpdateTicketTypeOptions();cpLoadTechnicians();cpLoadApplicants(c.custom_parent_equipment)}
function cpCloseTicketModal(){document.getElementById("cp-ticket-modal").style.display="none";CP.selectedTechnicians=[];CP.createdTicket=null;cpRenderSelectedTechnicians();cpClearModalConfirm();cpClearModalError();}
function cpCreateTicket(){
  var c=CP.data.component;
  var b=document.getElementById("cp-create-ticket-btn");
  var subject=document.getElementById("cp-ticket-subject").value.trim();

  cpClearModalConfirm();
  cpClearModalError();

  if(!subject){
    document.getElementById("cp-ticket-subject").focus();
    cpShowModalError("Subject is required.");
    return;
  }

  b.disabled=true;
  b.textContent="Creating…";

  cpCall("maintenance_app.api.create_service_ticket_from_equipment",{
    equipment_name:c.custom_parent_equipment,
    component_row_id:c.name,
    request_type:document.getElementById("cp-ticket-request-type").value,
    ticket_type:document.getElementById("cp-ticket-type").value,
    priority:document.getElementById("cp-ticket-priority").value,
    subject:subject,
    description:document.getElementById("cp-ticket-description").value,
    technicians:JSON.stringify(cpGetSelectedTechnicians()),
    applicant:(document.getElementById("cp-ticket-applicant")?document.getElementById("cp-ticket-applicant").value:"")||""
  }).then(function(r){
    if(r&&r.ticket){
      CP.createdTicket=r.ticket;

      var coverage=r.coverage||{};
      var serviceType=r.service_type||"Billable";

      cpShowModalConfirm(
        "✓ Ticket "+r.ticket+" created.\n"
        +"Equipment: "+(c.custom_parent_equipment||"—")+"\n"
        +"Component: "+(c.custom_display_name||c.name)+"\n"
        +"Service Type: "+serviceType
        +(coverage.message?"\n"+coverage.message:"")
      );

      var deskBtn=document.getElementById("cp-btn-open-ticket-desk");
      if(deskBtn)deskBtn.style.display="inline-flex";

      b.textContent="Ticket Created";
      b.disabled=true;
    }else{
      b.disabled=false;
      b.textContent="Create Ticket";
      cpShowModalError("Ticket could not be created.");
    }
  }).catch(function(err){
    console.error(err);
    b.disabled=false;
    b.textContent="Create Ticket";
    cpShowModalError("Ticket could not be created. Please check the error and try again.");
  });
}

function cpToggleMenu(){document.querySelector(".cp-sidebar").classList.toggle("open");document.getElementById("cp-backdrop").classList.toggle("open")}function cpCloseMenu(){document.querySelector(".cp-sidebar").classList.remove("open");document.getElementById("cp-backdrop").classList.remove("open")}
function load(){document.getElementById("cp-content").innerHTML='<div class="cp-loading">Loading component…</div>';return cpCall("maintenance_app.api.get_component_webview_data",{component_name:CP.name}).then(d=>{CP.data=d;render()}).catch(err=>{console.error(err);document.getElementById("cp-content").innerHTML=empty("⚠","Could not load this Equipment Component.")})}

document.addEventListener("click",function(event){
  var techOption=event.target.closest("[data-tech-user]");
  if(techOption){
    event.preventDefault();
    event.stopPropagation();
    cpAddTechnician(techOption.getAttribute("data-tech-user"));
    return;
  }

  var removeButton=event.target.closest("[data-remove-user]");
  if(removeButton){
    event.preventDefault();
    event.stopPropagation();
    cpRemoveTechnician(removeButton.getAttribute("data-remove-user"));
    return;
  }

  var picker=document.getElementById("cp-tech-picker");
  var dropdown=document.getElementById("cp-tech-suggestions");

  if(picker&&dropdown&&!picker.contains(event.target)){
    dropdown.classList.remove("open");
  }
});

document.addEventListener("DOMContentLoaded",()=>{CP.name=p("name");if(!CP.name){document.getElementById("cp-content").innerHTML=empty("⚠","No Equipment Component was specified.");return}load();document.addEventListener("keydown",x=>{if(x.key==="Escape"){cpCloseMenu();cpCloseTicketModal()}})});


