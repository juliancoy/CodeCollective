#!/usr/bin/env python3
"""Run the Code Collective local stack in Docker.

This is the top-level runner for local development. It does not use Docker
Compose. Containers read live source from bind mounts.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
import os
import sys
import time
import urllib.error
import urllib.request
import ssl
from pathlib import Path


root = Path(os.path.abspath(os.path.dirname(__file__)))
portal_dir = Path(os.environ.get("ORGPORTAL_DIR", root.parent / "OrgPortal")).resolve()
sys.path.append(str(portal_dir))



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
    import docker_utils

    images = docker_utils.DOCKER_CLIENT.images.list(name=DATACENTERS_IMAGE)
    if not force_rebuild:
        for image in images:
            if f"{DATACENTERS_IMAGE}:latest" in image.tags:
                return
    print("Building datacenters helper image from datacenters/Dockerfile.kimi...")
    docker_utils.DOCKER_CLIENT.images.build(
        path=str(root / "datacenters"),
        dockerfile="Dockerfile.kimi",
        tag=DATACENTERS_IMAGE,
        forcerm=True,
    )


def remove_container(name: str) -> None:
    import docker_utils

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
    import docker_utils

    name = PREFIX + "website"
    remove_container(name)
    site = shared_python_container(name)
    site["command"] = [
        "python3",
        "run.py",
        "serve",
        "--site-port",
        str(port),
    ]
    docker_utils.run_container(site)
    wait_for_http(f"http://127.0.0.1:{port}/projects.html", "main local site")
    wait_for_http(f"http://127.0.0.1:{port}/api/jobs/meta", "local USAJOBS data")


class LocalSiteHandler(SimpleHTTPRequestHandler):
    """Serve the site and USAJOBS API entirely from the mounted local files."""

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(directory or root), **kwargs)

    def local_object(self, key):
        folder = (Path(self.directory) / 'usa/data/publish').resolve()
        path = (folder / key).resolve()
        if not path.is_relative_to(folder):
            raise ValueError('Invalid dataset path')
        return path

    def jobs_response(self, path, query):
        if path == '/api/jobs/versions':
            latest = json.loads(self.local_object('jobs/latest.json').read_text())['version']
            versions = []
            for file in sorted(self.local_object('jobs').glob('v*/manifest.json'), reverse=True):
                version = file.parent.name
                if not re.fullmatch(r'v[0-9]{8}T[0-9]{6}Z', version):
                    continue
                manifest = json.loads(self.local_object(f'jobs/{version}/manifest.json').read_text())
                versions.append({key: manifest[key] for key in
                                 ('version', 'source_fetched_at', 'source_record_count')})
            body = json.dumps({'latest': latest, 'versions': versions}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return io.BytesIO(body)
        version = query.get('version', [''])[0]
        if not version:
            version = json.loads(self.local_object('jobs/latest.json').read_text())['version']
        if not re.fullmatch(r'v[0-9]{8}T[0-9]{6}Z', version):
            raise ValueError('Invalid jobs version')
        manifest_key = f'jobs/{version}/manifest.json'
        manifest = json.loads(self.local_object(manifest_key).read_text())
        if path == '/api/jobs/meta':
            body = json.dumps({**manifest, 'manifest_key': manifest_key}).encode()
            stream, size, compressed = io.BytesIO(body), len(body), False
        else:
            page = int(query.get('page', ['1'])[0])
            if page < 1:
                raise ValueError('Invalid page')
            state = query.get('state', ['ALL'])[0].upper()
            entry = manifest['states'].get(state)
            if not entry:
                raise FileNotFoundError('State not found')
            shard = next((item for item in entry['shards'] if item['page'] == page), None)
            if not shard:
                raise FileNotFoundError('Page not found')
            file = self.local_object(shard['key'])
            size, compressed = file.stat().st_size, True
            stream = file.open('rb')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        if compressed:
            self.send_header('Content-Encoding', 'gzip')
        self.end_headers()
        return stream

    def send_head(self):
        url = urlsplit(self.path)
        if url.path in ('/api/jobs/meta', '/api/jobs', '/api/jobs/versions'):
            try:
                return self.jobs_response(url.path, parse_qs(url.query))
            except (json.JSONDecodeError, KeyError):
                self.send_error(503, 'Local USAJOBS dataset is invalid')
            except ValueError:
                self.send_error(400, 'Invalid jobs query')
            except FileNotFoundError:
                self.send_error(404, 'Local USAJOBS data not found')
            return None
        path = Path(self.translate_path(self.path)).resolve()
        relative = Path(unquote(url.path))
        if (not path.is_relative_to(Path(self.directory).resolve())
                or any(part.startswith('.') for part in relative.parts)
                or path.suffix.lower() in {'.pem', '.key', '.db', '.sqlite', '.sqlite3'}):
            self.send_error(404)
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)
        return None


def serve(args):
    print(f'Local site and USAJOBS API: http://127.0.0.1:{args.site_port}/usa/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.site_port), LocalSiteHandler).serve_forever()


def start_r8(port: int) -> None:
    import docker_utils

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
    import docker_utils

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
            f"{WORKSPACE}/.env.kimi",
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
        f"{WORKSPACE}/.env.kimi",
    ]
    docker_utils.run_container(dashboard)
    wait_for_http(f"http://127.0.0.1:{args.kimi_dashboard_port}/", "datacenter dashboard")


def start_portal(prefix: str, network_name: str) -> None:
    portal_run_path = portal_dir / "run.py"
    spec = importlib.util.spec_from_file_location("codecollective_portal_run", portal_run_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {portal_run_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.pidp_dir = (root.parent / "pidp").resolve()
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
    print(f"USAJOBS visualizer:     http://127.0.0.1:{args.site_port}/usa/")
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
        PREFIX + "website",
        PREFIX + "r8-rowhome",
        PREFIX + "datacenters-research",
        PREFIX + "datacenters-dashboard",
        "codecollective-datacenters-site",
        "codecollective-datacenters-research",
        "codecollective-datacenters-dashboard",
    ):
        remove_container(name)


def status(_args: argparse.Namespace) -> None:
    import docker_utils

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

    serve_parser = subparsers.add_parser("serve", help="Serve local files and the local USAJOBS API")
    serve_parser.add_argument("--site-port", type=int, default=8877)
    serve_parser.set_defaults(func=serve)

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
