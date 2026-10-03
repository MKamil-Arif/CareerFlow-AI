/* ============================================================
   CareerFlow AI — frontend logic
   The backend is stateless. Everything personal (profile, matches,
   plans, progress, interview history) lives in this browser's
   localStorage and can be wiped with "Clear my data".
   ============================================================ */
"use strict";

// ---------- CONFIG ----------
const API_BASE = (() => {
  const configured = (window.CAREERFLOW_CONFIG && window.CAREERFLOW_CONFIG.API_BASE) || "";
  if (configured) return configured.replace(/\/+$/, "");
  // Opened from a file or a static dev server (e.g. VS Code Live Server on :5500)
  if (location.protocol === "file:" || location.port === "5500") return "http://127.0.0.1:8000";
  return ""; // same origin
})();
const STORAGE_KEY = "careerflow:v2";
const HISTORY_LIMIT = 20;
const REQUEST_TIMEOUT_MS = 60000;

// ---------- STORAGE (never throws) ----------
const storage = {
  get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); return true; } catch (_) { return false; } },
  remove(key) { try { localStorage.removeItem(key); } catch (_) { /* ignore */ } }
};

// ---------- STATE ----------
function freshState() {
  return {
    profile: null,
    profileNotice: "",
    matches: { sig: null, jobs: [], shown: [], mode: "", notice: "" },
    preference: "",
    targetJob: null,
    skillGap: { sig: null, jobId: null, gaps: null },
    plans: {},            // jobId -> { sig, plan, mode, notice }
    interview: { questions: [], current: -1, type: "" },
    difficulty: "medium",
    chat: [],             // [{role, content}] newest last
    cv: null,             // CV builder details
    cvTemplate: "modern",
    cvAccent: "#6a4cff",
    history: []           // newest first
  };
}
let state = freshState();

function loadState() {
  try { sessionStorage.removeItem("cf_state"); } catch (_) { /* old v1 key */ }
  const raw = storage.get(STORAGE_KEY);
  if (!raw) return;
  try {
    const saved = JSON.parse(raw);
    state = Object.assign(freshState(), saved);
    state.interview = Object.assign(freshState().interview, saved.interview || {});
  } catch (_) { state = freshState(); }
}
function saveState() {
  if (!storage.set(STORAGE_KEY, JSON.stringify(state))) {
    console.warn("CareerFlow: browser storage unavailable; data will be lost on reload.");
  }
}
function profileSig(profile) {
  if (!profile) return "";
  const text = JSON.stringify(profile);
  let hash = 0;
  for (let i = 0; i < text.length; i++) hash = (hash * 31 + text.charCodeAt(i)) | 0;
  return String(hash);
}

// ---------- HELPERS ----------
const $ = id => document.getElementById(id);
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
function safeUrl(url) {
  try { const u = new URL(url); return u.protocol === "https:" || u.protocol === "http:" ? u.href : ""; }
  catch (_) { return ""; }
}
function chips(list, cls, empty) {
  return list && list.length
    ? list.map(s => `<span class="chip ${cls}">${escapeHtml(s)}</span>`).join("")
    : `<span class="muted">${escapeHtml(empty)}</span>`;
}
function listItems(list, empty) {
  return list && list.length ? list.map(x => `<li>${escapeHtml(x)}</li>`).join("") : `<li class="muted">${escapeHtml(empty)}</li>`;
}
function setNotice(el, message) {
  if (!el) return;
  el.textContent = message || "";
  el.classList.toggle("hidden", !message);
}
function setBusy(button, busy, label) {
  if (!button) return;
  if (busy) { button.dataset.label = button.textContent; button.textContent = label || "Working…"; button.disabled = true; }
  else { button.textContent = button.dataset.label || button.textContent; button.disabled = false; }
}

