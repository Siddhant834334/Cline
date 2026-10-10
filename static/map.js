const $ = (id) => document.getElementById(id);

const MODE_CONFIG = {
  fastest: {
    id: "fastest",
    label: "Fastest",
    color: "#222673",
    bg: "#e8e7f8",
    textColor: "#171b5e",
    icon: (active) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="${active ? "#fff" : "#171b5e"}"><path d="M13 2.05v2.02c3.95.49 7 3.85 7 7.93 0 3.21-1.81 6-4.72 7.28L13 17v5l5-3.08C21.49 16.89 23 13.62 23 12c0-5.18-3.95-9.45-10-9.95zM11 2.05C4.95 2.55 1 6.82 1 12c0 1.62 1.51 4.89 5 6.92L11 22v-5l-2.28-1.72C6.81 14 5 11.21 5 8c0-4.08 3.05-7.44 7-7.95v2.02z"/></svg>`
  },
  balanced: {
    id: "balanced",
    label: "Balanced",
    color: "#F29900",
    bg: "#FEF3DC",
    textColor: "#8A5800",
    icon: (active) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="${active ? "#fff" : "#8A5800"}"><path d="M12 3L1 9l4 2.18V15c0 3.31 3.13 5 7 5s7-1.69 7-5v-3.82L21 9 12 3zm2.45 11.19c-.47.44-1.3.81-2.45.81s-1.98-.37-2.45-.81L8.5 13h7l-1.05 1.19zM17 12.5l-5-2.73-5 2.73v-.73l5-2.73 5 2.73v.73z"/></svg>`
  },
  calmest: {
    id: "calmest",
    label: "Safest",
    color: "#1E8E3E",
    bg: "#E6F4EA",
    textColor: "#145A2B",
    icon: (active) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="${active ? "#fff" : "#145A2B"}"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg>`
  }
};

const PLACES = [
  { name: "Disang Hostel, Footpath surrounding Disang", sub: "Hostel Zone, IIT Guwahati, Assam", lat: 26.1862, lng: 91.6938 },
  { name: "Bhupen Hazarika Auditorium, Footpath", sub: "Academic Complex, IIT Guwahati", lat: 26.18951, lng: 91.7002911 },
  { name: "Tower E, Lohit & Umiam Hostels", sub: "Hostel Zone, IIT Guwahati, Assam", lat: 26.1872635, lng: 91.6957466 },
  { name: "Academic Core & Lecture Halls", sub: "Core 1–5 Complex, IIT Guwahati", lat: 26.18951, lng: 91.7002911 },
  { name: "Kameng & Barak Hostels", sub: "Hostel Avenue, IIT Guwahati", lat: 26.1881, lng: 91.6912 },
  { name: "Brahmaputra & Dihing Hostels", sub: "Western Hostel Zone, IIT Guwahati", lat: 26.1868, lng: 91.6895 },
  { name: "Subansiri & Dhansiri Hostels", sub: "Central Hostel Road, IIT Guwahati", lat: 26.1902, lng: 91.6942 },
  { name: "Manas, Siang & Kapili Hostels", sub: "Hostel Sector, IIT Guwahati", lat: 26.1876, lng: 91.6928 },
  { name: "Lakshmibai National Central Library", sub: "Computer & Information Center, IITG", lat: 26.1922, lng: 91.6965 },
  { name: "New Student Activity Centre (SAC)", sub: "Gymkhana & Sports Complex, IITG", lat: 26.1905, lng: 91.6920 },
  { name: "IITG Hospital & Medical Centre", sub: "Guest House Road, IIT Guwahati", lat: 26.1948, lng: 91.6995 },
  { name: "Main Gate & Research Park", sub: "Amingaon Entrance, North Guwahati", lat: 26.1970, lng: 91.6915 },
  { name: "Serpentine Lake Promenade", sub: "Central Campus Viewpoint, IITG", lat: 26.1915, lng: 91.6950 },
  { name: "Khoka Market & Food Court", sub: "Campus Commercial Hub, IITG", lat: 26.1888, lng: 91.6885 },
  { name: "D-Type Faculty Quarters", sub: "Residential Sector, South IITG", lat: 26.1850, lng: 91.6905 }
];

