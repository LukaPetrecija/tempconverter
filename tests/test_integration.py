# Integration tests: exercise the whole app (routes + form + ORM + MySQL).
# Importing app.py connects to the DB, so a live MySQL must be reachable
# via the DB_* env vars before this runs.
import app as appmod

appmod.app.config["WTF_CSRF_ENABLED"] = False
appmod.app.config["TESTING"] = True
client = appmod.app.test_client()
HEADERS = {"User-Agent": "pytest"}

def test_homepage_loads():
    resp = client.get("/", headers=HEADERS)
    assert resp.status_code == 200
    assert b"Algebra" in resp.data          # college injected from env

def test_conversion_persists():
    resp = client.post("/", data={"celsius": "100"}, headers=HEADERS)
    assert resp.status_code == 200
    assert b"212" in resp.data              # 100C -> 212F shown in the log table
