# Deploying JubaSquare on a Linux Server

This is a single-machine deployment guide for Ubuntu/Debian.  Adapt as needed
for other distros.  The stack: **MongoDB + FastAPI backend + React frontend**.

---

## 1. Prerequisites

```bash
# Python 3.11+, Node 20+, Yarn, MongoDB 6+, Nginx
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx curl

# Node 20 (via nvm)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.nvm/nvm.sh
nvm install 20
npm i -g yarn

# MongoDB community edition — follow the official guide for your distro:
#   https://www.mongodb.com/docs/manual/installation/
sudo systemctl enable --now mongod
```

---

## 2. Clone & configure

```bash
git clone <your-repo> /opt/jubasquare
cd /opt/jubasquare

# Backend env
cp backend/.env.example backend/.env
nano backend/.env          # set MONGO_URL, JWT_SECRET, ADMIN_*, RESEND_API_KEY, etc.

# Frontend env (point at the public URL of your backend)
cp frontend/.env.example frontend/.env
nano frontend/.env         # set REACT_APP_BACKEND_URL=https://your-domain.com
```

---

## 3. Backend (FastAPI)

```bash
cd /opt/jubasquare/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# emergentintegrations is hosted on a custom CDN
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
deactivate
```

### systemd unit  `/etc/systemd/system/jubasquare-backend.service`

```ini
[Unit]
Description=JubaSquare backend (FastAPI)
After=network.target mongod.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/jubasquare/backend
EnvironmentFile=/opt/jubasquare/backend/.env
ExecStart=/opt/jubasquare/backend/.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jubasquare-backend
sudo journalctl -u jubasquare-backend -f       # live logs
```

---

## 4. Frontend (React build → static files)

```bash
cd /opt/jubasquare/frontend
yarn install --frozen-lockfile
yarn build                # outputs to ./build
```

Serve `build/` with Nginx (see step 5).  No Node process needed in production.

---

## 5. Nginx reverse proxy

`/etc/nginx/sites-available/jubasquare`:

```nginx
server {
    listen 80;
    server_name jubasquare.com www.jubasquare.com;

    # React static files
    root /opt/jubasquare/frontend/build;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri /index.html;
    }

    # Backend API — anything under /api goes to FastAPI on :8001
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        client_max_body_size 25M;          # for image/file uploads
    }

    # Optional: serve uploaded images (if you persist them on disk)
    location /uploads/ {
        alias /opt/jubasquare/backend/uploads/;
        access_log off;
        expires 30d;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/jubasquare /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Free HTTPS via Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d jubasquare.com -d www.jubasquare.com
```

With Nginx in front, your `frontend/.env` should be:

```
REACT_APP_BACKEND_URL=https://jubasquare.com
```

— same-origin, since `/api/*` is proxied to FastAPI.

---

## 6. First-run checklist

1. Visit `https://jubasquare.com` — you should see the Home page.
2. Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `backend/.env`.
3. Go to `/admin` → **Categories** tab and verify all default categories are seeded.
4. Go to **Settings** → adjust brand name / hero / modules.
5. Go to **Footer** → adjust links and contact info.
6. Change the admin password (top-right profile menu).

---

## 7. Updating

```bash
cd /opt/jubasquare
git pull
# Backend
cd backend && source .venv/bin/activate && pip install -r requirements.txt && deactivate
sudo systemctl restart jubasquare-backend
# Frontend
cd ../frontend && yarn install --frozen-lockfile && yarn build
sudo systemctl reload nginx
```

---

## Common gotchas

| Symptom | Fix |
|---|---|
| Frontend loads but API calls fail with CORS | Set `CORS_ORIGINS` in `backend/.env` to your domain (or `*` for testing) and restart backend. |
| `502 Bad Gateway` from Nginx | Backend isn't running — check `sudo journalctl -u jubasquare-backend -n 50`. |
| Login works but session is lost on refresh | Make sure your domain is HTTPS; cookies / localStorage tokens require a stable origin. |
| Image uploads fail with 413 | Increase `client_max_body_size` in Nginx (already set to 25M above). |
| Default admin password still works after deploy | Log in and change it in **Settings** → Profile, or update `ADMIN_PASSWORD` and re-seed. |
