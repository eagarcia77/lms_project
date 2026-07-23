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
RUN test -f app/course_builder.py && test -f app/runtime_entry.py
RUN python tools/fix_course_builder_response_types.py
RUN python tools/patch_admin_console_v2.py
RUN python tools/apply_admin_console.py
RUN python tools/apply_authoring_v5.py
RUN python tools/patch_authoring_v5_security.py
RUN python tools/patch_authoring_v6_padding.py
RUN python tools/apply_authoring_v6.py
RUN chmod +x start_runtime.sh
RUN python -m compileall -q app tools
RUN NEXUS_SESSION_SECRET=build-verification-secret-change-in-production python -c "from app.runtime_entry import app; routes=[(getattr(r,'path',''),set(getattr(r,'methods',[]) or [])) for r in app.routes]; required=[('/admin/login','GET'),('/admin/courses','GET'),('/admin/authoring','GET'),('/admin/authoring/courses','POST'),('/admin/authoring/courses/{course_id}','GET'),('/admin/authoring/courses/{course_id}/modules','POST'),('/admin/authoring/courses/{course_id}/ai-plan','POST'),('/admin/authoring/modules/{module_id}/items/new','GET'),('/admin/authoring/modules/{module_id}/items','POST'),('/admin/authoring/modules/{module_id}/google','POST'),('/admin/authoring/modules/{module_id}/odf/{kind}','GET'),('/admin/authoring/items/{item_id}/forum','GET'),('/admin/authoring/items/{item_id}/forum','POST'),('/admin/authoring/items/{item_id}/preview','GET')]; missing=[f'{m} {p}' for p,m in required if not any(rp==p and m in methods for rp,methods in routes)]; print('Course Studio V6 routes:', [('%s %s' % ('/'.join(sorted(methods)), path)) for path,methods in routes if path.startswith('/admin/authoring')]); assert not missing, missing"
RUN grep -q "register_authoring_v6" app/runtime_entry.py && grep -q "def register_authoring_v6" app/admin_authoring_v6.py

EXPOSE 8000
CMD ["./start_runtime.sh"]
