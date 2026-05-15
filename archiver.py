import argparse
import json
import os
import subprocess
from datetime import datetime

import requests

API_URL_TEMPLATE = "https://api.polytoria.com/v1/launcher/updates?os=windows&release={release}"
USER_AGENT = "PolytoriaLauncher/1.0"
COMPONENTS = ["Creator", "Client"]
VERSIONS_FILE = "versions.json"

def parse_version(version: str):
    """Parse version string into a comparable tuple.

    Stable versions sort higher than beta versions with the same base version.
    """
    parts = version.split("-")
    base_version = tuple(map(int, parts[0].split(".")))

    if len(parts) > 1 and parts[1].startswith("beta"):
        beta_num = int(parts[1][4:])
        return base_version + (0, beta_num)

    return base_version + (1,)


def is_beta_version(version: str):
    parts = version.split("-")
    return len(parts) > 1 and parts[1].startswith("beta")


def get_xsrf_token_and_session(pt_auth: str):
    if not pt_auth:
        raise RuntimeError("PT_AUTH is required to fetch a launch authorization token.")

    response = requests.post("https://polytoria.com/api/places/join", 
                             headers={"User-Agent": USER_AGENT}, 
                             cookies={"PT_AUTH": pt_auth})

    if response.status_code != 403:
        response.raise_for_status()

    xsrf_token = response.cookies.get("XSRF-TOKEN")
    if not xsrf_token:
        return None
    
    session = response.cookies.get("SESSION")
    if not session:
        return None

    return xsrf_token, session


def get_launch_token(pt_auth: str):
    print("Obtaining XSRF-TOKEN and SESSION...")
    
    xsrf_token, session = get_xsrf_token_and_session(pt_auth)
    if xsrf_token is None or session is None:
        raise RuntimeError("Failed to obtain XSRF-TOKEN and SESSION.")

    print("Obtaining launch token...")
    response = requests.post(
        "https://polytoria.com/api/places/join",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, "X-XSRF-TOKEN": xsrf_token},
        cookies={"PT_AUTH": pt_auth, "XSRF-TOKEN": xsrf_token, "SESSION": session},
        json={"placeID": 4161},
    )
    response.raise_for_status()

    data = response.json()
    if not data.get("success") or "token" not in data:
        raise RuntimeError(f"Unexpected launch token response: {data}")

    print("Launch token acquired.")
    return data["token"]


def load_versions():
    if not os.path.exists(VERSIONS_FILE):
        return {"stable": {}, "beta": {}}

    with open(VERSIONS_FILE, "r") as f:
        data = json.load(f)

    if "stable" not in data or "beta" not in data:
        raise ValueError(
            f"{VERSIONS_FILE} must contain top-level 'stable' and 'beta' sections."
        )

    return data


def save_versions(versions):
    with open(VERSIONS_FILE, "w") as f:
        json.dump(versions, f, indent=2)


def download_file(url: str, filename: str, headers: dict):
    if os.path.exists(filename):
        print(f"    File {filename} already exists, skipping download")
        return filename

    print(f"    Downloading from {url} ...")
    with requests.get(url, headers=headers, stream=True) as response:
        response.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in response.iter_content(8192):
                if chunk:
                    f.write(chunk)

    print("    Download complete")
    return filename


def gh_create_release(tag: str, name: str, body: str, file_path: str, prerelease: bool):
    cmd = ["gh", "release", "create", tag, file_path, "--title", name, "--notes", body]
    if prerelease:
        cmd.append("--prerelease")
    subprocess.run(cmd, check=True)


def gh_update_release(tag: str, name: str, body: str):
    cmd = ["gh", "release", "edit", tag, "--title", name, "--notes", body]
    subprocess.run(cmd, check=True)


def gh_release_exists(tag: str) -> bool:
    result = subprocess.run(
        ["gh", "release", "view", tag],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def process_component(component: str, info: dict, stored: dict, updated: dict, headers: dict, prerelease: bool):
    version = info["Version"]
    url = info["Download"]

    prev_version = stored.get(component, {}).get("version")
    if prev_version == version:
        print(f"  {component} version {version} is unchanged, skipping...")
        return

    if prev_version and parse_version(version) <= parse_version(prev_version):
        print(f"  {component} version {version} is older than stored version {prev_version}, skipping...")
        return

    print(f"  New version detected: {version} (previous: {prev_version})")
    ext = os.path.splitext(url)[1] or ".unk"
    filename = f"{component}-{version}{ext}"
    path = download_file(url, filename, headers)

    tag = f"{component}-{version}"
    name = f"{component} {version}"
    body = f"Archived {component} {version} at {datetime.utcnow().isoformat()} UTC"

    if not gh_release_exists(tag):
        print(f"  Creating new GitHub release: {tag}")
        gh_create_release(tag, name, body, path, prerelease)
    else:
        print(f"  Release {tag} already exists, skipping...")

    updated[component] = {"version": version}
    print(f"  {component} updated successfully")


def archive_release(release: str):
    release = release.lower()
    if release not in {"stable", "beta"}:
        raise ValueError("Release must be 'stable' or 'beta'.")

    api_url = API_URL_TEMPLATE.format(release=release)

    token = None
    if release == "beta":
        token = get_launch_token(os.getenv("PT_AUTH"))

    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = token

    print(f"Starting archive process for '{release}'...")
    print(f"Using API URL: {api_url}")

    versions = load_versions()
    updated_versions = {
        "stable": dict(versions["stable"]),
        "beta": dict(versions["beta"]),
    }

    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    data = response.json()
    print("Successfully fetched API data")

    for component in COMPONENTS:
        info = data.get(component)
        if not info:
            print(f"No data found for {component}")
            continue

        version = info["Version"]
        target_release = "beta" if is_beta_version(version) else "stable"
        stored_versions = versions[target_release]
        updated_section = updated_versions[target_release]
        prerelease = target_release == "beta"

        print(f"Processing {component} (target: {target_release})...")
        process_component(component, info, stored_versions, updated_section, headers, prerelease)

    print("Updating versions file...")
    versions["stable"] = updated_versions["stable"]
    versions["beta"] = updated_versions["beta"]
    save_versions(versions)
    print("Archive process completed successfully")


def parse_args():
    parser = argparse.ArgumentParser(description="Archive Polytoria stable and beta launcher builds")
    parser.add_argument(
        "--release",
        choices=["stable", "beta"],
        default=os.getenv("RELEASE", "stable"),
        help="Release channel to archive",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    archive_release(args.release)


if __name__ == "__main__":
    main()
