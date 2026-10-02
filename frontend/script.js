/* ============================================================
   CareerFlow AI — Frontend Logic (Live API Connected)
   Backend: FastAPI on Render
   State: Stored in browser sessionStorage (no database)
   ============================================================ */

// ---------- CONFIG ----------
const API_BASE = window.CAREERFLOW_API_BASE || "http://127.0.0.1:8000";

// ---------- GLOBAL STATE ----------
const appState = {
  profile: null,
  matchedJobs: [],
  targetJob: null,
  skillGap: null,
  learningPlan: null,
  interviewSession: {
    questions: [],
    current: -1,
    evaluations: []
  }
};

function saveState() {
  try {
    sessionStorage.setItem("cf_state", JSON.stringify(appState));
  } catch (e) {
    console.warn("Could not save state:", e);
  }
}

function loadState() {
  try {
    const s = sessionStorage.getItem("cf_state");
    if (s) Object.assign(appState, JSON.parse(s));
  } catch (e) {
    console.warn("Could not load state:", e);
  }
}

function clearState() {
  sessionStorage.removeItem("cf_state");
  appState.profile = null;
  appState.matchedJobs = [];
  appState.targetJob = null;
  appState.skillGap = null;
  appState.learningPlan = null;
  appState.interviewSession = { questions: [], current: -1, evaluations: [] };
}


/* ============================================================
   NAVIGATION
   ============================================================ */
function showApp() {
  document.getElementById("landing").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  window.scrollTo(0, 0);
  loadDashboard();
  updateReadinessBadge();
}

function showLanding() {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("landing").classList.remove("hidden");
  window.scrollTo(0, 0);
}

function navigate(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const pageEl = document.getElementById("page-" + page);
  if (pageEl) pageEl.classList.add("active");

  const navEl = document.querySelector(`.nav-item[data-page="${page}"]`);
  if (navEl) navEl.classList.add("active");

  const titles = {
    dashboard: "Dashboard",
    resume: "Resume Analyzer",
    jobs: "Job Matches",
    skills: "Skill Gap Analysis",
    learning: "Learning Plan",
    interview: "Interview Simulator"
  };
  document.getElementById("page-title").textContent = titles[page] || "Dashboard";

  // Lazy load page content
  if (page === "jobs") loadJobs();
  if (page === "skills") loadSkillGap();
  if (page === "learning") loadPlan();
  if (page === "interview") renderInterviewState();
}

document.querySelectorAll(".nav-item").forEach(item => {
  item.addEventListener("click", () => navigate(item.dataset.page));
});


/* ============================================================
   DASHBOARD
   ============================================================ */
function loadDashboard() {
  const profile = appState.profile;

  if (!profile) {
    document.getElementById("stat-profile").textContent = "—";
    document.getElementById("stat-jobs").textContent = "—";
    document.getElementById("stat-gaps").textContent = "—";
    document.getElementById("stat-plan").textContent = "—";
    ["skills", "projects", "clarity", "role"].forEach(k => {
      document.getElementById("bar-" + k).style.width = "0%";
      document.getElementById("val-" + k).textContent = "—";
    });
    document.getElementById("readiness-score").textContent = "0%";
    return;
  }

  // Compute readiness breakdown from profile signals
  const skillCount = profile.skills?.length || 0;
  const projCount = profile.projects?.length || 0;
  const expCount = profile.experience?.length || 0;
  const eduCount = profile.education?.length || 0;

  const scores = {
    skills: Math.min(100, skillCount * 8 + 20),
    projects: Math.min(100, projCount * 18 + 20),
    clarity: Math.min(100, (expCount + eduCount) * 18 + 30),
    role: appState.matchedJobs.length
      ? Math.round(appState.matchedJobs.reduce((a, j) => a + j.match, 0) / appState.matchedJobs.length)
      : Math.min(100, skillCount * 7 + 25)
  };

  const overall = Math.round(
    (scores.skills + scores.projects + scores.clarity + scores.role) / 4
  );

  document.getElementById("readiness-score").textContent = overall + "%";
  document.getElementById("stat-profile").textContent = overall + "%";
  document.getElementById("stat-jobs").textContent = appState.matchedJobs.length || "—";
  document.getElementById("stat-gaps").textContent = appState.skillGap
    ? (appState.skillGap.missing?.length || 0)
    : "—";

  const planTotal = appState.learningPlan?.length || 0;
  const planDone = document.querySelectorAll(".plan-item input:checked").length;
  document.getElementById("stat-plan").textContent = planTotal
    ? `${planDone}/${planTotal}`
    : "—";

  ["skills", "projects", "clarity", "role"].forEach(k => {
    document.getElementById("bar-" + k).style.width = scores[k] + "%";
    document.getElementById("val-" + k).textContent = scores[k] + "%";
  });
}

