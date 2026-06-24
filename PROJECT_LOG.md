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
