from __future__ import annotations

from fastapi import FastAPI

from app.academic_access import ensure_academic_schema, register_admin_course_creation
from app.faculty_portal import register_faculty_portal
from app.google_hub_safe import register_portal_home_and_google
from app.student_portal import register_student_portal


def register_academic_portal(app: FastAPI) -> None:
    ensure_academic_schema()
    register_admin_course_creation(app)
    register_portal_home_and_google(app)
    register_faculty_portal(app)
    register_student_portal(app)
    print("Portal académico por roles registrado: administrador, profesor y estudiante.", flush=True)