function updateReadinessBadge() {
  const badge = document.getElementById("readiness-score");
  if (!appState.profile) {
    badge.textContent = "0%";
    return;
  }
  const skillCount = appState.profile.skills?.length || 0;
  const score = Math.min(100, skillCount * 8 + 30);
  badge.textContent = score + "%";
}


/* ============================================================
   RESUME UPLOAD
   ============================================================ */
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");

if (dropzone) {
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", e => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", e => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });
}
if (fileInput) {
  fileInput.addEventListener("change", e => {
    if (e.target.files.length) handleFile(e.target.files[0]);
  });
}

async function handleFile(file) {
  const status = document.getElementById("uploadStatus");
  status.classList.remove("hidden", "success", "error", "loading");
  status.classList.add("loading");
  status.textContent = "⏳ Analyzing your resume with AI...";

  // Client-side validation
  if (file.type !== "application/pdf") {
    status.classList.remove("loading");
    status.classList.add("error");
    status.textContent = "❌ Only PDF files are allowed.";
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    status.classList.remove("loading");
    status.classList.add("error");
    status.textContent = "❌ File too large (max 5MB).";
    return;
  }

  try {
    const fd = new FormData();
    fd.append("file", file);

    const res = await fetch(`${API_BASE}/api/resume/analyze`, {
      method: "POST",
      body: fd
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(errText || "Analysis failed");
    }

    const data = await res.json();
    appState.profile = data.profile;
    saveState();

    status.classList.remove("loading");
    status.classList.add("success");
    status.textContent = "✅ Resume analyzed successfully!";

    renderProfile(data.profile);
    updateReadinessBadge();
    loadDashboard();
  } catch (err) {
    status.classList.remove("loading");
    status.classList.add("error");
    status.textContent = "❌ " + (err.message || "Something went wrong. Please try again.");
  }
}

function renderProfile(p) {
  const box = document.getElementById("profileResult");
  box.classList.remove("hidden");

  document.getElementById("p-skills").innerHTML =
    (p.skills && p.skills.length)
      ? p.skills.map(s => `<span class="chip">${escapeHtml(s)}</span>`).join("")
      : '<span class="muted">No skills detected</span>';

  document.getElementById("p-exp").innerHTML =
    (p.experience && p.experience.length)
      ? p.experience.map(e => `<li>${escapeHtml(e)}</li>`).join("")
      : "<li>No experience detected</li>";

  document.getElementById("p-edu").innerHTML =
    (p.education && p.education.length)
      ? p.education.map(e => `<li>${escapeHtml(e)}</li>`).join("")
      : "<li>No education detected</li>";

  document.getElementById("p-proj").innerHTML =
    (p.projects && p.projects.length)
      ? p.projects.map(e => `<li>${escapeHtml(e)}</li>`).join("")
      : "<li>No projects detected</li>";
}


/* ============================================================
   JOBS — Hybrid Matching
   ============================================================ */
async function loadJobs() {
  const list = document.getElementById("jobList");

  if (!appState.profile) {
    list.innerHTML = `
      <p class="muted">Please upload your resume first on the <b>Resume</b> page.</p>
    `;
    return;
  }

  list.innerHTML = `<p class="muted">⏳ Matching jobs against your profile...</p>`;

  try {
    const res = await fetch(`${API_BASE}/api/jobs/match`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: appState.profile })
    });

    if (!res.ok) throw new Error(await res.text());

    const data = await res.json();
    appState.matchedJobs = data.jobs || [];
    saveState();
    renderJobs(appState.matchedJobs);
    loadDashboard();
  } catch (err) {
    list.innerHTML = `<p class="muted">❌ Failed to load jobs: ${err.message}</p>`;
  }
}

function renderJobs(jobs) {
  const list = document.getElementById("jobList");

  if (!jobs || !jobs.length) {
    list.innerHTML = `<p class="muted">No matching jobs found. Try uploading a more detailed resume.</p>`;
    return;
  }

  list.innerHTML = jobs.map(j => `
    <div class="job-card">
      <div class="job-head">
        <div>
          <h4>${escapeHtml(j.title)}</h4>
          <div class="job-company">${escapeHtml(j.company)} · ${escapeHtml(j.location)}</div>
        </div>
        <div class="match-pill">${j.match}% match</div>
      </div>
      <div class="match-bar">
        <div class="match-fill" style="width:${j.match}%"></div>
      </div>
      <div class="job-skills">
        ${(j.matched || []).map(s => `<span class="chip ok">✓ ${escapeHtml(s)}</span>`).join("")}
        ${(j.missing || []).map(s => `<span class="chip bad">✗ ${escapeHtml(s)}</span>`).join("")}
      </div>
      ${j.explain ? `<p class="job-explain">${escapeHtml(j.explain)}</p>` : ""}
      <div class="job-actions">
        <button class="btn-primary" onclick="selectJob(${j.id})">Target This Role</button>
      </div>
    </div>
  `).join("");
}

