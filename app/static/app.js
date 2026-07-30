/* NEXUS_PWA_DISABLED_FOR_STABILITY */
const state = {
  config: null,
  me: null,
  courses: [],
  dashboard: null,
  xr: [],
  homeContent: { banners: [], announcements: [] },
  heroIndex: 0,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const FALLBACK_BANNERS = [
  {
    badge: "PLATAFORMA XR",
    title: "Explora el aprendizaje inmersivo",
    body: "Tecnología XR, inteligencia artificial y contenido adaptativo para transformar la educación.",
    image_url: "/static/assets/nuvedra-hero.svg",
    cta_label: "Descubre NUVEDRA",
    cta_url: "#announcements-title",
  },
  {
    badge: "INTELIGENCIA ADAPTATIVA",
    title: "Aprendizaje que responde a cada estudiante",
    body: "Analítica académica, rutas personalizadas y apoyo oportuno desde una sola plataforma.",
    image_url: "/static/assets/nuvedra-hero.svg",
    cta_label: "Explorar analítica",
    cta_url: "#view-analytics",
  },
  {
    badge: "INNOVACIÓN DOCENTE",
    title: "Diseña experiencias educativas de próxima generación",
    body: "Integra Google Workspace, realidad aumentada, realidad virtual y recursos interactivos.",
    image_url: "/static/assets/nuvedra-hero.svg",
    cta_label: "Abrir Course Studio",
    cta_url: "/course-studio",
  },
];

const FALLBACK_ANNOUNCEMENTS = [
  { badge: "EVENTO DESTACADO", title: "Semana de la Innovación Educativa", body: "Conferencias, demostraciones y experiencias prácticas sobre IA, XR y diseño educativo.", cta_label: "Ver agenda", cta_url: "#upcoming-title" },
  { badge: "NOTICIAS", title: "NUVEDRA incorpora nuevas aulas inmersivas", body: "Experiencias colaborativas y accesibles para conectar la teoría con la práctica.", cta_label: "Leer más", cta_url: "#announcements-title" },
  { badge: "TALLER DESTACADO", title: "Diseño de experiencias de aprendizaje XR", body: "Taller práctico para docentes que desean integrar experiencias inmersivas en sus cursos.", cta_label: "Ver detalles", cta_url: "#upcoming-title" },
];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Error ${response.status}`);
  return data;
}

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeURL(value, fallback = "#") {
  const raw = String(value || "").trim();
  if (!raw) return fallback;
  if (raw.startsWith("/") || raw.startsWith("#")) return raw;
  try {
    const url = new URL(raw, location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : fallback;
  } catch {
    return fallback;
  }
}

function toast(message) {
  const el = $("#toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 3500);
}

function activateView(name) {
  $$(".view").forEach(view => view.classList.toggle("active", view.id === `view-${name}`));
  $$(".nav-item").forEach(button => {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    active ? button.setAttribute("aria-current", "page") : button.removeAttribute("aria-current");
  });
  $("#primary-nav")?.classList.remove("open");
  $("#menu-button")?.setAttribute("aria-expanded", "false");
  $("#main")?.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function dateParts(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return {
    day: Number.isNaN(d.getTime()) ? "--" : d.getDate(),
    month: Number.isNaN(d.getTime()) ? "---" : d.toLocaleDateString("es-PR", { month: "short" }).toUpperCase(),
  };
}

function renderHero(index = 0) {
  const banners = state.homeContent.banners.length ? state.homeContent.banners : FALLBACK_BANNERS;
  if (!banners.length) return;
  state.heroIndex = (index + banners.length) % banners.length;
  const item = banners[state.heroIndex];
  const title = String(item.title || "NUVEDRA");
  const words = title.split(" ");
  const splitAt = Math.max(1, Math.floor(words.length / 2));
  const first = words.slice(0, splitAt).join(" ");
  const second = words.slice(splitAt).join(" ");

  $("#hero-badge").textContent = item.badge || "NUVEDRA";
  $("#home-title").innerHTML = `${escapeHTML(first)} <span>${escapeHTML(second)}</span>`;
  $("#hero-body").textContent = item.body || "";
  const image = $("#hero-image");
  image.src = safeURL(item.image_url, "/static/assets/nuvedra-hero.svg");
  const cta = $("#hero-cta");
  cta.href = safeURL(item.cta_url, "#announcements-title");
  cta.innerHTML = `<span aria-hidden="true">▶</span> ${escapeHTML(item.cta_label || "Descubre NUVEDRA")}`;

  $("#hero-dots").innerHTML = banners.map((_, i) => `<button type="button" data-slide="${i}" class="${i === state.heroIndex ? "active" : ""}" aria-label="Mostrar banner ${i + 1}" aria-current="${i === state.heroIndex ? "true" : "false"}"></button>`).join("");
  $$('[data-slide]').forEach(button => button.addEventListener("click", () => renderHero(Number(button.dataset.slide))));
}

function renderHomeContent() {
  renderHero(0);
  const announcements = state.homeContent.announcements.length ? state.homeContent.announcements : FALLBACK_ANNOUNCEMENTS;
  const container = $("#announcement-cards");
  if (!container) return;
  container.innerHTML = announcements.slice(0, 6).map((item, index) => `
    <article class="announcement-card">
      <span class="announcement-badge"><span aria-hidden="true">${index === 0 ? "▣" : index === 1 ? "◇" : "✦"}</span>${escapeHTML(item.badge || "ANUNCIO")}</span>
      <h3>${escapeHTML(item.title)}</h3>
      <p>${escapeHTML(item.body)}</p>
      <a href="${escapeHTML(safeURL(item.cta_url, "#"))}">${escapeHTML(item.cta_label || "Leer más")} →</a>
    </article>
  `).join("");
}

function renderDashboard() {
  if (!state.dashboard) return;
  const { stats, upcoming } = state.dashboard;
  const statsGrid = $("#stats-grid");
  if (statsGrid) {
    const cards = [
      [stats.courses, "Cursos activos", "Organización modular"],
      [stats.activities, "Actividades", "Tareas, foros y laboratorios"],
      [stats.xrExperiences, "Experiencias XR", "VR, AR y modelos 3D"],
      [`${stats.engagement}%`, "Participación", "Indicador semanal"],
    ];
    statsGrid.innerHTML = cards.map(card => `<article class="stat-card"><span>${escapeHTML(card[0])}</span><strong>${escapeHTML(card[1])}</strong><small>${escapeHTML(card[2])}</small></article>`).join("");
  }

  const upcomingList = $("#upcoming-list");
  if (upcomingList) {
    upcomingList.innerHTML = upcoming.map(item => {
      const d = dateParts(item.due_date);
      return `<article class="list-item"><div class="date-tile"><small>${escapeHTML(d.month)}</small>${escapeHTML(d.day)}</div><div class="list-item-content"><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(item.course_code)} · ${escapeHTML(item.points)} puntos</small></div><span class="chip">${escapeHTML(String(item.activity_type || "").replace("_", " "))}</span></article>`;
    }).join("") || '<div class="empty-state">No hay actividades próximas.</div>';
  }
}

function renderCourses() {
  const grid = $("#course-grid");
  if (!grid) return;
  grid.innerHTML = state.courses.map(course => `<article class="course-card" data-course-id="${Number(course.id)}" tabindex="0" role="button" aria-label="Abrir ${escapeHTML(course.title)}"><div class="course-band" style="background:${escapeHTML(course.accent || "#4338CA")}"></div><div class="course-body"><span class="course-code">${escapeHTML(course.code)}${course.xr_enabled ? " · XR" : ""}</span><h2>${escapeHTML(course.title)}</h2><p>${escapeHTML(course.description)}</p><div class="course-meta"><span>${escapeHTML(course.module_count)} módulos</span><span>${escapeHTML(course.activity_count)} actividades</span><span>${escapeHTML(course.progress)}%</span></div><div class="progress" style="--accent:${escapeHTML(course.accent || "#4338CA")};--progress:${Number(course.progress) || 0}%"><i></i></div></div></article>`).join("");
  $$(".course-card").forEach(card => {
    const open = () => openCourse(Number(card.dataset.courseId));
    card.addEventListener("click", open);
    card.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); } });
  });
}

