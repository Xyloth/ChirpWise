const state = {
  view: "dashboard",
  summary: null,
  filters: { families: [], sounds: [], regions: [], taxonomy_regions: [] },
  browse: {
    search: "",
    family: "",
    sound: "",
    region: "all",
    order: "common",
  },
  species: [],
  selectedSpeciesId: null,
  selectedSpecies: null,
  quiz: {
    sessionId: null,
    question: null,
    selectedId: null,
    reveal: null,
    startedAt: null,
  },
  settings: loadSettings(),
};

const titles = {
  dashboard: ["Dashboard", "Training overview and dataset health."],
  browse: ["Browse Birds", "Search the local library and inspect clips, metadata, and similar species."],
  quiz: ["Quiz", "Listen first, choose carefully, then review the source and distractors."],
  progress: ["Progress", "Accuracy by species, family, and recent sessions."],
  coverage: ["Dataset Coverage", "Find species with strong, partial, or missing local audio coverage."],
  attributions: ["Attributions", "Recording source, recordist, license, and generated attribution text."],
  settings: ["Settings", "Local quiz preferences stored in this browser profile."],
};

const content = document.querySelector("#content");
const viewTitle = document.querySelector("#view-title");
const viewSubtitle = document.querySelector("#view-subtitle");

document.querySelectorAll(".nav-button").forEach((button) => {
  button.addEventListener("click", () => navigate(button.dataset.view));
});

document.querySelector("#quick-quiz").addEventListener("click", () => navigate("quiz"));

window.addEventListener("popstate", () => {
  const view = new URL(location.href).searchParams.get("view") || "dashboard";
  state.view = view;
  render();
});

content.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (action === "select-species") {
    state.selectedSpeciesId = Number(target.dataset.id);
    await loadSpeciesDetail(state.selectedSpeciesId);
    renderBrowse();
  }
  if (action === "new-question") {
    await newQuestion();
  }
  if (action === "choose-answer") {
    state.quiz.selectedId = Number(target.dataset.id);
    renderQuiz();
  }
  if (action === "submit-answer") {
    await submitAnswer();
  }
  if (action === "reset-progress") {
    if (confirm("Reset all quiz attempts?")) {
      await api("/api/progress/reset", { method: "POST", body: "{}" });
      toast("Progress reset.");
      await refreshCommon();
      render();
    }
  }
});

content.addEventListener("input", async (event) => {
  const target = event.target;
  if (target.matches("[data-filter]")) {
    state.browse[target.dataset.filter] = target.value;
    await loadSpeciesList();
    renderBrowse();
  }
  if (target.matches("[data-setting]")) {
    const key = target.dataset.setting;
    if (target.type === "checkbox") {
      state.settings[key] = target.checked;
    } else if (target.type === "number" || target.type === "range") {
      state.settings[key] = Number(target.value);
    } else {
      state.settings[key] = target.value;
    }
    saveSettings();
    render();
  }
});

async function init() {
  await refreshCommon();
  const urlView = new URL(location.href).searchParams.get("view");
  state.view = urlView || "dashboard";
  await loadSpeciesList();
  document.querySelector("#db-status").classList.add("ok");
  render();
}

async function refreshCommon() {
  const [summary, filters] = await Promise.all([api("/api/summary"), api("/api/filters")]);
  state.summary = summary;
  state.filters = filters;
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(path, { ...options, headers });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || response.statusText);
  }
  return payload;
}

function navigate(view) {
  state.view = view;
  const url = new URL(location.href);
  url.searchParams.set("view", view);
  history.pushState({}, "", url);
  render();
}

function render() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
  const [title, subtitle] = titles[state.view] || titles.dashboard;
  viewTitle.textContent = title;
  viewSubtitle.textContent = subtitle;
  if (state.view === "dashboard") renderDashboard();
  if (state.view === "browse") renderBrowse();
  if (state.view === "quiz") renderQuiz();
  if (state.view === "progress") renderProgress();
  if (state.view === "coverage") renderCoverage();
  if (state.view === "attributions") renderAttributions();
  if (state.view === "settings") renderSettings();
}

