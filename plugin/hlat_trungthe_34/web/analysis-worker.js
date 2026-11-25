/* GEOS 3.13 trong Web Worker; tất cả phép đo ở CRS mét của lần chạy QGIS. */
import initGeos from './vendor/geos.js';
import {geojsonToGeosGeom, geosGeomToGeojson} from './vendor/geos-helpers.js';
import './vendor/proj4.js';

let G, manifest, chunks, lines, zones, projection, reader, scalar, sourceIndex, sourceGrid;
const cache = new Map(), EPS=1e-8;
const progress=(text)=>postMessage({type:'progress',text});
const destroy=p=>{if(p)G.GEOSGeom_destroy(p);};
const must=p=>{if(!p)throw new Error('GEOS không tạo được hình học.');return p;};
function area(p){if(G.GEOSArea(p,scalar)!==1)throw new Error('Không đo được diện tích.');return G.Module.getValue(scalar,'double');}
function bounds(p){const a=[];for(const f of ['GEOSGeom_getXMin','GEOSGeom_getYMin','GEOSGeom_getXMax','GEOSGeom_getYMax']){G[f](p,scalar);a.push(G.Module.getValue(scalar,'double'));}return a;}
const overlaps=(a,b)=>a[0]<=b[2]&&a[2]>=b[0]&&a[1]<=b[3]&&a[3]>=b[1];
function union(pointers){const collection=geojsonToGeosGeom({type:'GeometryCollection',geometries:[]},G);destroy(collection);
  if(!pointers.length)return must(G.GEOSGeom_createEmptyCollection(7));
  const p=G.Module._malloc(pointers.length*4);G.Module.HEAPU32.set(pointers.map(g=>G.GEOSGeom_clone(g)),p/4);
  const c=must(G.GEOSGeom_createCollection(7,p,pointers.length));G.Module._free(p);
  try{return must(G.GEOSUnaryUnion(c));}finally{destroy(c);}
}
function valid(g){if(G.GEOSisValid(g)===1)return g;const repaired=must(G.GEOSMakeValid(g));destroy(g);return repaired;}
function houseGeom(row,bytes){const raw=bytes.subarray(row[8],row[8]+row[9]),p=G.Module._malloc(raw.length);
  G.Module.HEAPU8.set(raw,p);let g;try{g=must(G.GEOSWKBReader_read(reader,p,raw.length));}finally{G.Module._free(p);}return valid(g);}
