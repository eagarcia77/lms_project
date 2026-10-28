"""Executable regression coverage for the WebXR classroom's rendered inline JavaScript."""
import ast
import html
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_xr_controller_and_nonimmersive_fallback():
    source = (ROOT / "app" / "student_portal.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classroom = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.JoinedStr)
        and any(isinstance(target, ast.Name) and target.id == "classroom" for target in node.targets)
    )
    rendered = eval(
        compile(ast.Expression(classroom), str(ROOT / "app" / "student_portal.py"), "eval"),
        {"esc": lambda value: html.escape(str(value)), "accent": "#4338ca", "item": {"title": "XR test"}},
    )
    # Test the actual emitted script rather than a copied JavaScript implementation.
    script = rendered.rsplit("<script>", 1)[1].split("</script>", 1)[0]
    result = subprocess.run(
        ["node", str(ROOT / "tests" / "xr_controller_harness.cjs")],
        input=script,
        text=True,
        capture_output=True,
        cwd=ROOT,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
