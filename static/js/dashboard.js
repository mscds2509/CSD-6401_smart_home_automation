const $ = (id) => document.getElementById(id);
let currentState = null;
let energyBreakdownChart = null;
let activityTimelineChart = null;
const roomIcons = { "Living Room":"🛋️", "Bedroom":"🛏️", "Kitchen":"🍳", "Hallway":"🚪" };
const deviceIcons = {light:"💡",fan:"🌀",heater:"♨️"};
const sceneIcons = {good_morning:"☀️",movie_mode:"🎬",away_mode:"🏡",relax_mode:"🌿"};
function escapeHtml(value){return String(value ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.remove("show"),2600);}
async function api(url,method="GET",body=null){const options={method,headers:{"Content-Type":"application/json"}};if(body!==null)options.body=JSON.stringify(body);const response=await fetch(url,options);if(response.status===401){location.href="/login";throw new Error("Please sign in again.");}const data=await response.json();if(!response.ok)throw new Error(data.error||"Request failed");return data;}
function renderStats(s){$("operatingMode").value=s.mode||"automatic";const modeBox=$("modeStatus");modeBox.className=`mode-status ${s.mode||"automatic"}`;modeBox.innerHTML=s.mode==="manual"?"<b>Manual mode</b><span>Automatic rules are paused. Device and room controls remain available.</span>":"<b>Automatic mode</b><span>Enabled rules can respond to sensor events.</span>";$("unreadCount").textContent=s.unread_notifications||0;$("homeTitle").textContent=s.home_name;$("totalDevices").textContent=s.summary.total;$("activeDevices").textContent=s.summary.active;$("inactiveDevices").textContent=s.summary.inactive;$("roomCount").textContent=s.summary.rooms;$("activeRules").textContent=s.summary.automations;$("activeWatts").textContent=s.energy.active_watts;$("hourlyKwh").textContent=s.energy.estimated_kwh_per_hour.toFixed(2);}
function renderScenes(s){$("sceneGrid").innerHTML=Object.entries(s.scenes).map(([id,scene])=>`<button class="scene-card" data-scene="${id}"><span class="scene-emoji">${sceneIcons[id]||"✨"}</span><b>${escapeHtml(scene.label)}</b><small>${escapeHtml(scene.description)}</small></button>`).join("");document.querySelectorAll("[data-scene]").forEach(b=>b.addEventListener("click",()=>{const label=b.querySelector("b")?.textContent.trim()||"Scene";const emoji=sceneIcons[b.dataset.scene]||"✨";perform(`/api/scene/${b.dataset.scene}`,"POST",null,`${emoji} ${label} activated`);}));}
function renderRooms(s){const filter=$("roomFilter").value;const search=$("deviceSearch").value.toLowerCase();const rooms=[...new Set(s.devices.map(d=>d.room))].sort();const sensorByRoom=Object.fromEntries((s.sensors||[]).map(x=>[x.room,x]));$("roomOverview").innerHTML=rooms.map(room=>{const list=s.devices.filter(d=>d.room===room);const sensor=sensorByRoom[room];return `<article class="room-overview-card"><span>${roomIcons[room]||"🏠"}</span><div><b>${escapeHtml(room)}</b><small>${list.filter(d=>d.is_on).length}/${list.length} devices active</small></div><strong>${sensor?sensor.temperature.toFixed(1)+"°C":"—"}</strong><small>${sensor?sensor.humidity.toFixed(0)+"% humidity":"No sensor"}</small></article>`;}).join("");const selected=$("roomFilter").value; $("roomFilter").innerHTML='<option value="all">All rooms</option>'+rooms.map(r=>`<option value="${escapeHtml(r)}">${escapeHtml(r)}</option>`).join("");$("roomFilter").value=rooms.includes(selected)?selected:"all";
const filtered=s.devices.filter(d=>(filter==="all"||d.room===filter)&&(`${d.name} ${d.room} ${d.kind}`.toLowerCase().includes(search)));const grouped={};filtered.forEach(d=>(grouped[d.room]??=[]).push(d));
$("roomGroups").innerHTML=Object.keys(grouped).length?Object.entries(grouped).map(([room,devices])=>`<article class="room-block"><div class="room-heading-row"><h3 class="room-title"><span>${roomIcons[room]||"🏠"}</span>${escapeHtml(room)}<small>${devices.length} device${devices.length===1?"":"s"} · ${devices.filter(d=>d.is_on).length} active</small></h3><div class="room-bulk"><button class="mini-btn" data-room-power="on" data-room="${escapeHtml(room)}">All ON</button><button class="mini-btn" data-room-power="off" data-room="${escapeHtml(room)}">All OFF</button></div></div><div class="device-grid">${devices.map(deviceCard).join("")}</div></article>`).join(""):'<div class="panel empty-state">No devices match your search.</div>';
document.querySelectorAll("[data-power]").forEach(b=>b.addEventListener("click",()=>perform(`/api/device/${b.dataset.power}/power`,"POST",{on:b.dataset.next==="on"},"Device updated")));
document.querySelectorAll("[data-setting]").forEach(input=>input.addEventListener("change",()=>perform(`/api/device/${input.dataset.device}/setting`,"POST",{field:input.dataset.setting,value:Number(input.value)},"Device setting saved")));
document.querySelectorAll("[data-room-power]").forEach(button=>button.addEventListener("click",()=>perform("/api/rooms/power","POST",{room:button.dataset.room,on:button.dataset.roomPower==="on"},`${button.dataset.room} devices switched ${button.dataset.roomPower.toUpperCase()}`)));
}
function deviceCard(d){const isOn=!!d.is_on;let control="";if(d.kind==="light")control=`<div class="device-control"><div class="range-row"><span>Brightness</span><input type="range" min="0" max="100" value="${d.brightness}" data-setting="brightness" data-device="${d.id}" ${isOn?"":"disabled"}><b>${d.brightness}%</b></div></div>`;if(d.kind==="fan")control=`<div class="device-control"><div class="range-row"><span>Speed</span><input type="range" min="1" max="5" value="${d.speed}" data-setting="speed" data-device="${d.id}" ${isOn?"":"disabled"}><b>${d.speed}/5</b></div></div>`;
const badges=(d.architecture_badges||[]).map(tag=>`<span class="architecture-badge ${tag.toLowerCase().replace(/[^a-z]+/g,"-")}">${escapeHtml(tag)}</span>`).join("");
return `<article class="device-card"><div class="device-head"><span class="device-icon">${deviceIcons[d.kind]||"🔌"}</span><button class="device-toggle ${isOn?"on":""}" aria-label="Toggle ${escapeHtml(d.name)}" data-power="${d.id}" data-next="${isOn?"off":"on"}"></button></div><h4>${escapeHtml(d.name)}</h4><div class="device-meta"><span>${escapeHtml(d.protocol)} · ${d.watts} W</span><span class="device-status ${isOn?"on":""}">${isOn?`● ON${d.on_since?` · since ${new Date(d.on_since).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}`:""}`:"○ OFF"}</span></div><div class="architecture-badges">${badges}</div>${control}</article>`;}
function renderRules(s){$("ruleCount").textContent=s.rules.length;const detail=r=>r.trigger_type==="time"?`At ${escapeHtml(r.schedule_time||"—")}`:r.trigger_type==="time_window"?`Between ${escapeHtml(r.window_start||"23:00")} and ${escapeHtml(r.window_end||"06:00")}`:r.trigger_type==="energy_threshold"?`Daily energy ≥ ${Number(r.threshold||1).toFixed(2)} kWh`:r.trigger_type==="anomaly"?`ON longer than ${Number(r.duration_seconds||3600)} seconds`:ruleTriggerLabel(r.trigger_type);$("ruleList").innerHTML=s.rules.length?s.rules.map(r=>`<div class="rule-item"><span class="rule-symbol">${r.trigger_type==="motion"?"◉":"◷"}</span><div class="rule-copy"><b>${escapeHtml(r.name)}</b><small>${detail(r)} · ${escapeHtml(r.device_id)} → ${r.action.toUpperCase()}</small></div><div class="rule-actions"><button class="mini-btn" data-rule-toggle="${r.id}" data-enabled="${r.enabled?0:1}">${r.enabled?"Pause":"Enable"}</button><button class="mini-btn danger" data-rule-delete="${r.id}">✕</button></div></div>`).join(""):'<div class="empty-state">No automation rules yet. Create your first rule.</div>';
document.querySelectorAll("[data-rule-toggle]").forEach(b=>b.addEventListener("click",()=>perform(`/api/rules/${b.dataset.ruleToggle}`,"PATCH",{enabled:b.dataset.enabled==="1"},"Rule updated")));document.querySelectorAll("[data-rule-delete]").forEach(b=>b.addEventListener("click",()=>{if(confirm("Delete this automation rule?"))perform(`/api/rules/${b.dataset.ruleDelete}`,"DELETE",null,"Rule deleted");}));}
function renderEnergy(s){const e=s.energy;$("todayKwh").textContent=Number(e.today_kwh||0).toFixed(4);if($("yesterdayKwh"))$("yesterdayKwh").textContent=Number(e.yesterday_kwh||0).toFixed(4);if($("energyDayChange")){$("energyDayChange").textContent=e.day_over_day_change_pct===null?"—":`${e.day_over_day_change_pct>0?"+":""}${e.day_over_day_change_pct}%`;$("energyDayChange").classList.toggle("positive",Number(e.day_over_day_change_pct)<=0);$("energyDayChange").classList.toggle("negative",Number(e.day_over_day_change_pct)>0);}if($("energyDayChangeNote"))$("energyDayChangeNote").textContent=e.day_over_day_change_pct===null?"No previous-day baseline yet":"Compared with yesterday";const max=Math.max(10,...e.device_breakdown.map(d=>d.watts));$("energyBreakdown").innerHTML=e.device_breakdown.map(d=>`<div class="breakdown-item"><span>${escapeHtml(d.name)}</span><span>${d.watts} W · ${Number(d.daily_kwh||0).toFixed(4)} kWh</span><div class="breakdown-bar"><i style="width:${Math.max(0,d.watts/max*100)}%"></i></div></div>`).join("");drawChart(e.recent_samples);drawEnergyBreakdownChart(e.device_breakdown||[]);const hist=e.daily_history||[];const maxDay=Math.max(0.001,...hist.map(x=>x.kwh));$("dailyEnergyHistory").innerHTML=hist.length?hist.map(x=>`<div class="daily-bar-row"><span>${escapeHtml(x.day.slice(5))}</span><div><i style="width:${Math.max(2,x.kwh/maxDay*100)}%"></i></div><b>${x.kwh.toFixed(4)}</b></div>`).join(""):'<p class="muted">Daily totals will appear as the simulation runs.</p>';const dev=e.device_history||[];const maxDev=Math.max(0.001,...dev.map(x=>x.kwh));$("deviceEnergyHistory").innerHTML=dev.map(x=>`<div class="breakdown-item"><span>${escapeHtml(x.name)}</span><span>${x.kwh.toFixed(4)} kWh</span><div class="breakdown-bar"><i style="width:${Math.max(0,x.kwh/maxDev*100)}%"></i></div></div>`).join("");}
function fitCanvas(canvas, height) {
  if (!canvas) return null;
  const width = Math.max(280, canvas.clientWidth || canvas.parentElement?.clientWidth || 600);
  const ratio = Math.max(1, window.devicePixelRatio || 1);
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  canvas.style.width = "100%";
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  return {ctx, width, height};
}
function drawEnergyBreakdownChart(items){
  const canvas = $("energyBreakdownChart");
  const fitted = fitCanvas(canvas, 230);
  if (!fitted) return;
  const {ctx, width, height} = fitted;
  const palette = ["#6258e8", "#3695d8", "#27a879", "#e6a23c", "#e36d78", "#8b70ce", "#25a6a1", "#b27a42"];
  const valid = (items || []).map(x => ({name: String(x.name || "Device"), watts: Math.max(0, Number(x.watts) || 0)}));
  const total = valid.reduce((sum, x) => sum + x.watts, 0);
  const cx = Math.min(width * .34, 170), cy = 112, outer = 76, inner = 48;
  if (total > 0) {
    let angle = -Math.PI / 2;
    valid.forEach((item, i) => {
      if (!item.watts) return;
      const next = angle + item.watts / total * Math.PI * 2;
      ctx.beginPath(); ctx.arc(cx, cy, outer, angle, next); ctx.arc(cx, cy, inner, next, angle, true); ctx.closePath();
      ctx.fillStyle = palette[i % palette.length]; ctx.fill(); angle = next;
    });
  } else {
    ctx.beginPath(); ctx.arc(cx, cy, outer, 0, Math.PI * 2); ctx.arc(cx, cy, inner, Math.PI * 2, 0, true); ctx.closePath(); ctx.fillStyle = "#e9ecf4"; ctx.fill();
  }
  ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = "#788397"; ctx.font = "700 9px Arial"; ctx.fillText("LIVE POWER", cx, cy - 10);
  ctx.fillStyle = "#17233f"; ctx.font = "700 19px Arial"; ctx.fillText(`${total.toFixed(0)} W`, cx, cy + 13);
  const lx = Math.min(width * .62, 310); let ly = 32;
  valid.forEach((item, i) => {
    ctx.fillStyle = palette[i % palette.length]; ctx.beginPath(); ctx.arc(lx, ly, 5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#344054"; ctx.font = "11px Arial"; ctx.textAlign = "left"; ctx.fillText(item.name.length > 19 ? item.name.slice(0, 18) + "…" : item.name, lx + 12, ly);
    ctx.fillStyle = "#788397"; ctx.textAlign = "right"; ctx.fillText(`${item.watts} W`, width - 12, ly);
    ly += 25;
  });
  if (!valid.length) { ctx.fillStyle = "#9aa3b2"; ctx.textAlign = "center"; ctx.font = "12px Arial"; ctx.fillText("No device power data available", width/2, height-12); }
}
function drawActivityTimeline(events){
  const canvas = $("activityTimelineChart");
  const fitted = fitCanvas(canvas, 180);
  if (!fitted) return;
  const {ctx, width, height} = fitted;
  const now = new Date(); const start = new Date(now.getTime() - 10 * 60000);
  const buckets = Array.from({length:11}, (_,i) => new Date(start.getTime() + i * 60000));
  const counts = buckets.map(() => 0);
  (events || []).forEach(ev => { const d = new Date(ev.created_at); if (Number.isNaN(d.getTime())) return; const n = Math.round((d.getTime() - buckets[0].getTime()) / 60000); if (n >= 0 && n < counts.length) counts[n]++; });
  const max = Math.max(1, ...counts), left = 38, right = 12, top = 14, bottom = 30, plotH = height-top-bottom, plotW = width-left-right;
  ctx.font = "10px Arial"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
  for (let i=0;i<4;i++) { const y=top+i*plotH/3; ctx.strokeStyle="#edf0f5"; ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(width-right,y); ctx.stroke(); ctx.fillStyle="#9aa3b2"; ctx.fillText(String(Math.ceil(max*(1-i/3))),left-8,y); }
  const points = counts.map((v,i)=>({x:left+i*plotW/10,y:top+plotH-(v/max)*plotH}));
  ctx.beginPath(); points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y)); ctx.strokeStyle="#6258e8"; ctx.lineWidth=2.5; ctx.stroke();
  ctx.lineTo(points[points.length-1].x,top+plotH); ctx.lineTo(points[0].x,top+plotH); ctx.closePath(); ctx.fillStyle="rgba(98,88,232,.10)"; ctx.fill();
  ctx.fillStyle="#6258e8"; points.forEach(p=>{ctx.beginPath();ctx.arc(p.x,p.y,2.5,0,Math.PI*2);ctx.fill();});
  ctx.fillStyle="#9aa3b2"; ctx.textAlign="center"; ctx.textBaseline="top";
  buckets.forEach((d,i)=>{if(i%2===0||i===10)ctx.fillText(d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}),left+i*plotW/10,height-20);});
}
function drawChart(samples){const canvas=$("energyChart");if(!canvas)return;const ctx=canvas.getContext("2d");if(!ctx)return;const width=canvas.clientWidth||600;const height=210;const ratio=window.devicePixelRatio||1;canvas.width=width*ratio;canvas.height=height*ratio;ctx.scale(ratio,ratio);ctx.clearRect(0,0,width,height);const values=(samples||[]).length?samples.map(s=>Number(s.watts)||0):[0,0];const max=Math.max(50,...values)*1.15;const left=34,right=12,top=15,bottom=28;const plotW=width-left-right,plotH=height-top-bottom;ctx.font="10px DM Sans";ctx.fillStyle="#9aa3b2";ctx.strokeStyle="#edf0f5";ctx.lineWidth=1;for(let i=0;i<4;i++){let y=top+i*plotH/3;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(width-right,y);ctx.stroke();ctx.fillText(Math.round(max*(1-i/3)),2,y+3);}const pts=values.map((v,i)=>({x:left+(values.length===1?plotW/2:i*plotW/(values.length-1)),y:top+plotH-(v/max)*plotH}));if(pts.length){ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.strokeStyle="#6258e8";ctx.lineWidth=2.5;ctx.stroke();const last=pts[pts.length-1];ctx.fillStyle="#6258e8";ctx.beginPath();ctx.arc(last.x,last.y,4,0,Math.PI*2);ctx.fill();}ctx.fillStyle="#9aa3b2";ctx.fillText("Recent samples",left,height-7);}
function renderSensors(s){$("sensorGrid").innerHTML=s.sensors.map(x=>`<article class="sensor-card"><b>${escapeHtml(x.room)}</b><div><strong>${x.temperature.toFixed(1)}°C</strong><span>Temperature</span></div><div><strong>${x.humidity.toFixed(0)}%</strong><span>Humidity</span></div></article>`).join("");}
function renderNotifications(s){$("notificationList").innerHTML=s.notifications.length?s.notifications.map(n=>`<div class="notification-item ${n.is_read?"read":"unread"}"><div><b>${escapeHtml(n.message)}</b><small>${new Date(n.created_at).toLocaleString()}</small></div>${n.is_read?"":`<button class="mini-btn" data-notification-read="${n.id}">Mark read</button>`}</div>`).join(""):'<p class="muted">No notifications yet.</p>';document.querySelectorAll("[data-notification-read]").forEach(b=>b.addEventListener("click",()=>perform(`/api/notifications/${b.dataset.notificationRead}/read`,"POST",{},"Marked as read")));}
function renderActivity(s){$("activityList").innerHTML=s.events.length?s.events.map(e=>`<div class="activity-item"><span class="activity-icon">${({device:"◉",sensor:"⌁",automation:"⌘",scene:"✳",command:"↶",system:"⌂",settings:"⚙"}[e.category]||"•")}</span><div class="activity-copy"><b>${escapeHtml(e.message)}</b><small>${new Date(e.created_at).toLocaleString()}</small></div><span class="activity-tag">${escapeHtml(e.category)}</span></div>`).join(""):'<div class="empty-state">No activity recorded yet.</div>';drawActivityTimeline(s.events);renderCommandHistory(s.command_history||[]);}
function renderCommandHistory(rows){const el=$("commandHistoryList");if(!el)return;el.innerHTML=rows.length?rows.map(c=>`<div class="command-history-row"><b>${escapeHtml(c.device_name)} · ${escapeHtml(c.action)}</b><span>${escapeHtml(c.source)}</span><small>${new Date(c.created_at).toLocaleString()}</small></div>`).join(""):'<p class="muted">No commands recorded yet.</p>';}
function renderSettings(s){
  const editingSettings=!!(document.activeElement&&document.activeElement.closest("#homeSettingsForm,#deviceConfigForm,#roomConfigForm"));
  if(!editingSettings){
    $("settingsHomeName").value=s.home_name||"My Smart Home";
    $("settingsMode").value=s.mode||"automatic";
  }
  const previousDevice=$("configDevice").value;
  $("configDevice").innerHTML=s.devices.map(d=>`<option value="${escapeHtml(d.id)}">${escapeHtml(d.name)}</option>`).join("");
  if(s.devices.some(d=>d.id===previousDevice))$("configDevice").value=previousDevice;
  const selected=s.devices.find(d=>d.id===$("configDevice").value)||s.devices[0];
  if(selected&&!editingSettings){$("configDeviceName").value=selected.name;$("configDeviceRoom").value=selected.room;$("configDeviceWatts").value=selected.watts;}
  const rooms=[...new Set(s.devices.map(d=>d.room))].sort();const previousRoom=$("configRoom").value;
  $("configRoom").innerHTML=rooms.map(r=>`<option value="${escapeHtml(r)}">${escapeHtml(r)}</option>`).join("");
  if(rooms.includes(previousRoom))$("configRoom").value=previousRoom;
  const pref=(s.room_preferences||[]).find(r=>r.room===$("configRoom").value)||{};
  if(!editingSettings){
    $("configRoomName").value=pref.room||$("configRoom").value||"";
    $("configRoomTemp").value=pref.target_temperature??22;$("configRoomHumidity").value=pref.target_humidity??45;$("configRoomNotes").value=pref.notes||"";
  }
  $("undoButton").disabled=!s.can_undo;
}
function ruleTriggerLabel(t){return ({motion:"Motion detected",time:"Scheduled time",door_open:"Door opens",temperature_high:"Temperature threshold",humidity_high:"Humidity threshold",energy_threshold:"Energy budget",time_window:"Time window",anomaly:"Long-running device"}[t]||t);}
async function loadState(){try{const s=await api("/api/state");currentState=s;renderStats(s);renderScenes(s);renderRooms(s);renderRules(s);renderEnergy(s);renderSensors(s);renderNotifications(s);renderActivity(s);renderSettings(s);if(!$("ruleDevice").options.length)$("ruleDevice").innerHTML=s.devices.map(d=>`<option value="${d.id}">${escapeHtml(d.name)}</option>`).join("");}catch(e){toast(e.message);}}
async function perform(url,method,body,message){try{await api(url,method,body);toast(message);await loadState();}catch(e){toast(e.message);}}
$("ruleForm").addEventListener("submit",async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget));try{await api("/api/rules","POST",data);e.currentTarget.reset();$("scheduleTime").value="19:00";toast("Automation created");await loadState();}catch(err){toast(err.message);}});
$("operatingMode").addEventListener("change",async e=>{try{await api("/api/mode","POST",{mode:e.target.value});toast(`Mode set to ${e.target.value}`);await loadState();}catch(err){toast(err.message);}});
$("notificationButton").addEventListener("click",()=>{$("notificationPanel").hidden=!$("notificationPanel").hidden;});
$("markAllRead").addEventListener("click",()=>perform("/api/notifications/read-all","POST",{},"All notifications marked read"));
$("energyRange").addEventListener("change",async e=>{try{const energy=await api(`/api/energy?days=${encodeURIComponent(e.target.value)}`);if(currentState){currentState.energy.daily_history=energy.daily_history;currentState.energy.device_history=energy.device_history;renderEnergy(currentState);}}catch(err){toast(err.message);}});
$("roomFilter").addEventListener("change",()=>currentState&&renderRooms(currentState));$("deviceSearch").addEventListener("input",()=>currentState&&renderRooms(currentState));$("refreshBtn").addEventListener("click",loadState);$("mobileMenu").addEventListener("click",()=>$("sidebar").classList.toggle("open"));
document.querySelectorAll(".nav-link").forEach(a=>a.addEventListener("click",()=>{document.querySelectorAll(".nav-link").forEach(x=>x.classList.remove("active"));a.classList.add("active");$("sidebar").classList.remove("open");}));
$("todayLabel").textContent=new Date().toLocaleDateString(undefined,{weekday:"long",month:"long",day:"numeric"});
$("undoButton").addEventListener("click",()=>perform("/api/undo","POST",{},"Last command undone"));
$("configDevice").addEventListener("change",()=>{if(!currentState)return;const d=currentState.devices.find(x=>x.id===$("configDevice").value);if(d){$("configDeviceName").value=d.name;$("configDeviceRoom").value=d.room;$("configDeviceWatts").value=d.watts;}});
$("configRoom").addEventListener("change",()=>{if(!currentState)return;const r=$("configRoom").value;const p=(currentState.room_preferences||[]).find(x=>x.room===r)||{};$("configRoomName").value=p.room||r;$("configRoomTemp").value=p.target_temperature??22;$("configRoomHumidity").value=p.target_humidity??45;$("configRoomNotes").value=p.notes||"";});
$("homeSettingsForm").addEventListener("submit",async e=>{e.preventDefault();try{const home_name=$("settingsHomeName").value.trim();await api("/api/settings","POST",{home_name});await api("/api/mode","POST",{mode:$("settingsMode").value});toast("Home preferences saved");await loadState();}catch(err){toast(err.message);}});
$("deviceConfigForm").addEventListener("submit",async e=>{e.preventDefault();const id=$("configDevice").value;try{await api(`/api/device/${id}/config`,"PATCH",{name:$("configDeviceName").value,room:$("configDeviceRoom").value,watts:Number($("configDeviceWatts").value)});toast("Device configuration saved");await loadState();}catch(err){toast(err.message);}});
$("roomConfigForm").addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/rooms/config","PATCH",{room:$("configRoom").value,name:$("configRoomName").value,target_temperature:Number($("configRoomTemp").value),target_humidity:Number($("configRoomHumidity").value),notes:$("configRoomNotes").value});toast("Room preferences saved");await loadState();}catch(err){toast(err.message);}});
document.querySelectorAll("[data-trigger]").forEach(button => { button.addEventListener("click", async () => { await perform("/api/trigger", "POST", {trigger_type: button.dataset.trigger}, ruleTriggerLabel(button.dataset.trigger) + " simulated"); }); });
document.querySelectorAll("[data-preset]").forEach(b=>b.addEventListener("click",()=>perform("/api/rules/preset/"+b.dataset.preset,"POST",{},b.textContent.trim()+" added")));
loadState();setInterval(loadState,2500);window.addEventListener("resize",()=>currentState&&drawChart(currentState.energy.recent_samples));
