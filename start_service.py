import os
import re
import sys
import time
import urllib.request
import subprocess
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

role = "admin"
port = 3000
pos_args = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(pos_args) >= 2:
    role = pos_args[0]
    port = int(pos_args[1])
for arg in sys.argv[1:]:
    if arg.startswith("--role="):
        role = arg.split("=", 1)[1]
    elif arg.startswith("--port="):
        port = int(arg.split("=", 1)[1])

# Start cloudflared tunnel for external public HTTPS access
cf_bin = os.path.join(BASE_DIR, "cloudflared")
url_file = os.path.join(DATA_DIR, f"url_{role}.txt")


def run_cloudflared():
    if not os.path.exists(cf_bin):
        return
    try:
        os.chmod(cf_bin, 0o755)
    except Exception:
        pass
    while True:
        proc = subprocess.Popen(
            [
                cf_bin,
                "tunnel",
                "--no-autoupdate",
                "--protocol", "http2",
                "--grace-period", "30s",
                "--retries", "10",
                "--url", f"http://127.0.0.1:{port}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        for line in proc.stdout:
            m = pattern.search(line)
            if m:
                pub_url = m.group(0)
                with open(url_file, "w", encoding="utf-8") as f:
                    f.write(pub_url)
                print(f"[PUBLIC-URL-{role.upper()}] {pub_url}", flush=True)
        proc.wait()
        time.sleep(2)


def run_keepalive_watchdog():
    """Pings local port and public Cloudflare URL every 60s & full 10-min cycle so the tunnel never drops."""
    cycle = 0
    while True:
        time.sleep(60)
        cycle += 1
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/sync-version?keepalive=1", timeout=8).read()
        except Exception:
            pass
        try:
            if os.path.exists(url_file):
                with open(url_file, "r", encoding="utf-8") as f:
                    pub_url = f.read().strip()
                if pub_url.startswith("https://"):
                    req = urllib.request.Request(
                        f"{pub_url}/api/sync-version?keepalive=1&cycle={cycle}",
                        headers={"User-Agent": "BomPreco-KeepAlive-Watchdog/1.0"},
                    )
                    urllib.request.urlopen(req, timeout=12).read()
        except Exception:
            pass


t = threading.Thread(target=run_cloudflared, daemon=True)
t.start()

t_ka = threading.Thread(target=run_keepalive_watchdog, daemon=True)
t_ka.start()

# Keep server.py running and auto-restart if reloaded
while True:
    server_proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "server.py"), f"--role={role}", f"--port={port}"],
        cwd=BASE_DIR,
    )
    try:
        server_proc.wait()
        time.sleep(0.5)
    except KeyboardInterrupt:
        server_proc.terminate()
        break