async function openCourse(id) {
  try {
    const data = await api(`/api/courses/${id}`);
    const panel = $("#course-detail");
    panel.hidden = false;
    panel.innerHTML = `<div class="panel-heading"><div><p class="eyebrow">${escapeHTML(data.course.code)}</p><h2>${escapeHTML(data.course.title)}</h2><p>${escapeHTML(data.course.instructor)}</p></div><button class="button secondary" id="close-course">Cerrar</button></div>${data.modules.map(module => `<section class="module"><h3>${escapeHTML(module.position)}. ${escapeHTML(module.title)}</h3>${module.activities.length ? module.activities.map(activity => `<div class="activity"><span class="type-icon">${activity.activity_type === "xr_lab" ? "XR" : "✓"}</span><div><strong>${escapeHTML(activity.title)}</strong><small>${escapeHTML(activity.due_date || "Sin fecha")} · ${escapeHTML(activity.points)} puntos</small></div></div>`).join("") : "<p>Este módulo todavía no tiene actividades.</p>"}</section>`).join("")}`;
    $("#close-course").addEventListener("click", () => { panel.hidden = true; });
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast(error.message);
  }
}

function renderXR() {
  const grid = $("#xr-cards");
  if (!grid) return;
  grid.innerHTML = state.xr.map(item => `<article class="xr-card"><small>${escapeHTML(item.mode)} · ${escapeHTML(item.course_code)}</small><h2>${escapeHTML(item.title)}</h2><p>${escapeHTML(item.description)}</p></article>`).join("");
}

