from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.academic_access import ASSESSMENT_TYPES, STUDENT_ROLES, esc, google_user, item_bundle, login_redirect, portal_page, require_course_role
from app.admin_authoring_v6 import safe_url
from app.admin_console import audit, db, execute, rows, utcnow


def _module_html(module: dict, items: list[dict]) -> str:
    links = "".join(
        f'<li><a href="/learn/items/{item["id"]}">{esc(item["title"])}</a> <small>({esc(item.get("item_type"))})</small></li>'
        for item in items
    ) or "<li>No hay contenido publicado.</li>"
    return f'<section class="card module"><h3>{int(module.get("position") or 1)}. {esc(module["title"])}</h3><p>{esc(module.get("description"))}</p><ul>{links}</ul></section>'


def register_student_portal(app: FastAPI) -> None:
    @app.get("/learn/courses/{course_id}", response_class=HTMLResponse, response_model=None)
    async def student_course(course_id: int, request: Request):
        user = google_user(request)
        if not user:
            return login_redirect(f"/learn/courses/{course_id}")
        with db() as conn:
            access = require_course_role(conn, course_id, user["email"], STUDENT_ROLES)
            if str(access.get("course_status")) != "active":
                raise HTTPException(403, "El curso todavía no está disponible.")
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? AND status='published' ORDER BY position,id", (course_id,)))
            sections: list[str] = []
            for module in modules:
                items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? AND status='published' ORDER BY position,id", (module["id"],)))
                sections.append(_module_html(module, items))
        content = "".join(sections) or '<p class="notice">El profesor todavía no ha publicado módulos.</p>'
        body = f'<p><a href="/portal">&larr; Mis cursos</a></p><h2>{esc(access["course_code"])}: {esc(access["title"])}</h2><p>{esc(access.get("description"))}</p>{content}'
        return portal_page("Curso", body, user)

    @app.get("/learn/items/{item_id}", response_class=HTMLResponse, response_model=None)
    async def student_item(item_id: int, request: Request):
        user = google_user(request)
        if not user:
            return login_redirect(f"/learn/items/{item_id}")
        with db() as conn:
            course_id, item, module = item_bundle(conn, item_id)
            access = require_course_role(conn, course_id, user["email"], STUDENT_ROLES)
            if str(access.get("course_status")) != "active" or str(item.get("status")) != "published" or str(module.get("status")) != "published":
                raise HTTPException(403, "El contenido no está publicado.")
            submissions = rows(execute(conn, "SELECT * FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, user["email"])))
        external = ""
        if item.get("external_url"):
            external = f'<p><a class="button secondary" href="{esc(item.get("external_url"), attr=True)}" target="_blank" rel="noopener">Abrir recurso</a></p>'
        embed = ""
        if item.get("embed_url"):
            embed = f'<iframe src="{esc(item.get("embed_url"), attr=True)}" title="{esc(item.get("title"), attr=True)}" allow="fullscreen; xr-spatial-tracking"></iframe>'
        classroom = ""
        try:
            metadata = __import__("json").loads(item.get("metadata_json") or "{}")
        except (ValueError, TypeError):
            metadata = {}
        if item.get("item_type") == "vr" and metadata.get("technology") == "webxr_classroom":
            room_style = metadata.get("room_style", "classroom")
            accent = "#047857" if room_style == "lab" else "#4338ca"
            classroom = f"""<section class="card" aria-label="Aula virtual inmersiva">
<h3>Aula WebXR · {esc(item.get("title"))}</h3>
<p>Utiliza el ratón para explorar el aula. En un visor compatible, abre esta página en el navegador y selecciona el botón VR si está disponible; apunta a una mesa con el controlador y utiliza el gatillo para seleccionarla. También puedes seguir las instrucciones de la clase sin visor.</p>\n<p id="xr-device-compatibility" role="status">Comprobando si el navegador permite experiencias inmersivas…</p>
<script src="https://aframe.io/releases/1.8.0/aframe.min.js" onerror="document.getElementById(\'xr-classroom-status\').textContent=\'No se pudo cargar el motor 3D. Comprueba la conexión o utiliza la alternativa textual.\'"></script>
<div style="width:100%;height:480px;position:relative;background:#e7ecf5;border-radius:14px;overflow:hidden">
<a-scene embedded vr-mode-ui="enabled: true" renderer="antialias: true" background="color: #E7ECF5">
<a-sky color="#E7ECF5"></a-sky><a-plane position="0 0 -4" rotation="-90 0 0" width="18" height="18" color="#cbd5e1"></a-plane>
<a-box position="0 2 -7" width="7" height="2.5" depth="0.12" color="{accent}"></a-box>
<a-text value="NUVEDRA - Aula virtual" align="center" width="5" color="#FFFFFF" position="0 2.8 -6.91"></a-text>
<a-text value="Explora y aprende" align="center" width="4" color="#FFFFFF" position="0 2 -6.91"></a-text>
<a-entity class="xr-guidance-panel" position="0 1.65 -2.3"><a-plane width="2.9" height="0.85" color="#0f172a" opacity="0.94"></a-plane><a-text id="xr-inworld-guidance" value="Recorrido: 0/3 | Siguiente: Objetivos" align="center" color="#ffffff" width="2.7" wrap-count="38" position="0 0 0.02"></a-text></a-entity>
<a-entity class="xr-guidance-panel" position="0 1.08 -2.3"><a-plane width="3.3" height="0.62" color="#1e293b" opacity="0.94"></a-plane><a-text id="xr-inworld-topic" value="Selecciona una mesa para consultar la actividad." align="center" color="#ffffff" width="3.05" wrap-count="47" position="0 0 0.02"></a-text></a-entity>
<a-entity id="xr-next-marker" position="-2 1.75 -3.5"><a-cone color="#f59e0b" radius-bottom="0.18" radius-top="0" height="0.3" rotation="180 0 0"></a-cone><a-text value="SIGUIENTE" align="center" width="2.5" color="#92400e" position="0 0.35 0"></a-text></a-entity>
<a-text class="xr-station-label" value="1. Objetivos" position="-2 1.2 -3.5" align="center" width="2.8" color="#1e293b"></a-text>
<a-text class="xr-station-label" value="2. Exploracion" position="2 1.2 -3.5" align="center" width="2.8" color="#1e293b"></a-text>
<a-text class="xr-station-label" value="3. Reflexion" position="0 1.2 -4.7" align="center" width="2.8" color="#1e293b"></a-text>
<a-box class="xr-station" data-topic="Objetivos: identifica el propósito de la actividad y los resultados de aprendizaje." position="-2 0.55 -3.5" width="1.4" height="0.15" depth="0.9" color="#64748b"></a-box>
<a-box class="xr-station" data-topic="Exploración: examina el aula y relaciona lo observado con las instrucciones." position="2 0.55 -3.5" width="1.4" height="0.15" depth="0.9" color="#64748b"></a-box>
<a-box class="xr-station" data-topic="Reflexión: comparte un hallazgo o una pregunta en la comunidad de aprendizaje." position="0 0.55 -4.7" width="1.4" height="0.15" depth="0.9" color="#64748b"></a-box>
<a-entity position="0 1.6 1"><a-camera><a-cursor color="{accent}" raycaster="objects: .xr-station"></a-cursor></a-camera></a-entity>
<a-entity laser-controls="hand: left" raycaster="objects: .xr-station; far: 10" line="color: #2563eb; opacity: 0.8"></a-entity>
<a-entity laser-controls="hand: right" raycaster="objects: .xr-station; far: 10" line="color: #2563eb; opacity: 0.8"></a-entity>
</a-scene></div><div role="group" aria-label="Seleccionar estación de aprendizaje" style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.75rem"><button type="button" class="xr-station-button" aria-pressed="false" data-station="0">1. Objetivos</button><button type="button" class="xr-station-button" aria-pressed="false" data-station="1">2. Exploración</button><button type="button" class="xr-station-button" aria-pressed="false" data-station="2">3. Reflexión</button></div><button type="button" id="xr-reset-visual">Restablecer preferencias visuales</button> <button type="button" id="xr-toggle-contrast" aria-pressed="false">Alto contraste 3D</button> <button type="button" id="xr-toggle-motion" aria-pressed="false">Reducir movimiento</button> <button type="button" id="xr-toggle-guidance" aria-pressed="true">Ocultar paneles 3D</button> <button type="button" id="xr-route-reset">Reiniciar recorrido</button><p>Atajos de teclado: Alt+1 Objetivos, Alt+2 Exploración, Alt+3 Reflexión y Alt+0 reiniciar. Funcionan fuera del modo inmersivo.</p><details><summary>Consultar instrucciones sin escena 3D</summary><ol><li><strong>Objetivos:</strong> identifica el propósito de la actividad y los resultados de aprendizaje.</li><li><strong>Exploración:</strong> examina el aula y relaciona lo observado con las instrucciones.</li><li><strong>Reflexión:</strong> comparte un hallazgo o una pregunta en la comunidad de aprendizaje.</li></ol></details><p id="xr-route-progress" role="status" aria-live="polite">Recorrido guiado: 0 de 3 estaciones consultadas. Selecciona Objetivos para comenzar.</p><p id="xr-learning-station" role="status">Estaciones de aprendizaje: Objetivos, Exploración y Reflexión. Apunta y selecciona una mesa para consultar su indicación. También puedes leerlas aquí: identifica los objetivos, explora la escena y comparte una reflexión en la comunidad.</p><fieldset id="xr-manual-checks"><legend>Verificación manual Meta Quest (sin validación automática)</legend><label><input type="checkbox" data-xr-check="Escena visible en visor"> Escena visible en visor</label> <label><input type="checkbox" data-xr-check="Controlador detectado"> Controlador detectado</label> <label><input type="checkbox" data-xr-check="Gatillo selecciona estacion"> Gatillo selecciona estación</label> <label><input type="checkbox" data-xr-check="Texto legible en visor"> Texto legible en visor</label> <label><input type="checkbox" data-xr-check="Salida de VR funcional"> Salida de VR funcional</label></fieldset><p>Marca únicamente las pruebas que hayas realizado personalmente. Las casillas no se guardan en el servidor.</p><button type="button" id="xr-export-session">Descargar resumen de sesión VR (.txt)</button><p id="xr-immersive-session" role="status" aria-live="polite">Sesión VR: todavía no se ha iniciado el modo inmersivo.</p><p id="xr-interaction-count" role="status">Interacciones de esta sesión: 0 selecciones; 0 estaciones distintas.</p><p id="xr-selection-diagnostic" role="status" aria-live="polite">Selección XR: todavía no se ha registrado una interacción con una estación.</p><p id="xr-controller-status" role="status" aria-live="polite">Controles XR: sin conexión detectada. Puedes utilizar el cursor, el ratón o los botones accesibles.</p><p id="xr-classroom-status" role="status">Si no aparece el aula, comprueba WebGL y la carga del motor A-Frame. El texto de la actividad permanece disponible.</p>
<script>
(function () {{
  const scene = document.querySelector('a-scene');
  const status = document.getElementById('xr-classroom-status');
  const compatibility = document.getElementById('xr-device-compatibility');
  let immersiveCapability = 'pendiente';
  if (compatibility) {{
    if (!window.isSecureContext) {{
      immersiveCapability = 'requiere contexto seguro';
      compatibility.textContent = 'El modo VR necesita una conexión segura (HTTPS). Puedes utilizar la versión 3D de escritorio.';
    }} else if (!navigator.xr || typeof navigator.xr.isSessionSupported !== 'function') {{
      immersiveCapability = 'API no disponible';
      compatibility.textContent = 'Este navegador no ofrece WebXR inmersivo. Puedes explorar el aula en pantalla y participar en su comunidad.';
    }} else {{
      navigator.xr.isSessionSupported('immersive-vr').then((supported) => {{
        immersiveCapability = supported ? 'compatible declarado' : 'no compatible declarado';
        compatibility.textContent = supported
          ? 'El navegador indica compatibilidad con VR inmersiva. Selecciona el botón VR del aula para solicitar acceso.'
          : 'No se detectó compatibilidad con VR inmersiva. La versión 3D de escritorio sigue disponible.';
      }}).catch(() => {{
        immersiveCapability = 'comprobacion fallida';
        compatibility.textContent = 'No fue posible comprobar la compatibilidad del visor. Prueba el botón VR si está disponible.';
      }});
    }}
  }}
  if (!scene || !status) return;
  if (!window.AFRAME) {{
    status.textContent = 'El motor 3D no está disponible. Comprueba la conexión o utiliza la alternativa textual.';
    return;
  }}
  window.setTimeout(() => {{
    if (!scene.hasLoaded) {{
      status.textContent = 'La escena 3D tarda en cargar. Comprueba la conexión y WebGL; la actividad textual sigue disponible.';
    }}
  }}, 12000);
  scene.addEventListener('loaded', () => {{
    status.textContent = 'Aula 3D cargada. Usa el botón VR de la escena para solicitar el modo inmersivo si tu dispositivo lo permite.';
  }}, {{ once: true }});
  scene.addEventListener('renderstart', () => {{
    status.textContent = 'Escena 3D lista para explorar. El modo VR depende del visor y del navegador.';
  }}, {{ once: true }});
  scene.addEventListener('webglcontextlost', () => {{
    status.textContent = 'Se perdió el contexto gráfico WebGL. Recarga la página o utiliza la alternativa textual.';
  }});

  const guidanceToggle = document.getElementById('xr-toggle-guidance');
  if (guidanceToggle) guidanceToggle.addEventListener('click', () => {{
    const show = guidanceToggle.getAttribute('aria-pressed') !== 'true';
    scene.querySelectorAll('.xr-guidance-panel').forEach((panel) => panel.setAttribute('visible', show));
    guidanceToggle.setAttribute('aria-pressed', show ? 'true' : 'false');
    guidanceToggle.textContent = show ? 'Ocultar paneles 3D' : 'Mostrar paneles 3D';
  }});

  const contrastToggle = document.getElementById('xr-toggle-contrast');
  const contrastPanels = Array.from(scene.querySelectorAll('.xr-guidance-panel a-plane'));
  const contrastTexts = Array.from(scene.querySelectorAll('.xr-guidance-panel a-text'));
  const contrastStations = Array.from(scene.querySelectorAll('.xr-station'));
  let highContrast = false;
  const syncContrast = () => {{
    contrastPanels.forEach((panel) => panel.setAttribute('color', highContrast ? '#000000' : (panel.getAttribute('height') === '0.85' ? '#0f172a' : '#1e293b')));
    contrastTexts.forEach((label) => label.setAttribute('color', '#ffffff'));
    contrastStations.forEach((station, index) => station.setAttribute('color', visited.has(index) ? (highContrast ? '#00ff99' : '#059669') : (highContrast ? '#ffffff' : '#64748b')));
    if (contrastToggle) {{
      contrastToggle.setAttribute('aria-pressed', highContrast ? 'true' : 'false');
      contrastToggle.textContent = highContrast ? 'Contraste estándar 3D' : 'Alto contraste 3D';
    }}
  }};
  if (contrastToggle) contrastToggle.addEventListener('click', () => {{
    highContrast = !highContrast;
    syncContrast();
  }});
  const motionToggle = document.getElementById('xr-toggle-motion');
  let reducedMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const syncMotionToggle = () => {{
    if (!motionToggle) return;
    motionToggle.setAttribute('aria-pressed', reducedMotion ? 'true' : 'false');
    motionToggle.textContent = reducedMotion ? 'Activar efectos de enfoque' : 'Reducir movimiento';
    if (reducedMotion) scene.querySelectorAll('.xr-station').forEach((station) => station.setAttribute('scale', '1 1 1'));
  }};
  if (motionToggle) motionToggle.addEventListener('click', () => {{
    reducedMotion = !reducedMotion;
    syncMotionToggle();
  }});
  syncMotionToggle();
  const resetVisual = document.getElementById('xr-reset-visual');
  if (resetVisual) resetVisual.addEventListener('click', () => {{
    highContrast = false;
    syncContrast();
    reducedMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    syncMotionToggle();
    scene.querySelectorAll('.xr-guidance-panel').forEach((panel) => panel.setAttribute('visible', true));
    if (guidanceToggle) {{
      guidanceToggle.setAttribute('aria-pressed', 'true');
      guidanceToggle.textContent = 'Ocultar paneles 3D';
    }}
    resetVisual.textContent = 'Preferencias visuales restablecidas';
  }});
  const stationStatus = document.getElementById('xr-learning-station');
  const inWorldTopic = scene.querySelector('#xr-inworld-topic');
  const stations = Array.from(scene.querySelectorAll('.xr-station'));
  const routeProgress = document.getElementById('xr-route-progress');
  const visited = new Set();
  let sessionSelections = 0;
  const selectionSources = {{scene: 0, button: 0, shortcut: 0}};
  const interactionCount = document.getElementById('xr-interaction-count');
  let immersiveEntries = 0;
  let immersiveExits = 0;
  let immersiveStartedAt = null;
  let immersiveElapsedMs = 0;
  const immersiveSessionStatus = document.getElementById('xr-immersive-session');
  const syncImmersiveSession = () => {{
    if (!immersiveSessionStatus) return;
    const elapsed = Math.round((immersiveElapsedMs + (immersiveStartedAt !== null ? performance.now() - immersiveStartedAt : 0)) / 1000);
    immersiveSessionStatus.textContent = 'Sesión VR: ' + (immersiveStartedAt !== null ? 'activa' : 'fuera del modo inmersivo') + '; entradas: ' + immersiveEntries + '; salidas: ' + immersiveExits + '; tiempo aproximado: ' + elapsed + ' s.';
  }};
  syncImmersiveSession();
  const exportSession = document.getElementById('xr-export-session');
  if (exportSession) exportSession.addEventListener('click', () => {{
    const lines = [
      'NUVEDRA - Resumen local de prueba VR',
      'Fecha: ' + new Date().toISOString(),
      'Navegador: ' + navigator.userAgent,
      'WebXR API disponible: ' + (Boolean(navigator.xr) ? 'si' : 'no'),
      'Compatibilidad inmersiva: ' + (compatibility?.textContent || 'sin diagnostico'),
      'Resultado WebXR immersive-vr: ' + immersiveCapability,
      'Contexto seguro HTTPS: ' + (window.isSecureContext ? 'si' : 'no'),
      'Selecciones totales: ' + sessionSelections,
      'Estaciones distintas en recorrido actual: ' + visited.size + '/3',
      'Escena 3D: ' + selectionSources.scene,
      'Botones accesibles: ' + selectionSources.button,
      'Atajos de teclado: ' + selectionSources.shortcut,
      'Estaciones consultadas: ' + (Array.from(visited).sort().map((index) => ['Objetivos', 'Exploracion', 'Reflexion'][index]).join(', ') || 'ninguna'),
      'Estado de controladores: ' + (document.getElementById('xr-controller-status')?.textContent || 'no disponible'),
      'Estado del aula: ' + (status?.textContent || 'no disponible'),
      'Diagnostico de seleccion: ' + (document.getElementById('xr-selection-diagnostic')?.textContent || 'no disponible'),
      'Modo inmersivo activo al exportar: ' + (scene?.is('vr-mode') ? 'si' : 'no'),
      'Entradas a modo VR: ' + immersiveEntries,
      'Salidas de modo VR: ' + immersiveExits,
      'Tiempo inmersivo aproximado (segundos): ' + Math.round((immersiveElapsedMs + (immersiveStartedAt !== null ? performance.now() - immersiveStartedAt : 0)) / 1000),
      'Verificaciones manuales (declaradas por quien realiza la prueba):',
      ...Array.from(document.querySelectorAll('#xr-manual-checks input[data-xr-check]')).map((check) => (check.checked ? '[REALIZADA] ' : '[PENDIENTE] ') + check.getAttribute('data-xr-check')),
      'Nota: el registro no demuestra compatibilidad con un visor fisico ni acredita calificaciones.'
    ];
    const blob = new Blob([lines.join('\\n') + '\\n'], {{type: 'text/plain;charset=utf-8'}});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'nuvedra-prueba-vr.txt';
    link.click();
    URL.revokeObjectURL(url);
  }});

  const syncInteractionCount = () => {{
    if (interactionCount) interactionCount.textContent = 'Interacciones de esta sesión: ' + sessionSelections + ' selecciones; ' + visited.size + ' estaciones distintas. Escena 3D: ' + selectionSources.scene + '; botones: ' + selectionSources.button + '; atajos: ' + selectionSources.shortcut + '.';
  }};
  const stationNames = ['Objetivos', 'Exploración', 'Reflexión'];
  const inWorldStationLabels = Array.from(scene.querySelectorAll('.xr-station-label'));
  const syncInWorldStationLabels = () => {{
    const labels = ['Objetivos', 'Exploracion', 'Reflexion'];
    inWorldStationLabels.forEach((label, index) => {{
      label.setAttribute('value', (index + 1) + '. ' + labels[index] + (visited.has(index) ? ' - HECHO' : ''));
      label.setAttribute('color', visited.has(index) ? '#065f46' : '#1e293b');
    }});
  }};

  const inWorldGuidance = scene.querySelector('#xr-inworld-guidance');
  const syncInWorldGuidance = () => {{
    if (!inWorldGuidance) return;
    const next = [0, 1, 2].find((step) => !visited.has(step));
    inWorldGuidance.setAttribute('value', next === undefined
      ? 'Recorrido: 3/3 | Comparte tu reflexion'
      : 'Recorrido: ' + visited.size + '/3 | Siguiente: ' + ['Objetivos', 'Exploracion', 'Reflexion'][next]);
  }};

  const stationButtons = Array.from(document.querySelectorAll('.xr-station-button'));
  const syncStationButtons = () => {{
    stationButtons.forEach((button, index) => {{
      const completed = visited.has(index);
      button.setAttribute('aria-pressed', completed ? 'true' : 'false');
      button.textContent = (completed ? '✓ ' : '') + (index + 1) + '. ' + stationNames[index];
    }});
  }};

  const nextMarker = scene.querySelector('#xr-next-marker');
  const markerPositions = ['-2 1.75 -3.5', '2 1.75 -3.5', '0 1.75 -4.7'];
  const updateMarker = () => {{
    if (!nextMarker) return;
    const next = [0, 1, 2].find((step) => !visited.has(step));
    if (next === undefined) {{
      nextMarker.setAttribute('visible', false);
    }} else {{
      nextMarker.setAttribute('visible', true);
      nextMarker.setAttribute('position', markerPositions[next]);
    }}
  }};

  const selectStation = (station, source = 'scene') => {{
    if (stationStatus) stationStatus.textContent = station.getAttribute('data-topic') || 'Estación seleccionada.';
    if (inWorldTopic) {{
      const topic = station.getAttribute('data-topic') || 'Estación seleccionada.';
      inWorldTopic.setAttribute('value', topic);
    }}
    const index = stations.indexOf(station);
    if (index < 0) return;
    visited.add(index);
    sessionSelections += 1;
    if (Object.prototype.hasOwnProperty.call(selectionSources, source)) selectionSources[source] += 1;
    syncInteractionCount();
    syncInWorldStationLabels();
    syncInWorldGuidance();
    syncStationButtons();
    updateMarker();
    station.setAttribute('color', highContrast ? '#00ff99' : '#059669');
    station.setAttribute('scale', '1 1 1');
    if (routeProgress) {{
      const next = [0, 1, 2].find((step) => !visited.has(step));
      routeProgress.textContent = next === undefined
        ? 'Recorrido completo: 3 de 3 estaciones consultadas. Comparte tu reflexión en la comunidad del aula.'
        : 'Recorrido guiado: ' + visited.size + ' de 3 estaciones consultadas. Próxima estación sugerida: ' + stationNames[next] + '.';
    }}
  }};
  const resetRoute = document.getElementById('xr-route-reset');
  if (resetRoute) resetRoute.addEventListener('click', () => {{
    visited.clear();
    syncInteractionCount();
    syncInWorldStationLabels();
    syncInWorldGuidance();
    syncStationButtons();
    updateMarker();
    stations.forEach((station) => {{
      station.setAttribute('color', highContrast ? '#ffffff' : '#64748b');
      station.setAttribute('scale', '1 1 1');
    }});
    if (routeProgress) routeProgress.textContent = 'Recorrido guiado: 0 de 3 estaciones consultadas. Selecciona Objetivos para comenzar.';
    if (stationStatus) stationStatus.textContent = 'Recorrido reiniciado. Selecciona una estación o consulta las instrucciones en texto.';
    if (inWorldTopic) inWorldTopic.setAttribute('value', 'Selecciona una mesa para consultar la actividad.');
  }});
  stations.forEach((station) => {{
    station.addEventListener('mouseenter', () => {{
      if (!reducedMotion) station.setAttribute('scale', '1.08 1.08 1.08');
    }});
    station.addEventListener('mouseleave', () => {{
      station.setAttribute('scale', '1 1 1');
    }});
    station.addEventListener('click', (event) => {{
      selectStation(station);
      const diagnostic = document.getElementById('xr-selection-diagnostic');
      if (!diagnostic) return;
      const cursor = event.detail && event.detail.cursorEl;
      const controller = cursor && cursor.components && cursor.components['laser-controls'];
      const origin = controller ? 'controlador XR' : (cursor ? 'cursor de la escena' : 'origen no identificado');
      diagnostic.textContent = 'Selección registrada: ' + (station.getAttribute('data-topic') || 'estación') + ' | Origen: ' + origin + '.';
    }});
  }});
  document.querySelectorAll('.xr-station-button').forEach((button) => {{
    button.addEventListener('click', () => {{
      const index = Number(button.getAttribute('data-station'));
      if (stations[index]) selectStation(stations[index], 'button');
    }});
  }});
  document.addEventListener('keydown', (event) => {{
    if (!event.altKey || event.ctrlKey || event.metaKey || event.repeat) return;
    const target = event.target;
    if (target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))) return;
    if (['1', '2', '3'].includes(event.key)) {{
      const station = stations[Number(event.key) - 1];
      if (station) {{
        event.preventDefault();
        selectStation(station, 'shortcut');
      }}
    }} else if (event.key === '0' && resetRoute) {{
      event.preventDefault();
      resetRoute.click();
    }}
  }});
  const controllerStatus = document.getElementById('xr-controller-status');
  const controllerHands = new Set();
  scene.querySelectorAll('[laser-controls]').forEach((controller) => {{
    const hand = controller.getAttribute('laser-controls')?.hand || 'control';
    controller.addEventListener('controllerconnected', () => {{
      controllerHands.add(hand);
      if (controllerStatus) controllerStatus.textContent = 'Controles XR detectados: ' + Array.from(controllerHands).join(', ') + '. Apunta a una estación y utiliza el gatillo.';
    }});
    controller.addEventListener('controllerdisconnected', () => {{
      controllerHands.delete(hand);
      if (controllerStatus) controllerStatus.textContent = controllerHands.size
        ? 'Controles XR detectados: ' + Array.from(controllerHands).join(', ') + '.'
        : 'Controles XR: sin conexión detectada. Puedes utilizar el cursor, el ratón o los botones accesibles.';
    }});
  }});
  scene.addEventListener('enter-vr', () => {{
    immersiveEntries += 1;
    if (immersiveStartedAt === null) immersiveStartedAt = performance.now();
    syncImmersiveSession();
    status.textContent = 'Sesión inmersiva iniciada. Puedes salir del modo VR desde los controles del visor.';
  }});
  scene.addEventListener('exit-vr', () => {{
    immersiveExits += 1;
    if (immersiveStartedAt !== null) {{
      immersiveElapsedMs += performance.now() - immersiveStartedAt;
      immersiveStartedAt = null;
    }}
    syncImmersiveSession();
    status.textContent = 'Has salido del modo VR. Puedes continuar en pantalla y consultar la comunidad.';
  }});
  scene.addEventListener('render-target-loaded', () => {{
    if (scene.hasLoaded && !scene.is('vr-mode')) {{
      status.textContent = 'Escena lista para explorar. El acceso inmersivo depende de los permisos del navegador.';
    }}
  }});
}})();
</script>
</section>"""
        discussion = ""
        if str(item.get("item_type")) in {"vr", "discussion"}:
            with db() as conn:
                posts = rows(execute(conn, "SELECT author_email,body,created_at FROM nexus_forum_posts WHERE item_id=? ORDER BY id DESC LIMIT 100", (item_id,)))
            rendered = "".join(
                f'<article class="card"><strong>{esc(post["author_email"])}</strong><p style="white-space:pre-wrap">{esc(post["body"])}</p><small>{esc(post["created_at"])}</small></article>'
                for post in posts
            ) or '<p class="notice">Todavía no hay aportaciones. Inicia la conversación sobre esta experiencia.</p>'
            composer = (
                f'<form method="post" action="/learn/items/{item_id}/discuss"><label>Tu aportación<textarea name="body" required maxlength="5000" placeholder="Comparte una observación o pregunta sobre la actividad."></textarea></label><button>Publicar aportación</button></form>'
                if str(access.get("course_role")) == "student"
                else '<p class="notice">Puedes leer las aportaciones, pero tu rol no permite publicar.</p>'
            )
            discussion = f'<section class="card" aria-label="Comunidad de aprendizaje"><h3>Comunidad de aprendizaje</h3><p>Conversación vinculada a esta actividad. Evita compartir información personal o confidencial.</p>{composer}{rendered}</section>'
        assessment = ""
        if str(item.get("item_type")) in ASSESSMENT_TYPES and str(access.get("course_role")) == "student":
            existing = submissions[0] if submissions else {}
            saved = '<p class="success">Su respuesta está guardada. Puede actualizarla mientras la evaluación esté disponible.</p>' if submissions else ""
            assessment = f'''<section class="card"><h3>Responder evaluación</h3>{saved}<form method="post" action="/learn/items/{item_id}/submit"><label>Respuesta<textarea name="response_text" required>{esc(existing.get("response_text"))}</textarea></label><label>Enlace de evidencia (opcional)<input type="url" name="response_url" value="{esc(existing.get("response_url"), attr=True)}"></label><button>Guardar y entregar</button></form></section>'''
        elif str(item.get("item_type")) in ASSESSMENT_TYPES:
            assessment = '<p class="notice">El rol de observador permite consultar la evaluación, pero no enviar respuestas.</p>'
        body = f'<p><a href="/learn/courses/{course_id}">&larr; Volver al curso</a></p><section class="card content-body"><span class="badge">{esc(item.get("item_type"))}</span><h2>{esc(item["title"])}</h2>{item.get("body_html") or ""}{external}{embed}</section>{classroom}{discussion}{assessment}'
        return portal_page("Contenido", body, user)

    @app.post("/learn/items/{item_id}/discuss", response_model=None)
    async def student_discussion_post(item_id: int, request: Request, body: str = Form(...)):
        user = google_user(request)
        if not user:
            return login_redirect(f"/learn/items/{item_id}")
        clean = body.strip()
        if not clean or len(clean) > 5000:
            raise HTTPException(400, "La aportación debe contener entre 1 y 5000 caracteres.")
        with db() as conn:
            course_id, item, module = item_bundle(conn, item_id)
            access = require_course_role(conn, course_id, user["email"], {"student"})
            if (str(access.get("course_status")) != "active"
                or str(item.get("status")) != "published"
                or str(module.get("status")) != "published"
                or str(item.get("item_type")) not in {"vr", "discussion"}):
                raise HTTPException(403, "La comunidad no está disponible.")
            execute(conn, "INSERT INTO nexus_forum_posts (item_id,author_email,body,created_at) VALUES (?,?,?,?)", (item_id, user["email"], clean, utcnow()))
            audit(conn, user["email"], "student_discussion_post_created", "item", str(item_id), "", request.client.host if request.client else "")
        return RedirectResponse(f"/learn/items/{item_id}", status_code=303)

    @app.post("/learn/items/{item_id}/submit", response_model=None)
    async def submit_assessment(item_id: int, request: Request, response_text: str = Form(...), response_url: str = Form("")):
        user = google_user(request)
        if not user:
            return login_redirect(f"/learn/items/{item_id}")
        response = response_text.strip()
        if not response:
            raise HTTPException(400, "La respuesta no puede estar vacía.")
        with db() as conn:
            course_id, item, module = item_bundle(conn, item_id)
            access = require_course_role(conn, course_id, user["email"], {"student"})
            if str(access.get("course_status")) != "active" or str(item.get("item_type")) not in ASSESSMENT_TYPES or str(item.get("status")) != "published" or str(module.get("status")) != "published":
                raise HTTPException(403, "Esta evaluación no está disponible.")
            evidence = safe_url(response_url) or None
            found = rows(execute(conn, "SELECT id FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, user["email"])))
            if found:
                execute(conn, "UPDATE nuvedra_submissions SET response_text=?,response_url=?,status='submitted',updated_at=? WHERE id=?", (response, evidence, utcnow(), found[0]["id"]))
            else:
                now = utcnow()
                execute(conn, "INSERT INTO nuvedra_submissions (item_id,student_email,response_text,response_url,status,submitted_at,updated_at) VALUES (?,?,?,?,?,?,?)", (item_id, user["email"], response, evidence, "submitted", now, now))
            audit(conn, user["email"], "student_assessment_submitted", "item", str(item_id), "submitted", request.client.host if request.client else "")
        return RedirectResponse(f"/learn/items/{item_id}", status_code=303)