function renderDashboard() {
  const s = state.summary || {};
  content.innerHTML = `
    <div class="grid cols-3">
      ${metric("Species", s.species ?? 0, "Taxa in the current scope")}
      ${metric("Recordings", s.recordings ?? 0, "Metadata rows with license tracking")}
      ${metric("Quiz Clips", s.clips ?? 0, "Playable local practice clips")}
    </div>
    <div class="grid cols-2">
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2>Training State</h2>
            <p>Weak-species review uses your missed answers once you have attempts recorded.</p>
          </div>
          <button class="primary-button" data-action="new-question">Queue Question</button>
        </div>
        <div class="grid cols-2">
          ${metric("Attempts", s.answered ?? 0, "Total quiz answers")}
          ${metric("Accuracy", percentText(s.accuracy), "Across all sessions")}
        </div>
      </section>
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2>Families</h2>
            <p>Current taxonomy and recordings are loaded from the local SQLite dataset.</p>
          </div>
        </div>
        ${familyBars(s.families || [])}
      </section>
    </div>
    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>Latest Dataset Build</h2>
          <p>Build records make coverage and license policy auditable.</p>
        </div>
      </div>
      ${buildSummary(s.latest_build)}
    </section>
  `;
}

async function loadSpeciesList() {
  const params = new URLSearchParams();
  const search = state.browse.search || "";
  const family = state.browse.family || "";
  const sound = state.browse.sound || "";
  const region = state.browse.region || "all";
  const order = state.browse.order || "common";
  if (search) params.set("search", search);
  if (family) params.set("family", family);
  if (sound) params.set("sound", sound);
  if (region && region !== "all") params.set("region", region);
  params.set("order", order);
  const payload = await api(`/api/species?${params}`);
  state.species = payload.species;
}

async function loadSpeciesDetail(id) {
  state.selectedSpecies = await api(`/api/species/${id}`);
}

function renderBrowse() {
  const selected = state.selectedSpecies;
  content.innerHTML = `
    <div class="split-view">
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2>Library</h2>
            <p>${state.species.length} species match the current filters.</p>
          </div>
        </div>
        <div class="field-row">
          <input class="input" data-filter="search" value="${escapeAttr(state.browse.search)}" placeholder="Search common, scientific, or eBird code">
          ${select("family", "All families", state.filters.families, state.browse.family)}
          ${select("sound", "All sounds", state.filters.sounds, state.browse.sound)}
          ${regionSelect("region", state.browse.region)}
          <select class="select" data-filter="order">
            <option value="common" ${state.browse.order === "common" ? "selected" : ""}>Common name</option>
            <option value="family" ${state.browse.order === "family" ? "selected" : ""}>Family</option>
            <option value="clips" ${state.browse.order === "clips" ? "selected" : ""}>Most clips</option>
            <option value="difficulty" ${state.browse.order === "difficulty" ? "selected" : ""}>Difficulty</option>
          </select>
        </div>
        <div class="species-list" style="margin-top:14px">
          ${state.species.map(speciesRow).join("") || `<div class="empty">No species match those filters.</div>`}
        </div>
      </section>
      <section class="detail-stack">
        ${selected ? speciesDetail(selected) : `<div class="empty">Select a species to inspect recordings, clips, and similar birds.</div>`}
      </section>
    </div>
  `;
  drawWaveforms();
}

function speciesRow(s) {
  return `
    <button class="species-row" data-action="select-species" data-id="${s.id}">
      <span>
        <strong>${escapeHtml(s.common_name)}</strong>
        <span class="latin">${escapeHtml(s.scientific_name)}</span>
        <span class="meta-line">
          <span>${escapeHtml(s.family || "Unknown family")}</span>
          <span>${s.recording_count} recordings</span>
          <span>${s.clip_count} clips</span>
        </span>
      </span>
      <span class="tag ${s.accuracy == null ? "gold" : "blue"}">${s.accuracy == null ? "untrained" : percentText(s.accuracy)}</span>
    </button>
  `;
}