const RECENT_ITEMS = [
  {
    from: { name: "Disang Hostel, Footpath surrounding...", sub: "Hostel Zone, IIT Guwahati", lat: 26.1862, lng: 91.6938 },
    to: { name: "Bhupen Hazarika Auditorium, Footpat...", sub: "Academic Core, IIT Guwahati", lat: 26.18951, lng: 91.7002911 }
  }
];

/* Initialize Leaflet Map */
const map = L.map("map", { zoomControl: true }).setView([26.1895, 91.6965], 15);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 19
}).addTo(map);

let cfg = {};
let start = null;
let end = null;
let placing = "source";
let markers = [];
let lastRes = null;
let sel = "calmest";
let heatmapVisible = true;
let travelProfile = "driving";

const baseLayer = L.layerGroup().addTo(map);
const routeLayer = L.layerGroup().addTo(map);

function lumaHeatColor(safetyScore) {
  const t = Math.max(0, Math.min(1, safetyScore));
  if (t <= 0.5) {
    const k = t / 0.5;
    return `rgb(234,${Math.round(67 + 121 * k)},${Math.round(53 - 49 * k)})`;
  }
  const n = (t - 0.5) / 0.5;
  return `rgb(${Math.round(249 - 197 * n)},${Math.round(171 - 3 * n)},${Math.round(0 + 83 * n)})`;
}

function parseDepartureTime() {
  const raw = ($("hour")?.value || "22:00").trim();
  if (raw.includes(":")) {
    const [hStr, mStr] = raw.split(":");
    const h = parseInt(hStr, 10);
    const m = parseInt(mStr, 10);
    return {
      hour: Number.isNaN(h) ? 22 : ((h % 24) + 24) % 24,
      minute: Number.isNaN(m) ? 0 : Math.max(0, Math.min(59, m))
    };
  }
  const n = parseInt(raw, 10);
  return {
    hour: Number.isNaN(n) ? 22 : ((n % 24) + 24) % 24,
    minute: 0
  };
}
const hourVal = () => parseDepartureTime().hour;
const minuteVal = () => parseDepartureTime().minute;
const hh = (h, m = 0) => `${String(h % 24).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
const fmtMin = (s) => {
  const m = Math.round(s / 60);
  return m < 1 ? "<1 min" : `${m} min`;
};

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "content-type": "application/json", ...(opts.headers || {}) }, ...opts });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || r.status);
  return j;
}

function makeLumaPin(color, letter) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="40" viewBox="0 0 28 40">
    <path d="M14 0C6.27 0 0 6.27 0 14c0 10.5 14 26 14 26s14-15.5 14-26C28 6.27 21.73 0 14 0z" fill="${color}"/>
    <circle cx="14" cy="14" r="6" fill="white"/>
    <text x="14" y="17" text-anchor="middle" fill="${color}" font-size="9" font-weight="700" font-family="Inter,sans-serif">${letter}</text>
  </svg>`;
  return L.divIcon({ html: svg, className: "", iconSize: [28, 40], iconAnchor: [14, 40], tooltipAnchor: [0, -40] });
}

function syncMarkers() {
  markers.forEach((m) => m.remove());
  markers = [];
  if (start) {
    markers.push(
      L.marker([start.lat, start.lng], { icon: makeLumaPin("#222673", "A") })
        .bindTooltip("Origin", { className: "luma-tooltip", direction: "top", offset: [0, -40] })
        .addTo(map)
    );
  }
  if (end) {
    markers.push(
      L.marker([end.lat, end.lng], { icon: makeLumaPin("#171b5e", "B") })
        .bindTooltip("Destination", { className: "luma-tooltip", direction: "top", offset: [0, -40] })
        .addTo(map)
    );
  }
}

async function loadNetwork() {
  const net = await api(`/api/network?hour=${hourVal() % 24}`);
  baseLayer.clearLayers();
  for (const s of net.segments) {
    const safety = s.st === "no_data" ? 0.25 : Math.max(0.05, 1 - s.r);
    const pct = Math.round(safety * 100);
    const col = s.closed ? "#171b5e" : lumaHeatColor(safety);
    const line = L.polyline(s.ll, {
      color: col,
      weight: s.closed ? 4.5 : 3,
      opacity: s.closed ? 0.9 : 0.62,
      lineCap: "round",
      dashArray: s.closed ? "4 6" : null
    });
    line.bindTooltip(`<div>Safety: <b>${pct}%</b></div>`, {
      className: "luma-tooltip",
      direction: "top",
      sticky: true
    });
    line.on("mouseover", function () { this.setStyle({ weight: 5, opacity: 0.9 }); });
    line.on("mouseout", function () { this.setStyle({ weight: s.closed ? 4.5 : 3, opacity: s.closed ? 0.9 : 0.62 }); });
    line.on("click", (e) => {
      L.DomEvent.stopPropagation(e);
      openDrawer(s.id);
    });
    baseLayer.addLayer(line);
  }
}