async function api(path, { method = "GET", json, body } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const options = { method, signal: controller.signal, headers: {} };
  if (json !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(json); }
  else if (body) options.body = body;
  let res;
  try {
    res = await fetch(API_BASE + path, options);
  } catch (err) {
    throw new Error(err.name === "AbortError"
      ? "The server took too long to respond. If it was asleep, wait a few seconds and try again."
      : "Cannot reach the server. Check your connection and try again.");
  } finally { clearTimeout(timer); }
  let data = null;
  try { data = await res.json(); } catch (_) { /* not JSON */ }
  if (!res.ok) {
    if (res.status === 429) throw new Error("You're going a bit fast — please wait a minute and try again.");
    const detail = data && data.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status}).`);
  }
  return data;
}

// ---------- THEME ----------
function applyTheme(theme) {
  const dark = theme === "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.querySelectorAll("[data-theme-label]").forEach(l => { l.textContent = dark ? "Light mode" : "Dark mode"; });
  document.querySelectorAll(".theme-toggle").forEach(b => {
    b.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    const icon = b.querySelector("[aria-hidden]");
    if (icon) icon.textContent = dark ? "☀️" : "🌙";
  });
}
function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
  storage.set("careerflow-theme", next);
}

/* ============================================================
   NAVIGATION
   ============================================================ */
const PAGE_TITLES = {
  dashboard: "Dashboard", resume: "Resume Analyzer", jobs: "Recommended Roles",
  skills: "Skill Gap Analysis", learning: "Learning Plan", interview: "Interview Simulator", cv: "CV Builder"
};

function showApp(page) {
  $("landing").classList.add("hidden");
  $("app").classList.remove("hidden");
  window.scrollTo(0, 0);
  checkService();
  navigate(page || "dashboard");
}
function showLanding() {
  $("app").classList.add("hidden");
  $("landing").classList.remove("hidden");
  window.scrollTo(0, 0);
}
function navigate(page) {
  if (!PAGE_TITLES[page]) page = "dashboard";
  if ($("app").classList.contains("hidden")) { showApp(page); return; }
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + page));
  document.querySelectorAll(".nav-item").forEach(n => {
    const active = n.dataset.page === page;
    n.classList.toggle("active", active);
    if (active) n.setAttribute("aria-current", "page"); else n.removeAttribute("aria-current");
  });
  $("page-title").textContent = PAGE_TITLES[page];
  renderTargetBars();
  if (page === "dashboard") renderDashboard();
  if (page === "jobs") loadJobs();
  if (page === "skills") loadSkillGap();
  if (page === "learning") loadPlan();
  if (page === "interview") { renderInterviewState(); renderHistory(); renderDifficulty(); }
  if (page === "cv") initCvBuilder();
}

let serviceChecked = false;
async function checkService() {
  if (serviceChecked) return;
  try {
    const health = await api("/api/health");
    serviceChecked = true;
    setNotice($("service-banner"), health.ai && !health.ai.configured
      ? "AI features are running in offline mode on this server — results use simpler built-in rules."
      : "");
  } catch (err) {
    setNotice($("service-banner"), err.message);
  }
}

/* ============================================================
   READINESS (single source of truth for badge + dashboard)
   ============================================================ */
function computeReadiness() {
  const p = state.profile;
  if (!p) return null;
  const n = key => (p[key] || []).length;
  const jobs = state.matches.sig === profileSig(p) ? state.matches.jobs : [];
  const top = jobs.slice(0, 3);
  const parts = {
    skills: Math.min(100, 20 + n("skills") * 8),
    projects: Math.min(100, 20 + n("projects") * 20),
    clarity: Math.min(100, 20 + (p.name ? 10 : 0) + (p.location ? 10 : 0) + Math.min(3, n("experience")) * 12 + Math.min(2, n("education")) * 12 + Math.min(2, n("certifications")) * 5),
    role: top.length ? Math.round(top.reduce((a, j) => a + j.match, 0) / top.length) : null
  };
  const values = Object.values(parts).filter(v => v !== null);
  return { parts, overall: Math.round(values.reduce((a, b) => a + b, 0) / values.length), estimatedRole: parts.role === null };
}

function renderDashboard() {
  const r = computeReadiness();
  const badge = $("readiness-score");
  ["skills", "projects", "clarity", "role"].forEach(k => {
    const v = r ? r.parts[k] : null;
    $("bar-" + k).style.width = (v || 0) + "%";
    $("val-" + k).textContent = v === null ? "—" : v + "%";
  });
  if (!r) {
    badge.textContent = "0%";
    ["stat-profile", "stat-jobs", "stat-gaps", "stat-plan"].forEach(id => { $(id).textContent = "—"; });
    $("readiness-note").textContent = "Upload your resume to see your readiness.";
    return;
  }
  badge.textContent = r.overall + "%";
  $("stat-profile").textContent = r.overall + "%";
  $("readiness-note").textContent = r.estimatedRole
    ? "Role alignment appears after you open the Jobs page."
    : "Role alignment is the average match of your top three roles.";
  const sig = profileSig(state.profile);
  $("stat-jobs").textContent = state.matches.sig === sig ? state.matches.jobs.length : "—";
  const gap = state.skillGap;
  $("stat-gaps").textContent = gap.gaps && gap.sig === sig && state.targetJob && String(gap.jobId) === String(state.targetJob.id) ? gap.gaps.missing.length : "—";
  const plan = currentPlan();
  $("stat-plan").textContent = plan ? `${plan.plan.filter(t => t.completed).length}/${plan.plan.length}` : "—";
  const initial = (state.profile.name || "U").trim().charAt(0).toUpperCase() || "U";
  $("avatar").textContent = initial;
}

/* ============================================================
   RESUME
   ============================================================ */
function setUploadStatus(kind, message) {
  const el = $("uploadStatus");
  el.classList.remove("hidden", "success", "error", "loading");
  el.classList.add(kind);
  el.textContent = message;
}

async function handleFile(file) {
  if (!file) return;
  const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name || "");
  if (!isPdf) return setUploadStatus("error", "❌ Only PDF files are allowed.");
  if (file.size > 5 * 1024 * 1024) return setUploadStatus("error", "❌ File too large (max 5 MB).");
  setUploadStatus("loading", "⏳ Analyzing your resume…");
  try {
    const fd = new FormData();
    fd.append("file", file);
    const data = await api("/api/resume/analyze", { method: "POST", body: fd });
    setProfile(data.profile, data.notice || "");
    setUploadStatus("success", data.mode === "ai"
      ? "✅ Resume analyzed. Review the details below and edit anything that's off."
      : "✅ Resume read with the offline parser. Please review and complete your profile below.");
  } catch (err) {
    setUploadStatus("error", "❌ " + err.message);
  } finally {
    $("fileInput").value = "";
  }
}

function setProfile(profile, notice) {
  const changed = profileSig(profile) !== profileSig(state.profile);
  state.profile = profile;
  state.profileNotice = notice || "";
  if (changed) {
    // Anything derived from the old profile is now stale.
    state.matches = { sig: null, jobs: [], shown: [], mode: "", notice: "" };
    state.skillGap = { sig: null, jobId: null, gaps: null };
  }
  saveState();
  renderProfile();
  renderDashboard();
}

function renderProfile() {
  const p = state.profile;
  const box = $("profileResult");
  if (!p) { box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  $("p-name").textContent = [p.name || "Name not detected", (p.career_level || "Entry") + " level"].join(" · ");
  $("p-location").textContent = p.location ? "Location: " + p.location : "Location not detected — add it to improve location matching.";
  $("p-skills").innerHTML = chips(p.skills, "", "No skills detected — add them below.");
  $("p-exp").innerHTML = listItems(p.experience, "No experience detected");
  $("p-edu").innerHTML = listItems(p.education, "No education detected");
  $("p-proj").innerHTML = listItems(p.projects, "No projects detected");
  $("p-certs").innerHTML = listItems(p.certifications, "No certifications detected");
  populateProfileEditor(p);
}

function populateProfileEditor(p) {
  const nl = "\n";
  const values = {
    "edit-name": p.name || "", "edit-skills": (p.skills || []).join(", "),
    "edit-experience": (p.experience || []).join(nl), "edit-education": (p.education || []).join(nl),
    "edit-projects": (p.projects || []).join(nl), "edit-certifications": (p.certifications || []).join(nl),
    "edit-location": p.location || "", "edit-level": p.career_level || "Entry"
  };
  Object.entries(values).forEach(([id, value]) => { const el = $(id); if (el) el.value = value; });
}

function readProfileForm() {
  const lines = id => $(id).value.split("\n").map(v => v.trim()).filter(Boolean).map(v => v.slice(0, 400));
  const seen = new Set();
  const skills = $("edit-skills").value.split(/[,\n]/).map(v => v.trim().slice(0, 80)).filter(v => {
    const k = v.toLowerCase(); if (!v || seen.has(k)) return false; seen.add(k); return true;
  });
  return {
    name: $("edit-name").value.trim().slice(0, 120),
    skills: skills.slice(0, 100),
    experience: lines("edit-experience").slice(0, 50),
    education: lines("edit-education").slice(0, 30),
    projects: lines("edit-projects").slice(0, 50),
    certifications: lines("edit-certifications").slice(0, 50),
    location: $("edit-location").value.trim().slice(0, 160),
    career_level: $("edit-level").value
  };
}

function saveEditedProfile(event) {
  if (event) event.preventDefault();
  setProfile(readProfileForm(), "");
  $("profileSaveStatus").textContent = "Saved in this browser.";
  setTimeout(() => { $("profileSaveStatus").textContent = ""; }, 3000);
}

function startManualProfile() {
  if (!state.profile) {
    state.profile = { name: "", skills: [], experience: [], education: [], projects: [], certifications: [], location: "", career_level: "Entry" };
    saveState();
  }
  renderProfile();
  $("profileEdit").open = true;
  $("edit-name").focus();
}

async function improveResume(button) {
  const out = $("improveOutput");
  if (!state.profile) { out.innerHTML = "<p class='muted'>Upload your resume first.</p>"; return; }
  if (!state.targetJob) { out.innerHTML = "<p class='muted'>Choose a target role on the <b>Jobs</b> page first.</p>"; return; }
  out.innerHTML = "<p class='muted'>⏳ Generating suggestions for " + escapeHtml(state.targetJob.title) + "…</p>";
  setBusy(button, true, "Generating…");
  try {
    const data = await api("/api/resume/improve", { method: "POST", json: { profile: state.profile, job: roleForApi() } });
    const rows = (data.suggestions || []).map(s => `
      <div class="plan-item"><div>
        <div class="day">${escapeHtml(s.area || "General")}</div>
        <p>${escapeHtml(s.suggestion || "")}</p>
        ${s.reason ? `<p class="muted">${escapeHtml(s.reason)}</p>` : ""}
      </div></div>`).join("");
    out.innerHTML = (data.notice ? `<div class="notice">${escapeHtml(data.notice)}</div>` : "")
      + (rows || "<p class='muted'>No suggestions generated.</p>")
      + `<p class="muted small-note">${escapeHtml(data.grounding || "")}</p>`;
  } catch (err) {
    out.innerHTML = `<p class="muted">❌ ${escapeHtml(err.message)}</p>`;
  } finally { setBusy(button, false); }
}

/* ============================================================
   JOBS — roles recommended from the user's CV (any field)
   ============================================================ */
const ROLE_FIELDS = ["id", "title", "field", "company", "location", "description", "required_skills", "preferred_skills",
  "education_requirements", "experience_requirements", "source", "why"];

/** The target role as the API expects it (generated roles only exist in this browser). */
function roleForApi(role) {
  const r = role || state.targetJob;
  const out = {};
  ROLE_FIELDS.forEach(k => { if (r && r[k] !== undefined && r[k] !== null) out[k] = r[k]; });
  if (!["catalog", "ai", "custom"].includes(out.source)) out.source = "catalog";
  return out;
}

const SOURCE_BADGE = { ai: "AI pick for your CV", custom: "Your chosen role", catalog: "From role catalog" };

async function loadJobs(mode) {
  // mode: undefined = use cache if still valid; "regenerate" = new, different roles; "refresh" = start over
  const list = $("jobList");
  if (!state.profile) {
    list.innerHTML = `<p class="muted">Please upload your resume first on the <b>Resume</b> page.</p>`;
    setNotice($("jobsNotice"), "");
    return;
  }
  const sig = profileSig(state.profile);
  if (!mode) $("jobPreference").value = state.preference || "";
  if (!mode && state.matches.sig === sig && state.matches.jobs.length) {
    setNotice($("jobsNotice"), state.matches.notice || "");
    filterJobs();
    return;
  }
  const preference = ($("jobPreference").value || "").trim();
  state.preference = preference;
  const exclude = mode === "regenerate" && state.matches.sig === sig ? (state.matches.shown || []).slice(-40) : [];
  list.innerHTML = `<p class="muted">⏳ ${mode === "regenerate" ? "Finding different roles" : "Finding roles that fit your CV"}…</p>`;
  const button = $("regenJobsBtn");
  setBusy(button, true, "Finding…");
  try {
    const data = await api("/api/jobs/recommend", { method: "POST", json: { profile: state.profile, preference, exclude } });
    let jobs = data.jobs || [];
    // Keep the role the user is working towards visible, even if the new list doesn't include it.
    const custom = state.matches.sig === sig ? state.matches.jobs.filter(j => j.source === "custom") : [];
    const keep = [...custom];
    if (state.targetJob && !jobs.some(j => String(j.id) === String(state.targetJob.id)) && !keep.some(j => String(j.id) === String(state.targetJob.id))) keep.unshift(state.targetJob);
    jobs = [...keep, ...jobs.filter(j => !keep.some(k => String(k.id) === String(j.id)))];
    const shown = [...new Set([...(exclude || []), ...jobs.map(j => j.title)])];
    state.matches = { sig, jobs, shown, mode: data.mode, notice: data.notice || "" };
    saveState();
    setNotice($("jobsNotice"), state.matches.notice);
    filterJobs();
    renderDashboard();
  } catch (err) {
    list.innerHTML = `<p class="muted">❌ Failed to load roles: ${escapeHtml(err.message)}</p>`;
  } finally { setBusy(button, false); }
}

async function addCustomRole(event) {
  if (event) event.preventDefault();
  const input = $("customRole");
  const title = input.value.trim();
  if (!state.profile) { setNotice($("jobsNotice"), "Upload your resume first."); return; }
  if (title.length < 2) { input.focus(); return; }
  const button = $("customRoleBtn");
  setBusy(button, true, "Adding…");
  try {
    const data = await api("/api/jobs/custom", { method: "POST", json: { profile: state.profile, title } });
    const job = data.job;
    state.matches.jobs = [job, ...state.matches.jobs.filter(j => String(j.id) !== String(job.id))];
    state.matches.sig = profileSig(state.profile);
    state.matches.shown = [...new Set([...(state.matches.shown || []), job.title])];
    saveState();
    input.value = "";
    setNotice($("jobsNotice"), data.notice || "");
    selectJob(job.id);
  } catch (err) {
    setNotice($("jobsNotice"), "Could not add that role: " + err.message);
  } finally { setBusy(button, false); }
}

function renderJobs(jobs) {
  const list = $("jobList");
  if (!jobs || !jobs.length) {
    list.innerHTML = `<p class="muted">No roles match that filter. Clear the filter, click <b>Suggest different roles</b>, or add your own target role.</p>`;
    return;
  }
  const targetId = state.targetJob ? String(state.targetJob.id) : null;
  list.innerHTML = jobs.map(j => {
    const match = Math.max(0, Math.min(100, Number(j.match) || 0));
    const isTarget = String(j.id) === targetId;
    const breakdown = Object.entries(j.score_breakdown || {})
      .map(([k, v]) => `<span>${escapeHtml(k.replace(/_/g, " "))}</span><b>${escapeHtml(v)}</b>`).join("");
    const meta = [j.field, j.company && j.company !== "Sample employer" ? j.company : "", j.location].filter(Boolean).map(escapeHtml).join(" · ");
    return `
    <div class="job-card${isTarget ? " targeted" : ""}">
      <div class="job-head">
        <div>
          <span class="source-badge ${escapeHtml(j.source || "catalog")}">${escapeHtml(SOURCE_BADGE[j.source] || SOURCE_BADGE.catalog)}</span>
          <h4>${escapeHtml(j.title)}</h4>
          <div class="job-company">${meta}</div>
        </div>
        <div class="match-pill">${match}% match</div>
      </div>
      <div class="match-bar"><div class="match-fill" data-width="${match}"></div></div>
      ${j.description ? `<p class="job-desc">${escapeHtml(j.description)}</p>` : ""}
      <div class="job-skills">
        ${(j.matched || []).map(s => `<span class="chip ok">✓ ${escapeHtml(s)}</span>`).join("")}
        ${(j.missing || []).map(s => `<span class="chip bad">✗ ${escapeHtml(s)}</span>`).join("")}
      </div>
      ${j.why ? `<p class="job-explain"><b>Why it fits:</b> ${escapeHtml(j.why)}</p>` : (j.explain ? `<p class="job-explain">${escapeHtml(j.explain)}</p>` : "")}
      <details class="score-details"><summary>Score breakdown</summary>
        <div class="score-grid">${breakdown}</div>
        <p class="muted">${escapeHtml(j.status || "Role type, not a live vacancy")}</p>
      </details>
      <div class="job-actions">
        <button type="button" class="btn-primary" data-action="select-job" data-job-id="${escapeHtml(j.id)}">${isTarget ? "✓ Your target — view skill gap" : "Target This Role"}</button>
      </div>
    </div>`;
  }).join("");
  // Widths are set from JS (not inline style attributes) to satisfy the Content-Security-Policy.
  list.querySelectorAll(".match-fill").forEach(el => { el.style.width = el.dataset.width + "%"; });
}

function filterJobs() {
  const q = ($("jobSearch").value || "").trim().toLowerCase();
  const rows = state.matches.jobs.filter(j => !q || [j.title, j.field, j.company, j.location, ...(j.required_skills || []), ...(j.preferred_skills || [])]
    .join(" ").toLowerCase().includes(q));
  renderJobs(rows);
}

/** Make a role the career target. Skill gap, learning plan and interview all follow it. */
function selectJob(jobId) {
  const job = state.matches.jobs.find(j => String(j.id) === String(jobId));
  if (!job) return;
  const changed = !state.targetJob || String(state.targetJob.id) !== String(job.id);
  state.targetJob = job;
  if (changed) {
    state.skillGap = { sig: null, jobId: null, gaps: null };
    state.interview = { questions: [], current: -1, type: "" };
    $("improveOutput").innerHTML = "";
    $("interview-feedback").classList.add("hidden");
    $("interview-answer").value = "";
    $("startInterviewBtn").dataset.label = "Start Interview";
    $("startInterviewBtn").textContent = "Start Interview";
  }
  saveState();
  renderTargetBars();
  navigate("skills");
}

function renderTargetBars() {
  const job = state.targetJob;
  document.querySelectorAll(".target-bar").forEach(bar => {
    if (!job) {
      bar.innerHTML = `<span>No target role yet.</span> <button type="button" class="link-btn" data-page="jobs">Choose a role →</button>`;
      return;
    }
    const meta = [job.field, job.location].filter(Boolean).map(escapeHtml).join(" · ");
    bar.innerHTML = `<span>🎯 Target role: <b>${escapeHtml(job.title)}</b>${meta ? ` <span class="muted">(${meta})</span>` : ""}</span>
      <button type="button" class="link-btn" data-page="jobs">Change role</button>`;
  });
}

/* ============================================================
   SKILL GAP
   ============================================================ */
function renderGaps(gaps) {
  $("gap-have").innerHTML = chips(gaps.have, "ok", "None yet");
  $("gap-missing").innerHTML = chips(gaps.missing, "bad", "None — you cover every required skill!");
  $("gap-improve").innerHTML = chips(gaps.improve, "warn", "None");
}

async function loadSkillGap() {
  if (!state.targetJob || !state.profile) {
    $("target-role-label").textContent = "—";
    $("gap-have").innerHTML = '<span class="muted">Select a target role on the Jobs page first.</span>';
    $("gap-missing").innerHTML = "";
    $("gap-improve").innerHTML = "";
    return;
  }
  $("target-role-label").textContent = state.targetJob.title;
  const sig = profileSig(state.profile);
  if (state.skillGap.gaps && state.skillGap.sig === sig && String(state.skillGap.jobId) === String(state.targetJob.id)) {
    renderGaps(state.skillGap.gaps);
    return;
  }
  $("gap-have").innerHTML = "<span class='muted'>⏳ Loading…</span>";
  $("gap-missing").innerHTML = "";
  $("gap-improve").innerHTML = "";
  try {
    const data = await api("/api/skills/gap", { method: "POST", json: { profile: state.profile, job: roleForApi() } });
    state.skillGap = { sig, jobId: state.targetJob.id, gaps: data.gaps };
    saveState();
    renderGaps(data.gaps);
    renderDashboard();
  } catch (err) {
    $("gap-have").innerHTML = `<span class="muted">❌ ${escapeHtml(err.message)}</span>`;
  }
}

/* ============================================================
   LEARNING PLAN
   ============================================================ */
function currentPlan() {
  if (!state.targetJob) return null;
  return state.plans[state.targetJob.id] || null;
}

async function loadPlan(force) {
  const list = $("planList");
  const button = $("regenPlanBtn");
  if (!state.targetJob || !state.profile) {
    list.innerHTML = `<p class="muted">Please select a target role on the <b>Jobs</b> page first.</p>`;
    button.classList.add("hidden");
    setNotice($("planNotice"), "");
    return;
  }
  button.classList.remove("hidden");
  $("plan-subtitle").textContent = `Tasks for ${state.targetJob.title}, tied to your skill gaps.`;
  const sig = profileSig(state.profile);
  const saved = currentPlan();
  if (saved && !force) {
    renderPlan(saved);
    setNotice($("planNotice"), saved.sig !== sig
      ? "Your profile changed since this plan was made. Click ↻ Regenerate for an updated plan (progress will reset)."
      : saved.notice || "");
    return;
  }
  list.innerHTML = `<p class="muted">⏳ Generating your personalized plan…</p>`;
  setBusy(button, true, "Generating…");
  try {
    const data = await api("/api/learning-plan", { method: "POST", json: { profile: state.profile, job: roleForApi() } });
    const entry = { sig, plan: data.plan || [], mode: data.mode, notice: data.notice || "" };
    state.plans[state.targetJob.id] = entry;
    saveState();
    renderPlan(entry);
    setNotice($("planNotice"), entry.notice);
    renderDashboard();
  } catch (err) {
    list.innerHTML = `<p class="muted">❌ Failed to generate plan: ${escapeHtml(err.message)}</p>`;
  } finally { setBusy(button, false); }
}

function renderPlan(entry) {
  const list = $("planList");
  const plan = entry && entry.plan;
  if (!plan || !plan.length) { list.innerHTML = `<p class="muted">No plan generated.</p>`; return; }
  list.innerHTML = plan.map((p, i) => {
    const url = safeUrl(p.resource_url);
    return `
    <div class="plan-item${p.completed ? " done" : ""}">
      <input type="checkbox" id="task-${i}" data-action="toggle-task" data-index="${i}" ${p.completed ? "checked" : ""} aria-label="Mark ${escapeHtml(p.day)} complete" />
      <div>
        <div class="day">${escapeHtml(p.day || "Day " + (i + 1))}${p.skill ? " · " + escapeHtml(p.skill) : ""}</div>
        <h5>${escapeHtml(p.title || "")}</h5>
        <p>${escapeHtml(p.desc || "")}</p>
        ${p.completion_criteria ? `<p class="muted"><b>Done when:</b> ${escapeHtml(p.completion_criteria)}</p>` : ""}
        ${url ? `<a class="resource-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(p.resource_title || "Open learning resource")} ↗</a>` : ""}
      </div>
    </div>`;
  }).join("");
}

function toggleTask(index, checked) {
  const entry = currentPlan();
  if (!entry || !entry.plan[index]) return;
  entry.plan[index].completed = checked;
  saveState();
  const item = $("task-" + index);
  if (item && item.parentElement) item.parentElement.classList.toggle("done", checked);
  renderDashboard();
}

/* ============================================================
   INTERVIEW
   ============================================================ */
function renderInterviewState() {
  const q = $("interview-q");
  const s = state.interview;
  if (!state.targetJob) {
    q.textContent = "Please select a target role on the Jobs page first.";
    $("q-label").textContent = "Question";
    return;
  }
  if (s.current < 0 || !s.questions[s.current]) {
    q.textContent = `Click "Start Interview" to begin practicing for ${state.targetJob.title}.`;
    $("q-label").textContent = "Question";
  } else {
    q.textContent = s.questions[s.current];
    $("q-label").textContent = `Question ${s.current + 1}${s.type ? " · " + s.type : ""}${s.level ? " · " + s.level : ""}`;
  }
}

async function startInterview(button) {
  if (!state.targetJob || !state.profile) { $("interview-q").textContent = "Please select a target role on the Jobs page first."; return; }
  $("interview-q").textContent = "⏳ Generating a role-specific question…";
  $("interview-feedback").classList.add("hidden");
  $("interview-answer").value = "";
  setBusy($("startInterviewBtn"), true, "Loading…");
  try {
    const data = await api("/api/interview/start", {
      method: "POST",
      json: { profile: state.profile, job_title: state.targetJob.title, job: roleForApi(), previous: state.interview.questions.slice(-30), difficulty: state.difficulty }
    });
    state.interview.level = data.difficulty || state.difficulty;
    state.interview.questions.push(data.question);
    state.interview.questions = state.interview.questions.slice(-30);
    state.interview.current = state.interview.questions.length - 1;
    state.interview.type = data.type || "";
    saveState();
    renderInterviewState();
    $("startInterviewBtn").dataset.label = "Next Question →";
    $("interview-answer").focus();
  } catch (err) {
    $("interview-q").textContent = "❌ " + err.message;
  } finally { setBusy($("startInterviewBtn"), false); }
}

async function submitAnswer() {
  const answer = $("interview-answer").value.trim();
  const fb = $("interview-feedback");
  const s = state.interview;
  if (s.current < 0 || !s.questions[s.current]) { fb.classList.remove("hidden"); fb.innerHTML = "<p>Click <b>Start Interview</b> first.</p>"; return; }
  if (!answer) { fb.classList.remove("hidden"); fb.innerHTML = "<p>Please type your answer first.</p>"; return; }
  const question = s.questions[s.current];
  fb.classList.remove("hidden");
  fb.innerHTML = "<p>⏳ Evaluating your answer…</p>";
  setBusy($("submitAnswerBtn"), true, "Evaluating…");
  try {
    const data = await api("/api/interview/evaluate", {
      method: "POST",
      json: { question, answer, job_title: state.targetJob.title, job: roleForApi(), difficulty: s.level || state.difficulty }
    });
    const avg = Math.round(((data.correctness || 0) + (data.completeness || 0) + (data.clarity || 0)) / 3);
    state.history.unshift({
      job_title: state.targetJob.title, question, answer: answer.slice(0, 2000),
      scores: { correctness: data.correctness, completeness: data.completeness, clarity: data.clarity },
      mode: data.mode, level: s.level || state.difficulty, created_at: new Date().toISOString()
    });
    state.history = state.history.slice(0, HISTORY_LIMIT);
    saveState();
    renderHistory();
    fb.innerHTML = `
      <h4>Feedback — Average Score: ${avg}/10${data.mode === "offline" ? " <span class='muted'>(offline rubric)</span>" : ""}</h4>
      <p><b>Correctness:</b> ${escapeHtml(data.correctness)}/10 · <b>Completeness:</b> ${escapeHtml(data.completeness)}/10 · <b>Clarity:</b> ${escapeHtml(data.clarity)}/10</p>
      <p class="feedback-text">${escapeHtml(data.feedback || "")}</p>
      ${data.improved_answer ? `<p><b>Try structuring it this way:</b> ${escapeHtml(data.improved_answer)}</p>` : ""}
      <button type="button" class="btn-primary" data-action="start-interview">Next Question →</button>`;
  } catch (err) {
    fb.innerHTML = `<p>❌ ${escapeHtml(err.message)}</p>`;
  } finally { setBusy($("submitAnswerBtn"), false); }
}

function renderHistory() {
  const el = $("interview-history-list");
  if (!state.history.length) { el.textContent = "No interview sessions yet."; return; }
  el.innerHTML = state.history.map(h => `
    <div class="history-row">
      <b>${escapeHtml(h.job_title)}</b><span>${escapeHtml((h.created_at || "").slice(0, 10))}</span>
      <p>${escapeHtml((h.question || "").slice(0, 140))}${(h.question || "").length > 140 ? "…" : ""}</p>
      <p>${h.level ? `<span class="level-tag ${escapeHtml(h.level)}">${escapeHtml(h.level)}</span> ` : ""}Scores: ${escapeHtml(h.scores.correctness)} / ${escapeHtml(h.scores.completeness)} / ${escapeHtml(h.scores.clarity)}${h.mode === "offline" ? " · offline rubric" : ""}</p>
    </div>`).join("");
}

/* ============================================================
   DATA RESET
   ============================================================ */
function resetData() {
  if (!window.confirm("Clear your profile, matches, learning plans and interview history from this browser?")) return;
  storage.remove(STORAGE_KEY);
  state = freshState();
  ["uploadStatus", "profileResult", "interview-feedback"].forEach(id => $(id).classList.add("hidden"));
  $("improveOutput").innerHTML = "";
  $("jobList").innerHTML = "";
  $("planList").innerHTML = "";
  $("jobSearch").value = "";
  $("jobPreference").value = "";
  setNotice($("jobsNotice"), "");
  $("avatar").textContent = "U";
  renderHistory();
  renderDifficulty();
  renderChat();
  cvInitialised = false;
  $("cvResult").classList.add("hidden");
  $("cvMissing").classList.add("hidden");
  navigate("dashboard");
}

/* ============================================================
   EVENTS (no inline handlers — keeps the CSP strict)
   ============================================================ */
document.addEventListener("click", event => {
  const el = event.target.closest("[data-action], [data-page]");
  if (!el || el.disabled) return;
  const action = el.dataset.action;
  switch (action) {
    case "toggle-theme": return toggleTheme();
    case "show-app": return showApp(el.dataset.page);
    case "show-landing": return showLanding();
    case "scroll-to": { const t = $(el.dataset.target); if (t) t.scrollIntoView({ behavior: "smooth" }); return; }
    case "select-job": return selectJob(el.dataset.jobId);
    case "regenerate-jobs": return loadJobs("regenerate");
    case "improve-resume": return improveResume(el);
    case "regenerate-plan": return loadPlan(true);
    case "start-interview": return startInterview(el);
    case "submit-answer": return submitAnswer();
    case "manual-profile": return startManualProfile();
    case "reset-data": return resetData();
    case "clear-history": state.history = []; saveState(); return renderHistory();
    case "toggle-task": return; // handled by "change"
    case "set-difficulty": return setDifficulty(el.dataset.level);
    case "open-coach": return openCoach();
    case "close-coach": return closeCoach();
    case "new-chat": return newChat();
    case "coach-suggest": return sendCoach(el.dataset.text);
    case "cv-template": return setCvTemplate(el.dataset.template);
    case "cv-accent": return setCvAccent(el.dataset.color);
    case "cv-prefill": return prefillCv(true);
    case "cv-add": return addCvEntry(el.dataset.list);
    case "cv-remove": return removeCvEntry(el.dataset.list, Number(el.dataset.index));
    case "cv-ai-summary": return aiSummary(el);
    case "cv-generate": return generateCv(false);
    case "cv-generate-anyway": return generateCv(true);
    case "cv-fix": return focusCvField(el.dataset.target, el.dataset.list);
    case "cv-download": return downloadCv();
    case "cv-edit": { $("cvForm").scrollIntoView({ behavior: "smooth" }); return; }
    default:
      if (el.dataset.page) navigate(el.dataset.page);
  }
});

document.addEventListener("change", event => {
  const el = event.target;
  if (el.dataset && el.dataset.action === "toggle-task") toggleTask(Number(el.dataset.index), el.checked);
});

function initUpload() {
  const dropzone = $("dropzone");
  const fileInput = $("fileInput");
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
  dropzone.addEventListener("dragover", e => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", e => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", e => { if (e.target.files.length) handleFile(e.target.files[0]); });
}

/* ============================================================
   INIT
   ============================================================ */
window.addEventListener("DOMContentLoaded", () => {
  applyTheme(document.documentElement.dataset.theme);
  loadState();
  initUpload();
  $("profileForm").addEventListener("submit", saveEditedProfile);
  $("jobSearch").addEventListener("input", filterJobs);
  $("customRoleForm").addEventListener("submit", addCustomRole);
  $("preferenceForm").addEventListener("submit", e => { e.preventDefault(); loadJobs("refresh"); });
  renderTargetBars();
  renderProfile();
  renderDashboard();
  renderHistory();
  renderDifficulty();
  initCoach();
  if (state.matches.jobs.length) filterJobs();
});

/* ============================================================
   INTERVIEW DIFFICULTY
   ============================================================ */
const DIFFICULTY_HINTS = {
  easy: "Short, basic questions — good for freshers and warming up.",
  medium: "Practical, real-work questions with one or two parts.",
  hard: "In-depth questions on trade-offs and tricky situations."
};

function setDifficulty(level) {
  if (!DIFFICULTY_HINTS[level]) return;
  state.difficulty = level;
  saveState();
  renderDifficulty();
}

function renderDifficulty() {
  const level = DIFFICULTY_HINTS[state.difficulty] ? state.difficulty : "medium";
  document.querySelectorAll(".seg-btn[data-level]").forEach(b => {
    const on = b.dataset.level === level;
    b.classList.toggle("active", on);
    b.setAttribute("aria-checked", on ? "true" : "false");
  });
  const hint = $("difficulty-hint");
  if (hint) hint.textContent = DIFFICULTY_HINTS[level] + " Applies to your next question.";
}

/* ============================================================
   CAREER COACH CHAT
   ============================================================ */
const CHAT_LIMIT = 30;
const COACH_GREETING = "Hi! I'm your Career Coach 👋 Ask me anything about roles that fit you, skills to learn, your CV or interview prep. I'll keep it short.";
let coachBusy = false;

/** Tiny, safe formatter: escapes everything, then allows **bold** and "- " bullet lines. */
function formatCoach(text) {
  const lines = escapeHtml(text).split(/\n+/);
  let html = "", inList = false;
  lines.forEach(line => {
    const bullet = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    const body = (bullet ? bullet[1] : line).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    if (bullet) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${body}</li>`; }
    else { if (inList) { html += "</ul>"; inList = false; } if (body.trim()) html += `<p>${body}</p>`; }
  });
  return html + (inList ? "</ul>" : "");
}

