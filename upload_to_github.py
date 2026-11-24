import base64
import os
import subprocess
import sys
import time
import webbrowser
import requests

CLIENT_ID = "178c6fc778ccc68e1d6a"  # Official GitHub CLI OAuth Client ID
REPO_NAME = "AbuFahad-AudioStudio"
REPO_DESC = "🎙️ كرت الصوت الوهمي (Abu fahad ©) — برنامج فوري لتضخيم الصوت والبيس العميق وصدى قوي جدا للمايك مع دعم فويس ميتر والديسكورد"


def copy_to_clipboard(text: str):
    try:
        p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
        p.communicate(input=text.encode("utf-8"))
    except Exception:
        pass


def get_github_token() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_candidates = [
        os.path.join(base_dir, ".gh_token"),
        os.path.join(r"C:\Users\djdjf\OneDrive\Desktop\Bluer Girl", ".gh_token"),
    ]

    for token_file in token_candidates:
        if os.path.exists(token_file):
            saved = open(token_file, "r", encoding="utf-8").read().strip()
            if saved:
                try:
                    r = requests.get(
                        "https://api.github.com/user",
                        headers={"Authorization": f"token {saved}"},
                        timeout=10,
                    )
                    if r.status_code == 200:
                        # cache locally
                        local_tf = os.path.join(base_dir, ".gh_token")
                        if not os.path.exists(local_tf):
                            try:
                                open(local_tf, "w", encoding="utf-8").write(saved)
                            except Exception:
                                pass
                        return saved
                except Exception:
                    pass

    resp = requests.post(
        "https://github.com/login/device/code",
        headers={"Accept": "application/json"},
        data={"client_id": CLIENT_ID, "scope": "repo"},
        timeout=15,
    ).json()

    device_code = resp["device_code"]
    user_code = resp["user_code"]
    verify_url = resp["verification_uri"]
    interval = int(resp.get("interval", 5))

    copy_to_clipboard(user_code)
    print("=" * 65, flush=True)
    print(f"🔑 كود التفعيل لحسابك في GitHub (تم نسخه للحافظة تلقائياً): {user_code}", flush=True)
    print(f"🌐 افتح الرابط وحط الكود واضغط Authorize: {verify_url}", flush=True)
    print("=" * 65, flush=True)

    try:
        webbrowser.open(verify_url)
    except Exception:
        pass

    while True:
        time.sleep(interval)
        poll = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=15,
        ).json()

        if "access_token" in poll:
            token = poll["access_token"]
            try:
                open(os.path.join(base_dir, ".gh_token"), "w", encoding="utf-8").write(token)
            except Exception:
                pass
            return token

        err = poll.get("error")
        if err == "authorization_pending":
            continue
        elif err == "slow_down":
            interval += 5
        else:
            raise RuntimeError(f"GitHub authorization stopped: {err}")


