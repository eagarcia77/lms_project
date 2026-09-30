# NUVEDRA

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eagarcia77/lms_project)

**Repository:** https://github.com/eagarcia77/lms_project  
**Current application:** https://nexus-edu-xr-eagarcia77.onrender.com

NUVEDRA is an intelligent, bilingual and immersive online-learning ecosystem. It is inspired by modern LMS platforms while extending course management with Google Workspace, accessible visual authoring, learning analytics, artificial intelligence and XR-ready learning experiences.

## Current capabilities

### Access and security

- Google OAuth 2.0 sign-in.
- Local NUVEDRA registration and authentication.
- Password recovery and secure session controls.
- Local passwords protected with `scrypt` and random salt.
- Protected academic routes and security-event logging.

### Visual Course Studio

Faculty can:

- create courses and organize modules;
- add pages, documents, videos and links;
- create assignments, discussions and assessments;
- connect Google Docs, Slides, Forms, Drive and Calendar;
- add H5P, simulations, AR, VR, WebXR and 360-degree resources;
- reorder, duplicate, preview, save and publish instructional content;
- use bilingual authoring views and accessible interface controls.

Google files remain in the connected user's Drive, while NUVEDRA stores the authorized link and course relationship.

### Platform services

- Academic, faculty, student and administrative portals.
- Announcements, progress and initial analytics.
- Google Classroom, Drive and Calendar integrations.
- AR laboratories with `<model-viewer>`.
- VR laboratories with A-Frame and WebXR.
- Responsive interface, accessibility support and automated tests.
- FastAPI, SQLite for development and PostgreSQL on Render.
- Docker and GitHub Actions deployment validation.

## Innovation roadmap

The next NUVEDRA development program adds:

1. **NUVEDRA AI Studio** for supervised course, objective, activity and rubric generation.
2. **Course-grounded intelligent tutors** that use faculty-approved materials.
3. **Adaptive learning pathways** based on diagnostic and mastery evidence.
4. **Explainable learning analytics and early alerts** with human intervention workflows.
5. **Competency tracking, microlearning and Open Badges credentials.**
6. **LTI 1.3, xAPI, SCORM, Common Cartridge and OneRoster interoperability.**
7. **Managed XR learning objects, digital simulations and accessible WebXR alternatives.**

See [`docs/NUVEDRA_INNOVATION_ARCHITECTURE.md`](docs/NUVEDRA_INNOVATION_ARCHITECTURE.md) for the architecture and phased delivery plan. The machine-readable feature registry is stored in [`config/innovation_features.json`](config/innovation_features.json).

## Google Cloud requirements

Enable:

1. Google Classroom API.
2. Google Drive API.
3. Google Docs API.
4. Google Slides API.
5. Google Forms API.
6. Google Calendar API.

Current authorized Render callback:

```text
https://nexus-edu-xr-eagarcia77.onrender.com/auth/google/callback
```

Required Render variables:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
```

Users who connected Google before new scopes were added must sign out and authorize the application again. See `docs/GOOGLE_SETUP.md`.

## Build and deployment

The Docker build applies the source and runtime patch packages in the sequence defined by the current `Dockerfile`. Render deploys changes from `main`. The health endpoint is `/healthz`.

## Local development

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python tools/apply_v3.py
python tools/apply_course_studio_package.py
pip install -r requirements.txt
uvicorn app.production_entry:app --reload
```

Use the exact patch sequence in the `Dockerfile` when local source packages have changed.

## Production-readiness status

NUVEDRA remains an MVP. Institutional use requires completion of advanced role governance, formal database migrations, tested backup and recovery, persistent token encryption, gradebook controls, privacy review, OAuth verification, accessibility testing and security validation.

AI capabilities must not be activated for institutional data until provider governance, consent, retention, audit and faculty-approval controls are implemented.
