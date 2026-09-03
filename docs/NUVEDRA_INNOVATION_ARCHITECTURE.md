# NUVEDRA Innovation Architecture

## Purpose

NUVEDRA is being developed as an intelligent, accessible and immersive learning ecosystem rather than a conventional LMS. This architecture organizes the next generation of capabilities around supervised artificial intelligence, adaptive learning, analytics, extended reality, interoperable credentials and standards-based integrations.

## Product principles

1. Human-supervised AI: faculty retain academic and grading authority.
2. Accessibility by design: WCAG 2.2 AA checks are part of authoring and publishing.
3. Evidence-based design: objectives, activities and assessments remain aligned.
4. Privacy and explainability: predictive indicators must expose the signals behind a recommendation.
5. Interoperability: NUVEDRA should support LTI 1.3, xAPI, Common Cartridge, SCORM, OneRoster and Open Badges where appropriate.
6. Bilingual operation: English-first interface with complete Spanish support.

## Capability domains

### 1. NUVEDRA AI Studio

Planned agents:

- Course Architect: course maps, modules, measurable objectives, activities and rubrics.
- Faculty Coach: pedagogical recommendations and instructional improvement.
- Assessment Agent: diagnostic, formative and summative assessment support.
- Accessibility Agent: contrast, headings, alternative text, captions, tables and keyboard-navigation checks.
- Research Assistant: literature matrices, research-question refinement, methodology support and APA 7 guidance.

AI output must be presented as a draft requiring faculty validation. Course-specific assistants should use retrieval from approved institutional and course materials rather than unrestricted generation.

### 2. Intelligent tutoring

Each course may activate a grounded tutor that can explain concepts, provide hints, generate practice, summarize approved materials and adapt explanations to the learner. The tutor should preserve citations to source materials and avoid making grading decisions.

### 3. Adaptive learning engine

The adaptive engine will connect diagnostic evidence, mastery rules, prerequisite relationships and recommended learning objects. Initial rule bands may be configured by faculty and must remain editable at course level.

### 4. Visual Course Studio

The existing Visual Course Studio is the primary authoring surface. Future blocks include:

- AI-assisted page, module and rubric generation;
- H5P and Lumi activities;
- interactive video;
- simulations;
- AR, VR, WebXR and 360-degree objects;
- competency alignment;
- accessibility validation before publishing;
- version history and approval workflow.

### 5. Learning analytics and early alerts

Dashboards are planned for students, faculty and institutional leaders. Indicators include participation, progress, objective mastery, missed work, assessment patterns and accessibility quality. Predictive alerts must include an explanation and a recommended human intervention.

### 6. NUVEDRA XR Lab

The XR layer will support GLB/GLTF models, model-viewer, A-Frame, Three.js and WebXR. Experiences should degrade gracefully to accessible 2D alternatives on devices without XR support.

### 7. Microlearning and competencies

Content may be repackaged into short learning capsules with a measurable outcome, practice and mastery check. Activities can map to course outcomes, institutional outcomes, professional standards and employability competencies.

### 8. Credentials

The platform roadmap includes digital badges, microcredentials and verifiable competency records. Open Badges should be evaluated before any blockchain-specific implementation.

### 9. Integrations

Priority integrations:

- Google Workspace;
- Blackboard Ultra, Canvas and Moodle through LTI 1.3;
- SCORM and Common Cartridge import/export;
- xAPI event capture;
- OneRoster for roster exchange;
- Open Badges for credentials.

## Delivery phases

### Phase 1: Foundation

- Complete NUVEDRA rebranding in documentation and runtime.
- Preserve current course, role, Google and Visual Course Studio functions.
- Add feature flags and architecture registry.
- Improve accessibility, auditability and backup readiness.

### Phase 2: AI-assisted authoring

- Course Architect MVP.
- Objective, activity and rubric generators.
- Faculty approval workflow.
- Course-grounded tutor prototype.

### Phase 3: Analytics

- Student progress dashboard.
- Faculty course analytics.
- Explainable early-alert rules.
- Competency tracking.

### Phase 4: Interoperability

- LTI 1.3 provider/tool foundation.
- xAPI statement service.
- Common Cartridge and SCORM workflows.
- Open Badges issuer evaluation.

### Phase 5: XR and adaptive learning

- Managed 3D/XR learning-object catalog.
- Accessible WebXR experiences.
- Adaptive pathways based on mastery evidence.

## Definition of done for innovative features

A feature is not production-ready until it has:

- role and permission controls;
- audit events;
- accessibility checks;
- privacy and data-retention review;
- automated tests;
- English and Spanish labels;
- documentation;
- graceful error handling;
- faculty or administrator oversight where AI is involved.