function renderChat(pending) {
  const box = $("coachMessages");
  if (!box) return;
  const msgs = [{ role: "assistant", content: COACH_GREETING }, ...state.chat];
  box.innerHTML = msgs.map(m => `<div class="msg ${m.role === "user" ? "user" : "bot"}${m.error ? " error" : ""}">${m.role === "user" ? `<p>${escapeHtml(m.content)}</p>` : formatCoach(m.content)}</div>`).join("")
    + (pending ? `<div class="msg bot typing" aria-label="Coach is typing"><span></span><span></span><span></span></div>` : "");
  box.scrollTop = box.scrollHeight;
}

function renderSuggestions(list) {
  const el = $("coachSuggestions");
  const items = list || (state.profile
    ? [state.targetJob ? `What should I learn first for ${state.targetJob.title}?` : "Which roles fit my profile?", "How can I improve my CV?", "How do I prepare for interviews?"]
    : ["How do I start my career search?", "What makes a good CV?", "How do I prepare for interviews?"]);
  el.innerHTML = items.slice(0, 3).map(t => `<button type="button" class="chip-btn" data-action="coach-suggest" data-text="${escapeHtml(t)}">${escapeHtml(t)}</button>`).join("");
}

function openCoach() {
  $("coach").classList.remove("hidden");
  document.body.classList.add("coach-open");
  renderChat();
  renderSuggestions();
  setTimeout(() => $("coachInput").focus(), 50);
}
function closeCoach() {
  $("coach").classList.add("hidden");
  document.body.classList.remove("coach-open");
}
function newChat() {
  state.chat = [];
  saveState();
  renderChat();
  renderSuggestions();
  $("coachInput").focus();
}