function speciesDetail(payload) {
  const s = payload.species;
  return `
    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>${escapeHtml(s.common_name)}</h2>
          <p><em>${escapeHtml(s.scientific_name)}</em></p>
        </div>
        <span class="tag">${escapeHtml(s.family || "Unknown")}</span>
      </div>
      <p>${escapeHtml(s.range_notes || "No range notes imported yet.")}</p>
      <div class="meta-line">
        <span>${escapeHtml(s.order_name || "Unknown order")}</span>
        <span>${escapeHtml(s.region_scope || "No region")}</span>
        <span>difficulty ${s.difficulty || 2}</span>
      </div>
    </section>
    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>Clips</h2>
          <p>Each clip keeps source and attribution metadata attached.</p>
        </div>
      </div>
      <div class="detail-stack">
        ${payload.clips.map(clipRow).join("") || `<div class="empty">No clips for this species.</div>`}
      </div>
    </section>
    <section class="panel">
      <div class="panel-header"><div><h2>Similar Species</h2><p>Used by quiz distractor selection.</p></div></div>
      ${payload.similar.length ? payload.similar.map((x) => `
        <div class="meta-line"><strong>${escapeHtml(x.common_name)}</strong><span>${escapeHtml(x.reason || "similar vocal space")}</span></div>
      `).join("") : `<div class="empty">No similarity rows yet.</div>`}
    </section>
  `;
}

function clipRow(c) {
  return `
    <div class="clip-row">
      <div class="meta-line">
        <span class="tag">${escapeHtml(c.clip_type || "audio")}</span>
        <span>${escapeHtml(c.quality || "unknown quality")}</span>
        <span>${escapeHtml(c.location || "unknown location")}</span>
      </div>
      ${state.settings.showWaveform ? `<canvas class="waveform" data-waveform="${c.waveform_url || ""}" width="720" height="120"></canvas>` : ""}
      <audio controls preload="metadata" src="${c.audio_url}"></audio>
      <div class="latin">${escapeHtml(c.attribution_text || "")}</div>
    </div>
  `;
}

function renderQuiz() {
  const q = state.quiz.question;
  const reveal = state.quiz.reveal;
  content.innerHTML = `
    <div class="quiz-layout">
      <section class="panel quiz-player">
        <div class="panel-header">
          <div>
            <h2>${q ? "Active Clip" : "Ready"}</h2>
            <p>${q ? `${escapeHtml(q.clip_type || "audio")} clip, difficulty ${q.difficulty || 2}` : "Start a question to hear a hidden species."}</p>
          </div>
          <button class="secondary-button" data-action="new-question">${q ? "Next" : "Start"}</button>
        </div>
        ${q ? `<audio controls autoplay src="${q.audio_url}"></audio>` : `<div class="empty">No clip loaded.</div>`}
        ${q && state.settings.blindMode ? `<div class="empty">Blind mode hides waveform cues.</div>` : ""}
      </section>
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2>Choices</h2>
            <p>${state.settings.choices}-choice mode with family/similarity-biased distractors.</p>
          </div>
        </div>
        <div class="answer-grid">
          ${q ? q.options.map(answerOption).join("") : `<div class="empty">Choices appear here after a question starts.</div>`}
        </div>
        <div class="field-row" style="margin-top:14px">
          <button class="primary-button" data-action="submit-answer" ${!state.quiz.selectedId || reveal ? "disabled" : ""}>Submit</button>
          <button class="secondary-button" data-action="new-question">Skip</button>
        </div>
        ${reveal ? revealBlock(reveal) : ""}
      </section>
    </div>
  `;
}

function answerOption(option) {
  const selected = state.quiz.selectedId === option.id;
  const reveal = state.quiz.reveal;
  const classes = ["answer-option"];
  if (selected) classes.push("selected");
  if (reveal && option.id === reveal.correct_species.id) classes.push("correct");
  if (reveal && selected && option.id !== reveal.correct_species.id) classes.push("incorrect");
  return `
    <button class="${classes.join(" ")}" data-action="choose-answer" data-id="${option.id}" ${reveal ? "disabled" : ""}>
      <strong>${escapeHtml(option.common_name)}</strong>
      <span class="latin">${escapeHtml(option.scientific_name)}</span>
      <span class="meta-line"><span>${escapeHtml(option.family || "Unknown family")}</span><span>${escapeHtml(option.reason || "distractor")}</span></span>
    </button>
  `;
}

