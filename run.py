#!/usr/bin/env python3
"""Run the Code Collective local stack in Docker.

This is the top-level runner for local development. It does not use Docker
Compose. Containers read live source from bind mounts.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
import urllib.error
import urllib.request
import ssl
from pathlib import Path


root = Path(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(str(root / "portal"))

import docker_utils


PREFIX = "codecollective-"
DATACENTERS_IMAGE = "codecollective-datacenters-kimi"
WORKSPACE = "/workspace"
KIMI_ENV_FILE = root / ".env.kimi"


def env_file_has_key(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}=") and stripped.split("=", 1)[1].strip():
            return True
    return False


def ensure_datacenters_image(force_rebuild: bool = False) -> None:
    images = docker_utils.DOCKER_CLIENT.images.list(name=DATACENTERS_IMAGE)
    if not force_rebuild:
        for image in images:
            if DATACENTERS_IMAGE in image.tags:
                return
    print("Building datacenters helper image from datacenters/Dockerfile.kimi...")
    docker_utils.DOCKER_CLIENT.images.build(
        path=str(root / "datacenters"),
        dockerfile="Dockerfile.kimi",
        tag=DATACENTERS_IMAGE,
        forcerm=True,
    )


def remove_container(name: str) -> None:
    try:
        container = docker_utils.DOCKER_CLIENT.containers.get(name)
        container.stop()
        container.remove(force=True)
    except Exception:
        pass


def wait_for_http(url: str, label: str, attempts: int = 120) -> None:
    context = ssl._create_unverified_context() if url.startswith("https://") else None
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2, context=context) as response:
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {label} at {url}")


def shared_python_container(name: str) -> dict:
    return {
        "image": DATACENTERS_IMAGE,
        "name": name,
        "detach": True,
        "network_mode": "host",
        "restart_policy": {"Name": "unless-stopped"},
        "working_dir": WORKSPACE,
        "volumes": {
            str(root): {"bind": WORKSPACE, "mode": "rw"},
        },
        "environment": {
            "PYTHONUNBUFFERED": "1",
        },
    }


def start_static_site(port: int) -> None:
    name = PREFIX + "site"
    remove_container(name)
    site = shared_python_container(name)
    site["command"] = [
        "python3",
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
    ]
    docker_utils.run_container(site)
    wait_for_http(f"http://127.0.0.1:{port}/projects.html", "main static site")


def start_r8(port: int) -> None:
    name = PREFIX + "r8-rowhome"
    remove_container(name)
    r8 = {
        "image": os.getenv("CODECOLLECTIVE_R8_IMAGE", "node:24-alpine"),
        "name": name,
        "detach": True,
        "network_mode": "host",
        "restart_policy": {"Name": "unless-stopped"},
        "working_dir": f"{WORKSPACE}/r8-rowhome",
        "volumes": {
            str(root): {"bind": WORKSPACE, "mode": "rw"},
            PREFIX + "r8-node-modules": {
                "bind": f"{WORKSPACE}/r8-rowhome/node_modules",
                "mode": "rw",
            },
        },
        "environment": {
            "NODE_ENV": "development",
            "VITE_PUBLIC_BASE": "/",
        },
        "command": [
            "sh",
            "-c",
            f"npm install && npm run dev -- --host 0.0.0.0 --port {port}",
        ],
    }
    docker_utils.run_container(r8)
    wait_for_http(f"https://127.0.0.1:{port}/", "R8 Vite site")


def start_datacenter_helpers(args: argparse.Namespace) -> None:
    research_name = PREFIX + "datacenters-research"
    dashboard_name = PREFIX + "datacenters-dashboard"
    for name in (research_name, dashboard_name):
        remove_container(name)

    has_kimi_key = bool(os.getenv("MOONSHOT_API_KEY")) or env_file_has_key(KIMI_ENV_FILE, "MOONSHOT_API_KEY")
    if has_kimi_key:
        research = shared_python_container(research_name)
        research["restart_policy"] = {"Name": "no"}
        research["command"] = [
            "python3",
            "datacenters/research_inventory_with_kimi.py",
            "--env-file",
            str(KIMI_ENV_FILE),
            "--workers",
            str(args.kimi_workers),
            "--max-searches",
            str(args.kimi_max_searches),
            "--max-tier",
            args.kimi_max_tier,
            "--control-host",
            "127.0.0.1",
            "--control-port",
            str(args.kimi_port),
            "--verbose",
        ]
        docker_utils.run_container(research)
        wait_for_http(f"http://127.0.0.1:{args.kimi_port}/status", "datacenter research API")
    else:
        print(f"Kimi API key not configured; start the inspector and save a key to {KIMI_ENV_FILE}")

    dashboard = shared_python_container(dashboard_name)
    dashboard["command"] = [
        "python3",
        "datacenters/kimi_research_dashboard.py",
        "--upstream",
        f"http://127.0.0.1:{args.kimi_port}",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.kimi_dashboard_port),
        "--env-file",
        str(KIMI_ENV_FILE),
    ]
    docker_utils.run_container(dashboard)
    wait_for_http(f"http://127.0.0.1:{args.kimi_dashboard_port}/", "datacenter dashboard")


def start_portal(prefix: str, network_name: str) -> None:
    portal_run_path = root / "portal" / "run.py"
    spec = importlib.util.spec_from_file_location("codecollective_portal_run", portal_run_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {portal_run_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run(prefix, network_name)


def start(args: argparse.Namespace) -> None:
    ensure_datacenters_image(force_rebuild=args.rebuild)
    start_static_site(args.site_port)
    if not args.no_r8:
        start_r8(args.r8_port)
    if not args.no_datacenters:
        start_datacenter_helpers(args)
    if args.with_portal:
        start_portal(args.portal_prefix, args.portal_network)

    print(f"Main site:             http://127.0.0.1:{args.site_port}/")
    print(f"Branding:              http://127.0.0.1:{args.site_port}/branding.html")
    print(f"Kimi Inspector:        http://127.0.0.1:{args.site_port}/kimi-inspector.html")
    if not args.no_r8:
        print(f"R8 dev site:           https://127.0.0.1:{args.r8_port}/")
    if not args.no_datacenters:
        print(f"Datacenter dashboard:  http://127.0.0.1:{args.kimi_dashboard_port}/")
        print(f"Datacenter control:    http://127.0.0.1:{args.kimi_port}/status")
    print(f"Live source mount:     {root} -> {WORKSPACE}")


def stop(_args: argparse.Namespace) -> None:
    for name in (
        PREFIX + "site",
        PREFIX + "r8-rowhome",
        PREFIX + "datacenters-research",
        PREFIX + "datacenters-dashboard",
        "codecollective-datacenters-site",
        "codecollective-datacenters-research",
        "codecollective-datacenters-dashboard",
    ):
        remove_container(name)


def status(_args: argparse.Namespace) -> None:
    print(docker_utils.list_containers(show_all=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--site-port", type=int, default=8877)
    start_parser.add_argument("--r8-port", type=int, default=5173)
    start_parser.add_argument("--kimi-port", type=int, default=8765)
    start_parser.add_argument("--kimi-dashboard-port", type=int, default=8766)
    start_parser.add_argument("--kimi-workers", type=int, default=int(os.getenv("KIMI_WORKERS", "2")))
    start_parser.add_argument("--kimi-max-searches", type=int, default=int(os.getenv("KIMI_MAX_SEARCHES", "5")))
    start_parser.add_argument("--kimi-max-tier", default=os.getenv("KIMI_MAX_TIER", "retry"))
    start_parser.add_argument("--no-r8", action="store_true")
    start_parser.add_argument("--no-datacenters", action="store_true")
    start_parser.add_argument("--with-portal", action="store_true")
    start_parser.add_argument("--portal-prefix", default="codecollective-")
    start_parser.add_argument("--portal-network", default="codecollective")
    start_parser.add_argument("--rebuild", action="store_true")
    start_parser.set_defaults(func=start)

    stop_parser = subparsers.add_parser("stop")
    stop_parser.set_defaults(func=stop)

    status_parser = subparsers.add_parser("status")
    status_parser.set_defaults(func=status)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