async function sendCoach(text) {
  const message = (text || "").trim().slice(0, 1500);
  if (!message || coachBusy) return;
  coachBusy = true;
  $("coachSend").disabled = true;
  state.chat.push({ role: "user", content: message });
  state.chat = state.chat.slice(-CHAT_LIMIT);
  saveState();
  renderChat(true);
  $("coachSuggestions").innerHTML = "";
  try {
    const payload = { messages: state.chat.filter(m => !m.error).slice(-10).map(m => ({ role: m.role, content: m.content })) };
    if (state.profile) payload.profile = state.profile;
    if (state.targetJob) payload.job = roleForApi();
    const data = await api("/api/chat", { method: "POST", json: payload });
    state.chat.push({ role: "assistant", content: data.reply });
    state.chat = state.chat.slice(-CHAT_LIMIT);
    saveState();
    renderChat();
    renderSuggestions(data.suggestions);
  } catch (err) {
    state.chat.push({ role: "assistant", content: "Sorry — " + err.message, error: true });
    renderChat();
    renderSuggestions();
  } finally {
    coachBusy = false;
    $("coachSend").disabled = false;
  }
}

function initCoach() {
  const input = $("coachInput");
  $("coachForm").addEventListener("submit", e => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    input.style.height = "";
    sendCoach(text);
  });
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("coachForm").requestSubmit(); }
  });
  input.addEventListener("input", () => { input.style.height = ""; input.style.height = Math.min(120, input.scrollHeight) + "px"; });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("coach").classList.contains("hidden")) closeCoach(); });
}

