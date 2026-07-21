const state = { config: null, me: null, courses: [], dashboard: null, xr: [] };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Error ${response.status}`);
  return data;
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 3500);
}

function activateView(name) {
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${name}`));
  $$(".nav-item").forEach(btn => {
    const active = btn.dataset.view === name;
    btn.classList.toggle("active", active);
    active ? btn.setAttribute("aria-current", "page") : btn.removeAttribute("aria-current");
  });
  $("#main").focus({ preventScroll: true });
  $(".sidebar").classList.remove("open");
}

function dateParts(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return { day: d.getDate(), month: d.toLocaleDateString("es-PR", { month: "short" }).toUpperCase() };
}

function renderDashboard() {
  const { stats, upcoming, announcements } = state.dashboard;
  const cards = [
    [stats.courses, "Cursos activos", "Organización modular"],
    [stats.activities, "Actividades", "Tareas, foros y laboratorios"],
    [stats.xrExperiences, "Experiencias XR", "VR, AR y modelos 3D"],
    [`${stats.engagement}%`, "Participación", "Indicador semanal"],
  ];
  $("#stats-grid").innerHTML = cards.map(c => `<article class="stat-card"><span>${c[0]}</span><strong>${c[1]}</strong><small>${c[2]}</small></article>`).join("");
  $("#upcoming-list").innerHTML = upcoming.map(item => {
    const d = dateParts(item.due_date);
    return `<article class="list-item"><div class="date-tile"><small>${d.month}</small>${d.day}</div><div class="list-item-content"><strong>${item.title}</strong><small>${item.course_code} · ${item.points} puntos</small></div><span class="chip">${item.activity_type.replace('_',' ')}</span></article>`;
  }).join("");
  $("#announcement-list").innerHTML = announcements.map(item => `<article class="list-item"><div class="type-icon">✦</div><div class="list-item-content"><strong>${item.title}</strong><small>${item.body}</small><small>${item.author}${item.course_code ? ` · ${item.course_code}` : ""}</small></div></article>`).join("");
}

function renderCourses() {
  $("#course-grid").innerHTML = state.courses.map(c => `<article class="course-card" data-course-id="${c.id}" tabindex="0" role="button" aria-label="Abrir ${c.title}"><div class="course-band" style="--accent:${c.accent};background:${c.accent}"></div><div class="course-body"><span class="course-code">${c.code}${c.xr_enabled ? " · XR" : ""}</span><h2>${c.title}</h2><p>${c.description}</p><div class="course-meta"><span>${c.module_count} módulos</span><span>${c.activity_count} actividades</span><span>${c.progress}%</span></div><div class="progress" style="--accent:${c.accent};--progress:${c.progress}%"><i></i></div></div></article>`).join("");
  $$(".course-card").forEach(card => {
    const open = () => openCourse(Number(card.dataset.courseId));
    card.addEventListener("click", open);
    card.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") open(); });
  });
}

