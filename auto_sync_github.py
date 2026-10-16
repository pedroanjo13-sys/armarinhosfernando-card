#!/usr/bin/env python3
import os
import json
import shutil
import datetime
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
SYNC_CFG_PATH = os.path.join(BASE_DIR, "data", "github_sync.json")


def sync_to_github(commit_msg="Atualizacao automatica Armarinhos Fernando Card"):
    if not os.path.exists(SYNC_CFG_PATH):
        return {"ok": False, "error": "github_sync.json ausente"}

    with open(SYNC_CFG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    username = cfg["username"]
    token = cfg["token"]

    # Keep root copies synced with public/
    for fname in ["index.html", "portal.html", "webpos.html", "cadastro.html", "styles.css", "app.js"]:
        src = os.path.join(PUBLIC_DIR, fname)
        dst = os.path.join(BASE_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    gitignore_path = os.path.join(BASE_DIR, ".gitignore")
    with open(gitignore_path, "w", encoding="utf-8") as f:
        f.write(
            "__pycache__/\n"
            "*.pyc\n"
            "cloudflared\n"
            "data/github_sync.json\n"
            "data/url_*.txt\n"
            "data/cobraflow.db\n"
            "data/credivarejo.db\n"
        )

    def run_git(args):
        return subprocess.run(args, cwd=BASE_DIR, capture_output=True, text=True)

    if not os.path.exists(os.path.join(BASE_DIR, ".git")):
        run_git(["git", "init", "-b", "main"])
    run_git(["git", "branch", "-M", "main"])
    run_git(["git", "config", "user.name", "Pedro Henrique Anjo"])
    run_git(["git", "config", "user.email", f"{username}@users.noreply.github.com"])

    run_git([
        "git", "add",
        "server.py", "start_service.py", "auto_sync_github.py",
        "requirements.txt", "Procfile", "Dockerfile", "render.yaml",
        "index.html", "portal.html", "webpos.html", "cadastro.html", "styles.css", "app.js", "logo-af.png",
        "public/", "data/dm_varejo.db", ".gitignore"
    ])
    run_git(["git", "commit", "--allow-empty", "-m", f"{commit_msg} [{datetime.datetime.now().strftime('%H:%M:%S')}]"])

    # Push to armarinhosfernando-card (and mirror) so Render stays 100% synced!
    repos = ["armarinhosfernando-card"]
    results = {}
    for rp in repos:
        auth_url = f"https://{username}:{token}@github.com/{username}/{rp}.git"
        res = run_git(["git", "push", "--force", auth_url, "main:main"])
        results[rp] = (res.returncode == 0)

    clean_url = f"https://github.com/{username}/armarinhosfernando-card.git"
    run_git(["git", "remote", "remove", "origin"])
    run_git(["git", "remote", "add", "origin", clean_url])

    return {
        "ok": all(results.values()),
        "synced_repos": [f"https://github.com/{username}/{r}" for r in repos]
    }


if __name__ == "__main__":
    out = sync_to_github("Deploy Completo Armarinhos Fernando + Layout Minimalista + Simulador ROI Diretoria")
    print(json.dumps(out, indent=2))
