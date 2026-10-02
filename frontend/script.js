/* ============================================================
   CareerFlow AI — Frontend Logic
   (Currently uses mock data. Replace fetch() calls with FastAPI)
   ============================================================ */

// ---------- NAVIGATION ----------
function showApp() {
  document.getElementById('landing').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  window.scrollTo(0, 0);
  loadDashboard();
}

function showLanding() {
  document.getElementById('app').classList.add('hidden');
  document.getElementById('landing').classList.remove('hidden');
  window.scrollTo(0, 0);
}

function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  document.getElementById('page-' + page).classList.add('active');
  const navEl = document.querySelector(`.nav-item[data-page="${page}"]`);
  if (navEl) navEl.classList.add('active');

  const titles = {
    dashboard: 'Dashboard', resume: 'Resume Analyzer', jobs: 'Job Matches',
    skills: 'Skill Gap Analysis', learning: 'Learning Plan', interview: 'Interview Simulator'
  };
  document.getElementById('page-title').textContent = titles[page] || 'Dashboard';

  if (page === 'jobs') loadJobs();
  if (page === 'skills') loadSkillGap();
  if (page === 'learning') loadPlan();
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => navigate(item.dataset.page));
});


// ============================================================
//  MOCK DATA (replace with API responses)
// ============================================================

const MOCK_PROFILE = {
  skills: ['JavaScript', 'HTML', 'CSS', 'React', 'Git', 'Python', 'SQL'],
  experience: ['Frontend Intern — TechNova (6 months)', 'Freelance Web Developer (1 year)'],
  education: ['BSc Computer Science — University of Punjab (2024)'],
  projects: ['E-commerce Store (React + Stripe)', 'Task Manager App (React + Firebase)'],
  career_level: 'Entry'
};

const MOCK_JOBS = [
  {
    id: 1, title: 'Junior Frontend Developer', company: 'TechNova', location: 'Lahore (Remote)',
    match: 87,
    matched: ['JavaScript', 'React', 'HTML', 'CSS', 'Git'],
    missing: ['TypeScript', 'Next.js'],
    explain: 'Strong match — your React and JavaScript skills align closely with the core stack. Missing TypeScript is a minor gap.'
  },
  {
    id: 2, title: 'React Developer', company: 'PixelWorks', location: 'Karachi (Hybrid)',
    match: 79,
    matched: ['JavaScript', 'React', 'Git'],
    missing: ['Redux', 'Jest', 'TypeScript'],
    explain: 'Good fit based on React experience. Testing and state management tools are the main gaps.'
  },
  {
    id: 3, title: 'Data Analyst (Entry)', company: 'InsightHub', location: 'Islamabad',
    match: 61,
    matched: ['Python', 'SQL'],
    missing: ['Pandas', 'Power BI', 'Statistics'],
    explain: 'Partial match — your Python and SQL foundations help, but analyst-specific tools are missing.'
  }
];

const MOCK_GAP = {
  have: ['JavaScript', 'React', 'HTML', 'CSS', 'Git', 'Python', 'SQL'],
  improve: ['Git', 'SQL'],
  missing: ['TypeScript', 'Next.js', 'Redux', 'Jest']
};

const MOCK_PLAN = [
  { day: 'Day 1', title: 'TypeScript Fundamentals', desc: 'Types, interfaces, generics. Build 3 small typed functions.' },
  { day: 'Day 2', title: 'TypeScript with React', desc: 'Convert one existing component to TS with proper props typing.' },
  { day: 'Day 3', title: 'Next.js Basics', desc: 'Routing, pages, and data fetching. Build a 2-page app.' },
  { day: 'Day 4', title: 'State Management with Redux', desc: 'Learn actions, reducers, store. Refactor a small app.' },
  { day: 'Day 5', title: 'Testing with Jest', desc: 'Write unit tests for 3 utility functions and 1 component.' },
  { day: 'Day 6', title: 'Mini Project', desc: 'Build a small dashboard using Next.js + TS + Redux.' },
  { day: 'Day 7', title: 'Polish & Portfolio', desc: 'Deploy the project, write a README, update your resume.' }
];

const MOCK_INTERVIEW_QUESTIONS = [
  'Explain the difference between state and props in React.',
  'How would you optimize a React app that feels slow on initial load?',
  'What is the virtual DOM and how does React use it?'
];


// ============================================================
//  DASHBOARD
// ============================================================
function loadDashboard() {
  const scores = { skills: 82, projects: 74, clarity: 68, role: 79 };
  const overall = Math.round((scores.skills + scores.projects + scores.clarity + scores.role) / 4);

  document.getElementById('readiness-score').textContent = overall + '%';
  document.getElementById('stat-profile').textContent = overall + '%';
  document.getElementById('stat-jobs').textContent = MOCK_JOBS.length;
  document.getElementById('stat-gaps').textContent = MOCK_GAP.missing.length;
  document.getElementById('stat-plan').textContent = '0/7';

  ['skills', 'projects', 'clarity', 'role'].forEach(k => {
    document.getElementById('bar-' + k).style.width = scores[k] + '%';
    document.getElementById('val-' + k).textContent = scores[k] + '%';
  });
}


// ============================================================
//  RESUME UPLOAD
// ============================================================
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', e => {
  e.preventDefault(); dropzone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', e => {
  if (e.target.files.length) handleFile(e.target.files[0]);
});