function revealBlock(reveal) {
  const rec = reveal.recording || {};
  return `
    <div class="reveal" style="margin-top:18px">
      <h3>${reveal.was_correct ? "Correct" : "Correct answer"}: ${escapeHtml(reveal.correct_species.common_name)}</h3>
      <p class="latin">${escapeHtml(reveal.correct_species.scientific_name)}</p>
      <div class="meta-line">
        <span>${escapeHtml(rec.location || "unknown location")}</span>
        <span>${escapeHtml(rec.recordist || "unknown recordist")}</span>
        <span>${escapeHtml(rec.license_name || "unknown license")}</span>
      </div>
      <p>${escapeHtml(rec.attribution_text || "No attribution text available.")}</p>
      ${reveal.similar?.length ? `<div>${reveal.similar.map((s) => `<span class="tag blue">${escapeHtml(s.common_name)}</span>`).join(" ")}</div>` : ""}
    </div>
  `;
}

async function newQuestion() {
  const params = new URLSearchParams();
  if (state.quiz.sessionId) params.set("session_id", state.quiz.sessionId);
  params.set("choices", state.settings.choices);
  if (state.settings.sound !== "all") params.set("sound", state.settings.sound);
  if (state.settings.region && state.settings.region !== "all") params.set("region", state.settings.region);
  if (state.settings.weakReview) params.set("weak", "true");
  const question = await api(`/api/quiz/next?${params}`);
  state.quiz.sessionId = question.session_id;
  state.quiz.question = question;
  state.quiz.selectedId = null;
  state.quiz.reveal = null;
  state.quiz.startedAt = performance.now();
  if (state.view !== "quiz") navigate("quiz");
  renderQuiz();
}

async function submitAnswer() {
  if (!state.quiz.question || !state.quiz.selectedId) return;
  const reveal = await api("/api/quiz/answer", {
    method: "POST",
    body: JSON.stringify({
      session_id: state.quiz.sessionId,
      clip_id: state.quiz.question.clip_id,
      chosen_species_id: state.quiz.selectedId,
      response_ms: Math.round(performance.now() - (state.quiz.startedAt || performance.now())),
    }),
  });
  state.quiz.reveal = reveal;
  await refreshCommon();
  renderQuiz();
}

async function renderProgress() {
  const payload = await api("/api/progress");
  content.innerHTML = `
    <div class="grid cols-2">
      <section class="panel">
        <div class="panel-header">
          <div><h2>Species Accuracy</h2><p>Lowest accuracy appears first.</p></div>
          <button class="danger-button" data-action="reset-progress">Reset</button>
        </div>
        ${progressTable(payload.species, "species")}
      </section>
      <section class="panel">
        <div class="panel-header"><div><h2>Family Accuracy</h2><p>Useful for same-family training packs.</p></div></div>
        ${progressTable(payload.families, "family")}
      </section>
    </div>
    <section class="panel">
      <div class="panel-header"><div><h2>Recent Sessions</h2><p>Local sessions are stored in SQLite.</p></div></div>
      ${sessionTable(payload.sessions)}
    </section>
  `;
}

