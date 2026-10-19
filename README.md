# 🐳 Docker-Three-Tier-App

![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-009639?logo=nginx&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)

A hands-on project that simulates what a DevOps engineer does at a company: take an application, containerize it, secure the networking, persist the data, publish the image to a registry, deploy it, and operate it day to day.

**Stack:** Nginx (reverse proxy) → Flask API (Gunicorn) → PostgreSQL

---

## 📖 The Scenario

> The dev team handed you a small **Task API** (Python/Flask) that stores tasks in PostgreSQL. Your job:
>
> 1. **Containerize** the API with a small, non-root, production-ready image.
> 2. **Isolate** the database: only the API can talk to it, never the outside world or the proxy.
> 3. **Persist** the database data so it survives container deletion and upgrades.
> 4. Put **Nginx** in front as the only public entry point.
> 5. **Publish** the image to Docker Hub so any server can pull it.
> 6. **Deploy** everything with Docker Compose.
> 7. **Operate** it: logs, health checks, backups, releases, rollback, and cleanup.

### Architecture

```text
                    Internet / User
                          │
                    :8080 │  (only published port)
                          ▼
        ┌───────────────────────────────────┐
        │  web  (nginx)                     │
        └───────────────┬───────────────────┘
                        │  frontend-net
        ┌───────────────▼───────────────────┐
        │  api  (flask + gunicorn :5000)    │
        └───────────────┬───────────────────┘
                        │  backend-net (internal)
        ┌───────────────▼───────────────────┐
        │  db   (postgres)  ── volume pgdata│
        └───────────────────────────────────┘
```

| Concept | How it is used here |
|---------|---------------------|
| **Networks** | `frontend-net` (web ↔ api) and `backend-net` (api ↔ db). `web` can never reach `db`. |
| **Volumes** | Named volume `pgdata` for DB data; bind mount for the Nginx config. |
| **Images** | Pull official images, build our own (multi-stage), tag, push, pull. |
| **Compose** | One file to run the whole stack with health checks and restart policies. |

---

## 🗂️ Project Structure

```text
Docker-Three-Tier-App/
├── app/
│   ├── app.py                # Flask API (/health, /tasks)
│   └── requirements.txt      # Pinned Python dependencies
├── nginx/
│   └── default.conf          # Reverse proxy to the API
├── Dockerfile                # Multi-stage, non-root, with HEALTHCHECK
├── docker-compose.yml        # web + api + db, networks, volume
├── .dockerignore
├── .env.example              # Copy to .env and edit
├── .gitignore
└── README.md
```

| File | Purpose |
|------|---------|
| [`app/app.py`](app/app.py) | Flask app with `GET /health`, `GET /tasks`, `POST /tasks`. Retries the DB connection on startup. |
| [`nginx/default.conf`](nginx/default.conf) | `proxy_pass http://api:5000`. `api` is the container name, resolved by Docker's internal DNS. |
| [`Dockerfile`](Dockerfile) | Multi-stage build (smaller image), runs as a non-root user, has a HEALTHCHECK, uses Gunicorn. |
| [`docker-compose.yml`](docker-compose.yml) | Defines the 3 services, 2 networks, and the `pgdata` volume. |
| [`.env.example`](.env.example) | Template for the variables Compose reads (credentials, image tag). |

---

## ⚡ Quick Start

**Prerequisites:** Docker Engine and the Docker Compose plugin.

```bash
git clone https://github.com/mohamedsala7320-sudo/Docker-Three-Tier-App.git
cd Docker-Three-Tier-App

cp .env.example .env          # then edit DOCKERHUB_USER and DB_PASSWORD
docker compose up -d --build

curl http://localhost:8080/health
```

Want to understand every piece first? Follow the phases below.

---

## 🚀 Phase 1 — Run Everything Manually (Docker CLI)

Before Compose, we build the stack by hand to understand every piece.

### 1.1 Check Docker is working

```bash
docker version                 # client + server versions
docker info                    # system-wide info (storage driver, networks, etc.)
docker run --rm hello-world    # quick sanity test; --rm deletes the container after it exits
```

### 1.2 Create the networks

```bash
docker network create frontend-net     # web <-> api
docker network create backend-net      # api <-> db
docker network ls                      # verify both exist
docker network inspect backend-net     # subnet, gateway, connected containers
```

### 1.3 Create the volume and start the database

