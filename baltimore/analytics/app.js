'use strict';
const $ = id => document.getElementById(id);
const fmt = n => n.toLocaleString();
const colors = ['#27c9b0', '#ffb454', '#789df8', '#e184bd', '#79cbe5', '#c2d66a', '#ff7455', '#718897'];
const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const state = { org: '', day: null, cell: '', page: 0 };
let all = [], filtered = [], map, cellsLayer, currentCells = [], mapError = false;
const SIZE = 25;
const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const countBy = (rows, getter) => {
  const counts = new Map();
  rows.forEach(e => { const key = getter(e); counts.set(key, (counts.get(key) || 0) + 1); });
  return [...counts].sort((a,b) => b[1]-a[1] || String(a[0]).localeCompare(String(b[0])));
};
function gridCell(e) {
  if (!e.coordinates) return '';
  const km = Number($('grid').value), dy = km/111.32, dx = km/(111.32*Math.cos(39.29*Math.PI/180));
  const [lat, lon] = e.coordinates;
  return `${Math.floor(lat/dy)},${Math.floor(lon/dx)}`;
}
function gridBounds(key) {
  const [y,x] = key.split(',').map(Number), km = Number($('grid').value);
  const dy = km/111.32, dx = km/(111.32*Math.cos(39.29*Math.PI/180));
  return [[y*dy,x*dx],[(y+1)*dy,(x+1)*dx]];
}
function update() {
  const query = $('search').value.trim().toLowerCase(), from = $('from').value, to = $('to').value;
  const category = $('category').value, city = $('city').value;
  filtered = all.filter(e => (!query || `${e.name} ${e.venue} ${e.org} ${e.city} ${e.tags.join(' ')}`.toLowerCase().includes(query))
    && (!from || e.date && e.date >= from) && (!to || e.date && e.date <= to)
    && (!category || e.category === category) && (!city || e.city === city)
    && (!state.org || e.org === state.org) && (state.day === null || e.weekday === state.day)
    && (!state.cell || gridCell(e) === state.cell));
  state.page = 0;
  $('count').textContent = fmt(filtered.length);
  $('organizers').textContent = fmt(new Set(filtered.filter(e => e.org !== 'Unknown').map(e => e.org)).size);
  const mapped = filtered.filter(e => e.coordinates).length;
  $('mapped').textContent = fmt(mapped);
  $('coverage').textContent = `${filtered.length ? Math.round(mapped/filtered.length*100) : 0}% of events`;
  const months = countBy(filtered.filter(e=>e.date), e=>e.date.slice(0,7));
  $('peak').textContent = months.length ? monthLabel(months[0][0]) : '—';
  $('peak-count').textContent = months.length ? `${fmt(months[0][1])} events` : '';
  $('status').textContent = from && to && from > to ? 'From must precede To.' : filtered.length ? '' : 'No matching events.';
  renderChips(); renderMap();
  renderPie('category-chart', countBy(filtered,e=>e.category), 'category');
  renderPie('org-chart', countBy(filtered,e=>e.org), 'org');
  renderPie('day-chart', days.map((d,i)=>[d,filtered.filter(e=>e.weekday===i).length]).filter(e=>e[1]), 'day', false);
  renderTimeline(months); renderTable();
}
function monthLabel(month) {
  return new Date(`${month}-01T12:00:00Z`).toLocaleDateString('en-US',{month:'short',year:'numeric',timeZone:'UTC'});
}
function renderChips() {
  $('chips').replaceChildren();
  for (const [label, clear] of [
    state.org ? [state.org,()=>state.org=''] : [],
    state.day !== null ? [days[state.day],()=>state.day=null] : [],
    state.cell ? ['Map area',()=>state.cell=''] : []
  ]) {
    if (!label) continue;
    const b = document.createElement('button'); b.textContent = `${label} ×`; b.setAttribute('aria-label', `Clear ${label} filter`);
    b.onclick = () => { clear(); update(); }; $('chips').append(b);
  }
}
function applySlice(type, names) {
  if (names.length !== 1) return;
  const name = names[0];
  if (type === 'category') $('category').value = $('category').value === name ? '' : name;
  if (type === 'org') state.org = state.org === name ? '' : name;
  if (type === 'day') state.day = state.day === days.indexOf(name) ? null : days.indexOf(name);
  update();
}
function renderPie(id, groups, type, collapse=true) {
  const target = $(id); target.replaceChildren();
  if (!groups.length) { target.innerHTML = '<div class="empty">No data</div>'; return; }
  let slices = groups.map(([name,n])=>({name,n,names:[name]}));
  if (collapse && slices.length > 7) slices = [...slices.slice(0,6), {name:'Other', n:slices.slice(6).reduce((s,e)=>s+e.n,0), names:slices.slice(6).map(e=>e.name)}];
  const total = slices.reduce((s,e)=>s+e.n,0), ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns,'svg'); svg.setAttribute('viewBox','0 0 200 200'); svg.classList.add('pie');
  svg.setAttribute('role','group'); svg.setAttribute('aria-label',`${type} pie chart`);
  const legend = document.createElement('div'); legend.className = 'legend';
  let angle = -Math.PI/2;
  slices.forEach((slice,i)=>{
    const end = angle + slice.n/total*Math.PI*2;
    const x1=100+88*Math.cos(angle), y1=100+88*Math.sin(angle), x2=100+88*Math.cos(end), y2=100+88*Math.sin(end);
    const path = document.createElementNS(ns,'path');
    path.setAttribute('d',slice.n===total ? 'M100 12 A88 88 0 1 1 100 188 A88 88 0 1 1 100 12 Z' : `M100 100 L${x1} ${y1} A88 88 0 ${end-angle>Math.PI?1:0} 1 ${x2} ${y2} Z`);
    path.setAttribute('fill',colors[i]); path.setAttribute('stroke','#102735'); path.setAttribute('stroke-width','2');
    const label = `${slice.name}: ${fmt(slice.n)} (${(slice.n/total*100).toFixed(1)}%)`;
    const title=document.createElementNS(ns,'title'); title.textContent=label; path.append(title);
    if (slice.names.length===1) {
      path.setAttribute('tabindex','0'); path.setAttribute('role','button'); path.setAttribute('aria-label',`Filter ${label}`);
      path.onclick=()=>applySlice(type,slice.names);
      path.onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();applySlice(type,slice.names);}};
    }
    svg.append(path);
    const b=document.createElement('button'); b.title=label; b.setAttribute('aria-label',label);
    b.innerHTML=`<i style="background:${colors[i]}"></i><span class="label">${safe(slice.name)}</span><span class="value">${(slice.n/total*100).toFixed(1)}%</span>`;
    if(slice.names.length>1) { b.disabled=true; b.title=`${label}\n${slice.names.join(', ')}`; }
    else b.onclick=()=>applySlice(type,slice.names);
    legend.append(b); angle=end;
  });
  target.append(svg,legend);
}
function selectCell(key) {
  state.cell=state.cell===key?'':key;
  if(state.cell && map) map.fitBounds(gridBounds(key),{maxZoom:14});
  update();
}
function renderMap() {
  const groups = new Map();
  filtered.forEach(e=>{const key=gridCell(e);if(!key)return;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(e);});
  currentCells=[...groups].sort((a,b)=>b[1].length-a[1].length);
  if(cellsLayer)cellsLayer.clearLayers();
  const max=currentCells[0]?.[1].length||1;
  currentCells.forEach(([key,rows])=>{
    if(!map)return;
    const strength=Math.sqrt(rows.length/max), color=strength>.7?'#ff7455':strength>.35?'#ffb454':'#27c9b0';
    const area=countBy(rows,e=>e.venue!=='Unknown'?e.venue:e.city)[0][0];
    const cell=L.rectangle(gridBounds(key),{color,weight:1,fillColor:color,fillOpacity:.2+strength*.5}).addTo(cellsLayer);
    const tooltip=document.createElement('div'); tooltip.textContent=`${area} · ${fmt(rows.length)} events`;
    cell.bindTooltip(tooltip,{sticky:true}).on('click',()=>selectCell(key));
  });
  $('map-count').textContent=`${fmt(filtered.filter(e=>e.coordinates).length)} mapped · ${fmt(groups.size)} cells`;
  $('hotspots').replaceChildren();
  currentCells.slice(0,7).forEach(([key,rows],index)=>{
    const names=countBy(rows,e=>e.venue!=='Unknown'?e.venue:e.city), area=names[0][0];
    const b=document.createElement('button');b.className='hotspot';b.title=area;
    b.innerHTML=`<span class="rank">${String(index+1).padStart(2,'0')}</span><span><strong>${safe(area)}</strong><small>${safe(countBy(rows,e=>e.city)[0][0])} · ${$('grid').value} km cell</small></span><span>${fmt(rows.length)}</span>`;
    b.onclick=()=>selectCell(key);$('hotspots').append(b);
  });
  if(!currentCells.length)$('hotspots').innerHTML='<div class="empty">No mapped events</div>';
}
function renderTimeline(monthCounts) {
  const target=$('timeline');target.replaceChildren();
  if(!monthCounts.length){target.innerHTML='<div class="empty">No dated events</div>';return;}
  const counts=new Map(monthCounts), max=Math.max(...counts.values());
  const ordered=[...counts.keys()].sort(), start=new Date(`${ordered[0]}-01T12:00:00Z`), last=ordered.at(-1);
  for(let cursor=start;cursor.toISOString().slice(0,7)<=last;cursor.setUTCMonth(cursor.getUTCMonth()+1)) {
    const month=cursor.toISOString().slice(0,7), n=counts.get(month)||0;
    const b=document.createElement('button');b.className='month';b.title=`${monthLabel(month)} · ${fmt(n)} events`;
    b.setAttribute('aria-label',`Filter ${b.title}`);
    b.innerHTML=`<i style="height:${n/max*125}px"></i><span>${month.slice(2)}</span>`;
    b.onclick=()=>{ $('from').value=`${month}-01`; const end=new Date(`${month}-01T12:00:00Z`);end.setUTCMonth(end.getUTCMonth()+1);end.setUTCDate(0);$('to').value=end.toISOString().slice(0,10);update();};
    target.append(b);
  }
}
function renderTable() {
  const sorted=[...filtered].sort((a,b)=>(b.date||'').localeCompare(a.date||'')||a.name.localeCompare(b.name));
  const total=Math.max(1,Math.ceil(sorted.length/SIZE));state.page=Math.max(0,Math.min(state.page,total-1));
  $('events').innerHTML=sorted.slice(state.page*SIZE,(state.page+1)*SIZE).map(e=>{
    let valid=false;try{valid=['http:','https:'].includes(new URL(e.url).protocol);}catch{}
    return `<tr><td>${safe(e.date||'Unknown')}</td><td>${valid?`<a href="${safe(e.url)}" target="_blank" rel="noopener noreferrer">${safe(e.name)}</a>`:safe(e.name)}</td><td>${safe(e.org)}</td><td>${safe(e.city)}</td></tr>`;
  }).join('')||'<tr><td colspan="4">No matching events</td></tr>';
  $('list-count').textContent=fmt(filtered.length);$('page').textContent=`${state.page+1} / ${total}`;
  $('prev').disabled=state.page===0;$('next').disabled=state.page>=total-1;$('export').disabled=!filtered.length;
}
function reset() {
  HTMLFormElement.prototype.reset.call($('filters'));Object.assign(state,{org:'',day:null,cell:'',page:0});update();
}
function exportCSV() {
  const quote=value=>`"${String(value??'').replace(/^[=+@\-\t\r]/,"'$&").replace(/"/g,'""')}"`;
  const rows=[['Date','Event','Organizer','City','Venue','Category','Latitude','Longitude','URL'],...filtered.map(e=>[e.date,e.name,e.org,e.city,e.venue,e.category,...(e.coordinates||['','']),e.url])];
  const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.map(row=>row.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8;'}));
  const a=document.createElement('a');a.href=url;a.download='baltimore-event-analytics.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function init() {
  try {
    const response=await fetch('data.json');if(!response.ok)throw new Error('Dataset unavailable');
    const data=await response.json();all=data.events;
    $('archive').textContent=`${fmt(all.length)} events · ${fmt(data.snapshots)} snapshots`;
    for(const [field,id] of [['category','category'],['city','city']]) {
      [...new Set(all.map(e=>e[field]))].sort().forEach(value=>{const option=document.createElement('option');option.value=value;option.textContent=value;$(id).append(option);});
    }
    if(window.L) {
      map=L.map('map',{scrollWheelZoom:false,minZoom:2}).setView([39.29,-76.61],10);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map).on('tileerror',()=>{
        if(mapError)return;mapError=true;
        const note=document.createElement('div');note.className='note';note.textContent='Basemap unavailable · event cells still active';$('map').after(note);
      });
      cellsLayer=L.layerGroup().addTo(map);
    } else $('map').innerHTML='<div class="empty">Map unavailable. Use the hotspot list.</div>';
    $('filters').onsubmit=e=>e.preventDefault();
    let timer;$('search').oninput=()=>{clearTimeout(timer);timer=setTimeout(update,180);};
    ['from','to','category','city'].forEach(id=>$(id).onchange=update);
    $('grid').onchange=()=>{state.cell='';update();};$('reset').onclick=reset;
    $('home').onclick=()=>map?.setView([39.29,-76.61],10);
    $('fit').onclick=()=>{if(map&&currentCells.length)map.fitBounds(L.latLngBounds(currentCells.flatMap(([key])=>gridBounds(key))),{padding:[20,20],maxZoom:13});};
    $('prev').onclick=()=>{state.page--;renderTable();};$('next').onclick=()=>{state.page++;renderTable();};$('export').onclick=exportCSV;
    update();
  } catch(error) {
    $('archive').textContent='Archive unavailable';$('status').textContent='Could not load data. Reload to retry.';console.error(error);
  }
}
init();