/* ============================================================
   CV BUILDER
   ============================================================ */
const CV_TEMPLATES = [
  { id: "modern", name: "Modern", note: "Colour sidebar, two columns" },
  { id: "classic", name: "Classic", note: "Traditional, centred header" },
  { id: "minimal", name: "Minimal", note: "Clean and airy" },
  { id: "professional", name: "Professional", note: "Bold header band" }
];
const CV_ACCENTS = ["#6a4cff", "#1f6feb", "#0f766e", "#b45309", "#be123c", "#334155"];
const CV_LISTS = {
  experience: { fields: [["title", "Job title"], ["org", "Company / organisation"], ["dates", "Dates (e.g. Jan 2024 – Present)"], ["location", "Location"]], bullets: "What you did and achieved (one per line)" },
  education: { fields: [["degree", "Degree / qualification"], ["school", "School / university"], ["dates", "Year(s)"], ["details", "Grade or details (optional)"]] },
  projects: { fields: [["name", "Project name"], ["link", "Link (optional)"]], bullets: "Short description (one point per line)" }
};
const SAMPLE_CV = {
  name: "Ayesha Khan", headline: "Marketing Executive", email: "ayesha@example.com", phone: "+92 300 0000000", location: "Lahore, Pakistan",
  linkedin: "", website: "", summary: "Marketing graduate with hands-on experience running social campaigns and writing SEO content.",
  skills: ["SEO", "Content Writing", "Canva", "Google Analytics", "Excel"],
  experience: [{ title: "Marketing Intern", org: "Brandly", dates: "2025", location: "Lahore", bullets: ["Grew Instagram followers by 40%", "Wrote 12 blog posts"] }],
  education: [{ degree: "BBA Marketing", school: "University of the Punjab", dates: "2021 – 2025", details: "" }],
  projects: [{ name: "Bakery campaign", link: "", bullets: ["Planned a 4-week social campaign"] }],
  certifications: ["Google Digital Garage"], languages: ["English", "Urdu"]
};
let cvInitialised = false;

