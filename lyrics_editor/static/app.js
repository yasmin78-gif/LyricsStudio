'use strict';
const $ = id => document.getElementById(id);
const audio = $('audio');
let state, token, selected, waveform, formDirty = false, queue = Promise.resolve();
let view = {start: 0, width: 60}, context, segment = null;
const statuses = {unreviewed: 'Ungeprüft', editing: 'In Bearbeitung', confirmed: 'Bestätigt'};
const row = () => state?.rows.find(r => r.id === selected);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const format = n => `${Math.floor(n / 60).toString().padStart(2, '0')}:${(n % 60).toFixed(3).padStart(6, '0')}`;
const framePos = n => {const f = n * (state?.fps || 24), near = Math.round(f); return Math.abs(f - near) <= 1e-7 ? near : f;};
function tc(n) {const f = Math.round(framePos(n)), rate = state.fps; return [Math.floor(f / (rate*3600)), Math.floor(f / (rate*60)) % 60, Math.floor(f / rate) % 60, f % rate].map(x => String(x).padStart(2, '0')).join(':');}
function notice(text, error = false) {$('notice').textContent = text; $('notice').classList.toggle('error', error);}
function busy(flag) {
  document.body.setAttribute('aria-busy', String(flag));
  for (const el of document.querySelectorAll('button,input,textarea,select')) {
    if (flag) {el.dataset.disabledBefore = String(el.disabled); el.disabled = true;}
    else if ('disabledBefore' in el.dataset) {el.disabled = el.dataset.disabledBefore === 'true'; delete el.dataset.disabledBefore;}
  }
  if (!flag) controls();
}
function run(fn) {queue = queue.then(async () => {busy(true); try {await fn();} catch (e) {notice(e.message, true);} finally {busy(false);}}); return queue;}
async function request(path, payload) {
  const response = await fetch(path, payload ? {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Editor-Token': token}, body: JSON.stringify({...payload, revision: state.revision})} : undefined);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Der Dienst ist nicht erreichbar.');
  return result;
}
function inputs() {
  const a = Number($('start').value), b = Number($('end').value), text = $('text').value.trim();
  if (!$('start').value.trim() || !$('end').value.trim() || !Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b <= a || b > state.duration) throw new Error('Bitte gültige Zeiten eingeben: 0 ≤ Beginn < Ende ≤ Songdauer.');
  if (!text) throw new Error('Der Text darf nicht leer sein.');
  return {text, start: a, end: b};
}
function previewInterval() {return {start: Number($('start').value), end: Number($('end').value)};}
function changed() {
  formDirty = true; $('acknowledge').checked = false; $('allowOverlap').checked = false;
  $('rowStatus').textContent = statuses.editing; $('rowStatus').className = 'status-pill editing';
  updateTiming(); controls(); draw();
}
function updateTiming() {
  const {start:a,end:b} = previewInterval();
  const startFrame = Math.floor(framePos(a)), endFrame = Math.ceil(framePos(b));
  $('startTc').textContent = Number.isFinite(a) && a >= 0 ? `${tc(startFrame/state.fps)} · Frame ${startFrame}` : 'Ungültiger Beginn';
  $('endTc').textContent = Number.isFinite(b) && b >= 0 ? `${tc(endFrame/state.fps)} · Frame ${endFrame} exklusiv` : 'Ungültiges Ende';
  const overlaps = state.rows.filter(r => !r.deleted && r.id !== selected && r.status === 'confirmed' && Math.floor(framePos(a)) < Math.ceil(framePos(r.end)) && Math.ceil(framePos(b)) > Math.floor(framePos(r.start)));
  $('intervalWarning').textContent = !Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b <= a || b > state.duration ? 'Bitte ein gültiges Intervall innerhalb des Songs einstellen.' : overlaps.length ? 'Achtung: Dieser Bereich überschneidet sich nach Frame-Rundung mit einer bestätigten Passage.' : '';
}
function controls() {
  if (!state) return;
  $('undo').disabled = !state.can_undo; $('redo').disabled = !state.can_redo;
  $('unconfirm').disabled = row()?.status !== 'confirmed' || formDirty;
  $('confirm').disabled = !row() || row().deleted || !$('acknowledge').checked || !$('reviewer').value.trim();
  $('apply').disabled = !formDirty;
  $('saveStatus').textContent = formDirty || state.dirty ? 'Nicht gespeicherte Änderungen' : state.has_saved_draft ? `Gespeicherter Stand · ${state.confirmed_count} bestätigt` : 'Unveränderte Vorschläge · noch kein Entwurf gespeichert';
  $('reload').disabled = !state.has_saved_draft;
  $('statePath').textContent = state.state_file;
}
function list() {
  const search = $('search').value.toLowerCase(), hidden = $('showHidden').checked;
  const rows = state.rows.filter(r => (hidden || !r.deleted) && (r.text.toLowerCase().includes(search) || r.id.toLowerCase().includes(search))).sort((a,b) => a.start - b.start || a.order - b.order);
  $('lyricsList').replaceChildren();
  for (const r of rows) {
    const button = document.createElement('button'); button.type = 'button';
    button.className = 'lyric-row ' + r.status + (r.id === selected ? ' selected' : '') + (r.deleted ? ' hidden-row' : '');
    button.dataset.id = r.id; button.setAttribute('aria-pressed', String(r.id === selected));
    const meta = document.createElement('span'); meta.className = 'row-meta';
    const times = document.createElement('span'); times.textContent = `${format(r.start)} – ${format(r.end)}`;
    const status = document.createElement('span'); status.className = 'row-status';
    const dot = document.createElement('span'); dot.className = 'dot ' + (r.deleted ? 'unreviewed' : r.status); dot.setAttribute('aria-hidden', 'true');
    status.append(dot, document.createTextNode(r.deleted ? 'Ausgeblendet' : statuses[r.status]));
    meta.append(times, status);
    const text = document.createElement('span'); text.className = 'line'; text.textContent = r.text;
    const id = document.createElement('span'); id.className = 'row-id'; id.textContent = r.id + (r.repeat_of ? ' · Wiederholung' : '');
    button.append(meta, text, id);
    button.addEventListener('click', () => run(async () => {await applyForm(); selected = r.id; renderForm(); list(); ensureVisible(); seekTo(r.start); if (r.deleted) notice('Ausgeblendeter Vorschlag. Zum Wiederherstellen „Wiederherstellen“ wählen.');}));
    $('lyricsList').append(button);
  }
  $('counts').textContent = `${state.rows.filter(r=>!r.deleted).length} Passagen · ${state.confirmed_count} bestätigt`;
}
function renderForm() {
  const r = row(); if (!r) return;
  $('selectedId').textContent = r.id;
  $('text').value = r.text; $('start').value = String(r.start); $('end').value = String(r.end);
  $('rowStatus').textContent = r.deleted ? 'Ausgeblendet' : statuses[r.status];
  $('rowStatus').className = 'status-pill ' + r.status;
  $('suggestion').textContent = r.suggestion ? `Whisper-Vorschlag: ${format(r.suggestion.start)}–${format(r.suggestion.end)} · nicht automatisch bestätigt` : 'Manuell angelegte Passage · ohne feste Songstruktur';
  $('remove').textContent = r.deleted ? 'Wiederherstellen' : 'Aus Entwurf entfernen';
  $('acknowledge').checked = false; $('allowOverlap').checked = false;
  formDirty = false; updateTiming(); controls(); draw();
}
async function applyForm() {
  if (!formDirty || !row()) return;
  const values = inputs();
  state = await request('/api/action', {action: 'update', id: selected, ...values});
  formDirty = false; list(); renderForm();
  notice('Änderungen übernommen. Bitte den Entwurf speichern.');
}
async function action(kind, extra = {}) {
  await applyForm();
  state = await request('/api/action', {action: kind, id: selected, ...extra});
  list(); renderForm(); ensureVisible();
}
function visible() {view.width = clamp(view.width, 1, state.duration); view.start = clamp(view.start, 0, Math.max(0, state.duration-view.width)); $('viewRange').max = String(Math.max(0, state.duration-view.width)); $('viewRange').value = String(view.start); $('visibleRange').textContent = `${format(view.start)} – ${format(view.start+view.width)} · ${view.width.toFixed(1)} s sichtbar`;}
function ensureVisible(fit = false) {
  const r = row(); if (!r) return;
  if (fit) {view.width = clamp((r.end-r.start)+6, 5, state.duration); view.start = r.start-3;}
  else if (r.start < view.start || r.end > view.start+view.width) view.start = r.start-2;
  visible(); draw();
}
function position() {if (segment) {const elapsed = Math.max(0, context.currentTime-segment.begins)*segment.rate; return Math.min(segment.end,segment.start+elapsed);} return audio.currentTime || 0;}
function stopSegment() {if (segment) {const p = position(), old = segment; segment = null; old.source.stop(); audio.currentTime = clamp(p,0,state.duration);}}
function seekTo(time) {stopSegment(); audio.currentTime = clamp(time,0,state.duration); updateClock(); draw();}
function updateClock() {$('position').textContent = format(position()); $('play').textContent = segment || !audio.paused ? 'Ⅱ Pause' : '▶ Wiedergabe';}
function togglePlay() {if (segment) {stopSegment(); updateClock(); return;} if (!audio.paused) audio.pause(); else audio.play().catch(e => notice('Wiedergabe konnte nicht starten: '+e.message,true)); updateClock();}
async function preview() {
  context ||= new AudioContext(); await context.resume(); await applyForm();
  const r = row(); inputs();
  if (r.end-r.start > 60) throw new Error('Bitte für die Bereichsvorschau einen Abschnitt bis 60 Sekunden wählen.');
  stopSegment(); audio.pause();
  const response = await fetch(`/api/segment?start=${r.start}&end=${r.end}`);
  if (!response.ok) throw new Error((await response.json()).error);
  const buffer = await context.decodeAudioData(await response.arrayBuffer());
  const source = context.createBufferSource(); source.buffer = buffer; source.connect(context.destination);
  source.playbackRate.value = Number($('rate').value);
  const current = {source,start:r.start,end:r.end,rate:source.playbackRate.value,begins:context.currentTime+.04};
  segment = current; source.onended = () => {if (segment === current) {segment=null; audio.currentTime=r.end; updateClock(); draw();}};
  source.start(current.begins); notice('Ausgewählten Originalaudio-Bereich abspielen. Zum Stoppen „Pause“ wählen.');
}
function draw() {
  if (!state) return;
  visible(); const canvas = $('waveCanvas'), rect = canvas.getBoundingClientRect(), w = rect.width, h = rect.height;
  if (!w) return;
  const ratio = devicePixelRatio || 1;
  if (canvas.width !== Math.round(w*ratio) || canvas.height !== Math.round(h*ratio)) {canvas.width=Math.round(w*ratio); canvas.height=Math.round(h*ratio);}
  const c = canvas.getContext('2d'); c.setTransform(ratio,0,0,ratio,0,0); c.clearRect(0,0,w,h);
  const toX = t => (t-view.start)/view.width*w;
  const selectedRange = previewInterval();
  if (Number.isFinite(selectedRange.start) && Number.isFinite(selectedRange.end)) {c.fillStyle = 'rgba(115,223,213,.12)'; c.fillRect(toX(selectedRange.start),28,toX(selectedRange.end)-toX(selectedRange.start),h-45);}
  c.font='11px Segoe UI'; c.fillStyle='#9dafc4'; c.strokeStyle='#25364b';
  const tick = view.width <= 5 ? .5 : view.width <= 15 ? 2 : view.width <= 45 ? 5 : view.width <= 100 ? 10 : 30;
  for (let t=Math.ceil(view.start/tick)*tick;t<=view.start+view.width;t+=tick) {const x=toX(t); c.beginPath();c.moveTo(x,25);c.lineTo(x,h-8);c.stroke();c.fillText(format(t).slice(0,5),x+4,17);}
  if (waveform) {
    const n=waveform.channels, lane=(h-45)/n, bins=waveform.peaks, dt=waveform.bucket_seconds;
    for (let channel=0;channel<n;channel++) {const mid=32+lane*(channel+.5); c.strokeStyle=channel===0?'#7dcfca':'#71a8c6'; c.beginPath();
      for (let x=0;x<w;x++) {const a=clamp(Math.floor((view.start+x/w*view.width)/dt),0,bins.length-1), b=clamp(Math.ceil((view.start+(x+1)/w*view.width)/dt),a+1,bins.length); let low=0,high=0;
        for(let i=a;i<b;i++){low=Math.min(low,bins[i][channel*2]);high=Math.max(high,bins[i][channel*2+1]);}
        c.moveTo(x,mid-low/32768*lane*.42);c.lineTo(x,mid-high/32768*lane*.42);
      } c.stroke();
    }
  }
  c.strokeStyle='#ffffff'; const playhead=toX(position());c.beginPath();c.moveTo(playhead,25);c.lineTo(playhead,h);c.stroke();
  for (const [id,t] of [['startHandle',selectedRange.start],['endHandle',selectedRange.end]]) {const x=toX(t); $(id).hidden=!row()||!Number.isFinite(t)||x<0||x>w; $(id).style.left=`${x}px`;}
}
function nudge(boundary,delta) {const el=$(boundary); const old=Number(el.value); if(!Number.isFinite(old))return; el.value=String(old+delta/state.fps); changed();}

$('play').onclick=togglePlay;
$('back5').onclick=()=>seekTo(position()-5); $('forward5').onclick=()=>seekTo(position()+5);
$('rate').onchange=()=>{audio.playbackRate=Number($('rate').value);if(segment){stopSegment();updateClock();notice('Tempo geändert. Bereich erneut starten.');}};
$('jump').onclick=()=>{try {const parts=$('seek').value.trim().replace(',','.').split(':').map(Number);let t;if(parts.some(x=>!Number.isFinite(x)))throw Error();if(parts.length===1)t=parts[0];else if(parts.length===2&&parts[1]<60)t=parts[0]*60+parts[1];else if(parts.length===3&&parts[1]<60&&parts[2]<60)t=parts[0]*3600+parts[1]*60+parts[2];else throw Error();if(t<0||t>state.duration)throw Error();seekTo(t);}catch{notice('Bitte eine Zielzeit innerhalb des Songs eingeben, z. B. 01:23.500 oder 83.5.',true);}};
$('seek').onkeydown=e=>{if(e.key==='Enter')$('jump').click();};
$('text').oninput=changed;
for(const boundary of ['start','end']) {$(boundary).oninput=changed;$(boundary).onkeydown=e=>{if(['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();nudge(boundary,(e.key==='ArrowUp'?1:-1)*(e.shiftKey?10:1));}};}
for(const button of document.querySelectorAll('[data-boundary]'))button.onclick=()=>nudge(button.dataset.boundary,Number(button.dataset.delta));
$('acknowledge').onchange=controls; $('reviewer').oninput=controls;
$('apply').onclick=()=>run(applyForm);
$('preview').onclick=()=>run(preview);
$('snap').onclick=()=>run(()=>action('snap'));
$('duplicate').onclick=()=>run(async()=>{await applyForm();const ids=new Set(state.rows.map(r=>r.id));await action('duplicate');selected=state.rows.find(r=>!ids.has(r.id)).id;list();renderForm();ensureVisible();notice('Neue Wiederholung angelegt. Zeiten prüfen und separat bestätigen.');});
$('insert').onclick=()=>run(async()=>{await applyForm();const ids=new Set(state.rows.map(r=>r.id));state=await request('/api/action',{action:'insert',start:clamp(position(),0,state.duration-.1)});selected=state.rows.find(r=>!ids.has(r.id)).id;list();renderForm();ensureVisible(true);});
$('remove').onclick=()=>run(async()=>{const r=row();await action(r.deleted?'restore':'delete');notice(r.deleted?'Passage wiederhergestellt.':'Passage nur aus dem Entwurf ausgeblendet. ASR-Quelldaten bleiben erhalten.');});
$('unconfirm').onclick=()=>run(async()=>{await action('unconfirm');notice('Bestätigung zurückgenommen. Bitte Entwurf speichern.');});
$('confirm').onclick=()=>run(async()=>{const reviewer=$('reviewer').value,ack=$('acknowledge').checked,allow=$('allowOverlap').checked;await applyForm();state=await request('/api/action',{action:'confirm',id:selected,reviewer,acknowledge:ack,allow_overlap:allow});list();renderForm();notice('Zeile ausdrücklich bestätigt und Entwurf gespeichert. Keine Änderung in Resolve.');});
$('save').onclick=()=>run(async()=>{await applyForm();state=await request('/api/save',{});list();controls();notice('Entwurf gespeichert. Vorherige Speicherstände bleiben erhalten.');});
$('reload').onclick=()=>run(async()=>{if((formDirty||state.dirty)&&!window.confirm('Nicht gespeicherte Änderungen verwerfen und den letzten gespeicherten Stand laden?'))return;state=await request('/api/reload',{});if(!state.rows.some(r=>r.id===selected))selected=state.rows.find(r=>!r.deleted)?.id;list();renderForm();notice('Gespeicherten Entwurf erneut geladen.');});
for(const kind of ['undo','redo'])$(kind).onclick=()=>run(async()=>{await applyForm();await action(kind);notice(kind==='undo'?'Letzte Änderung rückgängig gemacht.':'Änderung wiederhergestellt.');});
$('export').onclick=()=>run(async()=>{await applyForm();const out=await request('/api/export',{});state=out.state;controls();notice(`${out.confirmed_count} bestätigte Passagen als Schema-2.0-JSON gespeichert: ${out.path}`);});
$('search').oninput=list; $('showHidden').onchange=list;
$('zoomIn').onclick=()=>{view.start+=view.width/4;view.width/=2;draw();};
$('zoomOut').onclick=()=>{view.start-=view.width/2;view.width*=2;draw();};
$('panLeft').onclick=()=>{view.start-=view.width/2;draw();};$('panRight').onclick=()=>{view.start+=view.width/2;draw();};
$('showAll').onclick=()=>{view={start:0,width:state.duration};draw();};$('fitSelection').onclick=()=>ensureVisible(true);
$('viewRange').oninput=e=>{view.start=Number(e.target.value);draw();};
$('waveCanvas').onclick=e=>{const rect=e.target.getBoundingClientRect();seekTo(view.start+(e.clientX-rect.left)/rect.width*view.width);};
for(const [id,boundary] of [['startHandle','start'],['endHandle','end']]) {
  $(id).onpointerdown=e=>{e.preventDefault();$(id).setPointerCapture(e.pointerId);};
  $(id).onpointermove=e=>{if(!$(id).hasPointerCapture(e.pointerId))return;const rect=$('wave').getBoundingClientRect();$(boundary).value=String(clamp(view.start+(e.clientX-rect.left)/rect.width*view.width,0,state.duration));changed();};
  $(id).onpointerup=e=>{if($(id).hasPointerCapture(e.pointerId)){$(id).releasePointerCapture(e.pointerId);run(applyForm);}};
  $(id).onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();nudge(boundary,(e.key==='ArrowLeft'?-1:1)*(e.shiftKey?10:1));}};
}
document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key.toLowerCase()==='s'){e.preventDefault();$('save').click();return;}if(/INPUT|TEXTAREA|SELECT|BUTTON/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();togglePlay();}if(e.key.toLowerCase()==='j')seekTo(position()-(e.shiftKey?5:1));if(e.key.toLowerCase()==='l')seekTo(position()+(e.shiftKey?5:1));});
window.addEventListener('beforeunload',e=>{if(formDirty||state?.dirty){e.preventDefault();e.returnValue='';}});
window.addEventListener('resize',draw);
audio.addEventListener('error',()=>notice('Die WAV-Datei konnte im Browser nicht geladen werden.',true));
audio.addEventListener('play',updateClock);audio.addEventListener('pause',updateClock);audio.addEventListener('seeked',()=>{updateClock();draw();});
function animate(){updateClock();if(segment||!audio.paused)draw();requestAnimationFrame(animate);}
(async()=>{try{state=await request('/api/state');token=state.token;selected=state.rows.find(r=>!r.deleted)?.id;$('songTitle').textContent=state.title;document.title=state.title+' · Lyrics Studio';$('songDuration').textContent='/ '+format(state.duration);list();renderForm();ensureVisible();waveform=await request('/api/peaks');$('waveLoading').hidden=true;$('waveLoading').style.display='none';draw();notice(`${state.source_count} ASR-Vorschläge geladen. Kein Text und keine Zeitmarke wird automatisch bestätigt.`);requestAnimationFrame(animate);}catch(e){notice(e.message,true);}})();