function handleFile(file) {
  const status = document.getElementById('uploadStatus');
  status.classList.remove('hidden', 'success', 'error');
  status.classList.add('loading');
  status.textContent = '⏳ Analyzing your resume...';

  if (file.type !== 'application/pdf') {
    status.classList.replace('loading', 'error');
    status.textContent = '❌ Please upload a PDF file.';
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    status.classList.replace('loading', 'error');
    status.textContent = '❌ File too large (max 5MB).';
    return;
  }

  // TODO: Replace this timeout with a real fetch to /api/resume/upload & /api/resume/analyze
  setTimeout(() => {
    status.classList.replace('loading', 'success');
    status.textContent = '✅ Resume analyzed successfully!';
    renderProfile(MOCK_PROFILE);
  }, 1500);
}

function renderProfile(p) {
  const box = document.getElementById('profileResult');
  box.classList.remove('hidden');

  document.getElementById('p-skills').innerHTML =
    p.skills.map(s => `<span class="chip">${s}</span>`).join('');
  document.getElementById('p-exp').innerHTML =
    p.experience.map(e => `<li>${e}</li>`).join('');
  document.getElementById('p-edu').innerHTML =
    p.education.map(e => `<li>${e}</li>`).join('');
  document.getElementById('p-proj').innerHTML =
    p.projects.map(e => `<li>${e}</li>`).join('');
}


// ============================================================
//  JOBS
// ============================================================
function loadJobs() {
  const list = document.getElementById('jobList');
  list.innerHTML = MOCK_JOBS.map(j => `
    <div class="job-card">
      <div class="job-head">
        <div>
          <h4>${j.title}</h4>
          <div class="job-company">${j.company} · ${j.location}</div>
        </div>
        <div class="match-pill">${j.match}% match</div>
      </div>
      <div class="match-bar"><div class="match-fill" style="width:${j.match}%"></div></div>
      <div class="job-skills">
        ${j.matched.map(s => `<span class="chip ok">✓ ${s}</span>`).join('')}
        ${j.missing.map(s => `<span class="chip bad">✗ ${s}</span>`).join('')}
      </div>
      <p class="job-explain">${j.explain}</p>
      <div class="job-actions">
        <button class="btn-primary" onclick="selectJob(${j.id}, '${j.title}')">Target This Role</button>
      </div>
    </div>
  `).join('');
}

function selectJob(id, title) {
  document.getElementById('target-role-label').textContent = title;
  navigate('skills');
}


// ============================================================
//  SKILL GAP
// ============================================================
function loadSkillGap() {
  if (!document.getElementById('target-role-label').textContent ||
      document.getElementById('target-role-label').textContent === '—') {
    document.getElementById('target-role-label').textContent = 'Junior Frontend Developer';
  }
  document.getElementById('gap-have').innerHTML =
    MOCK_GAP.have.map(s => `<span class="chip ok">${s}</span>`).join('');
  document.getElementById('gap-improve').innerHTML =
    MOCK_GAP.improve.map(s => `<span class="chip warn">${s}</span>`).join('');
  document.getElementById('gap-missing').innerHTML =
    MOCK_GAP.missing.map(s => `<span class="chip bad">${s}</span>`).join('');
}


// ============================================================
//  LEARNING PLAN
// ============================================================
function loadPlan() {
  const list = document.getElementById('planList');
  list.innerHTML = MOCK_PLAN.map((p, i) => `
    <div class="plan-item">
      <input type="checkbox" id="task-${i}" onchange="updatePlanProgress()" />
      <div>
        <div class="day">${p.day}</div>
        <h5>${p.title}</h5>
        <p>${p.desc}</p>
      </div>
    </div>
  `).join('');
}

function updatePlanProgress() {
  const total = MOCK_PLAN.length;
  const done = document.querySelectorAll('.plan-item input:checked').length;
  document.getElementById('stat-plan').textContent = `${done}/${total}`;
}


// ============================================================
//  INTERVIEW
// ============================================================
let currentQIndex = 0;

function startInterview() {
  currentQIndex = 0;
  document.getElementById('interview-q').textContent = MOCK_INTERVIEW_QUESTIONS[0];
  document.getElementById('interview-answer').value = '';
  document.getElementById('interview-feedback').classList.add('hidden');
}

function submitAnswer() {
  const answer = document.getElementById('interview-answer').value.trim();
  if (!answer) { alert('Please type your answer first.'); return; }

  const fb = document.getElementById('interview-feedback');
  fb.classList.remove('hidden');

  // TODO: Replace with real API call to /api/interview/evaluate
  fb.innerHTML = `
    <h4>Feedback</h4>
    <p><b>Correctness:</b> 7/10 · <b>Completeness:</b> 6/10 · <b>Clarity:</b> 8/10</p>
    <p style="margin-top:10px;">Good understanding of the concept. Try adding a concrete example and mention performance implications to strengthen your answer.</p>
    <button class="btn-primary" style="margin-top:14px;" onclick="nextQuestion()">Next Question →</button>
  `;
}

function nextQuestion() {
  currentQIndex++;
  if (currentQIndex >= MOCK_INTERVIEW_QUESTIONS.length) {
    document.getElementById('interview-q').textContent = '🎉 Interview complete! Great practice session.';
    document.getElementById('interview-feedback').classList.add('hidden');
    return;
  }
  document.getElementById('interview-q').textContent = MOCK_INTERVIEW_QUESTIONS[currentQIndex];
  document.getElementById('interview-answer').value = '';
  document.getElementById('interview-feedback').classList.add('hidden');
}


// ============================================================
//  INIT
// ============================================================
window.addEventListener('DOMContentLoaded', () => {
  // Landing visible by default
});