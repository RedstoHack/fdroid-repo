import os
import requests
import yaml
import subprocess
import sys
from pathlib import Path

APPS_FILE = "apps.yml"
REPO_DIR = "fdroid"

def get_latest_github_release(repo_url):
    parts = repo_url.rstrip('/').split('/')
    owner, repo = parts[-2], parts[-1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {}
    if "GITHUB_TOKEN" in os.environ:
        headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"
        headers["Accept"] = "application/vnd.github+json"
    
    try:
        res = requests.get(api_url, headers=headers)
        if res.status_code == 200:
            return res.json()
        print(f"Failed to fetch GitHub release for {repo_url}: {res.status_code}")
    except Exception as e:
        print(f"Error fetching GitHub release: {e}")
    return None

def get_latest_gitlab_release(repo_url):
    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 4:
        print(f"Invalid GitLab URL: {repo_url}")
        return None
    host = parts[2]
    project_path = "%2F".join(parts[3:]) # Поддержка подгрупп в GitLab
    api_url = f"https://{host}/api/v4/projects/{project_path}/releases/permalink/latest"
    
    try:
        res = requests.get(api_url)
        if res.status_code == 200:
            return res.json()
        print(f"Failed to fetch GitLab release for {repo_url}: {res.status_code}")
    except Exception as e:
        print(f"Error fetching GitLab release: {e}")
    return None

def download_file(url, path, headers=None):
    print(f"Downloading {path} from {url}...")
    try:
        with requests.get(url, headers=headers or {}, stream=True) as r:
            r.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def main():
    if not os.path.exists(APPS_FILE):
        print(f"{APPS_FILE} not found.")
        return
        
    with open(APPS_FILE, 'r') as f:
        config = yaml.safe_load(f)
        
    apps = config.get("apps", {})
    if not os.path.exists(REPO_DIR):
        os.makedirs(os.path.join(REPO_DIR, "repo"))
        
    repo_path = Path(REPO_DIR)
    
    any_new = False
    for app_id, app_info in apps.items():
        repo_url = app_info.get("url")
        if not repo_url:
            continue
            
        print(f"\n--- Checking updates for {app_id} ---")
        
        release = None
        if "github.com" in repo_url:
            release = get_latest_github_release(repo_url)
        elif "gitlab" in repo_url:
            release = get_latest_gitlab_release(repo_url)
            
        if not release:
            continue
            
        assets = []
        if "github.com" in repo_url:
            assets = [a for a in release.get("assets", []) if a.get("name", "").endswith(".apk")]
        else:
            assets = [a for a in release.get("assets", {}).get("links", []) if a.get("name", "").endswith(".apk")]
            
        if not assets:
            print(f"No APK assets found in latest release for {app_id}.")
            continue
            
        for asset in assets:
            apk_name = asset["name"]
            apk_path = repo_path / "repo" / apk_name
            
            if apk_path.exists():
                print(f"Already have {apk_name}, skipping.")
                continue
                
            headers = {}
            if "github.com" in repo_url:
                asset_url = asset.get("browser_download_url")
                if "GITHUB_TOKEN" in os.environ:
                    headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"
            else:
                asset_url = asset.get("direct_asset_url") or asset.get("url")
                
            if download_file(asset_url, apk_path, headers):
                any_new = True
                print(f"Successfully downloaded {apk_name}")

    if any_new:
        print("\n--- Running fdroid update ---")
        env = os.environ.copy()
        if os.path.exists(os.path.expanduser("~/.local/bin")):
            env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env["PATH"]
            
        res = subprocess.run(["fdroid", "update", "--create-metadata"], cwd=REPO_DIR, env=env)
        if res.returncode == 0:
            print("fdroid update successful!")
        else:
            print("fdroid update failed!")
            sys.exit(1)
    else:
        print("\nNo new APKs downloaded. Skipping fdroid update.")

if __name__ == "__main__":
    main()