function syncUIState() {
  const hasRoutes = !!(lastRes && lastRes.status === "ok" && lastRes.cards && lastRes.cards.length);
  const step = start ? (end ? 3 : 2) : 1;

  $("fromDot").classList.toggle("empty", !start);
  $("toSq").classList.toggle("empty", !end);
  $("clearFromBtn").hidden = !start && !$("fromInput").value;
  $("clearToBtn").hidden = !end && !$("toInput").value;
  $("fromInput").classList.toggle("filled", !!start);
  $("toInput").classList.toggle("filled", !!end);
  $("fromInput").classList.toggle("active", placing === "source");
  $("toInput").classList.toggle("active", placing === "destination");

  $("sbar1").className = "step-bar-seg " + (step > 1 ? "done" : "current");
  $("sbar2").className = "step-bar-seg " + (step > 2 ? "done" : step === 2 ? "current" : "");
  $("sbar3").className = "step-bar-seg " + (step === 3 ? "done" : "");

  if (step === 1) {
    $("stepCaption").innerHTML = `<strong>Step 1</strong> of 3 &mdash; Set your starting point`;
  } else if (step === 2) {
    $("stepCaption").innerHTML = `<strong>Step 2</strong> of 3 &mdash; Choose your destination`;
  } else {
    $("stepCaption").innerHTML = `<strong>Step 3</strong> of 3 &mdash; Search your route`;
  }

  if (placing && !hasRoutes) {
    $("placingHint").hidden = false;
    $("placingText").innerHTML = `Tap the map to set your <strong>${placing}</strong>`;
    map.getContainer().style.cursor = "crosshair";
  } else {
    $("placingHint").hidden = true;
    map.getContainer().style.cursor = "";
  }

  $("go").disabled = !(start && end);
  $("goLabel").textContent = hasRoutes ? "Update Route" : "Compute Safe Route";

  $("sidebar").className = hasRoutes ? "docked-mode" : "floating-mode";
  $("stepSection").hidden = hasRoutes;
  $("timeBudgetWrap").hidden = false;
  $("sidebarFooter").hidden = hasRoutes;
  $("recentPanel").hidden = hasRoutes;
  if ($("mapCenterPrompt")) $("mapCenterPrompt").hidden = !!(start || end || hasRoutes);
  $("modePillsRow").hidden = !hasRoutes;
  $("route-panel-wrap").hidden = !hasRoutes;
  $("backToSearchBtn").hidden = !hasRoutes;
  $("topRightStack").classList.toggle("shifted", hasRoutes);
  $("locBtnLabel").textContent = hasRoutes ? "Center route" : "My location";
}