async function updateGoogleIdentity() {
  state.me = await api("/api/me");
  const buttons = $$('[data-google-connect]');
  const status = $("#google-status");
  const authNote = $("#auth-status");
  if (state.me.authenticated) {
    buttons.forEach(button => {
      button.textContent = `Google conectado: ${state.me.user.email}`;
      button.dataset.connected = "true";
    });
    if (status) {
      status.className = "notice success";
      status.textContent = `Google conectado como ${state.me.user.email}.`;
    }
    if (authNote) authNote.textContent = `Sesión de Google activa como ${state.me.user.email}.`;
  } else {
    buttons.forEach(button => {
      button.innerHTML = button.id === "connect-google" ? '<span class="google-g" aria-hidden="true">G</span><span>Continuar con Google</span>' : "Conectar cuenta de Google";
      button.dataset.connected = "false";
    });
    if (status) {
      status.className = "notice info";
      status.textContent = state.config.googleConfigured ? "Conecta tu cuenta institucional para usar Classroom, Drive, Calendar y Meet." : "Modo demostración: configura OAuth en Google Cloud para activar la integración real.";
    }
  }
}

async function handleGoogleConnect(event) {
  const connected = event.currentTarget.dataset.connected === "true";
  if (connected) {
    try {
      await api("/auth/logout", { method: "POST" });
      await updateGoogleIdentity();
      toast("Cuenta de Google desconectada.");
    } catch (error) {
      toast(error.message);
    }
  } else if (!state.config.googleConfigured) {
    toast("Primero configura las credenciales OAuth en Render.");
  } else {
    location.href = "/auth/google/login";
  }
}

async function googleAction(action) {
  const title = $("#google-result-title");
  const results = $("#google-results");
  if (action === "meet") {
    $("#meet-dialog").showModal();
    return;
  }
  const endpoints = { classroom: "/api/google/classroom/courses", drive: "/api/google/drive/files", calendar: "/api/google/calendar/events" };
  title.textContent = `Cargando ${action}…`;
  results.innerHTML = '<div class="empty-state">Consultando Google Workspace…</div>';
  try {
    const data = await api(endpoints[action]);
    if (action === "classroom") {
      const items = data.courses || [];
      title.textContent = "Cursos de Google Classroom";
      results.innerHTML = items.length ? items.map(item => `<div class="data-row"><span class="data-row-icon">C</span><div><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.section || item.courseState || "")}</small></div><a href="${escapeHTML(safeURL(item.alternateLink, "#"))}" target="_blank" rel="noopener">Abrir</a></div>`).join("") : '<div class="empty-state">No se encontraron cursos activos.</div>';
    } else if (action === "drive") {
      const items = data.files || [];
      title.textContent = "Archivos recientes de Google Drive";
      results.innerHTML = items.length ? items.map(item => `<div class="data-row"><span class="data-row-icon">▤</span><div><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.mimeType)} · ${new Date(item.modifiedTime).toLocaleDateString("es-PR")}</small></div>${item.webViewLink ? `<a href="${escapeHTML(safeURL(item.webViewLink, "#"))}" target="_blank" rel="noopener">Abrir</a>` : ""}</div>`).join("") : '<div class="empty-state">No se encontraron archivos.</div>';
    } else {
      const items = data.items || [];
      title.textContent = "Próximos eventos de Google Calendar";
      results.innerHTML = items.length ? items.map(item => `<div class="data-row"><span class="data-row-icon">21</span><div><strong>${escapeHTML(item.summary || "Evento sin título")}</strong><small>${new Date(item.start?.dateTime || item.start?.date).toLocaleString("es-PR")}</small></div><a href="${escapeHTML(safeURL(item.htmlLink, "#"))}" target="_blank" rel="noopener">Abrir</a></div>`).join("") : '<div class="empty-state">No hay eventos próximos.</div>';
    }
  } catch (error) {
    title.textContent = "No se pudo cargar Google Workspace";
    results.innerHTML = `<div class="notice error">${escapeHTML(error.message)}</div>`;
  }
}

async function createMeet(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    title: form.get("title"),
    start_iso: form.get("start_iso") ? new Date(form.get("start_iso")).toISOString() : null,
    duration_minutes: Number(form.get("duration_minutes")),
    attendees: String(form.get("attendees") || "").split(",").map(value => value.trim()).filter(Boolean),
  };
  try {
    const data = await api("/api/google/meet/create", { method: "POST", body: JSON.stringify(payload) });
    $("#meet-dialog").close();
    toast("Videoclase creada en Google Calendar.");
    const link = data.hangoutLink || data.htmlLink;
    if (link) window.open(link, "_blank", "noopener");
  } catch (error) {
    toast(error.message);
  }
}

