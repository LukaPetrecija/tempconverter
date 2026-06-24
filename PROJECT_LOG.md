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
## Step 7A — Docker Swarm cluster (simpler orchestrator, LO4)
- Built a 3-node Swarm from multipass VMs (Swarm needs the Docker engine; podman doesn't do Swarm).
- swarm1 = manager (2G, will host MySQL); swarm2, swarm3 = workers (1G, run the Flask app).
- Installed Docker via get.docker.com on each; `docker swarm init` on swarm1, workers joined with token.
- Multi-node is required so the two app replicas can be placed on different nodes (Task 6b).
- Nodes pull the app image straight from Docker Hub (docker.io/lpetrec/tempconverter:dev) — no rebuild.
- Verified: `docker node ls` shows 3 nodes Ready, swarm1 as Leader.

## Step 7B — Deploy to Docker Swarm + scale (LO4)
- Wrote tempconverter-stack.yml (in repo as appendix). db pinned to manager (swarm1) with a
  named volume; app = 2 replicas with max_replicas_per_node:1 (anti-affinity -> different nodes);
  published 80:5000 via Swarm routing mesh (built-in load balancing); restart_policy on-failure.
- Created the file in WSL and used `multipass transfer` into swarm1 (avoids cross-shell quoting issues).
- Deployed: `docker stack deploy -c tempconverter-stack.yml tempconverter`. Reached app 2/2, db 1/1.
- Placement verified via `docker stack ps`: app.1 on swarm2, app.2 on swarm3, db on swarm1.
- Self-healing observed: early app tasks Failed (exit 1) because they started before MySQL was ready;
  Swarm auto-restarted them until healthy. This is the Step-4 race condition solved automatically by
  the orchestrator (key reflection point).
- App reachable at http://<swarm1-ip> (port 80), load-balanced across replicas; conversions persist.
- Scaling (Task 6c): `docker service scale tempconverter_app=3`. With max 1/node and 2 eligible nodes,
  the 3rd replica stays Pending ("no suitable node") — the constraint correctly prevents doubling up.
  To truly reach 3: add a node (preferred), or relax max_replicas_per_node (loses HA guarantee).
  Scaled back to 2 for the required state.
## Step 8A — Kubernetes (k3s) cluster (complex orchestrator, LO6/LO4)
- Built a 3-node k3s cluster on multipass VMs: k8s1 = control-plane (hosts MySQL),
  k8s2 + k8s3 = workers (run app replicas).
- Installed k3s server on k8s1 with --disable traefik (frees port 80 for our LoadBalancer)
  and --write-kubeconfig-mode 644; workers joined via curl get.k3s.io with K3S_URL + K3S_TOKEN.
- Verified: `kubectl get nodes` shows all 3 Ready (k8s1 control-plane, k8s2/k8s3 workers).

## Troubleshooting — k3s workers not joining (LO5)
- Workers installed but never appeared in `get nodes`. Cause: the K3S_TOKEN was only the
  first half of the node-token. The real token is the FULL string "K10<hash>::server:<secret>",
  not just the leading hash segment.
- Fix: rewrote /etc/systemd/system/k3s-agent.service.env with the complete token and
  `systemctl restart k3s-agent`. Both workers registered and went Ready within ~1 min.
- Also: the curl|sh join can appear to hang at "Starting k3s-agent" — the install actually
  finished (k3s runs as a systemd service); closing the window doesn't undo it.
## Step 8B — Deploy to Kubernetes + scale (LO6, LO4)
- Manifests in tempconverter-k8s.yml (in repo as appendix): Secret (DB creds), db Deployment+Service
  (MySQL pinned to control-plane via nodeSelector+toleration, reachable as service "db"),
  app Deployment (replicas:2, podAntiAffinity requiredDuringScheduling on hostname = different nodes),
  app Service type LoadBalancer port 80 -> targetPort 5000.
- Built file in WSL, `multipass transfer` to k8s1, `kubectl apply -f`.
- Result: db + 2 app pods Running; app pods on k8s2 and k8s3 (different nodes, anti-affinity works).
- Self-healing: app pods showed 2-3 RESTARTS (started before MySQL ready, crashed, auto-restarted).
  Kubernetes does this by DEFAULT — no restart policy needed (vs Swarm's explicit restart_policy).
- Exposed on port 80 via LoadBalancer service (k3s built-in LB); reachable at http://<node-ip>.
- Scaling (6c): `kubectl scale deployment app --replicas=3`. 3rd pod stays Pending — hard
  podAntiAffinity + only 2 eligible nodes = nowhere legal to place it (scheduler logs the anti-affinity
  rule). Same outcome as Swarm's 2/3 cap, different mechanism. Resolutions: add a node, or switch to
  preferredDuringScheduling. Scaled back to 2.
## Step 8B — correction on scaling behaviour
- scale to replicas=3 did NOT leave a pod Pending (unlike Swarm). The 3rd app pod scheduled
  onto k8s1 (control-plane) because the app Deployment has no nodeSelector and k8s1 had no app
  pod yet — so all 3 replicas sit on 3 different nodes, anti-affinity fully satisfied.
- Kubernetes only hits Pending at replicas=4: with 3 nodes and max 1 app pod per node via
  podAntiAffinity, the 4th has nowhere legal to go. `describe pod` then logs a FailedScheduling
  message citing the anti-affinity rule.
- Comparison point (LO6): Swarm capped app at 2/3 (only 2 worker-eligible nodes for app);
  Kubernetes scaled to 3/3 cleanly (control-plane also schedulable). Same constraint type
  (one replica per node) enforced by different mechanisms (max_replicas_per_node vs podAntiAffinity).
## Step 9A — Orchestrator comparison + reflection (LO6)
- Built the Swarm-vs-Kubernetes comparison table (setup, config format, replicas, one-per-node
  mechanism, port-80 LB, self-healing, secrets, scaling, verbosity, learning curve).
- Key difference: self-healing — Swarm needs explicit restart_policy; Kubernetes restarts pods
  by default (observed via RESTARTS count with no policy set).
- CORRECTION to Step 7 note: did NOT verify Swarm capping at 2/3. Accurate statement: both
  enforce one replica per node; with 3 nodes both reach 3 replicas; Pending only when replicas > nodes.
- Reflection (Task 9): Swarm for simpler/smaller environments (fast, one file, gentle curve);
  Kubernetes for complex/production (granular control, default self-healing, huge ecosystem, portability).