function webGeometry(p){const g=geosGeomToGeojson(p,G);
  function convert(c){if(typeof c[0]==='number')return projection.forward(c).slice(0,2);return c.map(convert);}
  function walk(v){if(v.coordinates)v.coordinates=convert(v.coordinates);if(v.geometries)v.geometries.forEach(walk);return v;}
  return walk(g);
}
function metricGeometry(geometry){
  function convert(c){if(typeof c[0]==='number'){if(!Number.isFinite(c[0])||!Number.isFinite(c[1])||Math.abs(c[0])>180||Math.abs(c[1])>90)throw new Error('Tọa độ WGS84 không hợp lệ.');const xy=projection.inverse(c);if(xy.some(n=>!Number.isFinite(n)))throw new Error('Không chuyển được tọa độ.');return xy.slice(0,2);}return c.map(convert);}
  const g={type:geometry.type,coordinates:convert(geometry.coordinates)};
  return must(geojsonToGeosGeom(g,G));
}
function aoiGeometry(geometry){if(!['Polygon','MultiPolygon'].includes(geometry?.type))throw new Error('Vùng chọn phải là đa giác.');const g=metricGeometry(geometry);if(G.GEOSisValid(g)!==1||area(g)<=EPS){destroy(g);throw new Error('Đa giác tự cắt hoặc không có diện tích. Hãy vẽ lại.');}return g;}
const feature=(geometry,properties)=>({type:'Feature',geometry,properties});
const fc=features=>({type:'FeatureCollection',features});
function gridIndex(items){const grid=new Map(),size=1000;
  function cells(bb,cb){for(let x=Math.floor(bb[0]/size);x<=Math.floor(bb[2]/size);x++)for(let y=Math.floor(bb[1]/size);y<=Math.floor(bb[3]/size);y++)cb(x+':'+y);}
  items.forEach((item,i)=>cells(item.bb,key=>{if(!grid.has(key))grid.set(key,[]);grid.get(key).push(i);}));
  return bb=>{const found=new Set();cells(bb,key=>{for(const i of grid.get(key)||[])if(overlaps(bb,items[i].bb))found.add(i);});return [...found].map(i=>items[i]);};
}
function validate(args){if(!Array.isArray(args.distances)||args.distances.length!==3||args.distances.some(v=>!Number.isFinite(v)||v<.001||v>10000))throw new Error('Khoảng cách phải từ 0,001 đến 10.000 m.');
  if(args.zone&&!zones.some(z=>z.name===args.zone))throw new Error('Vùng quản lý không tồn tại.');
  if(args.voltage&&!lines.some(l=>String(l.voltage)===String(args.voltage)))throw new Error('Cấp điện áp không tồn tại.');
}
const width=(line,ds)=>ds[Math.abs(line.voltage-35)<EPS?0:Math.abs(line.voltage-22)<EPS?1:2];
const activeLines=args=>lines.filter(l=>!args.voltage||String(l.voltage)===String(args.voltage));
async function init(url){G=await initGeos();reader=G.GEOSWKBReader_create();scalar=G.Module._malloc(8);
  manifest=await (await fetch(url)).json();projection=globalThis.proj4(manifest.proj4,'EPSG:4326');
  lines=manifest.lines.map(l=>({...l,g:valid(must(geojsonToGeosGeom(l.geometry,G)))}));
  const names=[...new Set(manifest.zones.map(z=>z.name))];
  zones=names.map(name=>{const parts=manifest.zones.filter(z=>z.name===name).map(z=>valid(must(geojsonToGeosGeom(z.geometry,G))));const g=union(parts);parts.forEach(destroy);return {name,g,prepared:G.GEOSPrepare(g)};});
  chunks=[];let count=0;
  for(const chunk of manifest.chunks){const [rows,bytes]=await Promise.all([(await fetch(chunk.metadata)).json(),(await fetch(chunk.wkb)).arrayBuffer()]);chunks.push({rows,bytes:new Uint8Array(bytes)});count+=rows.length;progress('Đang nạp dữ liệu phân tích: '+count.toLocaleString('vi-VN')+' / '+manifest.house_count.toLocaleString('vi-VN')+' nhà');}
  if(count!==manifest.house_count)throw new Error('Bộ dữ liệu đầu vào chưa đầy đủ.');
  sourceIndex=new Map();for(const c of chunks)for(const row of c.rows)sourceIndex.set(row[0],{row,bytes:c.bytes,bb:row.slice(4,8)});
  sourceGrid=gridIndex([...sourceIndex.values()]);
  return {house_count:count,line_count:lines.length,crs:manifest.crs};
}
function analyze(args){validate(args);const key=JSON.stringify(args);if(cache.has(key))return cache.get(key);
  const scope=args.zone?zones.filter(z=>z.name===args.zone):zones;
  const selected=activeLines(args), buffers=[], records=[], pieces=[], lineFeatures=[];
  let corridor=0,prepared=0,mask=0;
  try{
    progress('Tạo và hợp nhất hành lang theo cấp điện áp…');
    for(const l of selected){const g=must(G.GEOSBuffer(l.g,width(l,args.distances),8));buffers.push({g,bb:bounds(g),line:l});}
    corridor=union(buffers.map(b=>b.g));
    if(args.zone){const clipped=must(G.GEOSIntersection(corridor,scope[0].g));destroy(corridor);corridor=clipped;}
    if(args.mask){mask=aoiGeometry(args.mask);const clipped=must(G.GEOSIntersection(corridor,mask));destroy(corridor);corridor=clipped;}
    prepared=G.GEOSPrepare(corridor);const query=gridIndex(buffers), cb=bounds(corridor), stats=new Map(scope.map(z=>[z.name,{vung_ql:z.name,so_nha:0,dt_vp_m2:0}]));
    let scanned=0;
    for(const chunk of chunks){for(const row of chunk.rows){scanned++;const bb=row.slice(4,8);if(!overlaps(cb,bb)||!query(bb).length)continue;
      const house=houseGeom(row,chunk.bytes);let cut=0;
      try{if(G.GEOSPreparedIntersects(prepared,house)!==1)continue;cut=must(G.GEOSIntersection(house,corridor));const a=area(cut);if(a<=EPS)continue;
        const ha=area(house),names=[],assigned=[];
        try{for(const z of scope){if(G.GEOSPreparedIntersects(z.prepared,cut)!==1)continue;const piece=must(G.GEOSIntersection(cut,z.g));
          const pa=area(piece);if(pa<=EPS){destroy(piece);continue;}assigned.push(piece);names.push(z.name);
          const stat=stats.get(z.name);stat.so_nha++;stat.dt_vp_m2+=pa;
          pieces.push(feature(webGeometry(piece),{source_fid:row[0],vung_ql:z.name,dt_vp_m2:pa}));}
          if(!args.zone){const allocated=union(assigned),remainder=must(G.GEOSDifference(cut,allocated));destroy(allocated);const pa=area(remainder);
            if(pa>EPS){const name='Chưa phân vùng';if(!stats.has(name))stats.set(name,{vung_ql:name,so_nha:0,dt_vp_m2:0});const stat=stats.get(name);stat.so_nha++;stat.dt_vp_m2+=pa;names.push(name);pieces.push(feature(webGeometry(remainder),{source_fid:row[0],vung_ql:name,dt_vp_m2:pa}));}destroy(remainder);}
        }finally{assigned.forEach(destroy);}
        records.push(feature(webGeometry(house),{source_fid:row[0],ma_nhan_dang:row[1],phan_loai:row[2],ten:row[3],dt_nha_m2:ha,dt_vp_m2:a,ty_le_pct:100*a/ha,vung_ql:names.join('; ')}));
      }finally{destroy(cut);destroy(house);}
    }progress('Đã xét '+scanned.toLocaleString('vi-VN')+' nhà · '+records.length.toLocaleString('vi-VN')+' nhà trong hành lang');}
    for(const l of selected){let g=G.GEOSGeom_clone(l.g);try{for(const region of [args.zone?scope[0].g:0,mask])if(region){const clipped=must(G.GEOSIntersection(g,region));destroy(g);g=clipped;}if(G.GEOSisEmpty(g)===0)lineFeatures.push(feature(webGeometry(g),{fid:l.id,capDienAp:l.voltage+' kV',soHieu:l.name}));}finally{destroy(g);}}
    const total=records.reduce((s,f)=>s+f.properties.dt_vp_m2,0), sum=[...stats.values()].reduce((s,z)=>s+z.dt_vp_m2,0);
    if(Math.abs(total-sum)>.01)throw new Error('Diện tích chi tiết và thống kê vùng không khớp.');
    const result={args, houses:fc(records), pieces:fc(pieces), corridor:fc([feature(webGeometry(corridor),{})]), lines:fc(lineFeatures),
      zones:fc(scope.map(z=>feature(webGeometry(z.g),stats.get(z.name)))),stats:[...stats.values()],count:records.length,area:total};
    cache.set(key,result);if(cache.size>4)cache.delete(cache.keys().next().value);return result;
  }finally{if(prepared)G.GEOSPreparedGeom_destroy(prepared);destroy(corridor);destroy(mask);buffers.forEach(b=>destroy(b.g));}
}
function related(args,fid){validate(args);const source=sourceIndex.get(fid),row=source?.row;if(!row)throw new Error('Không tìm được nhà nguồn FID '+fid);
  const h=houseGeom(row,source.bytes),list=[],bb=row.slice(4,8),scope=args.zone?zones.find(z=>z.name===args.zone):null,mask=args.mask?aoiGeometry(args.mask):0;
  try{for(const l of activeLines(args)){const d=width(l,args.distances),lb=bounds(l.g);if(!overlaps(bb,[lb[0]-d,lb[1]-d,lb[2]+d,lb[3]+d]))continue;
    const b=must(G.GEOSBuffer(l.g,d,8));let cut=0,clipped=0;
    try{cut=must(G.GEOSIntersection(h,b));for(const region of [scope?.g,mask])if(region){const next=must(G.GEOSIntersection(clipped||cut,region));destroy(clipped);clipped=next;}const a=area(clipped||cut);if(a<=EPS)continue;
      if(G.GEOSDistance(h,l.g,scalar)!==1)throw new Error('Không đo được khoảng cách nhà–đường dây.');
      list.push({id:l.id,voltage:l.voltage,name:l.name,distance:G.Module.getValue(scalar,'double'),width:d,area:a,geometry:webGeometry(l.g)});
    }finally{destroy(b);destroy(cut);destroy(clipped);}}
  }finally{destroy(h);destroy(mask);}return list.sort((a,b)=>a.distance-b.distance||a.id-b.id);
}
function measure(geometry){if(!['LineString','Polygon'].includes(geometry?.type))throw new Error('Chọn đường hoặc đa giác để đo.');const g=metricGeometry(geometry);try{
  if(G.GEOSisValid(g)!==1)throw new Error('Hình vẽ tự cắt hoặc không hợp lệ.');
  if(G.GEOSLength(g,scalar)!==1)throw new Error('Không đo được chiều dài.');
  return {length_m:G.Module.getValue(scalar,'double'),area_m2:geometry.type==='Polygon'?area(g):0,crs:manifest.crs};
}finally{destroy(g);}}
function sourceSearch(query,args,offset=0){validate(args);const q=String(query).trim().toLowerCase();if(!q)throw new Error('Nhập FID hoặc mã nhận dạng.');
  const exact=/^\d+$/.test(q)?sourceIndex.get(Number(q)):null;
  const sources=exact?[exact]:[...sourceIndex.values()].filter(s=>s.row[1].toLowerCase().includes(q));
  const matched=[],mask=args.mask?aoiGeometry(args.mask):0,zone=args.zone?zones.find(z=>z.name===args.zone):null;
  try{for(const s of sources){if(!mask&&!zone){matched.push(s);continue;}const g=houseGeom(s.row,s.bytes);try{
    if(mask&&G.GEOSIntersects(g,mask)!==1)continue;if(zone&&G.GEOSIntersects(g,zone.g)!==1)continue;
    matched.push(s);
  }finally{destroy(g);}}
  return {total:matched.length,features:matched.slice(offset,offset+30).map(s=>sourceFeature(s))};
  }finally{destroy(mask);}
}
function sourceFeature(s){const g=houseGeom(s.row,s.bytes);try{
  const names=[];for(const z of zones){if(G.GEOSPreparedIntersects(z.prepared,g)!==1)continue;const cut=must(G.GEOSIntersection(z.g,g));try{if(area(cut)>EPS)names.push(z.name);}finally{destroy(cut);}}
  return feature(webGeometry(g),{source_fid:s.row[0],ma_nhan_dang:s.row[1],phan_loai:s.row[2],ten:s.row[3],dt_nha_m2:area(g),vung_ql:names.join('; ')||'Chưa phân vùng'});
}finally{destroy(g);}}
function identify(coordinates,tolerance,args){validate(args);const point=metricGeometry({type:'Point',coordinates}),xy=projection.inverse(coordinates),d=Math.min(30,Math.max(0,Number(tolerance)||0)),mask=args.mask?aoiGeometry(args.mask):0,scope=args.zone?zones.find(z=>z.name===args.zone):null;
  try{for(const region of [mask,scope?.g])if(region&&G.GEOSIntersects(region,point)!==1)return {total:0,features:[]};
    const candidates=sourceGrid([xy[0]-d,xy[1]-d,xy[0]+d,xy[1]+d]),found=[];
    for(const s of candidates){const g=houseGeom(s.row,s.bytes);try{G.GEOSDistance(g,point,scalar);const distance=G.Module.getValue(scalar,'double');if(distance<=d+EPS)found.push({s,distance});}finally{destroy(g);}}
    found.sort((a,b)=>a.distance-b.distance||a.s.row[0]-b.s.row[0]);return {total:found.length,features:found.slice(0,8).map(({s,distance})=>({...sourceFeature(s),click_distance_m:distance}))};
  }finally{destroy(point);destroy(mask);}
}
onmessage=async({data:m})=>{try{const result=m.type==='init'?await init(m.url):m.type==='analyze'?analyze(m.args):m.type==='related'?related(m.args,m.fid):m.type==='measure'?measure(m.geometry):m.type==='sourceSearch'?sourceSearch(m.query,m.args,m.offset||0):m.type==='identify'?identify(m.coordinates,m.tolerance,m.args):null;postMessage({id:m.id,result});}catch(e){postMessage({id:m.id,error:e.message||String(e)});}};