function setupAutocomplete(inputEl, dropEl, listEl, isSource) {
  function findMatchingPlaces(filterText) {
    const q = (filterText || "").trim().toLowerCase();
    return PLACES.filter((p) => !q || p.name.toLowerCase().includes(q) || p.sub.toLowerCase().includes(q));
  }

  function applyChoice(chosen) {
    inputEl.value = chosen.name;
    dropEl.hidden = true;
    if (isSource) {
      start = { lat: chosen.lat, lng: chosen.lng, label: chosen.name };
      placing = end ? null : "destination";
    } else {
      end = { lat: chosen.lat, lng: chosen.lng, label: chosen.name };
      placing = null;
    }
    syncMarkers();
    syncUIState();
  }

  function renderList(filterText) {
    const matches = findMatchingPlaces(filterText);
    listEl.innerHTML = matches.map((p, idx) => `
      <li class="ac-item" data-idx="${idx}">
        <div class="ac-pin-circle">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
        </div>
        <div>
          <div class="ac-name">${p.name}</div>
          <div class="ac-sub">${p.sub}</div>
        </div>
      </li>
    `).join("");

    listEl.querySelectorAll(".ac-item").forEach((li) => {
      li.onmousedown = (e) => {
        e.preventDefault();
        applyChoice(matches[+li.dataset.idx]);
      };
    });
    dropEl.hidden = matches.length === 0;
  }

  inputEl.onfocus = () => {
    placing = isSource ? "source" : "destination";
    syncUIState();
    renderList(inputEl.value === (isSource ? start?.label : end?.label) ? "" : inputEl.value);
  };
  inputEl.oninput = () => {
    renderList(inputEl.value);
    const matches = findMatchingPlaces(inputEl.value);
    if (inputEl.value.trim().length >= 2 && matches.length > 0) {
      const top = matches[0];
      if (isSource) start = { lat: top.lat, lng: top.lng, label: top.name };
      else end = { lat: top.lat, lng: top.lng, label: top.name };
      syncMarkers();
      syncUIState();
    }
  };
  inputEl.onkeydown = (e) => {
    if (e.key === "Enter") {
      const matches = findMatchingPlaces(inputEl.value);
      if (matches.length > 0) applyChoice(matches[0]);
    }
  };
  inputEl.onblur = () => setTimeout(() => { dropEl.hidden = true; }, 160);
}

function renderRecent() {
  $("recentList").innerHTML = RECENT_ITEMS.map((item, i) => `
    <li>
      <button type="button" class="recent-btn" data-i="${i}">
        <div class="recent-line">
          <span style="width:8px;height:8px;border-radius:50%;background:#1A73E8;margin-top:4px;flex-shrink:0"></span>
          <span>${item.from.name}</span>
        </div>
        <div class="recent-line dest">
          <span style="width:8px;height:8px;border-radius:2px;background:#EA4335;margin-top:4px;flex-shrink:0"></span>
          <span>${item.to.name}</span>
        </div>
      </button>
    </li>
  `).join("");

  $("recentList").querySelectorAll(".recent-btn").forEach((btn) => {
    btn.onclick = () => {
      const item = RECENT_ITEMS[+btn.dataset.i];
      start = { lat: item.from.lat, lng: item.from.lng, label: item.from.name };
      end = { lat: item.to.lat, lng: item.to.lng, label: item.to.name };
      $("fromInput").value = item.from.name;
      $("toInput").value = item.to.name;
      placing = null;
      syncMarkers();
      findRoutes();
    };
  });
}

