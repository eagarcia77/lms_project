from fastapi.testclient import TestClient

from app.main import app


def test_health_and_core_endpoints():
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/config").json()["features"]["virtualReality"] is True
        assert len(client.get("/api/courses").json()) >= 3
        assert client.get("/api/dashboard").json()["stats"]["courses"] >= 3
        assert len(client.get("/api/xr").json()) >= 3
