'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');

let script = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { script += chunk; });
process.stdin.on('end', () => {
  class Element {
    constructor(attrs = {}) {
      this.attrs = { ...attrs };
      this.listeners = {};
      this.components = {};
      this.textContent = '';
      this.checked = false;
      this.hasLoaded = true;
      this.tagName = 'DIV';
      this.isContentEditable = false;
    }
    addEventListener(type, fn) {
      (this.listeners[type] ||= []).push(fn);
    }
    getAttribute(name) { return this.attrs[name] ?? null; }
    setAttribute(name, value) { this.attrs[name] = value; }
    emit(type, details = {}) {
      const event = { type, detail: details, target: this, preventDefault() {} };
      (this.listeners[type] || []).forEach((fn) => fn(event));
    }
    click() { this.emit('click'); }
  }

  function mount({ aframe = true, diagnostic = true, counter = true } = {}) {
    const scene = new Element();
    scene.vr = false;
    if (aframe) scene.is = (name) => name === 'vr-mode' && scene.vr;
    const stations = ['Objetivos', 'Exploración', 'Reflexión'].map((name) =>
      new Element({ 'data-topic': name + ': actividad de prueba.' }));
    const stationButtons = [0, 1, 2].map((index) =>
      new Element({ 'data-station': String(index), 'aria-pressed': 'false' }));
    const controllers = ['left', 'right'].map((hand) =>
      new Element({ 'laser-controls': { hand } }));
    const labels = [new Element(), new Element(), new Element()];
    const sceneIds = {
      '#xr-inworld-topic': new Element(),
      '#xr-inworld-guidance': new Element(),
      '#xr-next-marker': new Element(),
    };
    scene.querySelector = (selector) => sceneIds[selector] || null;
    scene.querySelectorAll = (selector) => ({
      '.xr-station': stations,
      '.xr-station-label': labels,
      '[laser-controls]': controllers,
      '.xr-guidance-panel': [],
      '.xr-guidance-panel a-plane': [],
      '.xr-guidance-panel a-text': [],
    }[selector] || []);
    const ids = Object.fromEntries([
      'xr-classroom-status', 'xr-device-compatibility', 'xr-toggle-guidance',
      'xr-toggle-contrast', 'xr-toggle-motion', 'xr-reset-visual',
      'xr-learning-station', 'xr-route-progress', 'xr-route-reset',
      'xr-interaction-count', 'xr-selection-diagnostic', 'xr-controller-status',
      'xr-immersive-session', 'xr-export-session',
    ].map((name) => [name, new Element()]));
    if (!diagnostic) delete ids['xr-selection-diagnostic'];
    if (!counter) delete ids['xr-interaction-count'];
    const docListeners = {};
    const document = {
      getElementById: (id) => ids[id] || null,
      querySelector: (selector) => selector === 'a-scene' ? scene : null,
      querySelectorAll: (selector) => ({
        '.xr-station-button': stationButtons,
        '#xr-manual-checks input[data-xr-check]': [],
      }[selector] || []),
      addEventListener(type, fn) { (docListeners[type] ||= []).push(fn); },
      createElement: () => new Element(),
    };
    let report = '';
    const window = {
      AFRAME: aframe ? {} : undefined,
      isSecureContext: aframe,
      matchMedia: () => ({ matches: false }),
      setTimeout: () => 1,
      setInterval: () => 1,
    };
    const context = {
      window, document, navigator: { userAgent: 'XR automated regression' },
      performance: { now: () => 1000 },
      Blob: class { constructor(parts) { this.parts = parts; } },
      URL: {
        createObjectURL(blob) { report = blob.parts.join(''); return 'blob:mock'; },
        revokeObjectURL() {},
      },
    };
    vm.runInNewContext(script, context, { filename: 'student_portal:inline.js' });
    return {
      scene, stations, stationButtons, controllers, ids,
      report: () => report,
      keydown(key) {
        const event = {
          key, altKey: true, ctrlKey: false, metaKey: false, repeat: false,
          target: { tagName: 'DIV', isContentEditable: false },
          preventDefault() {},
        };
        (docListeners.keydown || []).forEach((fn) => fn(event));
      },
    };
  }

  const controllerCursor = { components: { 'laser-controls': {} } };
  const desktopCursor = { components: { cursor: {} } };
  const readCount = (h) => h.ids['xr-interaction-count'].textContent;

  // Non-immersive cursor clicks count as scene interactions, not controller interactions.
  {
    const h = mount();
    h.stations[0].emit('click', { cursorEl: desktopCursor });
    assert.match(readCount(h), /1 selecciones; 1 estaciones distintas/);
    assert.match(readCount(h), /Escena 3D: 1; controlador XR: 0; controlador en VR: 0/);
    assert.match(h.ids['xr-selection-diagnostic'].textContent, /cursor de la escena/);
  }

  // A controller-originated event outside VR must not inflate the immersive counter.
  {
    const h = mount();
    h.stations[0].emit('click', { cursorEl: controllerCursor });
    assert.match(readCount(h), /controlador XR: 1; controlador en VR: 0/);
    h.ids['xr-export-session'].click();
    assert.match(h.report(), /Selecciones atribuidas a controlador XR: 1/);
    assert.match(h.report(), /scene \(controlador XR\) \| pantalla/);
  }

  // Immersive clicks are counted once; selection and diagnostics agree.
  {
    const h = mount();
    h.scene.vr = true;
    h.scene.emit('enter-vr');
    h.stations[1].emit('click', { cursorEl: controllerCursor });
    assert.match(readCount(h), /1 selecciones; 1 estaciones distintas/);
    assert.match(readCount(h), /controlador XR: 1; controlador en VR: 1/);
    assert.match(h.ids['xr-selection-diagnostic'].textContent, /controlador XR/);
    h.ids['xr-export-session'].click();
    assert.match(h.report(), /Selecciones con controlador durante modo VR: 1/);
    assert.match(h.report(), /scene \(controlador XR\) \| inmersivo/);
  }

  // Optional diagnostic (and optional live counter) cannot gate selection attribution.
  {
    const h = mount({ diagnostic: false });
    h.scene.vr = true;
    h.stations[2].emit('click', { cursorEl: controllerCursor });
    assert.match(readCount(h), /controlador XR: 1; controlador en VR: 1/);
    h.ids['xr-export-session'].click();
    assert.match(h.report(), /Diagnostico de seleccion: no disponible/);
    assert.match(h.report(), /Selecciones atribuidas a controlador XR: 1/);
    const noCounter = mount({ diagnostic: false, counter: false });
    noCounter.stations[0].emit('click', { cursorEl: controllerCursor });
    noCounter.ids['xr-export-session'].click();
    assert.match(noCounter.report(), /Selecciones atribuidas a controlador XR: 1/);
  }

  // Without A-Frame, buttons and shortcuts remain functional, without fictitious XR use.
  {
    const h = mount({ aframe: false });
    h.stationButtons[0].click();
    h.keydown('3');
    assert.match(readCount(h), /2 selecciones; 2 estaciones distintas/);
    assert.match(readCount(h), /Escena 3D: 0; controlador XR: 0; controlador en VR: 0; botones: 1; atajos: 1/);
    assert.match(h.ids['xr-route-progress'].textContent, /2 de 3/);
    assert.match(h.ids['xr-classroom-status'].textContent, /botones, atajos/);
    assert.match(h.ids['xr-device-compatibility'].textContent, /HTTPS/);
    h.ids['xr-route-reset'].click();
    assert.match(readCount(h), /2 selecciones; 0 estaciones distintas/);
    h.ids['xr-export-session'].click();
    assert.match(h.report(), /Botones accesibles: 1/);
    assert.match(h.report(), /Atajos de teclado: 1/);
  }

  console.log('XR controller attribution, optional diagnostics and fallback: 5 scenarios passed');
});
