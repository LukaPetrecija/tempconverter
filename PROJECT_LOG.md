# Intro to DevOps — Project Working Log

## Step 1 — Build container image
- Wrote Dockerfile (python:3.12-slim base): apt upgrade, install requirements,
  non-root appuser, EXPOSE 5000, CMD python app.py.
- Built: `podman build -t tempconverter:latest .` — success.
- Standalone test run failed at DB step with "Can't connect to MySQL server on
  'CHANGEME'". EXPECTED: app calls db.create_all() at startup; DB_* env vars unset
  so it used the default placeholder host. Confirms image/deps are correct.
  Will be resolved in Step 4 by adding MySQL container + env vars.
## Step 2 — Push to registry
- Registry: Docker Hub (public), namespace lpetrec.
- Added .dockerignore to keep .git/screenshots/log out of the image.
- Tagged docker.io/lpetrec/tempconverter:latest and pushed.
- Verified by re-pulling the image and via the Docker Hub web UI (screenshot).
## Step 3 — Update image and push :dev tag
- Edited templates/index.html: changed HTML <title> from
  "Celsius to Fahrenheit Converter" to "TempConverter".
- Verified with grep; will see it rendered in the browser in Step 4.
- Built tempconverter:dev (only COPY layer onward rebuilt, rest cached).
- Tagged and pushed docker.io/lpetrec/tempconverter:dev.
- Docker Hub now shows two tags: latest and dev (screenshot).
## Step 4 — Local deploy with podman + MySQL 8
- Created network tempconverter-net so containers resolve each other by name.
- Started mysql:8 with MYSQL_USER/PASSWORD -> auto-creates non-root user 'appuser'
  with full rights on the 'tempconverter' DB (satisfies non-root requirement).
- DB intentionally NOT port-exposed; only reachable by the app over the network.
- RACE CONDITION (key troubleshooting note): app runs db.create_all() at startup
  and crashes if MySQL isn't ready. MySQL first-init takes ~30s. Fixed by waiting
  with a poll loop until 'appuser' can connect before starting the app.
- Started app container with DB_HOST=tempconverter-db (container name) + STUDENT/COLLEGE.
- Verified: browser at localhost:5000 shows name/college + working conversions;
  SELECT CURRENT_USER() returns appuser@% (non-root); rows visible in temperature table.
- Note: cryptography lib in requirements.txt is needed for MySQL 8 caching_sha2_password auth.
## Troubleshooting — pytest ModuleNotFoundError 'converter'
- pytest collecting tests/test_unit.py put only the tests/ folder on the import path,
  so it couldn't import converter.py / app.py from the project root.
- Fix: added an empty conftest.py at the repo root, which makes pytest add the root
  to sys.path. Fixed both local runs and the CI pipeline (same pytest invocation).
## Step 5 — Container vs VM resource comparison (LO1)
- Container (tempconverter app, running): memory 96.12 MB, image 181 MB, startup 0.44 s; shares host kernel.
- VM (multipass Ubuntu 26.04, Hyper-V backend, idle): memory 350.9 MiB, disk 2.2 GiB, boot 19.18 s; full guest OS.
- Result: container uses ~3.6x less RAM, ~12x less disk, and starts ~44x faster — because it shares
  the host kernel instead of booting a whole operating system. (Note the container figure is the app
  actually running, while the VM figure is idle, so the real gap is even larger.)
- Measurement commands: `podman stats --no-stream`, `podman images`, `time podman start`;
  `multipass info devops-vm`, `multipass exec devops-vm -- systemd-analyze`.

## Step 6 — Git repo, unit/integration tests, CI pipeline (LO3)
- All code stored in own GitHub repo: github.com/LukaPetrecija/tempconverter.
- Refactored conversion math into converter.py so it is unit-testable in isolation.
- Unit tests (tests/test_unit.py): 4 cases on celsius_to_fahrenheit, no DB needed — pass locally.
- Integration tests (tests/test_integration.py): drive the real Flask app against a real MySQL,
  verifying the homepage renders and a conversion is persisted and shown.
- CI pipeline (.github/workflows/ci.yml): starts a MySQL 8 service, runs unit tests, waits for the DB,
  runs integration tests, then builds the container image. Full pipeline passes (green).

## Troubleshooting collected during Steps 5-6 (LO5)
- podman stats failed: needs cgroups v2. Enabled systemd via /etc/wsl.conf ([boot] systemd=true).
  The restart kept failing because Docker Desktop held the WSL VM open in the background;
  fixed by fully quitting Docker Desktop, then `wsl --shutdown` from Windows PowerShell.
- Lesson: `wsl` commands run from Windows PowerShell, NOT inside the Ubuntu shell.
- git push of the workflow file was rejected: a Personal Access Token needs the `workflow` scope,
  not just `repo`, to create/update files under .github/workflows/.
- CI build step failed with "no Dockerfile": the Dockerfile existed locally but had never been
  committed to git; `git add Dockerfile` + push fixed it. (Good argument for CI — it caught a file
  missing from the repo that a purely local test never would have.)