async function openCourse(id) {
  try {
    const data = await api(`/api/courses/${id}`);
    const panel = $("#course-detail");
    panel.hidden = false;
    panel.innerHTML = `<div class="panel-heading"><div><p class="eyebrow">${data.course.code}</p><h2>${data.course.title}</h2><p>${data.course.instructor}</p></div><button class="button secondary" id="close-course">Cerrar</button></div>${data.modules.map(m => `<section class="module"><h3>${m.position}. ${m.title}</h3>${m.activities.length ? m.activities.map(a => `<div class="activity"><span class="type-icon">${a.activity_type === 'xr_lab' ? 'XR' : '✓'}</span><div><strong>${a.title}</strong><small>${a.due_date || 'Sin fecha'} · ${a.points} puntos</small></div></div>`).join('') : '<p>Este módulo todavía no tiene actividades.</p>'}</section>`).join('')}`;
    $("#close-course").addEventListener("click", () => panel.hidden = true);
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { toast(error.message); }
}

function renderXR() {
  $("#xr-cards").innerHTML = state.xr.map(x => `<article class="xr-card"><small>${x.mode} · ${x.course_code}</small><h2>${x.title}</h2><p>${x.description}</p></article>`).join("");
}

async function updateGoogleIdentity() {
  state.me = await api("/api/me");
  const button = $("#connect-google");
  const status = $("#google-status");
  if (state.me.authenticated) {
    button.textContent = "Desconectar Google";
    button.dataset.connected = "true";
    status.className = "notice success";
    status.textContent = `Google conectado como ${state.me.user.email}.`;
    const initials = state.me.user.name?.split(" ").map(x => x[0]).slice(0, 2).join("") || "G";
    $(".avatar").textContent = initials;
    $(".profile-text strong").textContent = state.me.user.name || "Usuario Google";
    $(".profile-text small").textContent = "Cuenta conectada";
  } else {
    button.textContent = "Conectar cuenta de Google";
    button.dataset.connected = "false";
    status.className = "notice info";
    status.textContent = state.config.googleConfigured ? "Conecta tu cuenta institucional para usar Classroom, Drive, Calendar y Meet." : "Modo demostración: configura OAuth en Google Cloud para activar la integración real.";
  }
}

async function googleAction(action) {
  const title = $("#google-result-title");
  const results = $("#google-results");
  if (action === "meet") { $("#meet-dialog").showModal(); return; }
  const endpoints = { classroom: "/api/google/classroom/courses", drive: "/api/google/drive/files", calendar: "/api/google/calendar/events" };
  title.textContent = `Cargando ${action}…`;
  results.innerHTML = '<div class="empty-state">Consultando Google Workspace…</div>';
  try {
    const data = await api(endpoints[action]);
    if (action === "classroom") {
      const rows = data.courses || [];
      title.textContent = "Cursos de Google Classroom";
      results.innerHTML = rows.length ? rows.map(x => `<div class="data-row"><span class="data-row-icon">C</span><div><strong>${x.name}</strong><small>${x.section || x.courseState || ''}</small></div><a href="${x.alternateLink || '#'}" target="_blank" rel="noopener">Abrir</a></div>`).join('') : '<div class="empty-state">No se encontraron cursos activos.</div>';
    } else if (action === "drive") {
      const rows = data.files || [];
      title.textContent = "Archivos recientes de Google Drive";
      results.innerHTML = rows.length ? rows.map(x => `<div class="data-row"><span class="data-row-icon">▤</span><div><strong>${x.name}</strong><small>${x.mimeType} · ${new Date(x.modifiedTime).toLocaleDateString('es-PR')}</small></div>${x.webViewLink ? `<a href="${x.webViewLink}" target="_blank" rel="noopener">Abrir</a>` : ''}</div>`).join('') : '<div class="empty-state">No se encontraron archivos.</div>';
    } else {
      const rows = data.items || [];
      title.textContent = "Próximos eventos de Google Calendar";
      results.innerHTML = rows.length ? rows.map(x => `<div class="data-row"><span class="data-row-icon">21</span><div><strong>${x.summary || 'Evento sin título'}</strong><small>${new Date(x.start?.dateTime || x.start?.date).toLocaleString('es-PR')}</small></div><a href="${x.htmlLink}" target="_blank" rel="noopener">Abrir</a></div>`).join('') : '<div class="empty-state">No hay eventos próximos.</div>';
    }
  } catch (error) {
    title.textContent = "No se pudo cargar Google Workspace";
    results.innerHTML = `<div class="notice error">${error.message}</div>`;
  }
}

async function createMeet(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    title: form.get("title"),
    start_iso: form.get("start_iso") ? new Date(form.get("start_iso")).toISOString() : null,
    duration_minutes: Number(form.get("duration_minutes")),
    attendees: String(form.get("attendees") || "").split(",").map(x => x.trim()).filter(Boolean),
  };
  try {
    const data = await api("/api/google/meet/create", { method: "POST", body: JSON.stringify(payload) });
    $("#meet-dialog").close();
    toast("Videoclase creada en Google Calendar.");
    const link = data.hangoutLink || data.htmlLink;
    if (link) window.open(link, "_blank", "noopener");
  } catch (error) { toast(error.message); }
}

function bindEvents() {
  $$(".nav-item").forEach(btn => btn.addEventListener("click", () => activateView(btn.dataset.view)));
  $$('[data-go]').forEach(btn => btn.addEventListener("click", () => activateView(btn.dataset.go)));
  $("#menu-button").addEventListener("click", () => $(".sidebar").classList.toggle("open"));
  $("#connect-google").addEventListener("click", async e => {
    if (e.currentTarget.dataset.connected === "true") {
      await api("/auth/logout", { method: "POST" });
      await updateGoogleIdentity();
      toast("Cuenta de Google desconectada.");
    } else if (!state.config.googleConfigured) {
      toast("Primero configura las credenciales OAuth en el archivo .env.");
    } else {
      location.href = "/auth/google/login";
    }
  });
  $$('[data-google-action]').forEach(btn => btn.addEventListener("click", () => googleAction(btn.dataset.googleAction)));
  $("#meet-form").addEventListener("submit", createMeet);
  $("#new-course-button").addEventListener("click", () => toast("El diseñador visual de cursos se incorpora en la siguiente fase."));
  $("#global-search").addEventListener("input", e => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) return renderCourses();
    activateView("courses");
    const filtered = state.courses.filter(c => `${c.code} ${c.title} ${c.description}`.toLowerCase().includes(q));
    const original = state.courses;
    state.courses = filtered;
    renderCourses();
    state.courses = original;
  });
}

async function init() {
  try {
    [state.config, state.dashboard, state.courses, state.xr] = await Promise.all([
      api("/api/config"), api("/api/dashboard"), api("/api/courses"), api("/api/xr")
    ]);
    document.title = state.config.appName;
    renderDashboard(); renderCourses(); renderXR(); bindEvents(); await updateGoogleIdentity();
    if (new URLSearchParams(location.search).get("google") === "connected") {
      history.replaceState({}, "", "/");
      toast("Google Workspace conectado correctamente.");
      activateView("google");
    }
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  } catch (error) {
    document.body.innerHTML = `<main style="padding:40px"><h1>No se pudo iniciar NEXUS EDU XR</h1><p>${error.message}</p></main>`;
  }
}

document.addEventListener("DOMContentLoaded", init);