function selectJob(jobId) {
  const job = appState.matchedJobs.find(j => j.id === jobId);
  if (!job) return;
  appState.targetJob = job;
  appState.skillGap = null;
  appState.learningPlan = null;
  saveState();
  navigate("skills");
}


/* ============================================================
   SKILL GAP
   ============================================================ */
async function loadSkillGap() {
  const roleLabel = document.getElementById("target-role-label");
  const haveEl = document.getElementById("gap-have");
  const improveEl = document.getElementById("gap-improve");
  const missingEl = document.getElementById("gap-missing");

  if (!appState.targetJob) {
    roleLabel.textContent = "—";
    haveEl.innerHTML = '<span class="muted">Select a target role first</span>';
    improveEl.innerHTML = "";
    missingEl.innerHTML = "";
    return;
  }

  roleLabel.textContent = appState.targetJob.title;
  haveEl.innerHTML = "<span class='muted'>⏳ Loading...</span>";
  improveEl.innerHTML = "";
  missingEl.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/api/skills/gap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: appState.profile,
        job_id: appState.targetJob.id
      })
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    appState.skillGap = data.gaps;
    saveState();

    haveEl.innerHTML = (data.gaps.have && data.gaps.have.length)
      ? data.gaps.have.map(s => `<span class="chip ok">${escapeHtml(s)}</span>`).join("")
      : '<span class="muted">None</span>';

    improveEl.innerHTML = (data.gaps.improve && data.gaps.improve.length)
      ? data.gaps.improve.map(s => `<span class="chip warn">${escapeHtml(s)}</span>`).join("")
      : '<span class="muted">None</span>';

    missingEl.innerHTML = (data.gaps.missing && data.gaps.missing.length)
      ? data.gaps.missing.map(s => `<span class="chip bad">${escapeHtml(s)}</span>`).join("")
      : '<span class="muted">None — great fit!</span>';

    loadDashboard();
  } catch (err) {
    haveEl.innerHTML = `<span class="muted">❌ ${err.message}</span>`;
  }
}


/* ============================================================
   RESUME IMPROVEMENT
   ============================================================ */
async function improveResume() {
  const out = document.getElementById("improveOutput");
  if (!appState.targetJob) {
    alert("Please select a target job first from the Jobs page.");
    return;
  }
  out.innerHTML = "<p class='muted'>⏳ Generating personalized suggestions...</p>";

  try {
    const res = await fetch(`${API_BASE}/api/resume/improve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: appState.profile,
        job_id: appState.targetJob.id
      })
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    out.innerHTML = (data.suggestions || []).map(s => `
      <div class="plan-item">
        <div>
          <div class="day">${escapeHtml(s.area || "General")}</div>
          <p>${escapeHtml(s.suggestion || "")}</p>
        </div>
      </div>
    `).join("") || "<p class='muted'>No suggestions generated.</p>";
  } catch (err) {
    out.innerHTML = `<p class="muted">❌ ${err.message}</p>`;
  }
}


/* ============================================================
   LEARNING PLAN
   ============================================================ */
async function loadPlan() {
  const list = document.getElementById("planList");

  if (!appState.targetJob) {
    list.innerHTML = `
      <p class="muted">Please select a target role on the <b>Jobs</b> page first.</p>
    `;
    return;
  }

  list.innerHTML = `<p class="muted">⏳ Generating your personalized plan...</p>`;

  try {
    const res = await fetch(`${API_BASE}/api/learning-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: appState.profile,
        job_id: appState.targetJob.id
      })
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    appState.learningPlan = data.plan;
    saveState();
    renderPlan(data.plan);
  } catch (err) {
    list.innerHTML = `<p class="muted">❌ Failed to generate plan: ${err.message}</p>`;
  }
}

function renderPlan(plan) {
  const list = document.getElementById("planList");
  if (!plan || !plan.length) {
    list.innerHTML = `<p class="muted">No plan generated.</p>`;
    return;
  }

  list.innerHTML = plan.map((p, i) => `
    <div class="plan-item">
      <input type="checkbox" id="task-${i}" onchange="updatePlanProgress()" />
      <div>
        <div class="day">${escapeHtml(p.day || "Day " + (i + 1))}</div>
        <h5>${escapeHtml(p.title || "")}</h5>
        <p>${escapeHtml(p.desc || "")}</p>
      </div>
    </div>
  `).join("");
}

