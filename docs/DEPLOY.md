# RustDALI Server — Deployment

## Prerequisites

- Python 3 with `dali_rust` PyO3 bindings and FastAPI dependencies (system Anaconda)
- Node.js 18+ with `npm install` completed in `frontend/`
- PostgreSQL accessible (dione:45000, db=ecod_protein)
- `.env` file configured in project root (see `.env.example`)
- Frontend built: `cd frontend && npm run build`

## Quick Deploy (screen)

Good for internal/temporary use. Easy to start and stop.

```bash
# Start a screen session
screen -S rustdali

# Terminal 1: backend
source ~/.bashrc
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Ctrl-a c to open a new screen window

# Terminal 2: frontend
cd frontend
npx next start -p 3000
```

Useful screen commands:
- `Ctrl-a d` — detach (leaves everything running)
- `screen -r rustdali` — reattach
- `Ctrl-a c` — new window
- `Ctrl-a n` / `Ctrl-a p` — next/prev window
- `Ctrl-a k` — kill current window

Access at `http://<hostname>:3000` (frontend) and `http://<hostname>:8000/api/` (backend).

## Production Deploy (systemd + nginx)

For longer-lived deployments with auto-restart and a single entry point.

### 1. Install systemd units

Edit the `User`, `WorkingDirectory`, and `ExecStart` paths in the service
files to match your environment, then:

```bash
sudo cp deploy/rustdali-backend.service /etc/systemd/system/
sudo cp deploy/rustdali-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rustdali-backend rustdali-frontend
```

Check status:
```bash
sudo systemctl status rustdali-backend
sudo systemctl status rustdali-frontend
sudo journalctl -u rustdali-backend -f   # tail logs
```

### 2. Install nginx config

```bash
sudo cp deploy/rustdali.nginx.conf /etc/nginx/sites-available/rustdali
sudo ln -s /etc/nginx/sites-available/rustdali /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Access at `http://<hostname>/` — nginx routes `/api/` to the backend and
everything else to the frontend.

### 3. Tear down

```bash
sudo systemctl disable --now rustdali-backend rustdali-frontend
sudo rm /etc/systemd/system/rustdali-*.service
sudo rm /etc/nginx/sites-enabled/rustdali
sudo systemctl daemon-reload
sudo systemctl reload nginx
```