function emptyCv() {
  return { name: "", headline: "", email: "", phone: "", location: "", linkedin: "", website: "", summary: "",
    skills: [], experience: [], education: [], projects: [], certifications: [], languages: [] };
}

/** "Title — Company (dates)" → parts. Works for experience, education and project lines. */
function splitLine(line) {
  const m = String(line).match(/^(.*?)\s+[—–-]\s+(.*?)(?:\s*\(([^)]*)\))?\s*$/);
  if (m) return [m[1].trim(), m[2].trim(), (m[3] || "").trim()];
  const p = String(line).match(/^(.*?)\s*\(([^)]*)\)\s*$/);
  return p ? [p[1].trim(), "", p[2].trim()] : [String(line).trim(), "", ""];
}

function cvFromProfile(p) {
  const cv = emptyCv();
  if (!p) return cv;
  cv.name = p.name || "";
  cv.location = p.location || "";
  cv.headline = state.targetJob ? state.targetJob.title : "";
  cv.skills = (p.skills || []).slice();
  cv.experience = (p.experience || []).map(l => { const [title, org, dates] = splitLine(l); return { title, org, dates, location: "", bullets: [] }; });
  cv.education = (p.education || []).map(l => { const [degree, school, dates] = splitLine(l); return { degree, school, dates, details: "" }; });
  cv.projects = (p.projects || []).map(l => { const [name, desc] = splitLine(l); return { name, link: "", bullets: desc ? [desc] : [] }; });
  cv.certifications = (p.certifications || []).slice();
  return cv;
}

