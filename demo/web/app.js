/* GIS workspace. Thuộc tính nguồn chỉ vào DOM qua textContent. */
'use strict';
(() => {
  const D=window.HLAT_DATA, $=id=>document.getElementById(id), status=$('status');
  if(!D||!window.L){status.textContent='Không tải được thư viện hoặc dữ liệu bản đồ.';return;}
  const fmt=(n,d=2)=>Number(n).toLocaleString('vi-VN',{maximumFractionDigits:d});
  const fc=features=>({type:'FeatureCollection',features}), empty=()=>fc([]);
  const baseDistances=D.parameters.distances_m, baseArgs={distances:baseDistances,zone:'',voltage:''};
  const baseline={args:baseArgs,houses:D.layers.nha_vi_pham,pieces:D.layers.phan_vi_pham,corridor:D.layers.hanh_lang,
    lines:D.layers.duong_day,zones:D.layers.thong_ke_vung,stats:D.layers.thong_ke_vung.features.map(f=>f.properties),count:D.metrics.violation_houses,area:D.metrics.violation_area_m2};
  let state={A:baseline,B:null,active:'A',selected:null,page:0,query:'',busy:false,mask:null,sourceResults:null},worker,ready,serial=0,epoch=0,detailEpoch=0,searchEpoch=0;
  const pending=new Map();
  const node=(tag,text,className)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
  const map=L.map('map',{preferCanvas:true,maxZoom:20,zoomControl:false});L.control.zoom({position:'topright'}).addTo(map);
  for(const [name,z] of [['regions',350],['corridor',360],['powerlines',420],['houses',430],['pieces',440],['difference',450],['highlight',460]])map.createPane(name).style.zIndex=z;
  const osm=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxNativeZoom:19,maxZoom:20,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}), blank=L.layerGroup();
  (location.protocol==='file:'?blank:osm).addTo(map);
  const layers={
    zones:L.geoJSON(null,{pane:'regions',style:{color:'#617985',weight:1.4,fillOpacity:0},onEachFeature:(f,l)=>l.bindTooltip(String(f.properties.vung_ql||''),{sticky:true})}),
    corridor:L.geoJSON(null,{pane:'corridor',interactive:false,style:{color:'#dca740',weight:.5,fillColor:'#efbd4f',fillOpacity:.4}}),
    lines:L.geoJSON(null,{pane:'powerlines',style:{color:'#286b9a',weight:1.7,opacity:.8},onEachFeature:(f,l)=>{l.options.bubblingMouseEvents=false;const p=f.properties,box=node('div');box.append(node('b',p.capDienAp||'Đường dây'),node('div',p.soHieu||p.ten||'FID '+p.fid));l.bindPopup(box);}}),
    houses:L.geoJSON(null,{pane:'houses',bubblingMouseEvents:false,style:{color:'#ac4439',weight:1,fillColor:'#d7796c',fillOpacity:.6},onEachFeature:(f,l)=>{l.options.bubblingMouseEvents=false;l.on('click',()=>{if(!state.drawing)selectHouse(f,state.active,true);});}}),
    pieces:L.geoJSON(null,{pane:'pieces',interactive:false,style:{color:'#c63322',weight:.5,fillColor:'#d33826',fillOpacity:.8}}),
    difference:L.geoJSON(null,{pane:'difference',style:f=>({color:f.properties.change==='added'?'#137946':'#8053a1',weight:2,fillColor:f.properties.change==='added'?'#34a56d':'#a379be',fillOpacity:.65}),onEachFeature:(f,l)=>l.on('click',()=>{if(!state.drawing)selectHouse(f,f.properties.change==='added'?'B':'A',true);})}),
  };
  const highlight=L.geoJSON(null,{pane:'highlight',interactive:false,style:{color:'#00b9d0',weight:4,fillOpacity:0}}).addTo(map);
  for(const layer of Object.values(layers))layer.addTo(map);
  L.control.layers({'OpenStreetMap':osm,'Nền trắng':blank},{'Vùng quản lý':layers.zones,'Đường dây trung thế':layers.lines,'Hành lang an toàn':layers.corridor,'Nhà vi phạm':layers.houses,'Phần nhà trong HLAT':layers.pieces,'Nhà tăng / giảm':layers.difference},{position:'topright'}).addTo(map);
  L.control.scale({imperial:false}).addTo(map);
  const legend=L.control({position:'bottomright'});legend.onAdd=()=>{const el=L.DomUtil.create('div','map-legend');for(const [color,text] of [['#d7796c','Nhà vi phạm'],['#d33826','Phần nhà trong HLAT'],['#efbd4f','Hành lang an toàn'],['#286b9a','Đường dây trung thế'],['#34a56d','Nhà tăng thêm (B)'],['#a379be','Nhà không còn (B)']]){const r=node('div'),i=node('i');i.style.background=color;r.append(i,document.createTextNode(text));el.append(r);}L.DomEvent.disableClickPropagation(el);return el;};legend.addTo(map);
  const fullBounds=L.geoJSON(baseline.zones).getBounds();map.fitBounds(fullBounds,{padding:[25,25]});
  map.on('mousemove',e=>$('coordinates').textContent=e.latlng.lat.toFixed(5)+'° N, '+e.latlng.lng.toFixed(5)+'° E');
  for(const f of baseline.zones.features)$('zone').add(new Option(f.properties.vung_ql,f.properties.vung_ql));
  const voltages=[...new Set(baseline.lines.features.map(f=>Number(String(f.properties.capDienAp||'').replace(/[^0-9.,]/g,'').replace(',','.'))).filter(v=>v>0))].sort((a,b)=>b-a);
  for(const v of voltages)$('voltage').add(new Option(v+' kV',String(v)));
  ['35','22','other'].forEach((s,i)=>{$('a'+s).value=baseDistances[i];$('b'+s).value=baseDistances[i]+(i===2?1:2);});
  function rpc(type,extra={}){return new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});worker.postMessage({type,id,...extra});});}
  function startWorker(){worker=new Worker('analysis-worker.js',{type:'module'});
    worker.onmessage=({data:m})=>{if(m.type==='progress'){if(state.busy)status.textContent=m.text;else $('engine-state').textContent=m.text.startsWith('Đang nạp')?'Đang nạp bộ tính…':'Bộ tính sẵn sàng';return;}const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(new Error(m.error)):p.resolve(m.result);}};
    worker.onerror=e=>{const error=new Error(e.message||'Không tải được bộ tính toán. Hãy mở bản đồ qua HTTP/HTTPS.');for(const p of pending.values())p.reject(error);pending.clear();$('engine-state').textContent='Bộ tính chưa sẵn sàng';};
    ready=rpc('init',{url:D.source.manifest});ready.then(r=>$('engine-state').textContent=fmt(r.house_count,0)+' nhà nguồn').catch(e=>{$('engine-state').textContent='Không nạp được bộ tính';status.textContent=e.message;});
  }
  function setBusy(value){state.busy=value;$('cancel').hidden=!value;for(const el of [$('apply'),$('zone'),$('voltage'),$('search'),$('search-scope'),...document.querySelectorAll('.parameters input')])el.disabled=value||Boolean(state.drawing);$('scenario-form').setAttribute('aria-busy',String(value));window.dispatchEvent(new Event('hlat:busy'));}
  function scopeArgs(distances){return {distances,zone:$('zone').value,voltage:$('voltage').value,...(state.mask?{mask:state.mask}:{})};}
  async function calculation(args){if(JSON.stringify(args)===JSON.stringify(baseArgs))return baseline;return rpc('analyze',{args});}
  async function calculate(compare){const turn=++epoch;setBusy(true);status.textContent='Đang chuẩn bị dữ liệu phân tích…';
    try{await ready;const distances=s=>['35','22','other'].map(k=>Number($(s+k).value));
      const a=scopeArgs(compare?distances('a'):state.A.args.distances),b=scopeArgs(compare?distances('b'):state.B?.args.distances);
      const A=await calculation(a),B=compare||state.B?await calculation(b):null;if(turn!==epoch)return;
      state.A=A;state.B=B;state.page=0;state.selected=null;state.sourceResults=null;detailEpoch++;$('details').hidden=true;highlight.clearLayers();
      if(compare)$('scenario-state').textContent='Đã tính A / B với các khoảng cách đang hiển thị.';
      render();if($('search-scope').value==='source'&&state.query)await runSourceSearch(0,false);status.textContent='Đã cập nhật bản đồ, danh mục và thống kê cùng bộ lọc.';return true;
    }catch(e){if(turn===epoch){status.textContent='Chưa cập nhật: '+e.message;$('zone').value=state.A.args.zone;$('voltage').value=state.A.args.voltage;state.mask=state.A.args.mask||null;}return false;}
    finally{if(turn===epoch)setBusy(false);}
  }
  function current(){return state[state.active];}
  function scopeLabel(){return (current().args.zone||'Tất cả vùng')+' · '+(current().args.voltage?current().args.voltage+' kV':'Tất cả cấp điện áp')+' · Phương án '+state.active+(current().args.mask?' · Trong vùng khoanh':'');}
  function differences(){if(!state.B)return {added:[],removed:[]};const a=new Set(state.A.houses.features.map(f=>f.properties.source_fid)),b=new Set(state.B.houses.features.map(f=>f.properties.source_fid));return {added:state.B.houses.features.filter(f=>!a.has(f.properties.source_fid)),removed:state.A.houses.features.filter(f=>!b.has(f.properties.source_fid))};}
  function render(){const r=current();for(const [name,data] of [['houses',r.houses],['pieces',r.pieces],['corridor',r.corridor],['lines',r.lines],['zones',r.zones]])layers[name].clearLayers().addData(data);
    document.querySelector('.map-top').hidden=!state.B;
    $('total-houses').textContent=fmt(r.count,0);$('total-area').textContent=fmt(r.area);$('stats-scope').textContent=scopeLabel();
    $('view-b').disabled=!state.B;for(const s of ['A','B']){$('view-'+s.toLowerCase()).classList.toggle('active',s===state.active);$('view-'+s.toLowerCase()).setAttribute('aria-pressed',String(s===state.active));}
    $('comparison').hidden=!state.B;$('diff-control').hidden=!state.B;layers.difference.clearLayers();
    if(state.B){const diff=differences();if($('diff').checked)layers.difference.addData(fc([...diff.added.map(f=>({...f,properties:{...f.properties,change:'added'}})),...diff.removed.map(f=>({...f,properties:{...f.properties,change:'removed'}}))]));
      $('comparison-body').replaceChildren();for(const [label,a,b,d] of [['Số nhà',state.A.count,state.B.count,0],['Diện tích (m²)',state.A.area,state.B.area,2]]){const tr=node('tr');for(const v of [label,fmt(a,d),fmt(b,d),(b-a>0?'+':'')+fmt(b-a,d)])tr.append(node('td',v));tr.lastChild.className=b>=a?'increase':'decrease';$('comparison-body').append(tr);}
      $('changes').textContent=fmt(diff.added.length,0)+' nhà tăng thêm · '+fmt(diff.removed.length,0)+' nhà không còn trong hành lang của B so với A.';
    }
    $('stats-body').replaceChildren();for(const z of r.stats){const tr=node('tr');tr.tabIndex=0;for(const v of [z.vung_ql,fmt(z.so_nha,0),fmt(z.dt_vp_m2)])tr.append(node('td',v));const choose=()=>{if(state.busy)return;if([...$('zone').options].some(o=>o.value===z.vung_ql)){$('zone').value=z.vung_ql;filterChanged();}};tr.onclick=choose;tr.onkeydown=e=>{if(e.key==='Enter')choose();};$('stats-body').append(tr);}
    renderCatalog();window.hlatState=state;window.dispatchEvent(new Event('hlat:render'));
  }
  function enrichSource(f){const found=current().houses.features.find(h=>h.properties.source_fid===f.properties.source_fid);return {...f,properties:{...f.properties,dt_vp_m2:0,ty_le_pct:0,...(found?.properties||{})}};}
  function catalogMatches(){if($('search-scope').value==='source')return (state.sourceResults?.features||[]).map(enrichSource);const features=current().houses.features,q=state.query.toLowerCase();if(!q)return features;const exact=features.filter(f=>String(f.properties.source_fid)===q);return exact.length?exact:features.filter(f=>String(f.properties.ma_nhan_dang||'').toLowerCase().includes(q));}
  function renderCatalog(){const source=$('search-scope').value==='source',matches=catalogMatches(),size=source?30:15,total=source?(state.sourceResults?.total||0):matches.length,pages=Math.max(1,Math.ceil(total/size));state.page=Math.min(state.page,pages-1);$('catalog-list').replaceChildren();$('catalog-count').textContent=fmt(total,0)+' kết quả · '+(source?'Nhà nguồn trong vùng đang chọn; diện tích HLAT theo điện áp và phương án hiện tại.':scopeLabel());$('csv').textContent=source?'CSV trang này':'Tải CSV';
    for(const f of source?matches:matches.slice(state.page*size,(state.page+1)*size)){const p=f.properties,b=node('button',undefined,'house-row');b.type='button';b.classList.toggle('selected',state.selected===p.source_fid);const top=node('span',undefined,'row-top');top.append(node('strong','FID '+p.source_fid),node('span',fmt(p.dt_vp_m2)+' m²','area'));b.append(top,node('small',p.ma_nhan_dang||'Chưa có mã nhận dạng'),node('small',p.vung_ql));b.onclick=()=>selectHouse(f,state.active,true);$('catalog-list').append(b);}
    if(!matches.length)$('catalog-list').append(node('p',source&&!state.sourceResults?'Nhập FID hoặc mã rồi bấm Tìm để tra toàn bộ dữ liệu nguồn.':'Không có nhà phù hợp với bộ lọc hoặc từ khóa.','help'));
    $('page-number').textContent=(state.page+1)+' / '+pages;$('prev').disabled=state.page===0;$('next').disabled=state.page>=pages-1;
  }
  async function selectHouse(f,scenario,zoom){const p=f.properties,turn=++detailEpoch;state.selected=p.source_fid;$('details').hidden=false;$('stats').hidden=true;$('table-toggle').setAttribute('aria-expanded','false');$('detail-title').textContent='FID '+p.source_fid+' · Phương án '+scenario;
    window.dispatchEvent(new Event('hlat:select'));
    const box=node('div',undefined,'detail-grid'),center=L.geoJSON(f).getBounds().getCenter();
    for(const [label,value,wide] of [['Trong HLAT đang lọc',fmt(p.dt_vp_m2)+' m²'],['Tỷ lệ diện tích',fmt(p.ty_le_pct)+' %'],['Diện tích nhà',fmt(p.dt_nha_m2)+' m²'],['Loại đối tượng',p.phan_loai],['Mã nhận dạng',p.ma_nhan_dang||'Chưa có',true],['Vùng quản lý',p.vung_ql,true],['Vị trí tâm khung bao',center.lat.toFixed(6)+', '+center.lng.toFixed(6),true]]){const div=node('div',undefined,wide?'wide':'');div.append(node('small',label),node('b',value));box.append(div);}$('detail-values').replaceChildren(box);
    highlight.clearLayers().addData(f);if(zoom){map.fitBounds(L.geoJSON(f).getBounds(),{paddingTopLeft:[70,150],paddingBottomRight:[innerWidth>1100?410:70,70],maxZoom:19});if(innerWidth<=760)toggleSidebar(false);}
    renderCatalog();$('related-lines').replaceChildren(node('p','Đang truy vết đường dây…','help'));
    try{if(!D.source||location.protocol==='file:')throw new Error('Mở bằng máy chủ HTTP/HTTPS để truy vết đường dây.');await ready;const related=await rpc('related',{args:state[scenario].args,fid:p.source_fid});if(turn!==detailEpoch)return;
      $('related-lines').replaceChildren();for(const l of related){const b=node('button',undefined,'line-row');b.append(node('strong',l.voltage+' kV · '+(l.name||'Đường dây FID '+l.id)),node('small','FID '+l.id+' · Khoảng cách '+fmt(l.distance,3)+' m'),node('small','HLAT '+fmt(l.width,3)+' m mỗi phía · Giao '+fmt(l.area)+' m²'));b.onclick=()=>{highlight.clearLayers().addData(f).addData(feature(l.geometry,{}));const bound=L.geoJSON(l.geometry).getBounds();map.fitBounds(bound,{paddingTopLeft:[50,80],paddingBottomRight:[innerWidth>1100?410:50,50],maxZoom:18});if(innerWidth<=760)$('details').hidden=true;};$('related-lines').append(b);}
      if(!related.length)$('related-lines').append(node('p','Không có giao diện tích dương trong phạm vi đang chọn.','help'));
    }catch(e){if(turn===detailEpoch)$('related-lines').replaceChildren(node('p',e.message,'help'));}
  }
  const feature=(geometry,properties)=>({type:'Feature',geometry,properties});
  function toggleSidebar(open){$('sidebar').classList.toggle('collapsed',!open);$('sidebar-toggle').setAttribute('aria-expanded',String(open));setTimeout(()=>map.invalidateSize(),0);}
  $('sidebar-toggle').onclick=()=>toggleSidebar($('sidebar').classList.contains('collapsed'));
  for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>{for(const x of document.querySelectorAll('[data-tab]')){x.classList.toggle('active',x===b);x.setAttribute('aria-selected',String(x===b));}for(const name of ['catalog','compare'])$(name+'-panel').hidden=b.dataset.tab!==name;};
  const filterChanged=()=>{calculate(false).then(()=>{if(state.busy)return;const z=current().zones;const bounds=L.geoJSON(z).getBounds();if(bounds.isValid())map.fitBounds(bounds,{padding:[30,110]});});};
  $('zone').onchange=filterChanged;$('voltage').onchange=filterChanged;
  $('scenario-form').onsubmit=e=>{e.preventDefault();calculate(true);};
  $('scenario-form').oninput=()=>$('scenario-state').textContent='Tham số đã thay đổi. Bấm tính để cập nhật kết quả.';
  $('cancel').onclick=()=>{epoch++;worker.terminate();for(const p of pending.values())p.reject(new Error('Đã hủy tính toán.'));pending.clear();setBusy(false);state.mask=state.A.args.mask||null;window.dispatchEvent(new Event('hlat:render'));status.textContent='Đã hủy; giữ kết quả trước đó.';$('zone').value=state.A.args.zone;$('voltage').value=state.A.args.voltage;startWorker();};
  $('home').onclick=()=>{if(state.busy||state.drawing)return;const filtered=state.A.args.zone||state.A.args.voltage||state.mask;state.mask=null;$('zone').value='';$('voltage').value='';$('search').value='';state.query='';state.sourceResults=null;searchEpoch++;state.page=0;state.selected=null;detailEpoch++;$('details').hidden=true;highlight.clearLayers();map.closePopup();if(filtered)calculate(false).then(()=>map.fitBounds(fullBounds,{padding:[25,25]}));else{map.fitBounds(fullBounds,{padding:[25,25]});renderCatalog();}};
  $('close-detail').onclick=()=>{detailEpoch++;$('details').hidden=true;state.selected=null;highlight.clearLayers();renderCatalog();};
  $('table-toggle').onclick=()=>{$('stats').hidden=!$('stats').hidden;$('details').hidden=true;$('table-toggle').setAttribute('aria-expanded',String(!$('stats').hidden));};$('close-table').onclick=()=>{$('stats').hidden=true;$('table-toggle').setAttribute('aria-expanded','false');};
  for(const s of ['A','B'])$('view-'+s.toLowerCase()).onclick=()=>{state.active=s;state.page=0;state.selected=null;detailEpoch++;$('details').hidden=true;highlight.clearLayers();render();if($('search-scope').value==='source'&&state.query)runSourceSearch(0,false);status.textContent=scopeLabel();};
  $('diff').onchange=render;$('prev').onclick=()=>{state.page--;if($('search-scope').value==='source')runSourceSearch(state.page*30,false);else renderCatalog();};$('next').onclick=()=>{state.page++;if($('search-scope').value==='source')runSourceSearch(state.page*30,false);else renderCatalog();};
  async function runSourceSearch(offset=0,select=true){const turn=++searchEpoch;status.textContent='Đang tra cứu toàn bộ nhà nguồn…';try{await ready;const result=await rpc('sourceSearch',{query:state.query,args:current().args,offset});if(turn!==searchEpoch)return;state.sourceResults=result;state.page=Math.floor(offset/30);renderCatalog();if(select&&result.features.length)selectHouse(enrichSource(result.features[0]),state.active,true);status.textContent='Tìm thấy '+fmt(result.total,0)+' nhà nguồn trong phạm vi vùng đang chọn.';}catch(e){if(turn===searchEpoch)status.textContent=e.message;}}
  $('search-form').onsubmit=e=>{e.preventDefault();if(state.busy)return;state.query=$('search').value.trim();state.page=0;if(!state.query){status.textContent='Nhập FID hoặc mã nhận dạng nhà để tìm.';return;}if($('search-scope').value==='source'){runSourceSearch();return;}renderCatalog();const found=catalogMatches();if(found.length){selectHouse(found[0],state.active,true);status.textContent='Tìm thấy '+fmt(found.length,0)+' kết quả trong phạm vi đang lọc.';}else status.textContent='Không tìm thấy nhà trong phạm vi đang lọc.';};
  $('search').oninput=()=>{searchEpoch++;state.query=$('search').value.trim();state.page=0;state.sourceResults=null;renderCatalog();};
  $('search-scope').onchange=()=>{searchEpoch++;state.page=0;state.sourceResults=null;renderCatalog();};
  function download(name,rows){const safe=v=>{let s=String(v??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};const blob=new Blob(['\ufeff'+rows.map(r=>r.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  $('csv').onclick=()=>download('danh_muc_'+state.active+'.csv',[['source_fid','ma_nhan_dang','vung_ql','dt_nha_m2','dt_vp_m2','ty_le_pct'],...catalogMatches().map(f=>['source_fid','ma_nhan_dang','vung_ql','dt_nha_m2','dt_vp_m2','ty_le_pct'].map(k=>f.properties[k]))]);
  $('comparison-csv').onclick=()=>{if(!state.B)return;const a=new Map(state.A.stats.map(z=>[z.vung_ql,z])),b=new Map(state.B.stats.map(z=>[z.vung_ql,z])),rows=[['vung_ql','so_nha_A','so_nha_B','chenh_lech_so_nha','dt_A_m2','dt_B_m2','chenh_lech_m2']];for(const name of new Set([...a.keys(),...b.keys()])){const x=a.get(name)||{so_nha:0,dt_vp_m2:0},y=b.get(name)||{so_nha:0,dt_vp_m2:0};rows.push([name,x.so_nha,y.so_nha,y.so_nha-x.so_nha,x.dt_vp_m2,y.dt_vp_m2,y.dt_vp_m2-x.dt_vp_m2]);}rows.push(['Tổng duy nhất',state.A.count,state.B.count,state.B.count-state.A.count,state.A.area,state.B.area,state.B.area-state.A.area]);download('so_sanh_A_B.csv',rows);};
  render();toggleSidebar(false);
  if(D.source&&location.protocol!=='file:'){startWorker();status.textContent='Chọn nhà trên bản đồ hoặc trong danh mục để truy vết đường dây.';}
  else{for(const el of [$('apply'),$('zone'),$('voltage')])el.disabled=true;$('search-scope').options[1].disabled=true;status.textContent='Chế độ xem kết quả. Mở bằng MoBanDoWeb.bat để dùng phân tích nâng cao; xuất lại đủ ba lớp nếu chưa có dữ liệu nguồn.';}
  window.hlatMap=map;window.hlatLayers=layers;window.hlatRPC=rpc;
  window.hlatApp={getState:()=>state,current,ready:()=>ready,rpc,calculate,render,toggleSidebar,
    setMask:async mask=>{if(state.busy)throw new Error('Đợi phép tính hiện tại hoàn tất.');state.mask=mask;const ok=await calculate(false);window.dispatchEvent(new Event('hlat:render'));return ok;},
    showSource:(f,zoom=true)=>selectHouse(enrichSource(f),state.active,zoom),
    setDrawing:type=>{state.drawing=type;setBusy(state.busy);},
    restore:async session=>{const turn=++epoch;setBusy(true);try{await ready;
      const args=distances=>({distances,zone:session.zone,voltage:session.voltage,...(session.mask?{mask:session.mask}:{})});
      const A=await calculation(args(session.a)),B=session.b?await calculation(args(session.b)):null;if(turn!==epoch)return false;
      state.A=A;state.B=B;state.mask=session.mask;state.active=session.active==='B'&&B?'B':'A';state.query='';state.sourceResults=null;state.page=0;state.selected=null;detailEpoch++;$('details').hidden=true;highlight.clearLayers();
      $('zone').value=session.zone;$('voltage').value=session.voltage;$('search').value='';$('search-scope').value='violations';
      ['35','22','other'].forEach((k,i)=>{$('a'+k).value=session.a[i];$('b'+k).value=(session.b||baseDistances.map((d,j)=>d+(j===2?1:2)))[i];});
      $('scenario-state').textContent=session.b?'Đã khôi phục hai bộ khoảng cách từ phiên làm việc.':'Chưa tính phương án B.';render();return true;
    }catch(e){status.textContent='Không mở được phiên: '+e.message;return false;}finally{if(turn===epoch)setBusy(false);}}};
})();
