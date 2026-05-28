let allCandidates = [];
let activeAxis = "all";

const $ = (id) => document.getElementById(id);

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

function setStatus(msg) { $("status").textContent = msg; }

async function loadSummary() {
  try {
    const data = await api("/api/topics/summary?days=5");
    const dates = Object.keys(data.summary).sort().reverse().slice(0, 5);
    if (dates.length === 0) { $("summary").innerHTML = "<span class='src'>아직 수집된 데이터가 없습니다. [지금 수집 실행]을 눌러보세요.</span>"; return; }
    $("summary").innerHTML = dates.map((d) => {
      const s = data.summary[d];
      const srcStr = Object.entries(s.by_source).map(([k, v]) => `${k} ${v}`).join(" · ");
      return `<div class="day-box"><div class="date">${d}</div>
        <div class="total">${s.total}</div>
        <div class="breakdown">${srcStr}</div></div>`;
    }).join("");
  } catch (e) { $("summary").textContent = "요약 로드 실패: " + e.message; }
}

async function loadCandidates() {
  try {
    const data = await api("/api/topics/candidates?limit=300");
    allCandidates = data.candidates || [];
    $("dateLabel").textContent = `(${data.date} · ${data.count}건)`;
    renderCandidates();
  } catch (e) { $("candBody").innerHTML = `<tr><td colspan="6">로드 실패: ${e.message}</td></tr>`; }
}

function renderCandidates() {
  const filtered = activeAxis === "all"
    ? allCandidates
    : allCandidates.filter((c) => c.axis === activeAxis);
  if (filtered.length === 0) {
    $("candBody").innerHTML = `<tr><td colspan="6">해당 후보가 없습니다.</td></tr>`;
    return;
  }
  $("candBody").innerHTML = filtered.map((c) => `
    <tr>
      <td><span class="badge ${c.axis}">${axisLabel(c.axis)}</span></td>
      <td class="src">${c.source}</td>
      <td>${c.keyword || "-"}</td>
      <td class="title">${escapeHtml(c.title || "")}</td>
      <td>${Math.round(c.signal_value || 0)}</td>
      <td>${c.url ? `<a class="link" href="${c.url}" target="_blank">열기</a>` : "-"}</td>
    </tr>`).join("");
}

function axisLabel(a) {
  return { apple: "애플", samsung: "삼성", lanstar_core: "본업", appliance: "가전" }[a] || a;
}
function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

$("btnCollect").onclick = async () => {
  setStatus("수집 실행 중… (1~2분 소요)");
  $("btnCollect").disabled = true;
  try {
    const r = await api("/api/topics/collect-now", { method: "POST" });
    setStatus(`완료: ${r.saved}건 저장 (${JSON.stringify(r.by_source)})`);
    await loadSummary(); await loadCandidates();
  } catch (e) { setStatus("실패: " + e.message); }
  $("btnCollect").disabled = false;
};

$("btnRefresh").onclick = async () => { setStatus("새로고침…"); await loadSummary(); await loadCandidates(); setStatus(""); };

document.querySelectorAll(".chip").forEach((chip) => {
  chip.onclick = () => {
    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    activeAxis = chip.dataset.axis;
    renderCandidates();
  };
});

loadSummary();
loadCandidates();