function prefillCv(force) {
  const fresh = cvFromProfile(state.profile);
  if (force && state.cv) {
    if (!window.confirm("Replace the details below with the ones from your profile? Contact details you typed are kept.")) return;
    ["email", "phone", "linkedin", "website", "summary", "languages"].forEach(k => { if (state.cv[k] && (Array.isArray(state.cv[k]) ? state.cv[k].length : true)) fresh[k] = state.cv[k]; });
  }
  state.cv = fresh;
  saveState();
  renderCvForm();
}

function initCvBuilder() {
  if (!state.cv) state.cv = cvFromProfile(state.profile);
  renderTemplatePicker();
  if (!cvInitialised) {
    renderCvForm();
    $("cvForm").addEventListener("input", onCvInput);
    $("cvForm").addEventListener("submit", e => e.preventDefault());
    cvInitialised = true;
  }
}

function renderTemplatePicker() {
  $("templateGrid").innerHTML = CV_TEMPLATES.map(t => `
    <button type="button" class="template-card${state.cvTemplate === t.id ? " active" : ""}" data-action="cv-template" data-template="${t.id}" role="radio" aria-checked="${state.cvTemplate === t.id}">
      <div class="template-thumb" aria-hidden="true"><div class="thumb-scale">${renderCv(SAMPLE_CV, t.id, state.cvAccent)}</div></div>
      <b>${t.name}</b><span class="muted">${t.note}</span>
    </button>`).join("");
  $("accentPicker").innerHTML = CV_ACCENTS.map(c => `<button type="button" class="accent-dot${state.cvAccent === c ? " active" : ""}" data-action="cv-accent" data-color="${c}" aria-label="Accent ${c}" role="radio" aria-checked="${state.cvAccent === c}"></button>`).join("");
  $("accentPicker").querySelectorAll(".accent-dot").forEach(d => { d.style.background = d.dataset.color; });
  applyAccent($("templateGrid"));
  requestAnimationFrame(() => document.querySelectorAll(".template-thumb").forEach(t => t.style.setProperty("--thumb-scale", (t.clientWidth / 794).toFixed(4))));
}

function setCvTemplate(id) {
  state.cvTemplate = id; saveState(); renderTemplatePicker();
  if (!$("cvResult").classList.contains("hidden")) showCvPreview();
}
function setCvAccent(color) {
  if (!CV_ACCENTS.includes(color)) return;
  state.cvAccent = color; saveState(); renderTemplatePicker();
  if (!$("cvResult").classList.contains("hidden")) showCvPreview();
}
function applyAccent(root) {
  root.querySelectorAll(".cv").forEach(el => el.style.setProperty("--cv-accent", el.dataset.accent || state.cvAccent));
}

function renderCvForm() {
  const cv = state.cv || emptyCv();
  document.querySelectorAll("#cvForm [data-cv]").forEach(el => {
    const v = cv[el.dataset.cv];
    el.value = Array.isArray(v) ? v.join(el.dataset.cv === "certifications" ? "\n" : ", ") : (v || "");
  });
  Object.keys(CV_LISTS).forEach(renderCvList);
}

function renderCvList(list) {
  const spec = CV_LISTS[list];
  const items = state.cv[list] || [];
  const box = $("cv-" + list);
  box.innerHTML = items.length ? items.map((item, i) => `
    <div class="cv-entry">
      <div class="cv-entry-grid">
        ${spec.fields.map(([key, label]) => `<label>${escapeHtml(label)}<input type="text" maxlength="160" data-list="${list}" data-index="${i}" data-field="${key}" id="cv-${list}-${i}-${key}" value="${escapeHtml(item[key] || "")}" /></label>`).join("")}
      </div>
      ${spec.bullets ? `<label class="full">${escapeHtml(spec.bullets)}<textarea rows="2" maxlength="1500" data-list="${list}" data-index="${i}" data-field="bullets">${escapeHtml((item.bullets || []).join("\n"))}</textarea></label>` : ""}
      <button type="button" class="link-btn danger-link" data-action="cv-remove" data-list="${list}" data-index="${i}">Remove</button>
    </div>`).join("") : `<p class="muted small-note">Nothing added yet.</p>`;
}

function addCvEntry(list) {
  const blank = { experience: { title: "", org: "", dates: "", location: "", bullets: [] }, education: { degree: "", school: "", dates: "", details: "" }, projects: { name: "", link: "", bullets: [] } }[list];
  if (!blank) return;
  state.cv[list].push(blank);
  saveState();
  renderCvList(list);
  const first = $(`cv-${list}-${state.cv[list].length - 1}-${CV_LISTS[list].fields[0][0]}`);
  if (first) first.focus();
}
function removeCvEntry(list, index) {
  state.cv[list].splice(index, 1);
  saveState();
  renderCvList(list);
}

let cvSaveTimer = null;
function onCvInput(e) {
  const el = e.target;
  if (el.dataset.cv) {
    const key = el.dataset.cv;
    if (key === "skills" || key === "languages") state.cv[key] = el.value.split(/[,\n]/).map(v => v.trim()).filter(Boolean).slice(0, 40);
    else if (key === "certifications") state.cv[key] = el.value.split("\n").map(v => v.trim()).filter(Boolean).slice(0, 20);
    else state.cv[key] = el.value;
  } else if (el.dataset.list) {
    const item = state.cv[el.dataset.list][Number(el.dataset.index)];
    if (!item) return;
    item[el.dataset.field] = el.dataset.field === "bullets" ? el.value.split("\n").map(v => v.trim()).filter(Boolean).slice(0, 8) : el.value;
  }
  el.classList.remove("needs-input");
  clearTimeout(cvSaveTimer);
  cvSaveTimer = setTimeout(saveState, 300);
}

async function aiSummary(button) {
  if (!state.profile) { $("cv-summary").focus(); return; }
  setBusy(button, true, "✨ Writing…");
  try {
    const payload = { profile: state.profile, headline: state.cv.headline || "" };
    if (state.targetJob) payload.job = roleForApi();
    const data = await api("/api/cv/summary", { method: "POST", json: payload });
    state.cv.summary = data.summary;
    $("cv-summary").value = data.summary;
    $("cv-summary").classList.remove("needs-input");
    saveState();
  } catch (err) {
    button.insertAdjacentHTML("afterend", `<span class="cv-hint muted" role="status">Couldn't write a summary: ${escapeHtml(err.message)}</span>`);
    setTimeout(() => document.querySelectorAll(".cv-hint").forEach(h => h.remove()), 6000);
  } finally { setBusy(button, false); }
}

