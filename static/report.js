const sessionId = sessionStorage.fnnSession || (sessionStorage.fnnSession = crypto.randomUUID());
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const FIELD_META = {
  lighting_level: { label: "Street Lighting", invert: false },
  activity_level: { label: "Foot Activity", invert: false },
  walkability: { label: "Footpath Quality", invert: false },
  sightline_depth: { label: "Sightline Depth", invert: false },
  open_poi_distance: { label: "Nearby Open POI", invert: true },
  dog_report_risk: { label: "Stray Dog Safety", invert: true },
  waterlogging: { label: "Dry Surface", invert: true }
};

const QUICK_REPORTS = [
  { label: "Dark / Outage (Hinglish)", text: "Hostel ke paas wali road pe light nahi hai, bahut andhera hai" },
  { label: "Path Blocked", text: "Road is blocked by construction barricades" },
  { label: "Dog Pack", text: "Aggressive stray dog pack on this road at night" },
  { label: "Waterlogged", text: "Heavy waterlogging covering the footpath" }
];

async function openDrawer(sid, autoDemo = false) {
  const d = await api(`/api/segment/${encodeURIComponent(sid)}?hour=${hourVal() % 24}`);
  const safetyPct = Math.max(5, Math.round((1 - d.risk) * 100));

  const factorHtml = d.fields.map((f) => {
    const m = FIELD_META[f.field] || { label: f.field, invert: false };
    if (f.missing) {
      return `<div>
        <div class="factor-head"><span>${m.label}</span><span class="missing">Missing (Penalized)</span></div>
        <div class="bar-track"><div class="bar-fill" style="width:30%;background:#94a3b8"></div></div>
      </div>`;
    }
    const safetyVal = m.invert ? 1 - f.value : f.value;
    const pct = Math.round(safetyVal * 100);
    const barColor = pct >= 65 ? "#1e8e3e" : pct >= 40 ? "#f29900" : "#ea4335";
    return `<div>
      <div class="factor-head"><span>${m.label}</span><span style="color:${barColor}">${pct}%</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(6, pct)}%;background:${barColor}"></div></div>
    </div>`;
  }).join("");

  $("drawer").hidden = false;
  $("drawer").innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <span style="font-size:12px;font-weight:800;color:var(--navy-deep);text-transform:uppercase">Road Safety &middot; ${safetyPct}%</span>
      <button class="sec" onclick="$('drawer').hidden=true" style="padding:3px 9px;font-size:11px">Close</button>
    </div>
    <div class="muted" style="margin-bottom:6px">
      Segment <b>${esc(sid)}</b> &middot; ${Math.round(d.length_m)} m &middot; Coverage ${Math.round(d.coverage * 100)}%
      ${d.closed ? ' &middot; <span class="missing">CLOSED</span>' : ""}
    </div>
    <div class="factor-list">${factorHtml}</div>

    <div style="background:var(--lavender-tint);border:1.5px solid var(--lavender-card);border-radius:14px;padding:10px 12px">
      <div style="font-weight:700;font-size:12px;color:var(--navy-deep);margin-bottom:6px">Report Hazard on This Road</div>
      <div class="chip-row">
        ${QUICK_REPORTS.map((q, idx) => `<button class="chip qrep-chip" data-idx="${idx}">${q.label}</button>`).join("")}
      </div>
      <textarea id="rtext" rows="2" placeholder="e.g. Hostel ke paas wali road pe light nahi hai, bahut andhera hai"></textarea>
      <button id="rdraft" class="btn-compute" style="padding:9px 12px;font-size:12.5px">Draft Report</button>
      <div id="rbox"></div>
    </div>`;

  $("rdraft").onclick = () => draftReport(sid);
  document.querySelectorAll(".qrep-chip").forEach((b) => {
    b.onclick = () => {
      $("rtext").value = QUICK_REPORTS[+b.dataset.idx].text;
      draftReport(sid);
    };
  });

  if (autoDemo) {
    $("rtext").value = QUICK_REPORTS[0].text;
    draftReport(sid);
  }
}

async function draftReport(sid) {
  const text = $("rtext").value.trim();
  if (!text) return;
  $("rbox").innerHTML = `<p class="muted" style="margin:6px 0">Extracting structured category…</p>`;
  let d;
  try { d = await api("/api/report/draft", { method: "POST", body: JSON.stringify({ text, segment_id: sid }) }); }
  catch (e) { $("rbox").textContent = "Error: " + e.message; return; }
  const ext = d.extracted || {};
  const badge = d.extraction_mode === "replay" ? '<span class="badge replay">REPLAY (Cached AI)</span>'
    : d.extraction_mode === "live" ? '<span class="badge live-pill">LIVE AI</span>'
    : '<span class="badge warn">Manual Mode</span>';
  const opts = d.categories.map((c) => `<option value="${c}" ${c === ext.category ? "selected" : ""}>${c}</option>`).join("");
  $("rbox").innerHTML = `
    <div style="background:#fff;border-radius:10px;padding:9px;margin-top:8px;border:1px solid var(--color-border)">
      <div style="margin-bottom:4px">${badge}</div>
      ${ext.summary ? `<div style="font-size:11.5px;margin-bottom:4px"><b>Summary:</b> ${esc(ext.summary)}</div>` : ""}
      <select id="rcat" style="margin-top:4px">${opts}</select>
      <button id="rsubmit" class="btn-compute" style="padding:8px 12px;font-size:12px">Confirm &amp; Submit</button>
    </div>`;

  const key = crypto.randomUUID();
  $("rsubmit").onclick = async () => {
    try {
      const r = await api("/api/report/submit", { method: "POST", body: JSON.stringify({
        idempotency_key: key, text, segment_id: sid, category: $("rcat").value,
        extraction_mode: d.extraction_mode, extraction_confidence: ext.extraction_confidence ?? null, session: sessionId }) });
      const repId = r.report.report_id;
      $("rbox").innerHTML = `
        <div style="background:#fff;border-radius:10px;padding:9px;margin-top:8px;border:1.5px solid #1e8e3e">
          <div style="font-size:12px;font-weight:700;color:#145a2b;margin-bottom:6px">Submitted ${repId} (accepted)</div>
          <button id="instantVerifyBtn" class="btn-compute" style="padding:8px 10px;font-size:12px;background:#1e8e3e">
            Verify Now &amp; Reroute Map
          </button>
        </div>`;
      $("instantVerifyBtn").onclick = async () => {
        await api("/api/review/verify", {
          method: "POST",
          headers: { authorization: "Bearer demo-reviewer-token" },
          body: JSON.stringify({ report_id: repId, hour: (hourVal() - 1 + 24) % 24 })
        });
        await loadNetwork();
        if (start && end) await findRoutes();
        await openDrawer(sid, false);
      };
    } catch (e) { $("rbox").insertAdjacentHTML("beforeend", `<p class="missing">${esc(e.message)}</p>`); }
  };
}