def upload_project():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token = get_github_token()
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    user_info = requests.get(
        "https://api.github.com/user", headers=headers, timeout=15
    ).json()
    username = user_info["login"]
    print(f"\n✅ تم الدخول بحسابك في GitHub: @{username}", flush=True)

    # 1. Create or check repository
    repo_url = f"https://api.github.com/repos/{username}/{REPO_NAME}"
    r_check = requests.get(repo_url, headers=headers, timeout=15)
    if r_check.status_code == 404:
        print(f"📦 جاري إنشاء المستودع {REPO_NAME} في حسابك...", flush=True)
        r_create = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json={
                "name": REPO_NAME,
                "description": REPO_DESC,
                "private": False,
                "auto_init": True,
            },
            timeout=20,
        )
        r_create.raise_for_status()
        time.sleep(2)
    else:
        print(f"📦 المستودع {REPO_NAME} موجود، جاري تحديث الملفات...", flush=True)

    # 2. Collect all project files to commit (excluding >45MB binaries & git/cache)
    files_to_commit = []
    skip_dirs = {".git", "__pycache__", "build", "dist", "AbuFahad_AudioStudio"}
    skip_files = {".gh_token", "AbuFahad_AudioStudio.rar"}

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if fname in skip_files or fname.endswith(".pyc") or fname.endswith(".spec"):
                continue
            full_p = os.path.join(root, fname)
            if os.path.getsize(full_p) > 45 * 1024 * 1024:
                continue
            rel_p = os.path.relpath(full_p, base_dir).replace("\\", "/")
            files_to_commit.append((rel_p, full_p))

    gitignore_content = "__pycache__/\n*.pyc\n.gh_token\nbuild/\ndist/\n*.spec\n"

    # Get latest commit SHA on main/master
    ref_r = requests.get(
        f"https://api.github.com/repos/{username}/{REPO_NAME}/git/ref/heads/main",
        headers=headers,
        timeout=15,
    )
    if ref_r.status_code != 200:
        ref_r = requests.get(
            f"https://api.github.com/repos/{username}/{REPO_NAME}/git/ref/heads/master",
            headers=headers,
            timeout=15,
        )
    ref_data = ref_r.json()
    branch_ref = ref_data["ref"]
    latest_commit_sha = ref_data["object"]["sha"]

    commit_r = requests.get(
        f"https://api.github.com/repos/{username}/{REPO_NAME}/git/commits/{latest_commit_sha}",
        headers=headers,
        timeout=15,
    ).json()
    base_tree_sha = commit_r["tree"]["sha"]

    tree_items = []
    # Add .gitignore
    b_gi = requests.post(
        f"https://api.github.com/repos/{username}/{REPO_NAME}/git/blobs",
        headers=headers,
        json={"content": gitignore_content, "encoding": "utf-8"},
        timeout=15,
    ).json()
    tree_items.append(
        {
            "path": ".gitignore",
            "mode": "100644",
            "type": "blob",
            "sha": b_gi["sha"],
        }
    )

    for rel_p, full_p in files_to_commit:
        print(f"  ⬆️ رفع الملف: {rel_p}", flush=True)
        raw_bytes = open(full_p, "rb").read()
        b64_content = base64.b64encode(raw_bytes).decode("ascii")
        blob_r = requests.post(
            f"https://api.github.com/repos/{username}/{REPO_NAME}/git/blobs",
            headers=headers,
            json={"content": b64_content, "encoding": "base64"},
            timeout=30,
        )
        blob_r.raise_for_status()
        tree_items.append(
            {
                "path": rel_p,
                "mode": "100644",
                "type": "blob",
                "sha": blob_r.json()["sha"],
            }
        )

    new_tree = requests.post(
        f"https://api.github.com/repos/{username}/{REPO_NAME}/git/trees",
        headers=headers,
        json={"base_tree": base_tree_sha, "tree": tree_items},
        timeout=25,
    ).json()

    new_commit = requests.post(
        f"https://api.github.com/repos/{username}/{REPO_NAME}/git/commits",
        headers=headers,
        json={
            "message": "🎙️ كرت الصوت الوهمي (Abu fahad ©) v1.0 — تضخيم الصوت والبيس العميق وصدى قوي جدا للمايك مع دعم فويس ميتر",
            "tree": new_tree["sha"],
            "parents": [latest_commit_sha],
        },
        timeout=20,
    ).json()

    requests.patch(
        f"https://api.github.com/repos/{username}/{REPO_NAME}/git/{branch_ref}",
        headers=headers,
        json={"sha": new_commit["sha"], "force": True},
        timeout=15,
    ).raise_for_status()

    print("\n✅ تم رفع جميع الأكواد والملفات إلى المستودع بنجاح!", flush=True)

    # 3. Create GitHub Release v1.0.0 and attach RAR package
    print("🏷️ جاري إنشاء إصدار GitHub Release (v1.0.0) ورفع النسخة المضغوطة...", flush=True)
    rel_check = requests.get(
        f"https://api.github.com/repos/{username}/{REPO_NAME}/releases/tags/v1.0.0",
        headers=headers,
        timeout=15,
    )
    if rel_check.status_code == 200:
        release_data = rel_check.json()
    else:
        rel_create = requests.post(
            f"https://api.github.com/repos/{username}/{REPO_NAME}/releases",
            headers=headers,
            json={
                "tag_name": "v1.0.0",
                "name": "🎙️ كرت الصوت الوهمي v1.0.0 — Abu fahad Edition",
                "body": (
                    "### 🎙️ كرت الصوت الوهمي v1.0.0 (Abu fahad ©)\n"
                    "- **تضخيم عميق وضخم:** تحكم بقوة الدخل (Preamp) والبيس العميق والتردد التحتي والتشبع الأنبوبي (Drive).\n"
                    "- **صدى قوي جداً:** صدى متعدد الضربات مع تكرار عالي وتردد قاعة احترافي وتحكم مباشر بقوة الصدى حتى 200%.\n"
                    "- **10 وزنيات جاهزة:** تشمل وزنية أبو فهد الأساسية، تضخيم وحشي، صدى متكرر، صدى عميق، وغيرها.\n"
                    "- **تكامل مع Voicemeeter:** زر بنقرة واحدة لتشغيل وتوجيه المسار تلقائياً إلى B1 ومايك الديسكورد.\n"
                    "- **نسخة محمولة:** الملف المرفق أدناه جاهز للتشغيل مباشرة دون الحاجة لتثبيت أي برامج إضافية."
                ),
                "draft": False,
                "prerelease": False,
            },
            timeout=20,
        )
        release_data = rel_create.json()

    upload_url_template = release_data.get("upload_url", "").split("{")[0]
    existing_assets = {a["name"] for a in release_data.get("assets", [])}

    rar_path = os.path.join(base_dir, "AbuFahad_AudioStudio.rar")
    if os.path.exists(rar_path) and "AbuFahad_AudioStudio.rar" not in existing_assets and upload_url_template:
        sz_mb = os.path.getsize(rar_path) / (1024 * 1024)
        print(f"  📦 رفع ملف الإصدار: AbuFahad_AudioStudio.rar ({sz_mb:.1f} MB)...", flush=True)
        with open(rar_path, "rb") as af:
            up_headers = {
                "Authorization": f"token {token}",
                "Content-Type": "application/x-rar-compressed",
            }
            up_r = requests.post(
                f"{upload_url_template}?name=AbuFahad_AudioStudio.rar",
                headers=up_headers,
                data=af,
                timeout=300,
            )
            if up_r.status_code in (200, 201):
                print(f"     ✅ تم رفع AbuFahad_AudioStudio.rar بنجاح!", flush=True)

    final_html_url = f"https://github.com/{username}/{REPO_NAME}"
    copy_to_clipboard(final_html_url)
    print("\n" + "=" * 65, flush=True)
    print(f"🎉 اكتمل رفع المشروع بالكامل على حسابك في GitHub!", flush=True)
    print(f"🔗 رابط المستودع: {final_html_url}", flush=True)
    print("=" * 65, flush=True)
    try:
        webbrowser.open(final_html_url)
    except Exception:
        pass


if __name__ == "__main__":
    upload_project()
