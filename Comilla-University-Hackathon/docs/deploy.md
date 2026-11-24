# CI and CD

- **CI** (`.github/workflows/ci.yml`) runs on GitHub's machines for every push and every pull request
  into `main`: `ruff check .` and `pytest -q` for the backend, `npm run lint` and `npm run build` for
  the app, at the same time. No secrets needed. A red CI blocks the deploy.
- **CD** (`.github/workflows/cd.yml`) runs after CI passed on a push to `main`, or by hand (GitHub,
  Actions, CD, "Run workflow"). A GitHub machine connects to **our Azure VM over SSH** and runs
  `deploy/deploy.sh` there:
  1. `cd ~/Desktop/Comilla-University-Hackathon` and update it to `main` (`git reset --hard`):
     **uncommitted changes in that folder are discarded.** Git-ignored files are kept
     (`backend/.env`, `backend/data/`).
  2. `docker compose build backend`, then `docker compose up -d --wait` (from `backend/`). Compose
     replaces the backend container only when its image changed; Postgres and Chroma keep running.
     `--wait` fails the job if a container does not become healthy.
  3. Prints the backend container's health and `GET /health`.

The app itself is on Vercel, not on the VM.

## What runs on the VM

| Part | Listens on | Data |
|---|---|---|
| nginx (installed on the VM) | 80, 443 (internet): `https://api.<our domain>` | certificate from Let's Encrypt (certbot) |
| `ekcall-backend-1` (FastAPI, 1 worker) | 127.0.0.1:8000 | none: settings from `backend/.env`, models from `~/Desktop/models` (read-only) |
| `ekcall-postgres-1` | 127.0.0.1:5432 | Docker volume `ekcall_postgres-data` |
| `ekcall-chroma-1` | 127.0.0.1:8001 | Docker volume `ekcall_chroma-data` |

The containers restart by themselves after a crash or a reboot. The volumes are outside the project
folder: deleting or re-cloning the folder keeps the data; only `docker compose down -v` deletes it.
Only nginx is reachable from the internet; it forwards to the backend on 127.0.0.1:8000.

## One-time VM setup

The VM: Ubuntu Server 24.04 LTS (x64), 2 vCPU and 4 GiB RAM (the stack uses about 1 GB), Standard SSD
of 32 GB or more, static public IP. Inbound ports 22, 80 and 443 open; nothing else.

1. Swap (protects the image build) and Docker:
   ```
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER      # log out and in again; `docker ps` must work without sudo
   ```
2. The project folder:
   ```
   mkdir -p ~/Desktop && cd ~/Desktop
   git clone https://github.com/Tamim2276/Comilla-University-Hackathon.git
   ```
3. Settings and models (they are not in git):
   - `backend/.env` from `backend/.env.example`: the `POSTGRES_*`, `DATABASE_URL` and `CHROMA_*`
     lines, `PUBLIC_URL=https://api.<our domain>`, and the Vercel address in `FRONTEND_ORIGINS`.
     Then `chmod 600 backend/.env`.
   - The models: copy `ekcall_models.zip` to the VM (`scp`), then `unzip ekcall_models.zip -d ~/Desktop`
     (gives `~/Desktop/models` with `router/`, `e5/` and `tfidf_router.joblib`).
4. First start and data (from `backend/`):
   ```
   docker compose up -d --build --wait
   docker compose exec backend python -m scripts.ingest           # documents into Chroma
   docker compose exec backend python -m scripts.prewarm --voice  # answer cache
   ```
   To move existing data from a laptop instead, see `scripts/migrate_to_servers.py`.
5. HTTPS with our domain:
   - Namecheap, Domain List, the domain, Advanced DNS: an `A Record` with host `api` and the VM's
     public IP. Check with `dig +short api.<our domain>`.
   - nginx and the certificate:
     ```
     sudo apt install -y nginx certbot python3-certbot-nginx
     ```
     `/etc/nginx/sites-available/ekcall`:
     ```nginx
     server {
         listen 80;
         server_name api.<our domain>;

         location / {
             proxy_pass http://127.0.0.1:8000;
             proxy_http_version 1.1;
             proxy_set_header Host $host;
             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
             proxy_set_header X-Forwarded-Proto $scheme;
             proxy_read_timeout 130s;   # answers up to 60 s, cluster rebuild up to 120 s
             client_max_body_size 1m;
         }
     }
     ```
     ```
     sudo ln -s /etc/nginx/sites-available/ekcall /etc/nginx/sites-enabled/
     sudo nginx -t && sudo systemctl reload nginx
     sudo certbot --nginx -d api.<our domain>    # certificate, HTTPS and the http -> https redirect
     sudo certbot renew --dry-run                # renewal works (a timer renews automatically)
     ```
   - Use the address everywhere: the Twilio number's voice webhook
     `https://api.<our domain>/voice/incoming`, and Vercel's `VITE_API_URL=https://api.<our domain>`
     (then redeploy the app).
6. GitHub secrets for CD (repository Settings, Secrets and variables, Actions):

   | Secret | Value |
   |---|---|
   | `VM_SSH_KEY` | the whole private key file (the `.pem` from Azure), including the BEGIN and END lines |
   | `VM_HOST` | the VM's public IP (or `api.<our domain>`) |
   | `VM_USER` | the VM user name |

7. First deploy: GitHub, Actions, CD, "Run workflow" on `main`. It should end with the backend's
   `healthy` and the `/health` answer. Builds reuse the package layer unless `requirements.txt`
   changed.

## Every day

On the VM, from `~/Desktop/Comilla-University-Hackathon/backend`:
```
docker compose ps                  # all should say "healthy"
docker compose logs -f backend     # backend log
curl localhost:8000/health
```
Changed documents (`backend/data/raw_docs/`) are not re-ingested by the deploy. After such a deploy:
`docker compose exec backend python -m scripts.ingest`, then `... scripts.prewarm --voice`.

## Safety

- The CD job only runs for pushes to `main` of this repository (or by hand), never for pull requests or
  forks, because it runs commands on our VM.
- GitHub holds only the SSH key and the VM address. The backend's secrets stay in the VM's
  `backend/.env` (git-ignored, never in the image).
- SSH accepts keys only: `PasswordAuthentication no` in `/etc/ssh/sshd_config` (Azure's SSH key setup
  already does this; check it once).
- CD accepts the VM's SSH host key on first connect (`StrictHostKeyChecking=accept-new`), so it does not
  check that it reached the real VM. For full checking, add a `known_hosts` line from
  `ssh-keyscan -t ed25519 <VM_HOST>` to the workflow.
- Do not develop in the VM's project folder: every deploy resets it to `main`.