async function renderCoverage() {
  const params = new URLSearchParams();
  if (state.settings.region && state.settings.region !== "all") params.set("region", state.settings.region);
  const payload = await api(`/api/coverage?${params}`);
  content.innerHTML = `
    <div class="grid cols-3">
      ${metric("Complete", payload.complete, "At least two clips")}
      ${metric("Partial", payload.partial, "One local clip")}
      ${metric("Missing", payload.missing, "No quiz clips yet")}
    </div>
    <section class="panel">
      <div class="panel-header">
        <div><h2>Species Coverage</h2><p>Sorted by the weakest coverage first.</p></div>
        <select class="select" data-setting="region">${regionOptions(state.settings.region)}</select>
      </div>
      <div class="table-shell">
        <table>
          <thead><tr><th>Species</th><th>Family</th><th>Recordings</th><th>Clips</th><th>Song</th><th>Call</th></tr></thead>
          <tbody>
            ${payload.species.map((s) => `
              <tr>
                <td><strong>${escapeHtml(s.common_name)}</strong><div class="latin">${escapeHtml(s.scientific_name)}</div></td>
                <td>${escapeHtml(s.family || "")}</td>
                <td>${s.recordings}</td>
                <td>${s.clips}</td>
                <td>${s.song_clips || 0}</td>
                <td>${s.call_clips || 0}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

async function renderAttributions() {
  const payload = await api("/api/attributions");
  content.innerHTML = `
    <section class="panel">
      <div class="panel-header"><div><h2>${payload.count} Recording Attributions</h2><p>Generated automatically from database rows.</p></div></div>
      <div class="table-shell">
        <table>
          <thead><tr><th>Species</th><th>Source</th><th>Recordist</th><th>License</th><th>Attribution</th></tr></thead>
          <tbody>
            ${payload.recordings.map((r) => `
              <tr>
                <td><strong>${escapeHtml(r.common_name)}</strong><div class="latin">${escapeHtml(r.scientific_name)}</div></td>
                <td>${sourceLink(r)}</td>
                <td>${escapeHtml(r.recordist || "")}</td>
                <td>${licenseLink(r)}</td>
                <td>${escapeHtml(r.attribution_text || "")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderSettings() {
  content.innerHTML = `
    <section class="panel">
      <div class="panel-header"><div><h2>Quiz Defaults</h2><p>Stored locally in browser storage; the dataset remains in SQLite.</p></div></div>
      <div class="settings-grid">
        <div class="setting">
          <label for="choices">Choices</label>
          <input id="choices" data-setting="choices" type="range" min="3" max="8" value="${state.settings.choices}">
          <small>${state.settings.choices} answer options</small>
        </div>
        <div class="setting">
          <label for="sound">Sound type</label>
          <select id="sound" class="select" data-setting="sound">
            <option value="all">Songs and calls</option>
            ${state.filters.sounds.map((sound) => `<option value="${escapeAttr(sound)}" ${state.settings.sound === sound ? "selected" : ""}>${escapeHtml(sound)}</option>`).join("")}
          </select>
          <small>Filter quiz clips by imported clip type.</small>
        </div>
        <div class="setting">
          <label for="region">Training region</label>
          <select id="region" class="select" data-setting="region">
            ${regionOptions(state.settings.region)}
          </select>
          <small>Quiz selection uses recording country and coordinates when available.</small>
        </div>
        <div class="setting">
          <label class="toggle-row"><input type="checkbox" data-setting="weakReview" ${state.settings.weakReview ? "checked" : ""}> Weak-species review</label>
          <small>Bias question selection toward missed species once attempts exist.</small>
        </div>
        <div class="setting">
          <label class="toggle-row"><input type="checkbox" data-setting="blindMode" ${state.settings.blindMode ? "checked" : ""}> Blind mode</label>
          <small>Hide visual waveform cues during quiz playback.</small>
        </div>
        <div class="setting">
          <label class="toggle-row"><input type="checkbox" data-setting="showWaveform" ${state.settings.showWaveform ? "checked" : ""}> Show waveforms in library</label>
          <small>Render generated waveform summaries when present.</small>
        </div>
      </div>
    </section>
  `;
}

function progressTable(rows, kind) {
  if (!rows.length) return `<div class="empty">No quiz attempts recorded yet.</div>`;
  return `
    <div class="table-shell">
      <table>
        <thead><tr><th>${kind === "family" ? "Family" : "Species"}</th><th>Attempts</th><th>Accuracy</th></tr></thead>
        <tbody>
          ${rows.map((row) => {
            const label = kind === "family" ? row.family : row.common_name;
            return `
              <tr>
                <td><strong>${escapeHtml(label || "")}</strong>${kind === "species" ? `<div class="latin">${escapeHtml(row.scientific_name || "")}</div>` : ""}</td>
                <td>${row.attempts}</td>
                <td><div class="bar"><span style="width:${Math.round((row.accuracy || 0) * 100)}%"></span></div><div class="latin">${percentText(row.accuracy)}</div></td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function sessionTable(rows) {
  if (!rows.length) return `<div class="empty">No sessions yet.</div>`;
  return `
    <div class="table-shell">
      <table>
        <thead><tr><th>Started</th><th>Mode</th><th>Score</th><th>Total</th></tr></thead>
        <tbody>
          ${rows.map((row) => `
            <tr><td>${escapeHtml(row.started_at || "")}</td><td>${escapeHtml(row.mode || "")}</td><td>${row.score}</td><td>${row.total}</td></tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function metric(label, value, note) {
  return `
    <div class="metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${escapeHtml(String(value ?? ""))}</div>
      <div class="metric-note">${escapeHtml(note || "")}</div>
    </div>
  `;
}

function familyBars(rows) {
  if (!rows.length) return `<div class="empty">No family data available.</div>`;
  const max = Math.max(...rows.map((row) => row.species));
  return rows.map((row) => `
    <div class="meta-line" style="align-items:center; margin:10px 0">
      <strong style="min-width:150px">${escapeHtml(row.family)}</strong>
      <div class="bar"><span style="width:${Math.round((row.species / max) * 100)}%"></span></div>
      <span>${row.species}</span>
    </div>
  `).join("");
}

function buildSummary(build) {
  if (!build) return `<div class="empty">No dataset build recorded yet.</div>`;
  return `
    <div class="grid cols-3">
      ${metric("Taxonomy", build.taxonomy_source || "unknown", build.taxonomy_version || "")}
      ${metric("Region", build.region_scope || "unknown", "Current build scope")}
      ${metric("Policy", build.license_policy || "unknown", "License filter")}
    </div>
  `;
}

function select(name, label, options, selected = "") {
  return `
    <select class="select" data-filter="${name}">
      <option value="">${label}</option>
      ${options.map((option) => `<option value="${escapeAttr(option)}" ${selected === option ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}
    </select>
  `;
}

function regionSelect(name, selected = "all") {
  return `
    <select class="select" data-filter="${name}">
      ${regionOptions(selected)}
    </select>
  `;
}

function regionOptions(selected = "all") {
  const options = [{ id: "all", name: "All regions" }, ...(state.filters.regions || [])];
  return options.map((region) => `
    <option value="${escapeAttr(region.id)}" ${selected === region.id ? "selected" : ""}>${escapeHtml(region.name)}</option>
  `).join("");
}

async function drawWaveforms() {
  const canvases = [...document.querySelectorAll("canvas[data-waveform]")];
  for (const canvas of canvases) {
    const url = canvas.dataset.waveform;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f8faf8";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#176b5b";
    ctx.lineWidth = 3;
    let peaks = [];
    if (url) {
      try {
        const payload = await fetch(url).then((r) => r.json());
        peaks = payload.peaks || [];
      } catch {
        peaks = [];
      }
    }
    if (!peaks.length) {
      peaks = Array.from({ length: 80 }, (_, i) => 0.25 + 0.5 * Math.abs(Math.sin(i * 0.31)));
    }
    const step = canvas.width / peaks.length;
    const mid = canvas.height / 2;
    ctx.beginPath();
    peaks.forEach((peak, index) => {
      const x = index * step + step / 2;
      const height = Math.max(4, peak * (canvas.height - 18));
      ctx.moveTo(x, mid - height / 2);
      ctx.lineTo(x, mid + height / 2);
    });
    ctx.stroke();
  }
}

function sourceLink(r) {
  if (!r.source_url) return escapeHtml(r.source || "");
  return `<a href="${escapeAttr(r.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(r.source)} ${escapeHtml(r.source_recording_id || "")}</a>`;
}

function licenseLink(r) {
  if (!r.license_url) return escapeHtml(r.license_name || "");
  return `<a href="${escapeAttr(r.license_url)}" target="_blank" rel="noreferrer">${escapeHtml(r.license_name || "")}</a>`;
}

function percentText(value) {
  if (value == null) return "n/a";
  return `${Math.round(value * 100)}%`;
}

function loadSettings() {
  const defaults = {
    choices: 3,
    sound: "all",
    region: "northeast",
    weakReview: false,
    blindMode: false,
    showWaveform: true,
  };
  try {
    return { ...defaults, ...JSON.parse(localStorage.getItem("birdtrainer.settings") || "{}") };
  } catch {
    return defaults;
  }
}

function saveSettings() {
  localStorage.setItem("birdtrainer.settings", JSON.stringify(state.settings));
}

function toast(message) {
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 2400);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

init().catch((error) => {
  console.error(error);
  content.innerHTML = `<div class="empty">Startup error: ${escapeHtml(error.message)}</div>`;
});
