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

$("btnResearch").onclick = async () => {
  const kw = $("kwInput").value.trim();
  if (!kw) { alert("키워드를 입력하세요"); return; }
  $("btnResearch").disabled = true;
  $("researchResult").innerHTML = `<span class="src">'${escapeHtml(kw)}' 조사 중… (5개 소스 검색)</span>`;
  try {
    const r = await api("/api/topics/manual-research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: kw }),
    });
    renderResearch(r);
  } catch (e) {
    $("researchResult").innerHTML = `<span class="src">조사 실패: ${e.message}</span>`;
  }
  $("btnResearch").disabled = false;
};

$("kwInput").addEventListener("keydown", (e) => { if (e.key === "Enter") $("btnResearch").click(); });

function renderResearch(r) {
  const res = r.research;
  const srcLabels = { coupang: "쿠팡", naver_news: "네이버뉴스", naver_blog: "네이버블로그", hackernews: "해커뉴스", reddit: "레딧" };
  let html = `<div class="rsummary">`;
  for (const [k, n] of Object.entries(res.summary)) {
    html += `<span class="pill ${n > 0 ? "has" : ""}">${srcLabels[k] || k}: ${n}</span>`;
  }
  if (res.coupang_price) html += `<span class="price-tag">쿠팡 최저 ${res.coupang_price.toLocaleString()}원</span>`;
  html += `</div>`;

  for (const [src, items] of Object.entries(res.sources)) {
    if (!items || items.length === 0) continue;
    html += `<div class="src-group"><h4>${srcLabels[src] || src} (${items.length})</h4><ul>`;
    items.slice(0, 5).forEach((it) => {
      const t = it.title || it.name || "";
      const meta = it.points ? ` · ${it.points}pts` : (it.price ? ` · ${it.price.toLocaleString()}원` : (it.ups ? ` · ▲${it.ups}` : ""));
      const link = it.url ? `<a class="link" href="${it.url}" target="_blank">${escapeHtml(t.slice(0, 70))}</a>` : escapeHtml(t.slice(0, 70));
      html += `<li>${link}<span class="src">${meta}</span></li>`;
    });
    html += `</ul></div>`;
  }
  html += `<div class="next-step">✅ 조사 완료 (topic_id: ${r.topic_id}). 축: <b>${axisLabel(res.axis)}</b> · 수익화: ${res.coupang_monetizable ? "가능" : "불가"}`;
  if (res.coupang_product) {
    html += `<br>🔗 대표 수익화 제품: <b>${escapeHtml(res.coupang_product)}</b>${res.coupang_price ? ` (${res.coupang_price.toLocaleString()}원)` : ""}`;
  }
  html += `<br>다음 단계: 아래 버튼으로 스토리텔링 앵글 3개를 생성합니다.</div>`;
  html += `<div class="row" style="margin-top:12px">
    <button id="btnAngles" class="primary" data-topic="${r.topic_id}">✨ 앵글 3개 생성</button>
    <span id="angleStatus" class="status"></span>
  </div>`;
  html += `<div id="angleResult"></div>`;
  $("researchResult").innerHTML = html;

  document.getElementById("btnAngles").onclick = async (e) => {
    const tid = e.target.dataset.topic;
    e.target.disabled = true;
    $("angleStatus").textContent = "앵글 생성 중… (Claude 분석, 10~20초)";
    try {
      const ar = await api("/api/angles/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic_id: Number(tid) }),
      });
      if (ar.error) { $("angleStatus").textContent = "실패: " + ar.error; e.target.disabled = false; return; }
      $("angleStatus").textContent = `완료: ${ar.angles.length}개 생성`;
      renderAngles(ar.angles);
    } catch (err) {
      $("angleStatus").textContent = "실패: " + err.message;
      e.target.disabled = false;
    }
  };
}

const ANGLE_LABELS = {
  expectation_gap: { name: "기대갭", color: "#d4537e" },
  hidden_truth: { name: "숨겨진 진실", color: "#534ab7" },
  market_shock: { name: "시장 충격", color: "#ba7517" },
};

function renderAngles(angles) {
  let html = `<div class="angles">`;
  angles.forEach((a) => {
    const lbl = ANGLE_LABELS[a.angle_type] || { name: a.angle_type, color: "#888" };
    const points = (a.data_points || []).map((p) => `<li>${escapeHtml(p)}</li>`).join("");
    html += `<div class="angle-card">
      <div class="angle-type" style="background:${lbl.color}">${lbl.name}</div>
      <div class="angle-title">${escapeHtml(a.title || "")}</div>
      <div class="angle-hook">🎬 훅: ${escapeHtml(a.hook || "")}</div>
      <ul class="angle-points">${points}</ul>
      <div class="angle-close">❓ ${escapeHtml(a.closing_question || "")}</div>
      <div class="row" style="margin-top:12px">
        <button class="primary btn-script" data-angle="${a.id}">🎬 이 앵글로 대본 만들기</button>
        <span class="status script-status"></span>
      </div>
      <div class="script-result"></div>
    </div>`;
  });
  html += `</div>`;
  document.getElementById("angleResult").innerHTML = html;

  document.querySelectorAll(".btn-script").forEach((btn) => {
    btn.onclick = async (e) => {
      const aid = e.target.dataset.angle;
      const card = e.target.closest(".angle-card");
      const statusEl = card.querySelector(".script-status");
      const resultEl = card.querySelector(".script-result");
      e.target.disabled = true;
      statusEl.textContent = "대본 생성 중… (Claude 연출, 15~30초)";
      try {
        const sr = await api("/api/scripts/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ angle_id: Number(aid) }),
        });
        if (sr.error) { statusEl.textContent = "실패: " + sr.error; e.target.disabled = false; return; }
        statusEl.textContent = `완료: ${sr.script.scenes.length}개 장면`;
        renderScript(resultEl, sr.script, aid);
      } catch (err) {
        statusEl.textContent = "실패: " + err.message;
        e.target.disabled = false;
      }
    };
  });
}

