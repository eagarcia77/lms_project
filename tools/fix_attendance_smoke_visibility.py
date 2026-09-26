from pathlib import Path

path = Path("tools/smoke_test_attendance_participation_v1.py")
source = path.read_text(encoding="utf-8")
old = 'require(details, "Opening seminar", "student attendance history")'
new = 'require(details, "Class Meeting 1", "student attendance history")'
if old not in source:
    if new in source:
        raise SystemExit(0)
    raise RuntimeError("Attendance smoke assertion anchor missing")
path.write_text(source.replace(old, new, 1), encoding="utf-8")
