"""Clone private GitHub repos inside a LangSmith sandbox using device auth.

Requires:
    pip install "langsmith[sandbox]"

Usage:
    python python/examples/sandbox_private_github_app.py \
        --snapshot-id YOUR_SNAPSHOT_ID \
        --repo your-org/private-repo \
        --repo another-org/another-private-repo
"""

from __future__ import annotations

import argparse
import base64
import shlex
import time

import requests

from langsmith.sandbox import SandboxClient

GITHUB_APP_CLIENT_ID = "Iv23lioB3knEcicjfmAW"
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


def _device_code() -> dict[str, str | int]:
    response = requests.post(
        "https://github.com/login/device/code",
        headers={"Accept": "application/json"},
        data={"client_id": GITHUB_APP_CLIENT_ID},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _poll_device_token(device_code: str, interval: int, expires_in: int) -> str:
    deadline = time.monotonic() + expires_in
    while time.monotonic() < deadline:
        time.sleep(interval)
        response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_APP_CLIENT_ID,
                "device_code": device_code,
                "grant_type": DEVICE_GRANT_TYPE,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if access_token := data.get("access_token"):
            return str(access_token)
        error = data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        raise RuntimeError(data.get("error_description", f"GitHub auth failed: {data}"))
    raise TimeoutError("GitHub device authorization expired")


def _device_flow_token() -> str:
    data = _device_code()
    print(  # noqa: T201
        "Open {verification_uri} and enter code {user_code}".format(**data)
    )
    return _poll_device_token(
        str(data["device_code"]),
        int(data.get("interval", 5)),
        int(data["expires_in"]),
    )


def _github_proxy_config(token: str) -> dict[str, object]:
    basic_token = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "rules": [
            {
                "name": "github-auth",
                "match_hosts": ["github.com"],
                "headers": [
                    {
                        "name": "Authorization",
                        "type": "opaque",
                        "value": f"Basic {basic_token}",
                    }
                ],
            }
        ]
    }
def main() -> None:
    """Run the GitHub App sandbox clone example."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        action="append",
        required=True,
        help="GitHub repository to clone, as owner/name. Pass multiple times.",
    )
    parser.add_argument(
        "--snapshot-id",
        required=True,
        help="Existing LangSmith sandbox snapshot ID.",
    )
    args = parser.parse_args()

    token = _device_flow_token()

    client = SandboxClient()

    with client.sandbox(
        snapshot_id=args.snapshot_id,
        timeout=60,
        proxy_config=_github_proxy_config(token),
    ) as sb:
        sb.run("mkdir -p /workspace", shell="/bin/sh")

        for repo in args.repo:
            repo_url = f"https://github.com/{repo}.git"
            repo_name = repo.rsplit("/", 1)[-1]
            target_dir = f"/workspace/{repo_name}"
            print(f"Cloning {repo} into {target_dir}...")  # noqa: T201
            clone_cmd = " && ".join(
                [
                    f"git clone --depth 1 {shlex.quote(repo_url)} {target_dir}",
                    f"git -C {target_dir} rev-parse --short HEAD",
                ]
            )
            result = sb.run(
                clone_cmd,
                env={
                    "GIT_TERMINAL_PROMPT": "0",
                },
                shell="/bin/sh",
                timeout=120,
            )
            if result.exit_code != 0:
                raise RuntimeError(result.stderr)
            print(f"Cloned {repo} to {target_dir} at {result.stdout.strip()}")  # noqa: T201


if __name__ == "__main__":
    main()
