(() => {
  "use strict";

  const STORAGE_KEY = "nuvedra.language";
  const language = () => localStorage.getItem(STORAGE_KEY) === "es" ? "es" : "en";

  function applyLanguage(root = document) {
    const lang = language();
    document.documentElement.lang = lang;
    root.querySelectorAll("[data-i18n-en][data-i18n-es]").forEach((element) => {
      const value = lang === "es" ? element.dataset.i18nEs : element.dataset.i18nEn;
      if (value != null) element.textContent = value;
    });
    root.querySelectorAll("[data-placeholder-en][data-placeholder-es]").forEach((element) => {
      element.setAttribute("placeholder", lang === "es" ? element.dataset.placeholderEs : element.dataset.placeholderEn);
    });
    root.querySelectorAll("[data-title-en][data-title-es]").forEach((element) => {
      const value = lang === "es" ? element.dataset.titleEs : element.dataset.titleEn;
      element.setAttribute("title", value);
      element.setAttribute("aria-label", value);
    });
  }

  function serializeForm(form) {
    const data = {};
    for (const element of form.elements) {
      if (!element.name || element.type === "password" || element.type === "file") continue;
      if ((element.type === "checkbox" || element.type === "radio") && !element.checked) continue;
      data[element.name] = element.value;
    }
    return data;
  }

  function saveDraft(form) {
    const key = form.dataset.autosaveKey;
    if (!key) return;
    const payload = { savedAt: Date.now(), fields: serializeForm(form) };
    localStorage.setItem(`nuvedra.studio.draft.${key}`, JSON.stringify(payload));
    const status = form.querySelector(".studio-save-state");
    if (status) status.textContent = language() === "es" ? "Borrador guardado localmente" : "Draft saved locally";
  }

  function restoreDraft(form, payload) {
    if (!payload || !payload.fields) return;
    Object.entries(payload.fields).forEach(([name, value]) => {
      const element = form.elements.namedItem(name);
      if (!element || typeof element.value === "undefined") return;
      element.value = value;
      element.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const richInput = form.querySelector("[data-rich-input]");
    const richEditor = form.querySelector("[data-rich-editor]");
    if (richInput && richEditor) richEditor.innerHTML = richInput.value;
  }

  function initializeDrafts() {
    document.querySelectorAll("form[data-autosave-key]").forEach((form) => {
      const key = `nuvedra.studio.draft.${form.dataset.autosaveKey}`;
      let timer = null;
      let payload = null;
      try { payload = JSON.parse(localStorage.getItem(key) || "null"); } catch { payload = null; }

      if (payload && payload.fields) {
        const footer = form.querySelector(".studio-form-footer");
        if (footer) {
          const restore = document.createElement("button");
          restore.type = "button";
          restore.className = "studio-button studio-button--quiet";
          restore.textContent = language() === "es" ? "Restaurar borrador local" : "Restore local draft";
          restore.addEventListener("click", () => {
            restoreDraft(form, payload);
            restore.remove();
          });
          footer.prepend(restore);
        }
      }

      form.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => saveDraft(form), 650);
      });
      form.addEventListener("submit", () => {
        const richInput = form.querySelector("[data-rich-input]");
        const richEditor = form.querySelector("[data-rich-editor]");
        if (richInput && richEditor) richInput.value = richEditor.innerHTML;
        localStorage.removeItem(key);
      });
    });
  }

  function initializeTypeCards() {
    const form = document.querySelector("[data-item-form]");
    if (!form) return;
    const select = form.querySelector("[data-item-type]");
    document.querySelectorAll("[data-select-type]").forEach((button) => {
      button.addEventListener("click", () => {
        select.value = button.dataset.selectType || "page";
        select.dispatchEvent(new Event("change", { bubbles: true }));
        form.scrollIntoView({ behavior: "smooth", block: "start" });
        const title = form.querySelector("input[name='title']");
        if (title) title.focus();
      });
    });
  }

  function initializeAssessmentSettings() {
    document.querySelectorAll("[data-item-type]").forEach((select) => {
      const form = select.closest("form");
      if (!form) return;
      const settings = form.querySelector("[data-assessment-settings]");
      if (!settings) return;
      const update = () => { settings.hidden = select.value !== "assessment"; };
      select.addEventListener("change", update);
      update();
    });
  }

  function initializeRichEditors() {
    document.querySelectorAll("[data-rich-form]").forEach((form) => {
      const editor = form.querySelector("[data-rich-editor]");
      const hidden = form.querySelector("[data-rich-input]");
      if (!editor || !hidden) return;
      form.querySelectorAll("[data-command]").forEach((button) => {
        button.addEventListener("click", () => {
          editor.focus();
          const command = button.dataset.command;
          let value = button.dataset.commandValue || null;
          if (command === "createLink") {
            value = window.prompt(language() === "es" ? "Escriba el enlace completo" : "Enter the complete URL", "https://");
            if (!value) return;
          }
          document.execCommand(command, false, value);
          hidden.value = editor.innerHTML;
          editor.dispatchEvent(new Event("input", { bubbles: true }));
        });
      });
      editor.addEventListener("input", () => { hidden.value = editor.innerHTML; });
    });
  }

  function initializeConfirmations() {
    document.querySelectorAll("form[data-confirm]").forEach((form) => {
      form.addEventListener("submit", (event) => {
        const message = language() === "es" ? form.dataset.confirmEs : form.dataset.confirmEn;
        if (message && !window.confirm(message)) event.preventDefault();
      });
    });
  }

  function initializeLanguageObserver() {
    window.addEventListener("storage", (event) => {
      if (event.key === STORAGE_KEY) applyLanguage();
    });
  }

  function start() {
    if (!document.querySelector("[data-studio-root]")) return;
    applyLanguage();
    initializeDrafts();
    initializeTypeCards();
    initializeAssessmentSettings();
    initializeRichEditors();
    initializeConfirmations();
    initializeLanguageObserver();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
