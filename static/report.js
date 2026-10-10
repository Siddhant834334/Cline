const sessionId = sessionStorage.fnnSession || (sessionStorage.fnnSession = crypto.randomUUID());
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function openDrawer(sid) {
  const d = await api(`/api/segment/${encodeURIComponent(sid)}?hour=${hourVal() % 24}`);
  const rows = d.fields.map((f) => f.missing
    ? `<tr><td>${f.field}</td><td class="missing" colspan="4">missing (scored with the unknown penalty)</td></tr>`
    : `<tr><td>${f.field}</td><td>${f.value == null ? "–" : f.value.toFixed(2)}</td><td>${f.source}</td>
       <td>${(f.observed_at || "").replace("T", " ")}<br>to ${(f.valid_until || "open").replace("T", " ")}</td><td>${f.review_status}</td></tr>`).join("");
  $("drawer").hidden = false;
  $("drawer").innerHTML = `<b>Segment</b> <span class="muted">${esc(sid)}</span><br>
    risk <b>${d.risk.toFixed(2)}</b> · status <b>${d.status}</b> · coverage ${Math.round(d.coverage * 100)}% · ${Math.round(d.length_m)} m · access ${d.access}
    ${d.closed ? '<br><b class="missing">CLOSED by a verified event</b>' : ""}
    ${d.events.length ? `<br>active events: ${d.events.join(", ")}` : ""}
    <table><tr class="muted"><td>field</td><td>value</td><td>source</td><td>observed / valid until</td><td>review</td></tr>${rows}</table>
    <p class="muted">Raw field values (higher lighting = brighter). Synthetic unless the source column says otherwise.</p>
    <h4>Report a problem here</h4>
    <textarea id="rtext" rows="3" placeholder="e.g. Hostel ke paas wali road pe light nahi hai, bahut andhera hai"></textarea>
    <button id="rdraft">Draft report</button><div id="rbox"></div>`;
  $("rdraft").onclick = () => draftReport(sid);
}

async function draftReport(sid) {
  const text = $("rtext").value.trim();
  if (!text) return;
  $("rbox").textContent = "Extracting…";
  let d;
  try { d = await api("/api/report/draft", { method: "POST", body: JSON.stringify({ text, segment_id: sid }) }); }
  catch (e) { $("rbox").textContent = "Error: " + e.message; return; }
  const ext = d.extracted || {};
  const badge = d.extraction_mode === "replay" ? '<span class="badge replay">REPLAY (cached response)</span>'
    : d.extraction_mode === "live" ? '<span class="badge">LIVE extraction</span>'
    : '<span class="badge warn">MANUAL: extraction unavailable</span>';
  const opts = d.categories.map((c) => `<option ${c === ext.category ? "selected" : ""}>${c}</option>`).join("");
  $("rbox").innerHTML = `<p>${badge} <span class="muted">Draft: nothing saved yet.</span></p>
    <p class="muted">Original text kept verbatim: "${esc(text)}"</p>
    ${ext.summary ? `<p>Summary: ${esc(ext.summary)}</p>` : ""}
    ${ext.extraction_confidence != null ? `<p class="muted">Extraction confidence ${ext.extraction_confidence}: confidence in the parsing, not evidence the incident happened.</p>` : ""}
    <label>Category (correct it if needed)<select id="rcat">${opts}</select></label>
    <button id="rsubmit">Confirm &amp; submit</button>`;
  const key = crypto.randomUUID();
  $("rsubmit").onclick = async () => {
    try {
      const r = await api("/api/report/submit", { method: "POST", body: JSON.stringify({
        idempotency_key: key, text, segment_id: sid, category: $("rcat").value,
        extraction_mode: d.extraction_mode, extraction_confidence: ext.extraction_confidence ?? null, session: sessionId }) });
      $("rbox").innerHTML = `<p>Submitted <b>${r.report.report_id}</b>, state <b>${r.report.state}</b> (unverified).
        ${r.created ? "" : "(same idempotency key: same report)"}<br>
        <span class="muted">This changes no route until an authenticated reviewer verifies it.</span></p>`;
    } catch (e) { $("rbox").insertAdjacentHTML("beforeend", `<p class="missing">Error: ${esc(e.message)}</p>`); }
  };
}
