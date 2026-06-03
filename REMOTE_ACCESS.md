# Remote Access — reach the EagleSignal dashboard from your phone (mobile data, any network)

Goal: open the dashboard on your phone over 4G/5G, from anywhere, **without a public IP**.
The laptop stays on and runs the Docker container; a **Cloudflare Tunnel** makes an
*outbound* connection to Cloudflare, and your phone reaches the laptop *through* Cloudflare.
No router port-forwarding, no static IP, works behind CGNAT.

> **Research tool, not financial advice.** Because the API has mutating endpoints
> (`/run`, `/jobs/*`, `/manual-trades`), the tunnel is **always paired with a login**.
> Never expose port 8000 to the internet without the login below.

---

## Step 1 — Turn on the dashboard login (HTTP Basic)

The app enforces a login **only when `DASHBOARD_PASSWORD` is set**. Add credentials to
your `.env` (same file docker-compose already loads):

```dotenv
# .env
DASHBOARD_USER=ganesh
DASHBOARD_PASSWORD=pick-a-long-random-passphrase
```

Then rebuild + restart so the container has the new auth code and reads the vars:

```powershell
docker compose build
docker compose up -d api
```

Verify locally — this should now pop a browser login prompt:

```
http://localhost:8000/dashboard
```

`/health` stays open (no login) so Cloudflare can health-check the tunnel.
To disable the login again, remove `DASHBOARD_PASSWORD` and restart.

---

## Step 2 — Install cloudflared on Windows

```powershell
winget install --id Cloudflare.cloudflared
# or: download cloudflared-windows-amd64.exe from Cloudflare and put it on PATH
cloudflared --version
```

---

## Step 3 — Pick a tunnel

### Option A — Quick test (no domain, throwaway URL)

```powershell
cloudflared tunnel --url http://localhost:8000
```

It prints a `https://<random>.trycloudflare.com` URL. Open it on your phone over mobile
data — you'll get the login prompt, then the dashboard. The URL changes every run; good
for testing, not for daily use.

### Option B — Permanent URL (recommended; needs a domain on Cloudflare's free plan)

```powershell
# 1. Authenticate (opens a browser; pick your domain/zone)
cloudflared tunnel login

# 2. Create a named tunnel (stores a credentials file under %USERPROFILE%\.cloudflared\)
cloudflared tunnel create eaglesignal

# 3. Map a hostname to your local dashboard
cloudflared tunnel route dns eaglesignal eaglesignal.yourdomain.com
```

Create `%USERPROFILE%\.cloudflared\config.yml`:

```yaml
tunnel: eaglesignal
credentials-file: C:\Users\ganes\.cloudflared\<TUNNEL-UUID>.json

ingress:
  - hostname: eaglesignal.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

Run it:

```powershell
cloudflared tunnel run eaglesignal
```

Now `https://eaglesignal.yourdomain.com` works from any browser, on any network.

---

## Step 4 — Auto-start when the laptop turns on

Install cloudflared as a Windows service so the tunnel comes up at boot/login — no manual
start needed:

```powershell
# Run PowerShell as Administrator
cloudflared service install
Start-Service cloudflared
Get-Service cloudflared        # should show Running
```

Make sure Docker Desktop is also set to **start on login** (Docker Desktop → Settings →
General → "Start Docker Desktop when you sign in"), and the `api` service has
`restart: unless-stopped` (it does). Then: laptop on → Docker up → tunnel up → reachable.

---

## Step 5 — (Optional) Add a second login wall with Cloudflare Access

For an extra gate (email one-time-pin / Google login) *in front of* the app login:
Cloudflare dashboard → **Zero Trust → Access → Applications → Add a self-hosted app** →
hostname `eaglesignal.yourdomain.com` → policy = *Allow* your email only. Free up to 50
users. This is belt-and-suspenders on top of the HTTP Basic login from Step 1.

---

## Accessing from your phone (mobile data, different network)

1. Laptop on, Docker `api` running, `cloudflared` service running.
2. On the phone (cellular, not Wi-Fi), open:
   - Option A: the `*.trycloudflare.com` URL, or
   - Option B: `https://eaglesignal.yourdomain.com`
3. Enter the `DASHBOARD_USER` / `DASHBOARD_PASSWORD` when prompted.
4. The dashboard's refresh/re-scan buttons work — the browser re-sends your login
   automatically on each request.

---

## Security checklist

- [ ] `DASHBOARD_PASSWORD` set to a long random passphrase (this is your only wall on Option A).
- [ ] `.env` is **git-ignored** — never commit credentials.
- [ ] Prefer Option B + Cloudflare Access for daily use; reserve `trycloudflare.com` for tests.
- [ ] Secrets/API keys stay in `.env` on the laptop; the tunnel exposes only `localhost:8000`.
- [ ] To shut off remote access instantly: `Stop-Service cloudflared` (or close the `cloudflared` window).
- [ ] To disable the login: remove `DASHBOARD_PASSWORD` from `.env` and `docker compose up -d api`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| No login prompt appears | `DASHBOARD_PASSWORD` not set, or container not rebuilt — `docker compose build && docker compose up -d api`. |
| 502 / "no service" on the URL | Container not running on 8000 — `docker compose ps`, `docker compose up -d api`. |
| Tunnel URL works on Wi-Fi but not cellular | It shouldn't differ — both go through Cloudflare. Re-check the phone has data and the URL is exact. |
| Tunnel didn't start after reboot | `Get-Service cloudflared`; if stopped, `Start-Service cloudflared`. Confirm Docker Desktop starts on login. |
| Login prompt loops | Wrong user/password, or special characters in the password got mangled — try a simpler passphrase. |