function bindEvents() {
  $$(".nav-item").forEach(button => button.addEventListener("click", () => activateView(button.dataset.view)));
  $$('[data-go]').forEach(element => element.addEventListener("click", event => {
    event.preventDefault();
    activateView(element.dataset.go);
  }));
  $("#menu-button")?.addEventListener("click", event => {
    const nav = $("#primary-nav");
    const open = nav.classList.toggle("open");
    event.currentTarget.setAttribute("aria-expanded", String(open));
  });
  $("#hero-prev")?.addEventListener("click", () => renderHero(state.heroIndex - 1));
  $("#hero-next")?.addEventListener("click", () => renderHero(state.heroIndex + 1));
  $("#hero-cta")?.addEventListener("click", event => {
    const href = event.currentTarget.getAttribute("href") || "";
    if (href.startsWith("#view-")) {
      event.preventDefault();
      activateView(href.replace("#view-", ""));
    }
  });
  $$('[data-google-connect]').forEach(button => button.addEventListener("click", handleGoogleConnect));
  $$('[data-google-action]').forEach(button => button.addEventListener("click", () => googleAction(button.dataset.googleAction)));
  $("#meet-form")?.addEventListener("submit", createMeet);
  $("#new-course-button")?.addEventListener("click", () => { location.href = "/course-studio"; });
  $("#request-account")?.addEventListener("click", () => toast("La solicitud de cuentas se administrará desde el panel de usuarios."));
  $("#toggle-password")?.addEventListener("click", event => {
    const input = $("#login-password");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    event.currentTarget.setAttribute("aria-label", show ? "Ocultar contraseña" : "Mostrar contraseña");
  });
}

async function loadHomeContent() {
  try {
    state.homeContent = await api("/api/home-content", { cache: "no-store" });
  } catch {
    state.homeContent = { banners: FALLBACK_BANNERS, announcements: FALLBACK_ANNOUNCEMENTS };
  }
}

async function init() {
  try {
    const [config, dashboard, courses, xr] = await Promise.all([
      api("/api/config"),
      api("/api/dashboard"),
      api("/api/courses"),
      api("/api/xr"),
    ]);
    state.config = config;
    state.dashboard = dashboard;
    state.courses = courses;
    state.xr = xr;
    await loadHomeContent();
    document.title = state.config.appName || "NUVEDRA";
    renderHomeContent();
    renderDashboard();
    renderCourses();
    renderXR();
    bindEvents();
    await updateGoogleIdentity();

    if (new URLSearchParams(location.search).get("google") === "connected") {
      history.replaceState({}, "", "/");
      toast("Google Workspace conectado correctamente.");
      activateView("google");
    }

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.getRegistrations().then(registrations => registrations.forEach(registration => registration.unregister())).catch(() => {});
    }
  } catch (error) {
    document.body.innerHTML = `<main style="padding:40px"><h1>No se pudo iniciar NUVEDRA</h1><p>${escapeHTML(error.message)}</p><p><a href="/admin/system">Revisar el sistema</a></p></main>`;
  }
}

document.addEventListener("DOMContentLoaded", init);