```bash
docker volume create pgdata            # named volume managed by Docker
docker volume ls
docker volume inspect pgdata           # shows the mount point on the host

docker pull postgres:16-alpine         # download the image

docker run -d \
  --name db \
  --network backend-net \
  -e POSTGRES_DB=tasks \
  -e POSTGRES_USER=app \
  -e POSTGRES_PASSWORD=secret \
  -v pgdata:/var/lib/postgresql/data \
  postgres:16-alpine

docker ps                              # db should be "Up"
docker logs db                         # look for: "ready to accept connections"
```

> **Note:** the database has **no `-p` flag**, so it is not published to the host. Nobody outside can reach it.
>
> The `POSTGRES_*` variables are applied **only on the first start**, when the volume is empty. Changing them later on an existing volume has no effect.

### 1.4 Build and run the API

```bash
docker build -t task-api:1.0 .         # build the image from the Dockerfile
docker images                          # confirm the image and its size
docker history task-api:1.0            # see the layers

docker run -d \
  --name api \
  --network backend-net \
  -e DB_HOST=db \
  -e DB_NAME=tasks \
  -e DB_USER=app \
  -e DB_PASSWORD=secret \
  task-api:1.0

# The API must also be reachable by Nginx, so attach it to a second network
docker network connect frontend-net api

docker logs api
```

> The `DB_*` values must match the `POSTGRES_*` values used for the database.

### 1.5 Run Nginx as the public entry point

```bash
docker run -d \
  --name web \
  --network frontend-net \
  -p 8080:80 \
  -v "$(pwd)/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:1.27-alpine
```

### 1.6 Test the application

```bash
curl http://localhost:8080/health

curl -X POST http://localhost:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Learn Docker networking"}'

curl http://localhost:8080/tasks
```

### 1.7 Prove the network isolation works

```bash
# web -> api : should WORK (same network, DNS by name)
docker exec web wget -qO- http://api:5000/health

# web -> db : should FAIL (db is only on backend-net)
docker exec web ping -c 2 db
# expected: "bad address 'db'"

# api -> db : should WORK
docker exec api python -c "import socket; print(socket.gethostbyname('db'))"
```

### 1.8 Prove the data survives container deletion

```bash
docker rm -f db                        # delete the DB container completely

docker run -d --name db --network backend-net \
  -e POSTGRES_DB=tasks -e POSTGRES_USER=app -e POSTGRES_PASSWORD=secret \
  -v pgdata:/var/lib/postgresql/data \
  postgres:16-alpine

sleep 5
curl http://localhost:8080/tasks       # your task is still there ✅
```

### 1.9 Clean up Phase 1

```bash
docker rm -f web api db
docker network rm frontend-net backend-net
# the pgdata volume is kept so you can reuse the data
```

---

## 📦 Phase 2 — Publish the Image (Docker Hub)

```bash
export DOCKERHUB_USER=<your-dockerhub-username>

docker login                                           # enter your Docker Hub credentials

# Tag format: <username>/<repo>:<tag>
docker tag task-api:1.0 $DOCKERHUB_USER/task-api:1.0
docker tag task-api:1.0 $DOCKERHUB_USER/task-api:latest

docker images | grep task-api                          # verify the tags

docker push $DOCKERHUB_USER/task-api:1.0               # upload to the registry
docker push $DOCKERHUB_USER/task-api:latest
```

### Simulate a fresh server pulling the image

```bash
docker rmi $DOCKERHUB_USER/task-api:1.0 $DOCKERHUB_USER/task-api:latest task-api:1.0
docker pull $DOCKERHUB_USER/task-api:1.0               # downloaded from Docker Hub
docker images | grep task-api
```

> **Tip:** always deploy with a **fixed version tag** (`1.0`, `1.1`...) instead of `latest`. `latest` can change at any time, so you would not know exactly what is running and could not roll back reliably.

---

## 🧩 Phase 3 — Deploy with Docker Compose

```bash
cp .env.example .env            # then edit .env (DOCKERHUB_USER, DB_PASSWORD, ...)

docker compose config           # validate the file and preview the final config
docker compose up -d --build    # build (if needed) and start everything in the background
docker compose ps               # all services should be "running" / "healthy"
docker compose logs -f          # follow logs of all services (Ctrl+C to stop following)
```

Test again:

```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/tasks -H "Content-Type: application/json" -d '{"title":"Deploy with Compose"}'
curl http://localhost:8080/tasks
```

Compose creates the networks and volume automatically, prefixed with the project (folder) name:

```bash
docker network ls
docker volume ls
```

**What the Compose file adds on top of the manual setup:**

| Feature | Why it matters |
|---------|----------------|
| `depends_on` + `condition: service_healthy` | The API starts only after the DB is really ready. |
| `restart: unless-stopped` | Containers come back after a crash or a server reboot. |
| `internal: true` on `backend-net` | The backend network has no outbound internet access. |
| `.env` variables | Credentials are not hard-coded in the YAML. |

---

## 🛠️ Phase 4 — Day-2 Operations

### Monitoring and debugging

```bash
docker compose ps                          # service status and health
docker compose logs -f api                 # follow logs of one service
docker compose logs --tail=50 db           # last 50 lines
docker stats                               # live CPU / memory / network usage
docker compose exec api sh                 # open a shell inside the API container
docker compose exec db psql -U app -d tasks -c "SELECT * FROM tasks;"
```

### Backup and restore the database

**Logical backup (recommended, consistent dump):**

```bash
# Backup
docker compose exec -T db pg_dump -U app tasks > backup.sql

# Restore
cat backup.sql | docker compose exec -T db psql -U app -d tasks
```

**Raw volume backup (stop the DB first to get a consistent copy):**

```bash
docker volume ls                           # find the exact name: <project>_pgdata

docker compose stop db

docker run --rm \
  -v docker-three-tier-app_pgdata:/data \
  -v "$(pwd)":/backup \
  alpine tar czf /backup/pgdata-backup.tar.gz -C /data .

docker compose start db
```

> The volume name is `<project-folder>_pgdata` in lowercase. If you cloned this repo, it is `docker-three-tier-app_pgdata`. Always confirm with `docker volume ls`.

### Release a new version and roll back

```bash
# 1) change the code, then build and push v1.1
docker build -t $DOCKERHUB_USER/task-api:1.1 .
docker push $DOCKERHUB_USER/task-api:1.1

# 2) deploy it (only the api container is recreated; the DB and its data are untouched)
TAG=1.1 docker compose up -d

# 3) something broke? roll back in seconds
TAG=1.0 docker compose up -d
```

### Self-healing test

```bash
docker kill $(docker compose ps -q api)    # simulate a crash
sleep 5
docker compose ps                          # the restart policy brings it back automatically
```

---

## 🧹 Cleanup

```bash
docker compose down            # stop and remove containers + networks (volume is KEPT)
docker compose down -v         # also delete the volumes (⚠️ database data is lost)

docker image prune             # remove dangling images
docker system df               # see how much disk space Docker uses
docker system prune -a         # remove ALL unused containers, networks, and images (⚠️ be careful)
```

---

## 🧯 Troubleshooting Cheat Sheet

| Problem | Check / Fix |
|---------|-------------|
| Container exits immediately | `docker logs <name>`; `docker inspect <name> --format '{{.State.ExitCode}}'` |
| `port is already allocated` | Another process uses port 8080: change the left side of `-p 8080:80` |
| API cannot connect to DB | Same network? `docker network inspect backend-net`; is `DB_HOST=db` set? Do the credentials match? |
| Name resolution fails | DNS by name only works on **user-defined** networks, not on the default `bridge` |
| Data disappeared | Was the volume deleted by `down -v` or `docker volume rm`? Was `-v pgdata:...` missing in `docker run`? |
| Changed DB password has no effect | `POSTGRES_*` variables apply only when the volume is empty. Use `ALTER USER` or recreate the volume |
| Changes in code not applied | Rebuild: `docker compose up -d --build` |
| `permission denied` on docker.sock | `sudo usermod -aG docker $USER`, then log out and in |

---

## 🎯 Skills Demonstrated

- Writing an optimized **multi-stage Dockerfile** (small image, non-root user, healthcheck)
- **Docker networking:** user-defined bridge networks, DNS by container name, network isolation, `network connect`
- **Persistent storage:** named volumes, bind mounts, backup and restore
- **Registry workflow:** `login`, `tag`, `push`, `pull`, and versioned tags
- **Docker Compose:** multi-service stack, env files, health-based startup order, restart policies
- **Operations:** logs, exec, stats, versioned releases, rollback, and cleanup

---

## 👤 Author

**Mohamed Salah Shawky** — Junior Cloud DevOps Engineer
GitHub: [@mohamedsala7320-sudo](https://github.com/mohamedsala7320-sudo)
