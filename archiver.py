import os
import json
import hashlib
import requests
from datetime import datetime
import subprocess

API_URL = "https://api.polytoria.com/v1/launcher/updates?os=windows&release=stable"
HEADERS = {"User-Agent": "PolytoriaLauncher/1.0"}
VERSIONS_FILE = "versions.json"

COMPONENTS = ["Creator", "Client"]

def parse_version(v: str):
    return tuple(map(int, v.split(".")))

# def sha256_file(path):
#    h = hashlib.sha256()
#    with open(path, "rb") as f:
#        while chunk := f.read(8192):
#            h.update(chunk)
#    return h.hexdigest()

def load_versions():
    if not os.path.exists(VERSIONS_FILE):
        return {}
    with open(VERSIONS_FILE, "r") as f:
        return json.load(f)

def save_versions(versions):
    with open(VERSIONS_FILE, "w") as f:
        json.dump(versions, f, indent=2)

def download_file(url: str, filename: str):
    if os.path.exists(filename):
        return filename
    
    with requests.get(url, headers=HEADERS, stream=True) as r:
        r.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
    return filename


def gh_create_release(tag, name, body, file_path):
    cmd = ["gh", "release", "create", tag, file_path, "--title", name, "--notes", body]
    subprocess.run(cmd, check=True)

def gh_update_release(tag, name, body):
    cmd = ["gh", "release", "edit", tag, "--title", name, "--notes", body]
    subprocess.run(cmd, check=True)

def gh_release_exists(tag: str) -> bool:
    result = subprocess.run(
        ["gh", "release", "view", tag],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0

def process_component(component: str, info: dict, stored: dict, updated: dict):
    version = info["Version"]
    url = info["Download"]

    prev = stored.get(component, {})
    prev_version = prev.get("version")

    # Ignore if version is unchanged
    if prev_version == version:
        return

    ext = os.path.splitext(url)[1] or ".unk"
    filename = f"{component}-{version}{ext}"
    path = download_file(url, filename)

    tag = f"{component}-{version}"
    name = f"{component} {version}"
    body = f"Archived {component} {version} at {datetime.utcnow().isoformat()} UTC"

    # Upload new version
    if not prev_version or parse_version(version) > parse_version(prev_version):
        if not gh_release_exists(tag):
            gh_create_release(tag, name, body, path)
        else:
            gh_update_release(tag, f"{name} (Superseded)") # Mark old release as superseded (rollback occured)
            
        updated[component] = {"version": version}
        return

def main():
    stored_versions = load_versions()

    response = requests.get(API_URL, headers=HEADERS)
    response.raise_for_status()
    data = response.json()

    updated_versions = dict(stored_versions)

    for component in COMPONENTS:
        info = data.get(component)
        if not info:
            continue

        process_component(component, info, stored_versions, updated_versions)

    save_versions(updated_versions)

if __name__ == "__main__":
    main()