function updatePlanProgress() {
  const total = appState.learningPlan?.length || 0;
  const done = document.querySelectorAll(".plan-item input:checked").length;
  if (total) {
    document.getElementById("stat-plan").textContent = `${done}/${total}`;
  }
}


/* ============================================================
   INTERVIEW SIMULATOR
   ============================================================ */
function renderInterviewState() {
  const qEl = document.getElementById("interview-q");
  const session = appState.interviewSession;

  if (!appState.targetJob) {
    qEl.textContent = "Please select a target role on the Jobs page first.";
    return;
  }

  if (session.questions.length === 0 || session.current < 0) {
    qEl.textContent = `Click "Start Interview" to begin practicing for ${appState.targetJob.title}.`;
  } else {
    qEl.textContent = session.questions[session.current];
  }
}

async function startInterview() {
  if (!appState.targetJob) {
    alert("Please select a target job first from the Jobs page.");
    return;
  }

  const qEl = document.getElementById("interview-q");
  const fb = document.getElementById("interview-feedback");
  const answerEl = document.getElementById("interview-answer");

  qEl.textContent = "⏳ Generating a role-specific question...";
  fb.classList.add("hidden");
  answerEl.value = "";

  try {
    const res = await fetch(`${API_BASE}/api/interview/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: appState.profile,
        job_title: appState.targetJob.title
      })
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    appState.interviewSession.questions.push(data.question);
    appState.interviewSession.current = appState.interviewSession.questions.length - 1;
    saveState();

    qEl.textContent = data.question;
  } catch (err) {
    qEl.textContent = "❌ " + err.message;
  }
}

async function submitAnswer() {
  const answer = document.getElementById("interview-answer").value.trim();
  if (!answer) {
    alert("Please type your answer first.");
    return;
  }

  const session = appState.interviewSession;
  if (session.current < 0 || !session.questions[session.current]) {
    alert("Please click 'Start Interview' first.");
    return;
  }

  const question = session.questions[session.current];
  const fb = document.getElementById("interview-feedback");
  fb.classList.remove("hidden");
  fb.innerHTML = "<p>⏳ Evaluating your answer...</p>";

  try {
    const res = await fetch(`${API_BASE}/api/interview/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question,
        answer: answer,
        job_title: appState.targetJob.title
      })
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    session.evaluations.push(data);
    saveState();

    const avg = Math.round(
      ((data.correctness || 0) + (data.completeness || 0) + (data.clarity || 0)) / 3
    );

    fb.innerHTML = `
      <h4>Feedback — Average Score: ${avg}/10</h4>
      <p>
        <b>Correctness:</b> ${data.correctness}/10 ·
        <b>Completeness:</b> ${data.completeness}/10 ·
        <b>Clarity:</b> ${data.clarity}/10
      </p>
      <p style="margin-top:12px;">${escapeHtml(data.feedback || "")}</p>
      <button class="btn-primary" style="margin-top:16px;" onclick="startInterview()">
        Next Question →
      </button>
    `;
  } catch (err) {
    fb.innerHTML = `<p>❌ ${err.message}</p>`;
  }
}


/* ============================================================
   UTILITIES
   ============================================================ */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}


/* ============================================================
   INIT
   ============================================================ */
window.addEventListener("DOMContentLoaded", () => {
  loadState();

  // Restore UI if state exists
  if (appState.profile) {
    renderProfile(appState.profile);
    updateReadinessBadge();
  }
  if (appState.matchedJobs.length) {
    renderJobs(appState.matchedJobs);
  }
  if (appState.learningPlan) {
    renderPlan(appState.learningPlan);
  }
  if (appState.targetJob) {
    const label = document.getElementById("target-role-label");
    if (label) label.textContent = appState.targetJob.title;
  }
  if (appState.skillGap) {
    const haveEl = document.getElementById("gap-have");
    const improveEl = document.getElementById("gap-improve");
    const missingEl = document.getElementById("gap-missing");
    if (haveEl) haveEl.innerHTML = appState.skillGap.have.map(s => `<span class="chip ok">${escapeHtml(s)}</span>`).join("");
    if (improveEl) improveEl.innerHTML = appState.skillGap.improve.map(s => `<span class="chip warn">${escapeHtml(s)}</span>`).join("");
    if (missingEl) missingEl.innerHTML = appState.skillGap.missing.map(s => `<span class="chip bad">${escapeHtml(s)}</span>`).join("");
  }
  if (appState.targetJob) {
    renderInterviewState();
  }
});