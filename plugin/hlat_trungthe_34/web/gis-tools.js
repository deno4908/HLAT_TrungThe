/* Công cụ GIS: vẽ, đo, vùng truy vấn, nhận diện nhà và lưu phiên cục bộ. */
'use strict';
(() => {
  const app=window.hlatApp,map=window.hlatMap,$=id=>document.getElementById(id);
  if(!app||!map)return;
  const available=Boolean(HLAT_DATA.source)&&location.protocol!=='file:',fmt=(n,d=2)=>Number(n).toLocaleString('vi-VN',{maximumFractionDigits:d});
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  map.createPane('gis').style.zIndex=470;
  const drawingLayer=L.featureGroup().addTo(map),measureLayer=L.featureGroup().addTo(map),maskLayer=L.geoJSON(null,{pane:'gis',interactive:false,style:{color:'#252525',weight:2,dashArray:'7,5',fillOpacity:.035}}).addTo(map);
  let mode=null,points=[],measurements=[],finishing=false,drawEpoch=0,pickEpoch=0,doubleZoom=true;
  const choices=node('div');choices.id='click-matches';$('detail-values').after(choices);
  const help=text=>$('gis-help').textContent=text;
  function sync(){const s=app.getState();maskLayer.clearLayers();if(s.mask)maskLayer.addData(s.mask);
    $('aoi-status').textContent=s.mask?'· Giới hạn trong vùng đã khoanh':'';
    $('clear-aoi').disabled=s.busy||Boolean(mode)||!s.mask;
    for(const b of document.querySelectorAll('[data-draw]')){b.disabled=!available||s.busy||finishing;b.setAttribute('aria-pressed',String(b.dataset.draw===mode));}
    for(const id of ['load-session','save-session'])$(id).disabled=s.busy||Boolean(mode);
    if(!available)$('load-session').disabled=true;
    $('draw-finish').disabled=finishing;$('draw-undo').disabled=finishing||!points.length;$('draw-cancel').disabled=finishing;
  }
  window.addEventListener('hlat:render',()=>{pickEpoch++;choices.replaceChildren();sync();});window.addEventListener('hlat:busy',sync);
  window.addEventListener('hlat:select',()=>choices.replaceChildren());
  $('gis-toggle').onclick=()=>{$('gis-toolbar').hidden=!$('gis-toolbar').hidden;$('gis-toggle').setAttribute('aria-expanded',String(!$('gis-toolbar').hidden));setTimeout(()=>map.invalidateSize(),0);};
  function redraw(){drawingLayer.clearLayers();if(points.length>1){const opts={pane:'gis',interactive:false,color:'#333',weight:2,dashArray:'5,4',fillOpacity:.06};drawingLayer.addLayer(mode==='distance'?L.polyline(points,opts):L.polygon(points,opts));}
    for(const p of points)drawingLayer.addLayer(L.circleMarker(p,{pane:'gis',interactive:false,radius:4,color:'#222',weight:1,fillColor:'white',fillOpacity:1}));
    help((mode==='distance'?'Đo khoảng cách':mode==='area'?'Đo diện tích':'Khoanh vùng truy vấn')+' · '+points.length+' điểm. Nhấp thêm điểm, bấm Kết thúc vẽ; Esc để hủy.');sync();}
  function stop(){drawEpoch++;mode=null;points=[];drawingLayer.clearLayers();map.getContainer().classList.remove('drawing');if(doubleZoom)map.doubleClickZoom.enable();app.setDrawing(null);for(const id of ['draw-undo','draw-finish','draw-cancel'])$(id).hidden=true;sync();}
  function begin(type){if(app.getState().busy||finishing||!available)return;stop();doubleZoom=map.doubleClickZoom.enabled();map.doubleClickZoom.disable();mode=type;app.setDrawing(type);map.getContainer().classList.add('drawing');$('details').hidden=true;$('stats').hidden=true;app.toggleSidebar(false);for(const id of ['draw-undo','draw-finish','draw-cancel'])$(id).hidden=false;redraw();}
  for(const b of document.querySelectorAll('[data-draw]'))b.onclick=()=>begin(b.dataset.draw);
  map.on('click',async e=>{if(mode){if(finishing)return;const p=[e.latlng.lat,e.latlng.lng],last=points.at(-1);if(!last||Math.abs(last[0]-p[0])+Math.abs(last[1]-p[1])>1e-10)points.push(p);redraw();return;}
    if(!available||app.getState().busy||map.getZoom()<16)return;
    const turn=++pickEpoch;$('status').textContent='Đang nhận diện nhà tại vị trí nhấp…';try{await app.ready();const center=map.latLngToContainerPoint(e.latlng),near=map.containerPointToLatLng(center.add([6,0])),tolerance=Math.min(15,e.latlng.distanceTo(near));
      const result=await app.rpc('identify',{coordinates:[e.latlng.lng,e.latlng.lat],tolerance,args:app.current().args});if(turn!==pickEpoch)return;
      if(!result.features.length){$('status').textContent='Không có nhà nguồn tại vị trí này trong phạm vi đang lọc.';return;}
      app.showSource(result.features[0],false);choices.replaceChildren();
      if(result.features.length>1){choices.append(node('p','Có nhiều nhà gần vị trí nhấp; chọn FID để xem:'));for(const f of result.features){const b=node('button','FID '+f.properties.source_fid);b.onclick=()=>app.showSource(f,false);choices.append(b);}}
      $('status').textContent='Đã nhận diện nhà FID '+result.features[0].properties.source_fid+(result.features[0].click_distance_m>1e-6?' · Gần vị trí nhấp '+fmt(result.features[0].click_distance_m)+' m':'');
    }catch(error){if(turn===pickEpoch)$('status').textContent=error.message;}
  });
  function addMeasurement(record){measurements.push(record);const polygon=record.geometry.type==='Polygon',label=polygon?fmt(record.properties.area_m2)+' m² · Chu vi '+fmt(record.properties.length_m)+' m':fmt(record.properties.length_m)+' m';
    const layer=L.geoJSON(record,{pane:'gis',interactive:false,style:{color:'#473a91',weight:2,fillOpacity:.08}});layer.bindTooltip(label,{permanent:true,direction:'top',className:'measurement-label'});measureLayer.addLayer(layer);
  }
  async function finish(){if(!mode||finishing)return;const min=mode==='distance'?2:3;if(points.length<min){help('Cần ít nhất '+min+' điểm để hoàn tất.');return;}
    const turn=drawEpoch,kind=mode,coords=points.map(p=>[p[1],p[0]]),geometry=kind==='distance'?{type:'LineString',coordinates:coords}:{type:'Polygon',coordinates:[[...coords,coords[0]]]};
    finishing=true;sync();try{await app.ready();const measured=await app.rpc('measure',{geometry});if(turn!==drawEpoch)return;
      if(kind==='aoi'){const ok=await app.setMask(geometry);if(!ok){help('Chưa áp dụng vùng mới. Có thể sửa hình vẽ hoặc hủy.');return;}}
      else addMeasurement({type:'Feature',geometry,properties:{kind:kind==='distance'?'distance':'area',...measured}});
      stop();help(kind==='aoi'?'Đã khoanh vùng: bản đồ, danh mục, thống kê và A/B chỉ tính phần giao trong vùng.':(kind==='area'?'Diện tích '+fmt(measured.area_m2)+' m² · Chu vi ':'Khoảng cách ')+fmt(measured.length_m)+' m · '+measured.crs);$('status').textContent=$('gis-help').textContent;
    }catch(error){help(error.message);}finally{finishing=false;sync();}
  }
  $('draw-finish').onclick=finish;$('draw-undo').onclick=()=>{if(!finishing){points.pop();redraw();}};$('draw-cancel').onclick=()=>{stop();help('Đã hủy hình đang vẽ.');};
  document.addEventListener('keydown',e=>{if(!mode)return;if(e.key==='Escape'&&!finishing){e.preventDefault();stop();help('Đã hủy hình đang vẽ.');return;}if(e.target.closest('input,select,textarea,button'))return;if(e.key==='Enter'){e.preventDefault();finish();}else if(e.key==='Backspace'&&!finishing){e.preventDefault();points.pop();redraw();}});
  $('clear-aoi').onclick=async()=>{try{if(await app.setMask(null))help('Đã bỏ vùng khoanh; giữ bộ lọc điện áp, vùng quản lý và khoảng cách.');}catch(error){help(error.message);}};
  $('clear-measures').onclick=()=>{measurements=[];measureLayer.clearLayers();help('Đã xóa các phép đo.');};
  let locationMarker;
  $('coordinate-form').onsubmit=e=>{e.preventDefault();const lat=Number($('latitude').value),lng=Number($('longitude').value);if(!Number.isFinite(lat)||!Number.isFinite(lng)||Math.abs(lat)>90||Math.abs(lng)>180)return;
    if(locationMarker)map.removeLayer(locationMarker);locationMarker=L.circleMarker([lat,lng],{radius:7,color:'#222',fillColor:'#fff',fillOpacity:1}).addTo(map);locationMarker.bindTooltip(lat.toFixed(6)+', '+lng.toFixed(6));map.setView([lat,lng],18);help('Đang xem tọa độ WGS84: '+lat+', '+lng);$('status').textContent=$('gis-help').textContent;};
  function saveJSON(name,data,type='application/json'){const blob=new Blob([JSON.stringify(data,null,2)],{type}),url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function drawingFeatures(){return [...measurements,...(app.getState().mask?[{type:'Feature',geometry:app.getState().mask,properties:{kind:'query_area'}}]:[])];}
  $('export-geojson').onclick=()=>{const kind=$('export-kind').value,r=app.current(),features=kind==='drawings'?drawingFeatures():r[kind].features;
    saveJSON('hlat_'+kind+'.geojson',{type:'FeatureCollection',name:'HLAT '+kind,analysis:{...r.args,display_crs:'EPSG:4326',area_unit:'m2',length_unit:'m'},features},'application/geo+json');help('Đã xuất '+fmt(features.length,0)+' đối tượng GeoJSON WGS84 theo bộ lọc đang áp dụng.');};
  const fingerprint=()=>HLAT_DATA.source?.fingerprint||HLAT_DATA.created_at+'|'+HLAT_DATA.metrics.input_houses+'|'+HLAT_DATA.metrics.input_lines;
  $('save-session').onclick=()=>{const s=app.getState(),center=map.getCenter();saveJSON('hlat_phien_lam_viec.json',{format:'hlat34-session',version:1,dataset:fingerprint(),a:s.A.args.distances,b:s.B?.args.distances||null,active:s.active,zone:s.A.args.zone,voltage:s.A.args.voltage,mask:s.mask,measurements,view:{lat:center.lat,lng:center.lng,zoom:map.getZoom()}});help('Đã lưu tham số đã tính, vùng khoanh, phép đo và khung nhìn vào tệp JSON.');};
  function validateSession(s){if(s?.format!=='hlat34-session'||s.version!==1||s.dataset!==fingerprint())throw new Error('Phiên không đúng định dạng hoặc thuộc bộ dữ liệu khác.');
    for(const ds of [s.a,...(s.b?[s.b]:[])])if(!Array.isArray(ds)||ds.length!==3||ds.some(v=>!Number.isFinite(v)||v<.001||v>10000))throw new Error('Khoảng cách trong phiên không hợp lệ.');
    if(![...$('zone').options].some(o=>o.value===s.zone)||![...$('voltage').options].some(o=>o.value===s.voltage))throw new Error('Vùng hoặc điện áp trong phiên không tồn tại.');
    if(!['A','B'].includes(s.active)||!Array.isArray(s.measurements)||s.measurements.length>100)throw new Error('Danh sách phép đo không hợp lệ.');
    const v=s.view;if(!v||![v.lat,v.lng,v.zoom].every(Number.isFinite)||Math.abs(v.lat)>90||Math.abs(v.lng)>180||v.zoom<0||v.zoom>20)throw new Error('Khung nhìn không hợp lệ.');
    let count=0;function coordinates(c){if(!Array.isArray(c))throw new Error('Hình học không hợp lệ.');if(typeof c[0]==='number'){if(c.length<2||!Number.isFinite(c[1])||Math.abs(c[0])>180||Math.abs(c[1])>90||++count>10000)throw new Error('Tọa độ hình vẽ không hợp lệ hoặc quá lớn.');}else c.forEach(coordinates);}
    for(const g of [...s.measurements.map(f=>f.geometry),...(s.mask?[s.mask]:[])]){if(!g||!['LineString','Polygon'].includes(g.type))throw new Error('Hình vẽ không được hỗ trợ.');coordinates(g.coordinates);}return s;
  }
  $('load-session').onclick=()=>$('session-file').click();
  $('session-file').onchange=async()=>{const file=$('session-file').files[0];$('session-file').value='';if(!file||app.getState().busy||mode)return;
    try{if(file.size>2*1024*1024)throw new Error('Tệp phiên vượt quá 2 MB.');const s=validateSession(JSON.parse(await file.text()));await app.ready();const restored=[];
      for(const f of s.measurements){const measured=await app.rpc('measure',{geometry:f.geometry});restored.push({type:'Feature',geometry:f.geometry,properties:{kind:f.geometry.type==='Polygon'?'area':'distance',...measured}});}
      if(!await app.restore(s))return;measurements=[];measureLayer.clearLayers();restored.forEach(addMeasurement);map.setView([s.view.lat,s.view.lng],s.view.zoom);help('Đã mở phiên làm việc và tính lại số liệu theo tham số lưu.');$('status').textContent=$('gis-help').textContent;
    }catch(error){help('Không mở được phiên: '+error.message);}
  };
  sync();window.hlatGIS={begin,finish,stop,getMeasurements:()=>measurements,getDrawPoints:()=>points};
})();
