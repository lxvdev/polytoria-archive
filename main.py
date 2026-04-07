import requests
import json
import os
import subprocess
from datetime import datetime

API_URL = "https://api.polytoria.com/v1/launcher/updates?os=windows&release=stable"
DB_FILE = "versions.json"
COMPONENTS = ["Creator", "Client"]



# State handling

def load_versions():
    if not os.path.exists(DB_FILE):
        return {c: {} for c in COMPONENTS}

    with open(DB_FILE, "r") as f:
        data = json.load(f)

    for c in COMPONENTS:
        data.setdefault(c, {})

    return data


def save_versions(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)



# Version helpers

def parse_version(v):
    return tuple(int(x) for x in v.split("."))


def is_rollback(version, known_versions):
    if not known_versions:
        return False

    current = parse_version(version)
    highest = max(parse_version(v) for v in known_versions)
    return current < highest



# Download helper

def download_file(url, filename):
    headers = {"User-Agent": f"PolytoriaLauncher/1.0"}
    r = requests.get(url, headers=headers, stream=True, timeout=30)
    r.raise_for_status()
    with open(filename, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)



# GitHub Releases

def create_release(component, version, filename, rollback):
    tag = f"{component}-{version}"
    title = f"{component} {version}"
    notes = f"Archived {component} {version}"

    if rollback:
        title += " (rollback)"
        notes += "\n\n⚠️ First detected as rollback"

    subprocess.run([
        "gh", "release", "create", tag,
        filename,
        "--title", title,
        "--notes", notes
    ])


def update_release(component, version, entry):
    tag = f"{component}-{version}"
    rollback_count = entry["rollback_count"]
    total_count = entry["count"]
    history_lines = [
        f"{h['timestamp']} - {'rollback' if h['rollback'] else 'normal'}"
        for h in entry.get("history", [])
    ]
    notes = f"""Archived {component} {version}

⚠️ Rollback detected
Rollback occurrences: {rollback_count}
Total times seen: {total_count}

History:
""" + "\n".join(history_lines)

    subprocess.run([
        "gh", "release", "edit", tag,
        "--notes", notes
    ])

# Main

def run():
    versions = load_versions()

    headers = {"User-Agent": f"PolytoriaLauncher/1.0"}
    res = requests.get(API_URL, headers=headers, timeout=10)
    res.raise_for_status()
    data = res.json()

    for component in COMPONENTS:
        info = data.get(component)
        if not info:
            continue

        version = info["Version"]
        url = info["Download"]
        component_data = versions[component]
        known_versions = list(component_data.keys())

        rollback = is_rollback(version, known_versions)

        entry = component_data.get(version)
        timestamp = datetime.utcnow().isoformat()

        if entry:
            # Version seen before
            entry["count"] += 1
            entry.setdefault("history", []).append({"timestamp": timestamp, "rollback": rollback})

            if rollback:
                entry["rollback_count"] += 1
                print(f"⚠️ Repeated rollback: {component} {version}")
                update_release(component, version, entry)
            else:
                print(f"{component} {version} seen again (not rollback)")
            continue

        # New version
        print(f"New {component} version: {version}")
        ext = ".exe" if url.endswith(".exe") else ".7z"
        filename = f"{component}-{version}{ext}"

        download_file(url, filename)

        component_data[version] = {
            "count": 1,
            "rollback_count": 1 if rollback else 0,
            "history": [{"timestamp": timestamp, "rollback": rollback}]
        }

        if rollback:
            print(f"⚠️ Rollback detected: {component} {version}")
            create_release(component, version, filename, rollback)
        else:
            create_release(component, version, filename, rollback)

    save_versions(versions)


if __name__ == "__main__":
    run()