/* Consolidated Calibration Report controls, independent of MI completion and MI signature. */
(function(){
  'use strict';
  function el(t, cls, content){var x=document.createElement(t);if(cls)x.className=cls;if(content!==undefined)x.textContent=content;return x;}
  function api(name,args){return new Promise(function(resolve,reject){
    var attempts=0;function go(){
      if(!window.frappe || typeof window.frappe.call!=='function'){
        if(++attempts>80){reject(new Error('Frappe API unavailable'));return;}
        setTimeout(go,150);return;
      }
      window.frappe.call({method:'maintenance_app.calibration_batch.'+name,args:args||{},
        callback:function(r){if(r&&r.exc)reject(new Error('Server returned an error'));else resolve(r.message||{});},
        error:function(e){reject(e);}});
    }go();
  });}
  function start(){
    // This host is rendered ONLY on the Submit step of a submitted Calibration MI.
    var wrap=document.getElementById('gmao-cal-batch-host');if(!wrap)return;
    var mi=wrap.getAttribute('data-mi');if(!mi)return;
    var content=document.getElementById('gmao-cal-batch-content');if(!content)return;
    var state=el('div','tech2-muted');state.setAttribute('role','status');
    wrap.insertBefore(state,content);
    function status(t){state.textContent=t;}
    function button(txt,fn){var b=el('button','btn btn-secondary',txt);b.type='button';b.style.margin='5px';
      b.onclick=function(){b.disabled=true;Promise.resolve().then(fn).catch(function(e){console.error(e);status(e.message||'Action failed.');})
        .finally(function(){b.disabled=false;});};return b;}
    function render(){status('Loading calibration reports...');content.textContent='';
      return api('get_calibration_batch_workspace',{mi_name:mi}).then(function(data){
        status('Service Ticket '+data.st+' · Tech Mission '+data.tm);
        var candidates=data.candidates||[],drafts=data.drafts||[];
        var open=el('div');content.appendChild(open);
        open.appendChild(el('h5','', 'Completed interventions'));
        var eligible=[];
        candidates.forEach(function(c){
          var line=el('label');line.style.display='block';line.style.padding='7px 0';
          if(c.eligible){var cb=el('input');cb.type='checkbox';cb.value=c.mi;eligible.push(cb);line.appendChild(cb);}
          line.appendChild(document.createTextNode(' '+c.mi+' · '+c.equipment_label+
            (c.report?' (Report '+c.report+(c.finalized?' — signed':' — draft')+')':'')));
          open.appendChild(line);
        });
        if(!candidates.length)open.appendChild(el('p','tech2-muted','No submitted Calibration MIs in this Tech Mission yet.'));
        if(!drafts.length){
          open.appendChild(button('Start New Calibration Report',function(){return api('create_calibration_batch',{mi_name:mi})
            .then(render);}));
        }
        drafts.forEach(function(d){
          var box=el('div','tech2-card');box.style.margin='10px 0';content.appendChild(box);
          box.appendChild(el('h5','', 'Draft report '+d.name));
          box.appendChild(el('p','tech2-muted',d.mis.length?('Included MIs: '+d.mis.join(', ')):'No MIs added yet'));
          box.appendChild(button('Add Selected MIs',function(){var chosen=eligible.filter(function(x){return x.checked;}).map(function(x){return x.value;});
            if(!chosen.length)throw new Error('Select completed MIs first.');
            return api('add_interventions_to_batch',{report_name:d.name,mi_names:JSON.stringify(chosen)})
            .then(render);
          }));
          box.appendChild(button('Review & Sign Report',function(){return preview(d.name,box);}));
        });
        if(!drafts.length && eligible.length)content.appendChild(el('p','tech2-muted','Create a report, then select completed MIs to add.'));
      }).catch(function(e){status('Unable to load report workspace: '+e.message);console.error(e);});
    }
    function preview(name,host){
      return api('get_calibration_batch_preview',{report_name:name}).then(function(p){
        var old=document.getElementById('gmao-cal-review');if(old)old.remove();
        var area=el('div','tech2-card');area.id='gmao-cal-review';area.style.marginTop='12px';host.appendChild(area);
        area.appendChild(el('h5','', 'Review results before client signing'));
        (p.items||[]).forEach(function(item){
          area.appendChild(el('strong','',item.mi+' · '+item.equipment));
          (item.records||[]).forEach(function(r){
            area.appendChild(el('p','', (r.component||'Complete Equipment')+' · '+r.result+' ('+r.name+')'));
            (r.readings||[]).forEach(function(v){
              area.appendChild(el('p','tech2-muted',String(v.point||'Test')+' · Before: '+String(v.before==null?'—':v.before)+' · After: '+String(v.after==null?'—':v.after)+' · '+String(v.result||'')));
            });
            if(r.table && r.table.columns && r.table.rows){
              var tb=el('table','table table-bordered');var head=el('tr');
              r.table.columns.forEach(function(col){head.appendChild(el('th','',col.label));});tb.appendChild(head);
              r.table.rows.forEach(function(v){var tr=el('tr');r.table.columns.forEach(function(col){
                tr.appendChild(el('td','',String(v[String(col.key)]==null?'':v[String(col.key)])));});tb.appendChild(tr);});
              area.appendChild(tb);
            }
          });
        });
        if(!p.items || !p.items.length){area.appendChild(el('p','tech2-muted','Add MIs before signing.'));return;}
        // Jar data is stored on the consolidated report before signing.
        var jarBox=el('div','tech2-card');jarBox.style.margin='12px 0';area.appendChild(jarBox);
        jarBox.appendChild(el('h5','', 'Calibration measuring jar'));
        var capLabel=el('label','', 'Measuring jar capacity (litres) *');capLabel.style.display='block';jarBox.appendChild(capLabel);
        var jarCap=el('input','form-control');jarCap.type='number';jarCap.step='any';jarCap.min='0.001';jarCap.required=true;
        jarCap.placeholder='e.g. 20';jarCap.value=(p.measure_jar_capacity_l==null?'':String(p.measure_jar_capacity_l));jarBox.appendChild(jarCap);
        var idLabel=el('label','', 'Measuring jar ID (optional)');idLabel.style.display='block';idLabel.style.marginTop='10px';jarBox.appendChild(idLabel);
        var jarId=el('input','form-control');jarId.type='text';jarId.maxLength=140;
        jarId.placeholder='e.g. JAR-001';jarId.value=p.measure_jar_identifier||'';jarBox.appendChild(jarId);
        // GMAO_CAL_TWO_SIGNATURES_V1: logged-in technician signs the batch.
        var techBox=el('div','tech2-card');techBox.style.margin='12px 0';area.appendChild(techBox);
        techBox.appendChild(el('h5','', 'Technician confirmation'));
        var techNameLabel=el('label','', 'Technician (logged-in user)');techNameLabel.style.display='block';techBox.appendChild(techNameLabel);
        var techName=el('input','form-control');techName.type='text';techName.readOnly=true;
        techName.value=p.technician_name||p.technician_user||'';techBox.appendChild(techName);
        techBox.appendChild(el('label','', 'Technician signature *'));
        function makeSignaturePad(host){
          var c=el('canvas');c.width=580;c.height=180;c.style.width='100%';c.style.maxWidth='580px';
          c.style.height='180px';c.style.border='1px solid #bbb';c.style.touchAction='none';c.style.background='#fff';host.appendChild(c);
          var context=c.getContext('2d');var down=false;var drawn=false;
          function reset(){context.clearRect(0,0,c.width,c.height);context.fillStyle='#fff';context.fillRect(0,0,c.width,c.height);
            context.lineWidth=2;context.strokeStyle='#111';context.lineJoin='round';context.lineCap='round';drawn=false;}
          function pos(e){var r=c.getBoundingClientRect();return {x:(e.clientX-r.left)*c.width/r.width,y:(e.clientY-r.top)*c.height/r.height};}
          reset();
          c.addEventListener('pointerdown',function(e){e.preventDefault();down=true;c.setPointerCapture(e.pointerId);var pt=pos(e);context.beginPath();context.moveTo(pt.x,pt.y);});
          c.addEventListener('pointermove',function(e){if(!down)return;e.preventDefault();var pt=pos(e);context.lineTo(pt.x,pt.y);context.stroke();drawn=true;});
          c.addEventListener('pointerup',function(){down=false;});c.addEventListener('pointercancel',function(){down=false;});
          host.appendChild(button('Clear Technician Signature',function(){reset();}));
          return {hasSignature:function(){return drawn;}, data:function(){return c.toDataURL('image/png');}};
        }
        var technicianPad=makeSignaturePad(techBox);
        var lab=el('label','', 'Client representative (full name)');lab.style.display='block';area.appendChild(lab);
        var input=el('input','form-control');input.placeholder='Client name';input.maxLength=140;area.appendChild(input);
        area.appendChild(el('p','tech2-muted','Client acknowledges all results, including any failed calibrations.'));
        var canvas=el('canvas');canvas.width=580;canvas.height=180;canvas.style.width='100%';canvas.style.maxWidth='580px';canvas.style.height='180px';canvas.style.border='1px solid #bbb';canvas.style.touchAction='none';canvas.style.background='#fff';area.appendChild(canvas);
        var ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
        ctx.lineWidth=2;ctx.strokeStyle='#111';ctx.lineJoin='round';ctx.lineCap='round';var pressed=false,drawn=false;
        function xy(e){var r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*canvas.width/r.width,y:(e.clientY-r.top)*canvas.height/r.height};}
        canvas.addEventListener('pointerdown',function(e){e.preventDefault();pressed=true;canvas.setPointerCapture(e.pointerId);var p=xy(e);ctx.beginPath();ctx.moveTo(p.x,p.y);});
        canvas.addEventListener('pointermove',function(e){if(!pressed)return;e.preventDefault();var p=xy(e);ctx.lineTo(p.x,p.y);ctx.stroke();drawn=true;});
        canvas.addEventListener('pointerup',function(){pressed=false;});canvas.addEventListener('pointercancel',function(){pressed=false;});
        area.appendChild(button('Clear Signature',function(){ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);drawn=false;}));
        area.appendChild(button('Client Signed — Submit Report',function(){
          if(!technicianPad.hasSignature())throw new Error('Technician signature is required.');
          if(!drawn)throw new Error('Client signature is required.');
          if(!input.value.trim())throw new Error('Enter the client representative name.');
          var capacity=Number(jarCap.value);
          if(!jarCap.value.trim() || !Number.isFinite(capacity) || capacity<=0)
            throw new Error('Enter a valid measuring jar capacity in litres.');
          if(!window.confirm('Submit signed calibration report '+name+'? This cannot be edited afterward.'))return;
          return api('sign_and_submit_calibration_batch',{report_name:name,client_name:input.value,
            measure_jar_capacity_l:capacity,measure_jar_identifier:jarId.value.trim(),
            signature_data:canvas.toDataURL('image/png'),
            technician_signature_data:technicianPad.data()}).then(function(x){status('Report '+x.name+' signed and submitted.');return render();});
        }));
      });
    }
    render();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
