(() => {
  "use strict";

  const storageKey = "nuvedra.language";
  const language = localStorage.getItem(storageKey) === "es" ? "es" : "en";
  const spanishToEnglish = {
    "Correo del instructor": "Instructor email",
    "Administrador e instructor:": "Administrator and instructor:",
    "puede conservar su propio correo para administrar el curso y también crear su contenido, o sustituirlo por el correo de otro profesor.": "You may keep your own email to administer the course and also create its content, or replace it with another instructor's email.",
    "Portal académico": "Academic portal",
    "Administración": "Administration",
    "está utilizando su sesión administrativa. Solo verá herramientas docentes en los cursos donde su correo tenga el rol de instructor.": "You are using your administrative session. Instructor tools are available only in courses where your email has the instructor role.",
    "Administrador e instructor": "Administrator and instructor"
  };
  const englishToSpanish = {
    "Instructor email": "Correo del instructor",
    "Administrator and instructor:": "Administrador e instructor:",
    "You may keep your own email to administer the course and also create its content, or replace it with another instructor's email.": "Puede conservar su propio correo para administrar el curso y también crear su contenido, o sustituirlo por el correo de otro profesor.",
    "Academic portal": "Portal académico",
    "Administration": "Administración",
    "You are using your administrative session. Instructor tools are available only in courses where your email has the instructor role.": "Está utilizando su sesión administrativa. Solo verá herramientas docentes en los cursos donde su correo tenga el rol de instructor.",
    "Course code and title are required.": "El código y el título del curso son obligatorios.",
    "A course with this code already exists.": "Ya existe un curso con este código.",
    "Invalid course status.": "El estado del curso no es válido.",
    "The end date cannot be earlier than the start date.": "La fecha final no puede ser anterior a la fecha inicial.",
    "Another course already uses this code.": "Otro curso ya utiliza este código.",
    "NUVEDRA homepage was not found.": "No se encontró la página principal de NUVEDRA."
  };
  const dictionary = language === "en" ? spanishToEnglish : englishToSpanish;

  function translate(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const parent = node.parentElement;
      if (!parent || parent.closest("script,style,textarea,pre,code,[data-no-translate]")) continue;
      const value = node.nodeValue || "";
      const key = value.trim();
      if (!dictionary[key]) continue;
      const leading = value.match(/^\s*/)?.[0] || "";
      const trailing = value.match(/\s*$/)?.[0] || "";
      node.nodeValue = `${leading}${dictionary[key]}${trailing}`;
    }
  }

  function apply() {
    translate(document.body);
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        for (const node of record.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) translate(node);
        }
      }
    });
    observer.observe(document.body, {childList: true, subtree: true});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, {once: true});
  else apply();
})();