/** Everything a complete CV needs. Each item says which field to jump to. */
function cvMissing(cv) {
  const missing = [];
  const need = (ok, label, target, list) => { if (!ok) missing.push({ label, target, list }); };
  need(cv.name.trim().length >= 2, "Your full name", "cv-name");
  need(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cv.email.trim()), cv.email.trim() ? "A valid email address" : "Your email address", "cv-email");
  need(cv.phone.replace(/\D/g, "").length >= 7, "Your phone number", "cv-phone");
  need(cv.location.trim().length >= 2, "Your location (city, country)", "cv-location");
  need(cv.summary.trim().split(/\s+/).length >= 10, "A professional summary (at least 2 sentences)", "cv-summary");
  need(cv.skills.length >= 3, "At least 3 skills", "cv-skills");
  need(cv.education.some(e => e.degree.trim() && e.school.trim()), "Your education (degree and school)", "cv-education", "education");
  need(cv.experience.some(e => e.title.trim()) || cv.projects.some(p => p.name.trim()), "At least one experience or project", "cv-experience", "experience");
  cv.experience.forEach((e, i) => { if (e.title.trim() && !e.org.trim()) need(false, `Company for "${e.title}"`, `cv-experience-${i}-org`); });
  return missing;
}

function focusCvField(target, list) {
  let el = $(target);
  if (list && (!state.cv[list].length || el === $("cv-" + list))) {
    if (!state.cv[list].length) addCvEntry(list);
    el = $(`cv-${list}-0-${CV_LISTS[list].fields[0][0]}`);
  }
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("needs-input");
  setTimeout(() => el.focus(), 300);
}

function generateCv(anyway) {
  const box = $("cvMissing");
  const missing = cvMissing(state.cv);
  if (missing.length && !anyway) {
    box.innerHTML = `<p><b>A few details are missing.</b> Add them for a complete CV:</p>
      <ul>${missing.map(m => `<li><span>${escapeHtml(m.label)}</span> <button type="button" class="link-btn" data-action="cv-fix" data-target="${escapeHtml(m.target)}"${m.list ? ` data-list="${m.list}"` : ""}>Add now</button></li>`).join("")}</ul>
      <button type="button" class="btn-ghost" data-action="cv-generate-anyway">Generate anyway</button>`;
    box.classList.remove("hidden");
    $("cvResult").classList.add("hidden");
    box.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  box.classList.add("hidden");
  showCvPreview();
  $("cvResult").classList.remove("hidden");
  $("cvResult").scrollIntoView({ behavior: "smooth", block: "start" });
}

function showCvPreview() {
  $("cvPreview").innerHTML = renderCv(state.cv, state.cvTemplate, state.cvAccent);
  applyAccent($("cvPreview"));
}

function downloadCv() {
  const holder = $("cvPrint");
  holder.innerHTML = renderCv(state.cv, state.cvTemplate, state.cvAccent);
  applyAccent(holder);
  const oldTitle = document.title;
  document.title = ((state.cv.name || "My").trim() + " CV").replace(/[\\/:*?"<>|]/g, "");
  document.body.classList.add("printing-cv");
  const done = () => { document.body.classList.remove("printing-cv"); document.title = oldTitle; holder.innerHTML = ""; window.removeEventListener("afterprint", done); };
  window.addEventListener("afterprint", done);
  window.print();
  setTimeout(() => { if (document.body.classList.contains("printing-cv") && !window.matchMedia("print").matches) done(); }, 1500);
}

/** Render a CV as HTML for a template. All values are escaped. */
function renderCv(cv, template, accent) {
  const e = escapeHtml;
  const link = u => { const s = safeUrl(u); return s ? `<a href="${e(s)}">${e(s.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, ""))}</a>` : ""; };
  const contact = [cv.email && `<span>✉ ${e(cv.email)}</span>`, cv.phone && `<span>☎ ${e(cv.phone)}</span>`, cv.location && `<span>⌂ ${e(cv.location)}</span>`,
    cv.linkedin && `<span>in ${link(cv.linkedin)}</span>`, cv.website && `<span>🔗 ${link(cv.website)}</span>`].filter(Boolean);
  const bullets = list => list && list.length ? `<ul>${list.map(b => `<li>${e(b)}</li>`).join("")}</ul>` : "";
  const sec = (title, body) => body ? `<section class="cv-sec"><h3>${title}</h3>${body}</section>` : "";
  const exp = (cv.experience || []).filter(x => x.title || x.org).map(x => `
    <div class="cv-item"><div class="cv-item-head"><b>${e(x.title)}</b>${x.org ? `<span class="cv-org">${e(x.org)}${x.location ? ", " + e(x.location) : ""}</span>` : ""}<span class="cv-date">${e(x.dates)}</span></div>${bullets(x.bullets)}</div>`).join("");
  const edu = (cv.education || []).filter(x => x.degree || x.school).map(x => `
    <div class="cv-item"><div class="cv-item-head"><b>${e(x.degree)}</b><span class="cv-org">${e(x.school)}</span><span class="cv-date">${e(x.dates)}</span></div>${x.details ? `<p>${e(x.details)}</p>` : ""}</div>`).join("");
  const proj = (cv.projects || []).filter(x => x.name).map(x => `
    <div class="cv-item"><div class="cv-item-head"><b>${e(x.name)}</b>${x.link ? `<span class="cv-org">${link(x.link)}</span>` : ""}</div>${bullets(x.bullets)}</div>`).join("");
  const skills = (cv.skills || []).length ? `<div class="cv-skills">${cv.skills.map(s => `<span>${e(s)}</span>`).join("")}</div>` : "";
  const certs = (cv.certifications || []).length ? bullets(cv.certifications) : "";
  const langs = (cv.languages || []).length ? `<p>${cv.languages.map(e).join(" · ")}</p>` : "";
  const summary = cv.summary ? `<p>${e(cv.summary)}</p>` : "";
  const head = `<h1>${e(cv.name || "Your Name")}</h1>${cv.headline ? `<p class="cv-headline">${e(cv.headline)}</p>` : ""}`;
  const main = sec("Profile", summary) + sec("Experience", exp) + sec("Projects", proj) + sec("Education", edu);
  const side = sec("Skills", skills) + sec("Certifications", certs) + sec("Languages", langs);
  const t = ["modern", "classic", "minimal", "professional"].includes(template) ? template : "modern";
  const accentAttr = `data-accent="${e(accent || "#6a4cff")}"`;
  if (t === "modern") {
    return `<article class="cv t-modern" ${accentAttr}><aside class="cv-side">${head}<div class="cv-contact">${contact.join("")}</div>${side}</aside><div class="cv-main">${main}</div></article>`;
  }
  if (t === "professional") {
    return `<article class="cv t-professional" ${accentAttr}><header class="cv-band">${head}<div class="cv-contact">${contact.join("")}</div></header><div class="cv-cols"><div class="cv-main">${main}</div><aside class="cv-side">${side}</aside></div></article>`;
  }
  return `<article class="cv t-${t}" ${accentAttr}><header class="cv-header">${head}<div class="cv-contact">${contact.join("")}</div></header>${sec("Profile", summary)}${sec("Skills", skills)}${sec("Experience", exp)}${sec("Projects", proj)}${sec("Education", edu)}${sec("Certifications", certs)}${sec("Languages", langs)}</article>`;
}
window.addEventListener("resize", () => document.querySelectorAll(".template-thumb").forEach(t => t.style.setProperty("--thumb-scale", (t.clientWidth / 794).toFixed(4))));
