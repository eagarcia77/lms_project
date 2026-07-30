(() => {
  "use strict";

  const STORAGE_KEY = "nuvedra.language";
  const DEFAULT_LANGUAGE = "en";
  const supported = new Set(["en", "es"]);

  const text = {
    "Saltar al contenido principal": "Skip to main content",
    "Saltar al contenido": "Skip to content",
    "Abrir menú": "Open menu",
    "Navegación principal": "Primary navigation",
    "Inicio": "Home",
    "Cursos": "Courses",
    "Google Hub": "Google Hub",
    "Laboratorio XR": "XR Lab",
    "Analítica": "Analytics",
    "Características de la plataforma": "Platform features",
    "Inmersivo": "Immersive",
    "Inteligente": "Intelligent",
    "Innovador": "Innovative",
    "Administrar": "Manage",
    "Administrar anuncios y banners": "Manage announcements and banners",
    "PLATAFORMA XR": "XR PLATFORM",
    "Explora el": "Explore",
    "aprendizaje inmersivo": "immersive learning",
    "Tecnología XR, inteligencia artificial y contenido adaptativo para transformar la educación.": "XR technology, artificial intelligence, and adaptive content to transform education.",
    "Descubre NUVEDRA": "Discover NUVEDRA",
    "Banner anterior": "Previous banner",
    "Banner siguiente": "Next banner",
    "Seleccionar banner": "Select banner",
    "Información destacada": "Featured information",
    "Anuncios y novedades": "Announcements and updates",
    "Administrar anuncios": "Manage announcements",
    "Beneficios de NUVEDRA": "NUVEDRA benefits",
    "Aprendizaje inmersivo": "Immersive learning",
    "Experiencias XR que conectan la teoría con la práctica.": "XR experiences that connect theory with practice.",
    "Inteligencia adaptativa": "Adaptive intelligence",
    "Contenido que responde al progreso del estudiante.": "Content that responds to each student's progress.",
    "Colaboración global": "Global collaboration",
    "Google Workspace, Meet y trabajo compartido.": "Google Workspace, Meet, and collaborative work.",
    "Seguridad y privacidad": "Security and privacy",
    "Acceso protegido y trazabilidad administrativa.": "Protected access and administrative traceability.",
    "ACCESO A LA PLATAFORMA": "PLATFORM ACCESS",
    "Bienvenido a": "Welcome to",
    "Accede a tu cuenta para continuar tu aprendizaje.": "Sign in to continue your learning.",
    "Continuar con Google": "Continue with Google",
    "o continúa con tu correo": "or continue with your email",
    "Correo electrónico": "Email address",
    "Contraseña": "Password",
    "Mantener sesión iniciada": "Keep me signed in",
    "Iniciar sesión": "Sign in",
    "¿Olvidé mi contraseña?": "Forgot my password?",
    "Solicitar una cuenta": "Request an account",
    "La cuenta por correo utiliza el acceso administrativo durante esta fase.": "Email sign-in currently uses the administrative access system.",
    "Próximamente": "Coming up",
    "Agenda académica": "Academic calendar",
    "Ver calendario": "View calendar",
    "Actividad": "Activity",
    "Indicadores de la plataforma": "Platform indicators",
    "Indicadores académicos": "Academic indicators",
    "Aprendizaje": "Learning",
    "Mis cursos": "My courses",
    "Contenido organizado por módulos, con progreso claro y acceso directo a cada actividad.": "Content organized by modules, with clear progress and direct access to each activity.",
    "Crear curso": "Create course",
    "Un solo lugar para Classroom, Drive, Calendar, Meet, Docs, Slides, Sheets, Forms y YouTube.": "One place for Classroom, Drive, Calendar, Meet, Docs, Slides, Sheets, Forms, and YouTube.",
    "Conectar cuenta de Google": "Connect Google account",
    "La plataforma opera en modo demostración hasta configurar OAuth en Google Cloud.": "The platform runs in demonstration mode until Google Cloud OAuth is configured.",
    "Sincronizar cursos y tareas": "Sync courses and assignments",
    "Archivos y materiales": "Files and materials",
    "Agenda y fechas límite": "Schedule and due dates",
    "Crear una videoclase": "Create a video class",
    "Documentos colaborativos": "Collaborative documents",
    "Presentaciones académicas": "Academic presentations",
    "Datos y calificaciones": "Data and grades",
    "Pruebas y encuestas": "Quizzes and surveys",
    "Datos conectados": "Connected data",
    "Selecciona una aplicación": "Select an application",
    "Conecta Google y selecciona Classroom, Drive o Calendar.": "Connect Google and select Classroom, Drive, or Calendar.",
    "Laboratorio de aprendizaje inmersivo": "Immersive learning lab",
    "Experiencias accesibles desde computadora, móvil, Meta Quest, Apple Vision Pro y otros dispositivos compatibles.": "Accessible experiences on computers, mobile devices, Meta Quest, Apple Vision Pro, and other compatible devices.",
    "Realidad aumentada": "Augmented reality",
    "Objeto 3D interactivo": "Interactive 3D object",
    "Móvil": "Mobile",
    "Ver en mi espacio": "View in my space",
    "Realidad virtual": "Virtual reality",
    "Salón de cobertura Wi-Fi": "Wi-Fi coverage classroom",
    "Punto de acceso": "Access point",
    "Espacio académico": "Academic workspace",
    "Acceso académico": "Academic access",
    "Acceso para profesores y estudiantes": "Access for instructors and students",
    "Utilice su cuenta de Google institucional. NUVEDRA mostrará únicamente los cursos y funciones asignados por el administrador.": "Use your institutional Google account. NUVEDRA will display only the courses and functions assigned by the administrator.",
    "La funciones dependen del rol asignado por el administrador.": "Functions depend on the role assigned by the administrator.",
    "Las funciones dependen del rol asignado por el administrador.": "Functions depend on the role assigned by the administrator.",
    "Cursos que desarrollo": "Courses I teach",
    "Cursos en los que estudio": "Courses I take",
    "Profesor": "Instructor",
    "Profesores": "Instructors",
    "Estudiante": "Student",
    "Estudiantes": "Students",
    "Crear y editar contenido": "Create and edit content",
    "Entrar al curso": "Enter course",
    "Su cuenta está conectada, pero todavía no tiene un curso activo asignado. Comuníquese con el administrador.": "Your account is connected, but no active course has been assigned yet. Contact the administrator.",
    "Salir": "Sign out",
    "Volver": "Back",
    "Volver al curso": "Back to course",
    "Volver al módulo": "Back to module",
    "Todos los cursos": "All courses",
    "Curso del profesor": "Instructor course",
    "El administrador creó y asignó el curso. Como profesor, puede desarrollar módulos, contenido y evaluaciones.": "The administrator created and assigned the course. As the instructor, you can develop modules, content, and assessments.",
    "Crear módulo": "Create module",
    "Módulos": "Modules",
    "Editar módulo": "Edit module",
    "Información del módulo": "Module information",
    "Título": "Title",
    "Descripción": "Description",
    "Resultados de aprendizaje": "Learning outcomes",
    "Duración": "Duration",
    "Duración estimada": "Estimated duration",
    "Posición": "Position",
    "Orden": "Order",
    "Estado": "Status",
    "Borrador": "Draft",
    "Publicado": "Published",
    "Programado": "Scheduled",
    "Oculto": "Hidden",
    "Activo": "Active",
    "Activo para estudiantes": "Active for students",
    "Archivado": "Archived",
    "Guardar módulo": "Save module",
    "Añadir contenido o evaluación": "Add content or assessment",
    "Tipo": "Type",
    "Contenido, instrucciones o pregunta": "Content, instructions, or question",
    "Enlace externo o de Google": "External or Google link",
    "URL para incrustar, WebXR o multimedia": "Embed, WebXR, or media URL",
    "Puntos": "Points",
    "Fecha límite": "Due date",
    "Alternativa accesible": "Accessible alternative",
    "Descripción, transcripción o actividad equivalente.": "Description, transcript, or equivalent activity.",
    "Añadir al módulo": "Add to module",
    "Google Hub sencillo:": "Simple Google Hub:",
    "cree el recurso en": "create the resource in",
    "luego pegue el enlace compartido.": "then paste the shared link.",
    "Contenido del módulo": "Module content",
    "Elemento": "Item",
    "Acciones": "Actions",
    "Editar": "Edit",
    "Vista previa": "Preview",
    "No hay contenido.": "There is no content yet.",
    "Editar contenido o evaluación": "Edit content or assessment",
    "Contenido HTML": "HTML content",
    "Enlace externo o Google": "External or Google link",
    "URL incrustada": "Embedded URL",
    "Configuración avanzada JSON": "Advanced JSON configuration",
    "Guardar cambios": "Save changes",
    "Responder evaluación": "Submit assessment",
    "Respuesta": "Response",
    "Enlace de la respuesta": "Response link",
    "Enviar respuesta": "Submit response",
    "Observador": "Observer",
    "Google todavía no está configurado": "Google is not configured yet",
    "Conectar Google": "Connect Google",
    "Google Drive": "Google Drive",
    "Google Drive es opcional. Conecte Google para seleccionar archivos o simplemente pegue un enlace compartido.": "Google Drive is optional. Connect Google to select files, or simply paste a shared link.",
    "Google Hub sencillo": "Simple Google Hub",
    "Opción 1: pegar enlace compartido": "Option 1: paste a shared link",
    "Opción 2: seleccionar desde Drive": "Option 2: select from Drive",
    "Enlace compartido": "Shared link",
    "Vincular al módulo": "Link to module",
    "La conexión con Google es independiente de la cuenta administrativa y solamente se usa para seleccionar o crear recursos.": "The Google connection is separate from the administrative account and is used only to select or create resources.",
    "Vincular": "Link",
    "Google Drive no devolvió archivos.": "Google Drive did not return any files.",
    "Panel general": "Dashboard",
    "Inicio y operaciones": "Overview and operations",
    "Portada y anuncios": "Homepage and announcements",
    "Banners, avisos y programación": "Banners, notices, and scheduling",
    "Diseño académico": "Academic design",
    "Cursos, módulos y evaluación": "Courses, modules, and assessment",
    "Innovación IA/XR": "AI/XR innovation",
    "IA, RA, VR, 360 y calidad": "AI, AR, VR, 360, and quality",
    "Gestión de cursos": "Course management",
    "Estados y supervisión": "Status and oversight",
    "Matrículas": "Enrollments",
    "Participantes y roles": "Participants and roles",
    "Usuarios": "Users",
    "Administradores y permisos": "Administrators and permissions",
    "Auditoría": "Audit",
    "Trazabilidad institucional": "Institutional traceability",
    "Respaldos": "Backups",
    "Exportación de datos": "Data export",
    "Sistema": "System",
    "Servicios y diagnóstico": "Services and diagnostics",
    "Administración integral": "Integrated administration",
    "Administración principal": "Main administration",
    "Abrir plataforma": "Open platform",
    "Vista de la plataforma": "Platform view",
    "Menú": "Menu",
    "NUVEDRA Course Workspace": "NUVEDRA Course Workspace",
    "Cree cursos, edite los existentes y organice contenido, Google Workspace y tecnologías emergentes desde un solo lugar.": "Create courses, edit existing courses, and organize content, Google Workspace, and emerging technologies in one place.",
    "Crear curso": "Create course",
    "Código": "Code",
    "Periodo": "Term",
    "Plantilla": "Template",
    "Curso en blanco": "Blank course",
    "Modelo 5E": "5E model",
    "Diseño inverso": "Backward design",
    "Aprendizaje por proyectos": "Project-based learning",
    "Aprendizaje inmersivo AR/VR": "Immersive AR/VR learning",
    "Crear y comenzar a editar": "Create and start editing",
    "Flujo integrado": "Integrated workflow",
    "Configure la información general del curso.": "Configure the general course information.",
    "Cree o edite módulos y resultados de aprendizaje.": "Create or edit modules and learning outcomes.",
    "Incorpore Docs, Slides, Sheets, Forms, Quiz, Meet y archivos de Drive.": "Add Docs, Slides, Sheets, Forms, quizzes, Meet, and Drive files.",
    "Añada H5P, simulaciones, RA, RV, WebXR y recorridos 360°.": "Add H5P, simulations, AR, VR, WebXR, and 360° tours.",
    "Revise la calidad y publique desde Innovación IA/XR.": "Review quality and publish from AI/XR Innovation.",
    "Cursos existentes": "Existing courses",
    "Administrar y editar": "Manage and edit",
    "Tecnologías emergentes": "Emerging technologies",
    "Configuración administrativa": "Administrative settings",
    "Profesor responsable": "Primary instructor",
    "Guardar configuración": "Save settings",
    "Asignaciones y acceso": "Assignments and access",
    "Profesor principal:": "Primary instructor:",
    "Administrar matrículas": "Manage enrollments",
    "Calidad e innovación": "Quality and innovation",
    "Estructura desarrollada por el profesor": "Structure developed by the instructor",
    "Supervisión": "Oversight",
    "Revisar estructura": "Review structure",
    "El profesor todavía no ha creado módulos.": "The instructor has not created modules yet.",
    "Separación de funciones:": "Separation of responsibilities:",
    "el administrador configura y asigna el curso; el profesor desarrolla módulos, contenido y evaluaciones desde": "the administrator configures and assigns the course; the instructor develops modules, content, and assessments from",
    "el estudiante solo consulta lo publicado y responde evaluaciones.": "students only view published content and submit assessments.",
    "Inglés": "English",
    "Español": "Spanish"
  };

  const attributes = {
    "Ingresa tu correo electrónico": "Enter your email address",
    "Ingresa tu contraseña": "Enter your password",
    "Mostrar contraseña": "Show password",
    "Agosto-Diciembre 2026": "August–December 2026",
    "Descripción textual, transcripción o actividad equivalente.": "Text description, transcript, or equivalent activity.",
    "https://docs.google.com/...": "https://docs.google.com/..."
  };

  function language() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return supported.has(stored) ? stored : DEFAULT_LANGUAGE;
  }

  function translateTextNode(node) {
    const value = node.nodeValue || "";
    const key = value.trim();
    if (!key || !Object.prototype.hasOwnProperty.call(text, key)) return;
    const leading = value.match(/^\s*/)?.[0] || "";
    const trailing = value.match(/\s*$/)?.[0] || "";
    node.nodeValue = `${leading}${text[key]}${trailing}`;
  }

  function shouldSkip(element) {
    return Boolean(element.closest("script,style,textarea,pre,code,[data-no-translate]"));
  }

  function translateTree(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const parent = node.parentElement;
      if (parent && !shouldSkip(parent)) translateTextNode(node);
    }
    root.querySelectorAll("[placeholder],[aria-label],[title]").forEach((element) => {
      for (const name of ["placeholder", "aria-label", "title"]) {
        const current = element.getAttribute(name);
        if (current && attributes[current]) element.setAttribute(name, attributes[current]);
        else if (current && text[current]) element.setAttribute(name, text[current]);
      }
    });
  }

  function addSwitcher(activeLanguage) {
    if (document.getElementById("nuvedra-language-switcher")) return;
    const style = document.createElement("style");
    style.textContent = `
      .nuvedra-language-switcher{position:fixed;right:14px;bottom:14px;z-index:9999;display:flex;gap:4px;padding:5px;background:rgba(9,11,43,.94);border:1px solid rgba(255,255,255,.25);border-radius:999px;box-shadow:0 8px 24px rgba(9,11,43,.25)}
      .nuvedra-language-switcher button{margin:0!important;padding:7px 11px!important;border:0;border-radius:999px;background:transparent;color:#fff;font:700 13px/1.2 Inter,Segoe UI,Arial,sans-serif;cursor:pointer}
      .nuvedra-language-switcher button[aria-pressed="true"]{background:#fff;color:#171a2b}
      .nuvedra-language-switcher button:focus-visible{outline:3px solid #ffb000;outline-offset:2px}
      @media(max-width:600px){.nuvedra-language-switcher{right:8px;bottom:8px}}
      @media(prefers-reduced-motion:reduce){.nuvedra-language-switcher *{transition:none!important}}
    `;
    document.head.appendChild(style);

    const container = document.createElement("div");
    container.id = "nuvedra-language-switcher";
    container.className = "nuvedra-language-switcher";
    container.setAttribute("role", "group");
    container.setAttribute("aria-label", activeLanguage === "es" ? "Seleccionar idioma" : "Select language");

    const options = [
      ["en", "English"],
      ["es", "Español"]
    ];
    for (const [code, label] of options) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.setAttribute("aria-pressed", String(activeLanguage === code));
      button.addEventListener("click", () => {
        localStorage.setItem(STORAGE_KEY, code);
        document.documentElement.lang = code;
        window.location.reload();
      });
      container.appendChild(button);
    }
    document.body.appendChild(container);
  }

  function apply() {
    const activeLanguage = language();
    document.documentElement.lang = activeLanguage;
    if (activeLanguage === "en") translateTree(document.body);
    addSwitcher(activeLanguage);

    if (activeLanguage === "en") {
      const observer = new MutationObserver((records) => {
        for (const record of records) {
          for (const node of record.addedNodes) {
            if (node.nodeType === Node.TEXT_NODE) translateTextNode(node);
            else if (node.nodeType === Node.ELEMENT_NODE && !shouldSkip(node)) translateTree(node);
          }
        }
      });
      observer.observe(document.body, {childList: true, subtree: true});
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, {once: true});
  else apply();
})();
