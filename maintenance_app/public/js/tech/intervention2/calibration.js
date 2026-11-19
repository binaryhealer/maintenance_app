(function () {
  'use strict';
  var panel = document.getElementById('tech2-calibration-panel');
  if (!panel) return;
  var mi = panel.getAttribute('data-mi');
  var targets = document.getElementById('tech2-cal-targets');
  var tests = document.getElementById('tech2-cal-tests');
  var status = document.getElementById('tech2-cal-status');
  var testStatus = document.getElementById('tech2-cal-test-status');
  var saveTargets = document.getElementById('tech2-cal-save');
  var saveReadings = document.getElementById('tech2-cal-save-readings');
  var showAll = document.getElementById('tech2-cal-show-all');
  var data = null;
  function k(eq,comp){return eq + '|' + (comp || '');}
  function text(el,s){el.textContent=s == null ? '' : String(s);return el;}
  function make(tag,cls,label){var x=document.createElement(tag);if(cls)x.className=cls;if(label!==undefined)text(x,label);return x;}
  function notice(el,msg){if(el)text(el,msg);}
  function call(method,args){
    return new Promise(function(resolve,reject){
      var tries=0;
      function go(){
        if(window.frappe && typeof window.frappe.call==='function'){
          try{window.frappe.call({method:'maintenance_app.'+(method.indexOf('save_calibration_targets')===0?'calibration_pwa':(method.indexOf('calibration_table')!==-1?'calibration_table':'calibration_workflow'))+'.'+method,
            args:args,callback:function(r){if(r&&r.exc)reject(new Error('Request failed'));else resolve((r&&r.message)||{});},error:reject});}
          catch(e){reject(e);}return;
        }
        if(++tries>=60){reject(new Error('Frappe API unavailable'));return;}
        setTimeout(go,200);
      }
      go();
    });
  }
  function selectedMap(){var s={};(data.records||[]).forEach(function(r){s[k(r.equipment,r.component)]=r;});return s;}
  // Display names are for technicians; record links still use stable IDs.
  function targetName(rec){
    var equipment=(data.equipment||[]).find(function(e){return e.name===rec.equipment;});
    var equipmentLabel=equipment ? (equipment.label||equipment.name) : rec.equipment;
    if (!rec.component) return equipmentLabel + ' — Complete Equipment';
    var component=equipment && (equipment.components||[]).find(function(c){return c.name===rec.component;});
    var componentLabel=component ? (component.label||component.name) : rec.component;
    // Existing component labels may already contain the parent equipment name.
    // Avoid repeating it in the heading.
    if (componentLabel.indexOf(equipmentLabel+' - ')===0)
      componentLabel=componentLabel.slice(equipmentLabel.length+3);
    else if (componentLabel.indexOf(equipmentLabel+' — ')===0)
      componentLabel=componentLabel.slice(equipmentLabel.length+3);
    return equipmentLabel + ' → ' + componentLabel;
  }
  function row(eq,comp,label,options,saved,readonly,required,defaultTemplate){
    var wrap=make('div','tech2-cal-target'+(comp?' tech2-cal-component':''));
    wrap.dataset.equipment=eq;wrap.dataset.component=comp||'';
    var choice=make('label');var check=make('input');check.type='checkbox';check.checked=!!saved;check.disabled=!!readonly;
    choice.appendChild(check);choice.appendChild(make('span','',label));wrap.appendChild(choice);
    var select=make('select');select.className='tech2-cal-template';select.disabled=!!readonly;
    var empty=make('option','','Choose calibration template');empty.value='';select.appendChild(empty);
    options.forEach(function(opt){var o=make('option','',opt.label);o.value=opt.name;select.appendChild(o);});
    if(saved && saved.template)select.value=saved.template;
    else if(defaultTemplate && options.some(function(opt){return opt.name===defaultTemplate;}))select.value=defaultTemplate;
    select.hidden=!check.checked;
    if(!options.length){var note=make('div','tech2-cal-muted','No compatible calibration template configured');wrap.appendChild(note);if(!saved)check.disabled=true;}
    wrap.appendChild(select);
    check.addEventListener('change',function(){select.hidden=!check.checked;});
    return wrap;
  }
  // GMAO_PARTIAL_CAL_CONTINUE_V1: follow-up MI read-only calibration progress.
  function render(){
    targets.innerHTML='';
    var saved=selectedMap();
    var previous=(data.previous_calibrations||{});
    var total=0,completed=0;
    (data.equipment||[]).forEach(function(eq){
      (eq.components||[]).forEach(function(c){
        if(c.requires_calibration || previous[c.name]){
          total++;
          if(previous[c.name] && previous[c.name].completed)completed++;
        }
      });
    });
    function previousResultsForComponent(component){return previous[component]||null;}
    if(Object.keys(previous).length){
      var summary=make('p','tech2-cal-muted',
        'Continue Work: '+completed+' of '+total+' required/previously tested component(s) completed in earlier interventions.');
      targets.appendChild(summary);
    }
    if(!data.equipment || !data.equipment.length){notice(targets,'No equipment assigned to this intervention.');return;}
    data.equipment.forEach(function(eq){
      var box=make('section','tech2-cal-equipment');box.appendChild(make('strong','',eq.label||eq.name));
      var root=saved[k(eq.name,'')];
      if(eq.requires_calibration || (showAll&&showAll.checked) || root || previous['']){
        var equipmentHistory=previous[''];
        if(equipmentHistory && equipmentHistory.completed && !root){
          box.appendChild(make('p','tech2-cal-muted','Complete equipment calibrated in '+equipmentHistory.mi+
            ' ('+equipmentHistory.result+'). Already completed; read-only.'));
        }else{
          box.appendChild(row(eq.name,'','Calibrate complete equipment',eq.templates||[],root,data.readonly,eq.requires_calibration,eq.default_template));
          if(equipmentHistory && !equipmentHistory.completed)
            box.appendChild(make('p','tech2-cal-muted','Previous result: Fail in '+equipmentHistory.mi+'. Select to retest if needed.'));
        }
      }
      var count=0;
      (eq.components||[]).forEach(function(c){
        var previous=saved[k(eq.name,c.name)];
        var historical=previousResultsForComponent(c.name);
        if(!c.requires_calibration && !(showAll&&showAll.checked) && !previous && !historical)return;
        if(historical && historical.completed && !previous){
          var old=make('div','tech2-cal-target tech2-cal-component');
          old.appendChild(make('strong','',c.label));
          old.appendChild(make('p','tech2-cal-muted',
            '✓ Completed in '+historical.mi+' — '+historical.result+' ('+historical.record+'). Read-only.'));
          box.appendChild(old);
        }else{
          box.appendChild(row(eq.name,c.name,c.label,c.templates||[],previous,data.readonly,c.requires_calibration,eq.default_template));
          if(historical && !historical.completed){
            box.appendChild(make('p','tech2-cal-muted',
              'Previous calibration failed in '+historical.mi+'. Select this component only if retesting.'));
          }
        }
        count++;
      });
      if(!count && !eq.requires_calibration && !root && !(showAll&&showAll.checked))
        box.appendChild(make('div','tech2-cal-muted','No components marked for calibration. Use Show all components for exceptional work.'));
      targets.appendChild(box);
    });
  }
  function fetchData(){return call('get_calibration_workspace',{mi_name:mi}).then(function(d){data=d;render();return d;});}
  function pointInput(point,old){
    var wrap=make('div','tech2-cal-measure');wrap.dataset.point=point.name;
    wrap.appendChild(make('strong','', 'Test: ' + point.name));
    var details=[];if(point.unit)details.push('Unit: '+point.unit);
    if(point.method==='Absolute Tolerance')details.push('Expected '+point.expected+' ± '+point.tolerance);
    if(point.method==='Range')details.push('Allowed '+point.minimum+' to '+point.maximum);
    if(point.method==='Record Only')details.push('Record only — no automatic Pass/Fail');
    wrap.appendChild(make('p','tech2-cal-muted',details.join(' · ')));
    if(point.instructions)wrap.appendChild(make('p','tech2-cal-muted',point.instructions));
    var fields=make('div','tech2-cal-fields');
    [['before','Before reading'],['after','After reading']].forEach(function(f){
      var outer=make('label','',f[1]);var input=make('input');input.type='number';input.step='any';input.dataset.kind=f[0];
      if(old && old[f[0]]!==null && old[f[0]]!==undefined)input.value=old[f[0]];
      outer.appendChild(input);fields.appendChild(outer);
    });
    wrap.appendChild(fields);var remarks=make('label','','Notes (optional)');var field=make('input');field.dataset.kind='remarks';field.value=(old&&old.remarks)||'';remarks.appendChild(field);wrap.appendChild(remarks);
    if(old && old.result && old.result!=='Not Tested')wrap.appendChild(make('p','tech2-cal-result','Draft test result: '+old.result));
    return wrap;
  }
  function renderCustomTable(card,rec){
    call('get_calibration_table',{mi_name:mi,record_name:rec.name}).then(function(tbl){
      if(!tbl.enabled)return;
      var section=make('div','tech2-cal-custom-table');
      section.appendChild(make('h5','',tbl.title || 'Calibration Measurements'));
      section.appendChild(make('p','tech2-cal-muted','Enter your measurements in order, then choose the result and save.'));
      var entries=make('div','tech2-cal-reading-entries');section.appendChild(entries);
      var rows=(tbl.rows||[]).map(function(r){return Object.assign({},r);});
      var readOnly=!!tbl.readonly||!!data.readonly;
      var dirty=false;
      var localMessage=make('p','tech2-cal-save-message','');
      localMessage.setAttribute('role','status');localMessage.setAttribute('aria-live','polite');
      var save=null;
      var selectedResult=['Pass','Fail','Pass After Adjustment'].indexOf(rec.overall_result)>=0 ? rec.overall_result : '';
      function markDirty(){dirty=true;localMessage.textContent='Unsaved calibration changes';localMessage.className='tech2-cal-save-message is-pending';}
      function refreshRows(){
        entries.innerHTML='';
        rows.forEach(function(row,index){
          var group=make('fieldset','tech2-cal-measure tech2-cal-reading-row');
          group.appendChild(make('legend','', 'Measurement '+(index+1)));
          var grid=make('div','tech2-cal-reading-grid');
          (tbl.columns||[]).forEach(function(col){
            var label=make('label','tech2-cal-field');
            var name=make('span','tech2-cal-field-name',col.label+(col.required?' *':''));
            label.appendChild(name);
            var field=(col.key==='custom_generic_notes')?make('textarea','tech2-cal-input'):make('input','tech2-cal-input');
            if(field.tagName==='INPUT'){
              field.type=col.type==='Number'?'number':'text';
              if(field.type==='number')field.step='any';
            }else{field.rows=2;}
            field.value=row[col.key] == null?'':row[col.key];
            field.disabled=readOnly;
            field.setAttribute('aria-label',col.label);
            if(col.required)field.required=true;
            if(col.help)field.title=col.help;
            field.addEventListener('input',function(){row[col.key]=field.value;markDirty();});
            label.appendChild(field);grid.appendChild(label);
          });
          group.appendChild(grid);
          if(!readOnly){
            var del=make('button','btn btn-secondary tech2-cal-remove','Remove measurement');del.type='button';
            del.addEventListener('click',function(){rows.splice(index,1);markDirty();refreshRows();});group.appendChild(del);
          }
          entries.appendChild(group);
        });
      }
      refreshRows();
      if(!readOnly){
        var add=make('button','btn btn-secondary tech2-cal-add','+ Add measurement');add.type='button';
        add.addEventListener('click',function(){rows.push({});markDirty();refreshRows();});section.appendChild(add);
      }
      var resultBox=make('fieldset','tech2-cal-result-box');
      resultBox.appendChild(make('legend','tech2-cal-result-heading','Overall Calibration Result *'));
      var options=['Pass','Fail','Pass After Adjustment'];
      var groupName='tech2-cal-outcome-'+rec.name.replace(/[^a-zA-Z0-9_-]/g,'-');
      options.forEach(function(value){
        var label=make('label','tech2-cal-radio-option');
        var radio=make('input');radio.type='radio';radio.name=groupName;radio.value=value;
        radio.checked=selectedResult===value;radio.disabled=readOnly;
        radio.addEventListener('change',function(){selectedResult=value;markDirty();if(save)save.disabled=false;});
        label.appendChild(radio);label.appendChild(make('span','',value));resultBox.appendChild(label);
      });
      section.appendChild(resultBox);
      if(!readOnly){
        save=make('button','btn btn-primary tech2-cal-combined-save','Save Calibration Table & Result');
        save.type='button';save.disabled=!selectedResult;
        save.addEventListener('click',function(){
          if(!selectedResult){
            localMessage.textContent='Please select Overall Calibration Result.';
            localMessage.className='tech2-cal-save-message is-error';return;
          }
          if(!rows.length){
            localMessage.textContent='Add at least one measurement before saving.';
            localMessage.className='tech2-cal-save-message is-error';return;
          }
          // Required mapped fields are checked here and again on the server.
          for(var i=0;i<rows.length;i++){
            for(var j=0;j<(tbl.columns||[]).length;j++){
              var column=tbl.columns[j];
              if(column.required && String(rows[i][column.key] == null?'':rows[i][column.key]).trim()===''){
                localMessage.textContent='Measurement '+(i+1)+': '+column.label+' is required.';
                localMessage.className='tech2-cal-save-message is-error';return;
              }
            }
          }
          save.disabled=true;
          localMessage.textContent='Saving measurements and result...';
          localMessage.className='tech2-cal-save-message is-pending';
          call('save_calibration_table_with_result',{
            mi_name:mi,record_name:rec.name,rows:JSON.stringify(rows),result:selectedResult
          }).then(function(reply){
            dirty=false;rec.overall_result=selectedResult;
            localMessage.textContent='✓ Measurements and '+selectedResult+' result saved successfully.';
            localMessage.className='tech2-cal-save-message is-success';
            notice(testStatus,'Calibration saved for '+rec.name);
          }).catch(function(error){
            console.error(error);
            localMessage.textContent='Save failed. Please check the server message and retry.';
            localMessage.className='tech2-cal-save-message is-error';
          }).finally(function(){save.disabled=false;});
        });
        section.appendChild(save);
      }
      section.appendChild(localMessage);
      card.appendChild(section);
    }).catch(function(e){console.error(e);card.appendChild(make('p','tech2-cal-muted','Unable to load calibration table.'));});
  }
  function showTests(){
    tests.innerHTML='';
    var records=(data.records||[]).filter(function(r){return r.status!=='Cancelled';});
    if(!records.length){tests.hidden=true;if(saveReadings)saveReadings.hidden=true;return;}
    tests.hidden=false;tests.appendChild(make('h4','','Calibration Tests'));
    records.forEach(function(rec){
      var card=make('section','tech2-cal-test-card');card.dataset.record=rec.name;
      card.appendChild(make('h5','',targetName(rec)));
      card.appendChild(make('p','tech2-cal-muted','Calibration template: '+(rec.template||'Not selected')));
      // A Custom Table may intentionally have no standard test points.

      (rec.points||[]).forEach(function(p){var old=(rec.readings||[]).find(function(r){return r.name===p.name;});card.appendChild(pointInput(p,old));});
      if(saveReadings && !data.readonly && rec.points && rec.points.length){var one=make('button','btn btn-secondary','Save readings for this target');one.type='button';one.addEventListener('click',function(){saveOne(card,one);});card.appendChild(one);}
      else card.querySelectorAll('input').forEach(function(i){i.disabled=true;});
      tests.appendChild(card);
      renderCustomTable(card,rec);


    });
    if(saveReadings)saveReadings.hidden=true;
  }
  function saveOne(card,button){
    var rows=[];
    card.querySelectorAll('.tech2-cal-measure').forEach(function(wrap){
      var r={name:wrap.dataset.point};wrap.querySelectorAll('[data-kind]').forEach(function(f){r[f.dataset.kind]=f.value;});rows.push(r);
    });
    button.disabled=true;notice(testStatus,'Saving draft readings...');
    call('save_calibration_readings',{mi_name:mi,record_name:card.dataset.record,readings:JSON.stringify(rows)})
      .then(function(r){notice(testStatus,r.message||'Draft saved');return fetchData();})
      .then(showTests)
      .catch(function(e){console.error(e);notice(testStatus,'Readings not saved. Check the browser console and server response.');})
      .finally(function(){button.disabled=false;});
  }
  if(showAll)showAll.addEventListener('change',render);
  if(saveTargets)saveTargets.addEventListener('click',function(){
    if(!data || data.readonly)return;
    var chosen=[];
    targets.querySelectorAll('.tech2-cal-target').forEach(function(wrap){
      // Historical completed components are rendered read-only without a checkbox.
      // Skip them: they are already stored in their original submitted MI.
      var cb=wrap.querySelector('input[type="checkbox"]');
      if(!cb || !cb.checked)return;
      var select=wrap.querySelector('select');
      if(!select){throw new Error('Selected calibration target has no template selector');}
      chosen.push({equipment:wrap.dataset.equipment,component:wrap.dataset.component,template:select.value});
    });
    if(!chosen.length){notice(status,'Select at least one calibration target.');return;}
    if(chosen.some(function(r){return !r.template;})){notice(status,'Choose a template for every selected target.');return;}
    saveTargets.disabled=true;notice(status,'Saving targets...');
    call('save_calibration_targets',{mi_name:mi,targets:JSON.stringify(chosen)})
      .then(function(r){notice(status,r.message||'Targets saved');return fetchData();})
      .then(function(){showTests();if(!tests.hidden)tests.scrollIntoView({behavior:'smooth',block:'start'});})
      .catch(function(e){console.error(e);notice(status,'Unable to save targets. Check the server response.');})
      .finally(function(){saveTargets.disabled=false;});
  });
  // GMAO_CAL_FINISH_READINGS_GATE_V1
  // Prevent leaving Calibration Work while selected targets are unsaved,
  // edited readings are unsaved, or the saved records fail MI-submit checks.
  var finishLink = panel.querySelector('.tech2-cal-next-btn');
  if (finishLink) finishLink.addEventListener('click', function(event){
    if (event.defaultPrevented || !data || data.readonly) {
      if (!data) { event.preventDefault(); notice(testStatus, 'Calibration is loading. Try again.'); }
      return;
    }
    event.preventDefault();
    if (finishLink.dataset.checking === '1') return;
    var saved = selectedMap();
    var notSaved = false;
    targets.querySelectorAll('.tech2-cal-target').forEach(function(wrap){
      var cb = wrap.querySelector('input[type="checkbox"]');
      if (cb && cb.checked && !saved[k(wrap.dataset.equipment, wrap.dataset.component)]) {
        notSaved = true;
      }
    });
    if (notSaved) {
      notice(testStatus, 'Save Targets & Continue to Tests before Finish Work.');
      return;
    }
    var pending = panel.querySelectorAll('.tech2-cal-save-message.is-pending, .tech2-cal-save-message.is-error');
    if (pending.length) {
      notice(testStatus, 'Save the calibration measurements and result for every selected component before Finish Work.');
      return;
    }
    // GMAO_CAL_FINISH_CHECK_UNLOCK_V2: never leave the link locked forever.
    finishLink.dataset.checking = '1';
    finishLink.setAttribute('aria-disabled', 'true');
    notice(testStatus, 'Checking saved calibration readings...');
    var checkTimeout;
    var deadline = new Promise(function(resolve, reject){
      checkTimeout = setTimeout(function(){
        reject(new Error('Calibration preflight timed out after 15 seconds'));
      }, 15000);
    });
    Promise.race([
      call('check_calibration_finish_ready', {mi_name: mi}),
      deadline
    ])
      .then(function(reply){
        if (!reply || !reply.ok) throw new Error('Calibration validation did not succeed');
        clearTimeout(checkTimeout);
        notice(testStatus, 'Calibration validated. Opening Finish Work...');
        window.location.assign(finishLink.href);
      })
      .catch(function(error){
        clearTimeout(checkTimeout);
        console.error('Finish Work calibration readiness failed:', error);
        notice(testStatus, 'Cannot continue: ' + (error && error.message ? error.message : 'calibration check failed') + '. Please retry, or check the browser Network tab.');
        finishLink.dataset.checking = '0';
        finishLink.removeAttribute('aria-disabled');
      });
  });
  fetchData().then(showTests).catch(function(e){console.error(e);notice(targets,'Unable to load calibration targets.');});
})();
