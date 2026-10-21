import os
from pathlib import Path
import sys

here = Path(os.path.abspath(os.path.dirname(__file__)))
root = here.parent
sys.path.append(str(root))

import docker_utils
import editme


def ensure_ballot_backend_image() -> None:
    images = docker_utils.DOCKER_CLIENT.images.list(name="org-backend")
    for image in images:
        if "org-backend" in image.tags:
            return
    print("Building org-backend image from org-backend/Dockerfile...")
    docker_utils.DOCKER_CLIENT.images.build(
        path=str(here),
        tag="org-backend",
    )


def run(network_name: str = "BALLOT", prefix: str = "") -> None:
    ensure_ballot_backend_image()
    backend = dict(
        image="org-backend",
        name=prefix + "org-backend",
        detach=True,
        network=network_name,
        restart_policy={"Name": "always"},
        volumes={
            str(here): {"bind": "/app", "mode": "rw"},
        },
        environment={
            "REDIS_HOST": f"{prefix}redis",
            "REDIS_PORT": "6379",
            "PIDP_JWKS_URL": "http://pidp:8000/.well-known/jwks.json",
            "PIDP_BASE_URL": "http://pidp:8000",
            "PIDP_JWT_ISSUER": os.getenv("PIDP_JWT_ISSUER"),
            "PIDP_JWT_AUDIENCE": os.getenv("PIDP_JWT_AUDIENCE"),
            "COCKROACH_DB_URL": (
                f"cockroachdb+psycopg2://{editme.COCKROACH_USER}@{prefix}cockroach:"
                f"{editme.COCKROACH_SQL_PORT}/{editme.COCKROACH_DB}"
                f"?sslmode={'disable' if editme.COCKROACH_INSECURE else 'require'}"
            ),
            "COCKROACH_ASYNC_URL": (
                f"postgresql://{editme.COCKROACH_USER}@{prefix}cockroach:"
                f"{editme.COCKROACH_SQL_PORT}/{editme.COCKROACH_DB}"
                f"?sslmode={'disable' if editme.COCKROACH_INSECURE else 'require'}"
            ),
            "SPICEDB_HTTP_URL": "http://spicedb:8443",
            "SPICEDB_PRESHARED_KEY": editme.SPICEDB_PRESHARED_KEY,
            "ORG_ADMIN_USER_IDS": os.getenv("ORG_ADMIN_USER_IDS", ""),
            # Native notifications avoid repeatedly scanning Linux bind mounts.
            "WATCHFILES_FORCE_POLLING": os.getenv("WATCHFILES_FORCE_POLLING", "false"),
            "MODERATOR_EMAILS": os.getenv("MODERATOR_EMAILS", "julian2@julian2.edu"),
        },
    )
    docker_utils.run_container(backend)