map.on("click", async (e) => {
  const { lat, lng } = e.latlng;
  const isSource = placing === "source" || !start;
  const fallbackLabel = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  if (isSource) {
    start = { lat, lng, label: fallbackLabel };
    $("fromInput").value = fallbackLabel;
    placing = end ? null : "destination";
  } else {
    end = { lat, lng, label: fallbackLabel };
    $("toInput").value = fallbackLabel;
    placing = null;
  }
  syncMarkers();
  syncUIState();

  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`, {
      headers: { "Accept-Language": "en-US,en;q=0.9" }
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.display_name) {
        const pretty = data.display_name.split(",").slice(0, 2).join(", ").trim();
        if (isSource && start && Math.abs(start.lat - lat) < 1e-5) {
          start.label = pretty;
          $("fromInput").value = pretty;
        } else if (!isSource && end && Math.abs(end.lat - lat) < 1e-5) {
          end.label = pretty;
          $("toInput").value = pretty;
        }
      }
    }
  } catch (_) {}
});

async function findRoutes() {
  if (!start || !end) return;
  $("goLabel").textContent = "Computing routes…";
  try {
    lastRes = await api("/api/route", {
      method: "POST",
      body: JSON.stringify({
        start: [start.lat, start.lng],
        end: [end.lat, end.lng],
        hour: hourVal() % 24,
        minute: minuteVal(),
        detour: +$("detour").value
      })
    });
  } catch (e) {
    $("status").textContent = "Error: " + e.message;
    syncUIState();
    return;
  }
  $("status").textContent = "";
  renderCards();
}

function renderCards() {
  const res = lastRes;
  routeLayer.clearLayers();
  if (!res || res.status !== "ok" || !res.cards.length) {
    $("status").textContent = res ? `Unreachable: ${res.reason}` : "";
    syncUIState();
    return;
  }

  const active = res.cards.some((c) => c.name === sel) ? sel : (res.cards.some((c) => c.name === "calmest") ? "calmest" : res.cards[0].name);
  sel = active;
  syncUIState();

  $("modePillsRow").innerHTML = res.cards.map((c) => {
    const m = MODE_CONFIG[c.name] || MODE_CONFIG.calmest;
    const isSel = c.name === active;
    const title = c.also && c.also.length ? `${m.label} & ${c.also.map((a) => MODE_CONFIG[a]?.label || a).join(" & ")}` : m.label;
    return `<button class="route-mode-pill" data-m="${c.name}" style="border-color:${isSel ? m.color : "#DDD5C8"};background:${isSel ? m.color : "#fff"};color:${isSel ? "#fff" : m.textColor};box-shadow:${isSel ? `0 3px 10px ${m.color}40` : "none"}">
      ${m.icon(isSel)} <span>${title}</span>
    </button>`;
  }).join("");

  $("modePillsRow").querySelectorAll(".route-mode-pill").forEach((b) => {
    b.onclick = () => {
      sel = b.dataset.m;
      renderCards();
    };
  });

  const cur = res.cards.find((c) => c.name === active) || res.cards[0];
  const fast = res.cards.find((c) => c.name === "fastest" || (c.also && c.also.includes("fastest"))) || res.cards[0];
  const m = MODE_CONFIG[cur.name] || MODE_CONFIG.calmest;

  const safetyPct = cur.length_m > 0 ? Math.max(8, Math.round(((cur.length_m - cur.concerning_m) / cur.length_m) * 100)) : 85;
  const safetyTier = safetyPct >= 75 ? "High Safety" : safetyPct >= 55 ? "Moderate Safety" : "Low Safety";
  const safetyColor = safetyPct >= 75 ? "#1E8E3E" : safetyPct >= 55 ? "#F29900" : "#EA4335";
  const timeDiff = Math.round(cur.time_s - fast.time_s);
  const distKm = (cur.length_m / 1000).toFixed(1);
  const stretchSaved = Math.round(fast.longest_stretch_m - cur.longest_stretch_m);
  const travelText = travelProfile === "foot" ? "Walk" : "Drive";

  const aiText = cur.name === "calmest"
    ? `Prioritizes well-lit, low-risk roads. Avg safety: ${safetyPct}%. Caps longest dark stretch to ${Math.round(cur.longest_stretch_m)} m. Recommended for night travel.`
    : cur.name === "fastest"
    ? `Quickest path (${fmtMin(cur.time_s)}) but passes a ${Math.round(cur.longest_stretch_m)} m dark stretch. Switch to Safest for stronger protection.`
    : `Balanced: keeps longest dark stretch under ${Math.round(cur.longest_stretch_m)} m while keeping ${safetyPct}% safety — a smart everyday choice.`;

  $("cards").innerHTML = `
    <div class="rp-header">
      <div class="rp-title-group">
        <div class="rp-icon-badge" style="background:${m.color}18;color:${m.color}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>
        </div>
        <div>
          <h2 class="rp-h2">${m.label} &middot; ${travelText}</h2>
          <p class="rp-sub">Safety analysis for your selected path</p>
        </div>
      </div>
      <button class="sec" id="simHazardBtn" style="font-size:11.5px;padding:5px 11px">Report / Test Hazard on Route</button>
    </div>

    <div class="rp-stats-row">
      <div class="rp-stat-card">
        <div class="rp-stat-top">
          <div class="rp-stat-ico" style="background:#E8F0FE;color:#1A73E8">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z"/></svg>
          </div>
          <span class="rp-stat-lbl">Travel Time</span>
        </div>
        <span class="rp-stat-val">${fmtMin(cur.time_s)}</span>
        <span class="rp-stat-sub" style="color:${timeDiff > 0 ? "#F29900" : "#1E8E3E"}">${timeDiff > 0 ? `+${timeDiff}s vs fastest` : "Shortest possible"}</span>
      </div>

      <div class="rp-stat-card">
        <div class="rp-stat-top">
          <div class="rp-stat-ico" style="background:${safetyColor}18;color:${safetyColor}">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>
          </div>
          <span class="rp-stat-lbl">Safety Score</span>
        </div>
        <span class="rp-stat-val">${safetyPct}%</span>
        <span class="rp-stat-sub" style="color:${safetyColor}">${safetyTier}</span>
      </div>

      <div class="rp-stat-card">
        <div class="rp-stat-top">
          <div class="rp-stat-ico" style="background:#F0EBE2;color:#6B6259">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M21 3L3 10.53v.98l6.84 2.65L12.48 21h.98L21 3z"/></svg>
          </div>
          <span class="rp-stat-lbl">Est. Distance</span>
        </div>
        <span class="rp-stat-val">${distKm} km</span>
        <span class="rp-stat-sub" style="color:#9C9284">Actual road distance</span>
      </div>

      <div class="rp-stat-card">
        <div class="rp-stat-top">
          <div class="rp-stat-ico" style="background:${m.color}18;color:${m.color}">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
          </div>
          <span class="rp-stat-lbl">${cur.name === "fastest" ? "Safety Tradeoff" : "Safety Gain"}</span>
        </div>
        <span class="rp-stat-val">${cur.name === "fastest" ? "—" : `-${stretchSaved} m`}</span>
        <span class="rp-stat-sub" style="color:${cur.name === "fastest" ? "#EA4335" : m.color}">${cur.name === "fastest" ? "Switch to Safest for protection" : "shorter dark stretch vs fastest"}</span>
      </div>
    </div>

    <div class="rp-level-wrap">
      <div class="rp-level-head">
        <span class="rp-level-lbl">Route Safety Level</span>
        <span style="font-size:10.5px;font-weight:700;color:${m.color}">${safetyPct}% safe</span>
      </div>
      <div class="rp-level-track">
        <div class="rp-level-fill" style="width:${safetyPct}%;background:linear-gradient(90deg, ${safetyColor}80, ${m.color})"></div>
      </div>
      <div class="rp-level-ticks">
        <span style="color:#EA4335">Low</span>
        <span style="color:#F29900">Moderate</span>
        <span style="color:#1E8E3E">High</span>
      </div>
    </div>

    <div class="rp-eval-box" style="border-color:${m.color}40">
      <div style="display:flex;gap:10px;align-items:flex-start">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="${m.color}" style="flex-shrink:0;margin-top:2px">
          <path d="M19 3l-1.4 3.1L14.5 7.5l3.1 1.4L19 12l1.4-3.1L23.5 7.5l-3.1-1.4L19 3zm-7 3L8.5 12.5 2 16l6.5 3.5L12 26l3.5-6.5L22 16l-6.5-3.5L12 6z"/>
        </svg>
        <div>
          <p style="font-size:11px;color:#1A73E8;font-weight:800;text-transform:uppercase;letter-spacing:0.02em;margin-bottom:3px">AI Evaluation</p>
          <p style="font-size:11.5px;color:#3C4043;font-weight:500;line-height:1.5">${aiText}</p>
        </div>
      </div>
      <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end;flex-shrink:0">
        ${cur.reason_codes.map((rc) => `<span class="hl-pill">${rc}</span>`).join("")}
      </div>
    </div>
  `;

  $("simHazardBtn").onclick = () => {
    const seg = cur.geometry.find((g) => !g.conc) || cur.geometry[0];
    if (seg) openDrawer(seg.id, true);
  };

  const order = [...res.cards].sort((a, b) => (a.name === active) - (b.name === active));
  const boundsPts = [];
  for (const c of order) {
    const isSel = c.name === active;
    const mCfg = MODE_CONFIG[c.name] || MODE_CONFIG.calmest;
    const cSafePct = c.length_m > 0 ? Math.max(8, Math.round(((c.length_m - c.concerning_m) / c.length_m) * 100)) : 85;
    for (const g of c.geometry) {
      if (isSel) boundsPts.push(...g.ll);
      const line = L.polyline(g.ll, {
        color: mCfg.color,
        weight: isSel ? 5 : 4,
        opacity: isSel ? 0.9 : 0.6,
        dashArray: isSel ? null : "1, 8",
        lineCap: "round",
        lineJoin: "round"
      });
      line.bindTooltip(
        `<div style="display:flex;flex-direction:column;gap:2px">
          <span style="font-weight:600;color:${mCfg.color}">${mCfg.label} &middot; ${travelText}</span>
          <span>ETA: ${fmtMin(c.time_s)}</span>
          <span>Safety: ${cSafePct}%</span>
        </div>`,
        { className: "luma-tooltip", direction: "top", sticky: true }
      );
      line.on("click", (e) => {
        L.DomEvent.stopPropagation(e);
        if (!isSel) {
          sel = c.name;
          renderCards();
        } else {
          openDrawer(g.id);
        }
      });
      routeLayer.addLayer(line);
    }
  }

  if (boundsPts.length) {
    map.fitBounds(boundsPts, { paddingTopLeft: [60, 60], paddingBottomRight: [60, 240], maxZoom: 16 });
  }
}

$("clearFromBtn").onclick = (e) => {
  e.stopPropagation();
  start = null;
  $("fromInput").value = "";
  lastRes = null;
  routeLayer.clearLayers();
  placing = "source";
  syncMarkers();
  syncUIState();
};

$("clearToBtn").onclick = (e) => {
  e.stopPropagation();
  end = null;
  $("toInput").value = "";
  lastRes = null;
  routeLayer.clearLayers();
  placing = "destination";
  syncMarkers();
  syncUIState();
};

$("backToSearchBtn").onclick = () => {
  lastRes = null;
  routeLayer.clearLayers();
  $("drawer").hidden = true;
  placing = null;
  syncUIState();
};

$("btn-heatmap-toggle").onclick = () => {
  heatmapVisible = !heatmapVisible;
  $("btn-heatmap-toggle").classList.toggle("active-primary", heatmapVisible);
  if ($("heatmapIcon")) $("heatmapIcon").setAttribute("fill", heatmapVisible ? "#ffffff" : "#222673");
  $("heatmapDot").style.display = heatmapVisible ? "inline-block" : "none";
  if (heatmapVisible) baseLayer.addTo(map);
  else map.removeLayer(baseLayer);
};

$("btn-my-location").onclick = () => {
  if (lastRes && lastRes.cards && lastRes.cards.length) {
    renderCards();
  } else {
    map.flyTo([26.1895, 91.6965], 15, { duration: 1.0 });
  }
};

$("mode-drive").onclick = () => {
  travelProfile = "driving";
  $("mode-drive").classList.add("active");
  $("mode-walk").classList.remove("active");
  $("profileLabel").textContent = "Driving routes";
  if (lastRes) renderCards();
};

$("mode-walk").onclick = () => {
  travelProfile = "foot";
  $("mode-walk").classList.add("active");
  $("mode-drive").classList.remove("active");
  $("profileLabel").textContent = "Walking routes";
  if (lastRes) renderCards();
};

$("hour").oninput = () => {
  const dep = parseDepartureTime();
  if ($("hourv")) $("hourv").textContent = hh(dep.hour, dep.minute);
};
$("hour").onchange = () => {
  const dep = parseDepartureTime();
  if ($("hourv")) $("hourv").textContent = hh(dep.hour, dep.minute);
  loadNetwork();
  if (start && end && lastRes) findRoutes();
};
if ($("nowTimeBtn")) {
  $("nowTimeBtn").onclick = () => {
    const now = new Date();
    const val = hh(now.getHours(), now.getMinutes());
    $("hour").value = val;
    if ($("hourv")) $("hourv").textContent = val;
    loadNetwork();
    if (start && end && lastRes) findRoutes();
  };
}

$("detour").oninput = () => {
  const extraPct = Math.round((+$("detour").value - 1) * 100);
  $("detv").textContent = extraPct <= 0 ? "Shortest only" : `Up to +${extraPct}%`;
};
$("detour").onchange = () => {
  if (start && end && lastRes) findRoutes();
};

$("go").onclick = findRoutes;
$("reset").onclick = () => {
  start = end = lastRes = null;
  $("fromInput").value = "";
  $("toInput").value = "";
  routeLayer.clearLayers();
  syncMarkers();
  syncUIState();
};

(async () => {
  cfg = await api("/api/config");
  $("params").textContent = `TAU=${cfg.tau} · R=${cfg.r_m} m · Δ=${cfg.delta_m} m`;
  setupAutocomplete($("fromInput"), $("fromDropdown"), $("fromList"), true);
  setupAutocomplete($("toInput"), $("toDropdown"), $("toList"), false);
  renderRecent();

  $("profileLabel").textContent = "Driving routes";
  placing = "source";
  syncMarkers();
  syncUIState();
  await loadNetwork();
  if (!heatmapVisible) map.removeLayer(baseLayer);
})();
