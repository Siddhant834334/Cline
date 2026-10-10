const $ = (id) => document.getElementById(id);
const COLORS = { fastest: "#e8a33d", calmest: "#4fc3f7", balanced: "#ba68c8" };
const map = L.map("map").setView([26.19, 91.694], 15);
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: "&copy; OpenStreetMap contributors &copy; CARTO", maxZoom: 20 }).addTo(map);
let cfg = {}, start = null, end = null, markers = [], lastRes = null, sel = null;
const baseLayer = L.layerGroup().addTo(map), routeLayer = L.layerGroup().addTo(map);

const riskColor = (r, st) => st === "no_data" ? "#888" : r > cfg.tau ? (r > 0.7 ? "#e53935" : "#fb8c00") : "#43a047";
const hourVal = () => +$("hour").value;
const hh = (h) => String(h % 24).padStart(2, "0") + ":00" + (h >= 24 ? " (after midnight)" : "");
const fmtMin = (s) => (s / 60).toFixed(1) + " min";

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "content-type": "application/json", ...(opts.headers || {}) }, ...opts });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || r.status);
  return j;
}

async function loadNetwork() {
  const net = await api(`/api/network?hour=${hourVal() % 24}`);
  baseLayer.clearLayers();
  for (const s of net.segments) {
    const line = L.polyline(s.ll, { color: s.closed ? "#fff" : riskColor(s.r, s.st), weight: 3, opacity: s.closed ? 0.9 : 0.45,
      dashArray: s.st === "no_data" || s.closed ? "4 6" : null });
    line.on("click", (e) => { L.DomEvent.stopPropagation(e); openDrawer(s.id); });
    baseLayer.addLayer(line);
  }
}

function setMarker(ll, label) {
  markers.push(L.marker(ll, { title: label }).bindTooltip(label, { permanent: true, direction: "top" }).addTo(map));
}

map.on("click", (e) => {
  if (!start) { start = e.latlng; setMarker(start, "Start"); }
  else if (!end) { end = e.latlng; setMarker(end, "End"); findRoutes(); }
});

function resetAll() {
  start = end = null; sel = null; lastRes = null; markers.forEach((m) => m.remove()); markers = [];
  routeLayer.clearLayers(); $("cards").innerHTML = ""; $("status").textContent = ""; $("drawer").hidden = true;
}

async function findRoutes() {
  if (!start || !end) { $("status").textContent = "Set start and end first."; return; }
  $("status").textContent = "Routing…";
  try {
    lastRes = await api("/api/route", { method: "POST", body: JSON.stringify({
      start: [start.lat, start.lng], end: [end.lat, end.lng], hour: hourVal() % 24, detour: +$("detour").value }) });
  } catch (e) { $("status").textContent = "Error: " + e.message; return; }
  renderCards();
}

function cardHtml(c) {
  const also = c.also ? ` <span class="muted">(= ${c.also.join(", ")})</span>` : "";
  return `<h3>${c.name}${also}</h3><div class="muted">${c.claim}</div><table>
    <tr><td>Walk time</td><td>${fmtMin(c.time_s)} · ${Math.round(c.length_m)} m</td></tr>
    <tr><td><b>Longest continuous concerning stretch</b></td><td><b>${Math.round(c.longest_stretch_m)} m</b> (${c.longest_stretch_min.toFixed(1)} min)</td></tr>
    <tr><td>Total concerning</td><td>${Math.round(c.concerning_m)} m (${c.concerning_min.toFixed(1)} min)</td></tr>
    <tr><td>Max single-segment risk</td><td>${c.max_segment_risk.toFixed(2)}</td></tr>
    <tr><td>Unknown (no data)</td><td>${Math.round(c.unknown_m)} m</td></tr>
    <tr><td>Data coverage</td><td>${c.coverage == null ? "–" : Math.round(c.coverage * 100) + "%"}</td></tr></table>
    <div class="codes">${c.reason_codes.join(" · ")}</div>`;
}

function renderCards() {
  const res = lastRes;
  $("cards").innerHTML = "";
  routeLayer.clearLayers();
  if (res.status !== "ok") { $("status").textContent = `Unreachable: ${res.reason}. No connection is invented.`; return; }
  const active = res.cards.some((c) => c.name === sel) ? sel : res.cards[0].name;
  $("status").innerHTML = `Departure ${res.departure.replace("T", " ")} · budget ${fmtMin(res.budget_s)} · ` +
    `${res.cards.length} distinct route(s)` +
    (res.dropped.length ? ` · dropped: ${res.dropped.map((d) => d.name + " (" + d.why + ")").join(", ")}` : "");
  for (const c of res.cards) {
    const div = document.createElement("div");
    div.className = "card" + (c.name === active ? " sel" : "");
    div.style.setProperty("--c", COLORS[c.name]);
    div.innerHTML = cardHtml(c);
    div.onclick = () => { sel = c.name; renderCards(); };
    $("cards").appendChild(div);
  }
  const order = [...res.cards].sort((a, b) => (a.name === active) - (b.name === active));
  for (const c of order) {
    const on = c.name === active;
    for (const g of c.geometry) {
      const l = L.polyline(g.ll, { color: on ? riskColor(g.r, g.st) : COLORS[c.name], weight: on ? 7 : 4,
        opacity: on ? 0.95 : 0.5, dashArray: g.st === "no_data" ? "6 8" : null });
      l.on("click", (e) => { L.DomEvent.stopPropagation(e); openDrawer(g.id); });
      routeLayer.addLayer(l);
    }
  }
}

$("hour").oninput = () => { $("hourv").textContent = hh(hourVal()); };
$("hour").onchange = () => { loadNetwork(); if (lastRes) findRoutes(); };
$("detour").oninput = () => { $("detv").textContent = (+$("detour").value).toFixed(1); };
$("go").onclick = findRoutes;
$("reset").onclick = resetAll;
(async () => {
  cfg = await api("/api/config");
  $("params").textContent = `TAU=${cfg.tau} · R=${cfg.r_m} m · Δ=${cfg.delta_m} m · unknown counts as concerning`;
  $("hour").oninput(); $("detour").oninput();
  loadNetwork();
})();
