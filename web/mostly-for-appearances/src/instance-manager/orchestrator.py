import hashlib
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from kr8s.objects import Namespace, Secret, object_from_spec

logger = logging.getLogger(__name__)

PHONE_DOMAIN = os.environ.get("PHONE_DOMAIN", "sip.tangerine.example")
RESERVATION_TTL = timedelta(hours=int(os.environ.get("RESERVED_TTL", "1")))
DEPLOYMENT_TTL = timedelta(hours=int(os.environ.get("DEPLOYED_TTL", "8")))

MANIFEST_DIR = Path(__file__).parent / "phone-manifests"
NS_MANIFEST = "namespace.yaml"
INSTANCE_MANIFEST = "phone.manifest.yaml"

MANAGER_LABEL = "managed-by"
MANAGER_NAME = "instance-manager"
DEPLOYED_AT_ANNO = "instance-manager/deployed"
EXPIRES_AT_ANNO = "instance-manager/expires-at"

# secrets to replicate to other namespaces
PULL_SECRET_NAME = "rcds-web-mostly-for-appearances-pull"
TLS_SECRET_NAME = "tangerine-wildcard-tls"
SECRETS_TO_COPY = [PULL_SECRET_NAME, TLS_SECRET_NAME]
CURRENT_NS = "rcds-web-mostly-for-appearances"


manifest_template_env = Environment(
    loader=FileSystemLoader(MANIFEST_DIR),
    keep_trailing_newline=True,
)


def ns_name_for(ext: str) -> str:
    """Return the namespace name for a given extension."""
    return f"phone-{ext}"


def ui_domain_for(ext: str) -> str:
    """Build the full ingress domain for the given extension."""
    hash = hashlib.sha256(ext.encode()).hexdigest()[:10]
    return f"phone-{hash}.{PHONE_DOMAIN}"


def get_managed_namespaces() -> list[Namespace]:
    return list(
        Namespace.list(
            label_selector={MANAGER_LABEL: MANAGER_NAME},
        )
    )  # type: ignore


def get_namespace_for(ext: str) -> Namespace | None:
    """Get the namespace for a given extension, or None if it doesn't exist."""
    try:
        return Namespace.get(name=ns_name_for(ext))
    except Exception:
        return None


def create_namespace(ext: str, ttl: timedelta) -> Namespace:
    """Create a namespace for the given extension by rendering the namespace
    manifest template and applying it to the cluster."""
    now = datetime.now(timezone.utc)
    template = manifest_template_env.get_template(NS_MANIFEST)
    rendered = template.render(
        ext=ext,
        reserved=now.isoformat(),
        expires=(now + ttl).isoformat(),
        managed_anno=MANAGER_LABEL,
        managed_by=MANAGER_NAME,
    )
    doc = yaml.safe_load(rendered)
    ns = Namespace(doc)
    ns.create()
    return ns


def cleanup_expired() -> None:
    """Remove expired namespaces and all their contents."""
    now = datetime.now(timezone.utc)
    for ns in get_managed_namespaces():
        annotations = ns.annotations or {}
        expires_str = annotations.get(EXPIRES_AT_ANNO)
        if not expires_str:
            continue
        try:
            expires_at = datetime.fromisoformat(expires_str)
        except ValueError:
            logger.warning(f"Invalid expires-at annotation on {ns.name}: {expires_str}")
            continue
        if now > expires_at:
            logger.info(f"Namespace {ns.name} has expired, deleting")
            try:
                ns.delete()
            except Exception:
                logger.exception(f"Error deleting namespace {ns.name}")


def ext_info(ext: str) -> dict:
    """Return phone site and caller API URLs for a given extension."""
    return {
        "phone_ui": f"https://{ui_domain_for(ext)}",
        "trigger_service": f"http://call-triggerer.{ns_name_for(ext)}:8000",
    }


def reserve_extension() -> str:
    """Reserve a new random extension by creating a namespace for it.

    Returns the extension string.
    Raises RuntimeError if no unique extension could be generated.
    Raises Exception if the namespace creation fails.
    """
    try:
        existing = {
            (ns.labels or {}).get("ext") or ns.name.removeprefix("phone-")
            for ns in get_managed_namespaces()
        }
    except Exception:
        logger.exception("Failed to list existing namespaces")
        existing = set()

    for _ in range(100):
        ext = str(random.randint(10000, 99999))
        if ext not in existing:
            create_namespace(ext, RESERVATION_TTL)
            logger.info(f"Reserved extension {ext}")
            return ext

    raise RuntimeError("No available extensions")


def deploy_extension(ext: str) -> dict:
    """Deploy infrastructure for an extension.

    Handles namespace creation if the extension was not previously reserved.
    Returns the extension info dict on success.

    Raises ValueError if the extension is already deployed.
    Raises Exception on k8s failures.
    """
    ns = get_namespace_for(ext)

    # Already deployed
    if ns is not None:
        annotations = ns.annotations or {}
        if annotations.get(DEPLOYED_AT_ANNO) == "true":
            raise ValueError("already deployed")

    # Not reserved — warn but create namespace anyway
    if ns is None:
        logger.warning(f"Extension {ext} was not reserved, deploying anyway")
        ns = create_namespace(ext, DEPLOYMENT_TTL)

    # Deploy the actual workload resources
    logger.info(f"Deploying Kubernetes resources for extension {ext}")

    # Copy over image pull secret / wildcard tls
    for secret in SECRETS_TO_COPY:
        raw = Secret.get(secret, namespace=CURRENT_NS).raw_template
        raw.metadata.namespace = ns.name
        Secret(raw).create()

    template = manifest_template_env.get_template(INSTANCE_MANIFEST)
    rendered = template.render(
        extension=ext,
        domain=ui_domain_for(ext),
        pull_secret=PULL_SECRET_NAME,
        tls_secret=TLS_SECRET_NAME,
    )

    instance_manifest = [doc for doc in yaml.safe_load_all(rendered) if doc]

    for doc in instance_manifest:
        doc.setdefault("metadata", {})["namespace"] = ns.name
        resource = object_from_spec(doc)
        resource.create()

    # Mark as deployed and extend the TTL
    now = datetime.now(timezone.utc)
    ns.annotate(
        {
            DEPLOYED_AT_ANNO: "true",
            EXPIRES_AT_ANNO: (now + DEPLOYMENT_TTL).isoformat(),
        }
    )

    return ext_info(ext)


def get_extension_info(ext: str) -> dict | None:
    """Look up a deployed extension and return its info, or None if not found/deployed."""
    ns = get_namespace_for(ext)
    if ns is None:
        return None

    annotations = ns.annotations or {}
    if annotations.get(DEPLOYED_AT_ANNO) != "true":
        return None

    return ext_info(ext)
