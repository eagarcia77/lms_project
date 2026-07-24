FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

RUN python -m py_compile tools/*.py app/*.py
RUN python tools/apply_v3.py
RUN python tools/apply_course_studio_package.py
RUN pip install --no-cache-dir -r requirements.txt
RUN test -f tools/apply_course_studio.py
RUN python tools/apply_course_studio.py
RUN python tools/fix_course_builder_response_types.py
RUN python tools/patch_admin_console_v2.py
RUN python tools/apply_admin_console.py
RUN test -f app/unified_authoring.py && test -f app/production_entry.py && test -f app/admin_authoring_v6.py
RUN chmod +x start_runtime.sh
RUN python -m compileall -q app tools
RUN NEXUS_SESSION_SECRET=build-verification-secret-change-in-production python -c "from app.production_entry import app; routes=[(getattr(r,'path',''),set(getattr(r,'methods',[]) or [])) for r in app.routes]; required=[('/healthz','GET'),('/course-studio','GET'),('/admin/login','GET'),('/admin/authoring','GET'),('/admin/authoring/courses','POST'),('/admin/authoring/courses/{course_id}','GET'),('/admin/authoring/courses/{course_id}/modules','POST'),('/admin/authoring/modules/{module_id}','GET'),('/admin/authoring/modules/{module_id}/content','POST'),('/admin/authoring/modules/{module_id}/activities','POST'),('/admin/authoring/modules/{module_id}/google','POST'),('/admin/authoring/modules/{module_id}/drive','GET'),('/admin/authoring/modules/{module_id}/odf/{kind}','GET'),('/admin/authoring/items/{item_id}/forum','GET'),('/admin/authoring/items/{item_id}/preview','GET')]; missing=[f'{m} {p}' for p,m in required if not any(rp==p and m in methods for rp,methods in routes)]; print('Unified Studio routes:', [('%s %s' % ('/'.join(sorted(methods)), path)) for path,methods in routes if path.startswith(('/admin/authoring','/course-studio'))]); assert not missing, missing"
RUN grep -q "def register_unified_authoring" app/unified_authoring.py && grep -q "register_unified_authoring" app/production_entry.py

EXPOSE 8000
CMD ["./start_runtime.sh"]