const BROLL_COLORS = {
  "제품렌더": "#534ab7", "실물": "#1d9e75", "스크린녹화": "#185fa5",
  "밈": "#d4537e", "그래픽": "#ba7517", "인물": "#993c1d",
};

function renderScript(el, script, angleId) {
  let html = `<div class="script-box">
    <div class="script-head">📝 ${escapeHtml(script.title || "")} · ${script.total_duration_sec || 25}초 · ${script.scenes.length}장면</div>`;
  script.scenes.forEach((s) => {
    const bc = BROLL_COLORS[s.broll_type] || "#888";
    const emph = (s.emphasis || []).map((k) => `<span class="emph">${escapeHtml(k)}</span>`).join(" ");
    const headline = s.headline ? `<div class="sc-headline">🔝 헤드라인: ${escapeHtml(s.headline)}</div>` : "";
    html += `<div class="scene">
      <div class="sc-top">
        <span class="sc-time">${escapeHtml(s.time || "")}</span>
        <span class="sc-broll" style="background:${bc}">${escapeHtml(s.broll_type || "")}</span>
        <span class="sc-sfx">🔊 ${escapeHtml(s.sfx || "")}</span>
      </div>
      ${headline}
      <div class="sc-narr">🎙️ ${escapeHtml(s.narration || "")}</div>
      <div class="sc-cap">💬 ${escapeHtml(s.caption || "")} ${emph}</div>
      <div class="sc-visual">🎬 ${escapeHtml(s.visual || "")}</div>
    </div>`;
  });
  if (script.production_notes) {
    html += `<div class="script-notes">📌 제작노트: ${escapeHtml(script.production_notes)}</div>`;
  }
  html += `<div class="align-row">
    <span class="align-label">🎤 정확한 타이밍:</span>
    <input type="file" class="audio-input" accept="audio/*" data-angle="${angleId}">
    <button class="align-btn" data-angle="${angleId}">음성으로 자막 정렬</button>
    <span class="align-status"></span>
  </div>`;
  html += `<div class="dl-row">
    <a class="dl-btn" href="/api/exports/subtitles/${angleId}.srt" download>📄 SRT 다운로드</a>
    <a class="dl-btn" href="/api/exports/subtitles/${angleId}.fcpxml" download>🎬 FCPXML 다운로드</a>
  </div>
  <div class="dl-help">
    <b>🎬 FCPXML</b>: 내 자막 템플릿(MP네모메모심플) 적용 — FCP에 템플릿이 설치돼 있어야 함.<br>
    &nbsp;&nbsp;FCP에서 <b>파일 → 가져오기 → Final Cut Pro XML</b> → 장면마다 자막 자동 배치<br>
    <b>📄 SRT</b>: 템플릿 없이도 100% 동작. <b>파일 → 가져오기 → 자막</b> (타이밍·텍스트만)<br>
    음성 정렬 안 하면 예상 타임코드로 생성됩니다.
  </div>`;
  html += `</div>`;
  el.innerHTML = html;

  // 음성 업로드 정렬
  const alignBtn = el.querySelector(".align-btn");
  if (alignBtn) {
    alignBtn.onclick = async () => {
      const fileInput = el.querySelector(".audio-input");
      const statusEl = el.querySelector(".align-status");
      if (!fileInput.files.length) { statusEl.textContent = "음성 파일을 선택하세요"; return; }
      alignBtn.disabled = true;
      statusEl.textContent = "음성 분석 중… (Whisper STT, 길이에 따라 10~40초)";
      const fd = new FormData();
      fd.append("audio", fileInput.files[0]);
      try {
        const r = await fetch(`/api/exports/align/${angleId}`, { method: "POST", body: fd });
        const d = await r.json();
        if (d.error) { statusEl.textContent = "실패: " + d.error; alignBtn.disabled = false; return; }
        statusEl.textContent = `✅ 정렬 완료 (${d.duration?.toFixed(1)}초, ${d.scene_count}장면). 이제 다운로드하면 정확한 타이밍이 적용됩니다.`;
      } catch (err) {
        statusEl.textContent = "실패: " + err.message;
        alignBtn.disabled = false;
      }
    };
  }
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
