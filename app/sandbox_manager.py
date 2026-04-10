import json
import os
import random
import re
import string
import threading
import time

import docker

STATE_FILE = os.environ.get("STATE_FILE", "/data/sandboxes.json")

_client = None
_lock = threading.Lock()
_sandboxes = {}  # sid -> sandbox dict

# Image/name patterns used to locate the Traefik container
_TRAEFIK_IMG_PATTERNS = ("traefik/traefik", "traefik:")

# Env vars injected by base images that are not meaningful to promote.
_FILTER_ENV_KEYS = {
    "PATH", "HOME", "USER", "SHELL", "TERM", "HOSTNAME", "LANG", "LC_ALL",
    "LC_CTYPE", "DEBIAN_FRONTEND", "TZ", "GPG_KEY", "DOCKER",
}
_FILTER_ENV_PREFIXES = ("PYTHON_", "PYTHON", "GPG_")


def _get_client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def _random_id():
    return "".join(random.choices(string.hexdigits[:16], k=4)).lower()


def _save_state():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(_sandboxes, f)


def _find_traefik_container(client):
    """Return the running Traefik container, or None if not found."""
    try:
        for c in client.containers.list():
            tags = [t.lower() for t in (c.image.tags or [])]
            image_str = " ".join(tags)
            if any(p in image_str for p in _TRAEFIK_IMG_PATTERNS) or c.name.lower() == "traefik":
                return c
    except Exception:
        pass
    return None


def _ensure_sandbox_network(client, cfg):
    """
    Create the dedicated sandbox network if it does not exist, then connect
    the Traefik container to it so it can proxy traffic to sandbox containers.

    Sandbox containers live on this network only — they are NOT placed on the
    production reverse-proxy network, which isolates them from other homelab
    services.

    Returns the network name.
    """
    net_name = cfg["sandbox"]["network"]
    try:
        net = client.networks.get(net_name)
    except docker.errors.NotFound:
        net = client.networks.create(net_name, driver="bridge")

    # Connect Traefik so it can route to sandbox containers via this network.
    traefik = _find_traefik_container(client)
    if traefik:
        net.reload()
        connected_ids = {c.id for c in net.containers}
        if traefik.id not in connected_ids:
            try:
                net.connect(traefik)
            except Exception:
                pass  # already connected, or transient error — not fatal

    return net_name


def load_state():
    global _sandboxes
    try:
        with open(STATE_FILE) as f:
            _sandboxes = json.load(f)
    except Exception:
        _sandboxes = {}
    client = _get_client()
    stale = []
    for sid, sb in _sandboxes.items():
        try:
            client.containers.get(sb["container_name"])
        except docker.errors.NotFound:
            stale.append(sid)
    for sid in stale:
        del _sandboxes[sid]
    _save_state()


def list_sandboxes():
    now = int(time.time())
    with _lock:
        result = []
        for sb in _sandboxes.values():
            entry = dict(sb)
            entry["expires_in"] = max(0, sb["expires_at"] - now)
            result.append(entry)
    return sorted(result, key=lambda x: x["created_at"], reverse=True)


def create_sandbox(image, port, ttl_hours, cfg, environment=None):
    client = _get_client()

    # Use a dedicated, isolated sandbox network — not the production network.
    sandbox_network = _ensure_sandbox_network(client, cfg)

    cert_resolver = cfg["traefik"]["cert_resolver"]
    entrypoint = cfg["traefik"]["entrypoint"]
    domain = cfg["domains"][0]
    max_sandboxes = cfg["sandbox"]["max_sandboxes"]

    with _lock:
        if len(_sandboxes) >= max_sandboxes:
            raise ValueError(f"Maximum of {max_sandboxes} concurrent sandboxes reached.")

    raw = image.split("/")[-1].split(":")[0]
    slug = re.sub(r"[^a-z0-9]", "", raw.lower())[:12] or "sandbox"

    sid = _random_id()
    container_name = f"sandbox-{slug}-{sid}"
    fqdn = f"try-{slug}-{sid}.{domain}"
    expires_at = int(time.time()) + ttl_hours * 3600

    labels = {
        "traefik.enable": "true",
        f"traefik.http.routers.{container_name}.rule": f"Host(`{fqdn}`)",
        f"traefik.http.routers.{container_name}.entrypoints": entrypoint,
        f"traefik.http.routers.{container_name}.tls.certresolver": cert_resolver,
        "homelab-sandbox": "true",
        "homelab-sandbox-id": sid,
    }
    if port:
        labels[f"traefik.http.services.{container_name}.loadbalancer.server.port"] = str(port)

    env = {"ALLOWED_HOSTS": "*"}
    env.update(environment or {})

    run_kwargs = dict(
        name=container_name,
        detach=True,
        labels=labels,
        network=sandbox_network,
        restart_policy={"Name": "no"},
        environment=env,
    )

    # Security hardening — controlled by config
    if cfg["sandbox"]["cap_drop_all"]:
        run_kwargs["cap_drop"] = ["ALL"]

    if cfg["sandbox"]["no_new_privileges"]:
        run_kwargs["security_opt"] = ["no-new-privileges:true"]

    mem = cfg["sandbox"].get("memory_limit", "")
    if mem:
        run_kwargs["mem_limit"] = mem

    cpu = cfg["sandbox"].get("cpu_limit", 0)
    if cpu:
        run_kwargs["nano_cpus"] = int(float(cpu) * 1_000_000_000)

    client.containers.run(image, **run_kwargs)

    sb = {
        "id": sid,
        "image": image,
        "port": port,
        "container_name": container_name,
        "fqdn": fqdn,
        "url": f"https://{fqdn}",
        "created_at": int(time.time()),
        "expires_at": expires_at,
        "ttl_hours": ttl_hours,
    }
    with _lock:
        _sandboxes[sid] = sb
        _save_state()
    return sb


def destroy_sandbox(sid):
    client = _get_client()
    with _lock:
        sb = _sandboxes.get(sid)
        if not sb:
            return False
        try:
            c = client.containers.get(sb["container_name"])
            c.stop(timeout=5)
            c.remove()
        except docker.errors.NotFound:
            pass
        del _sandboxes[sid]
        _save_state()
    return True


def get_sandbox(sid):
    with _lock:
        sb = _sandboxes.get(sid)
        if not sb:
            return None
        now = int(time.time())
        entry = dict(sb)
        entry["expires_in"] = max(0, sb["expires_at"] - now)
        return entry


def get_promote_data(sid):
    """Return structured data for pre-filling the New Service editor."""
    with _lock:
        sb = _sandboxes.get(sid)
        if not sb:
            return None
        sb = dict(sb)

    # Inspect running container for meaningful env vars
    client = _get_client()
    env_dict = {}
    try:
        c = client.containers.get(sb["container_name"])
        for entry in (c.attrs.get("Config", {}).get("Env") or []):
            if "=" not in entry:
                continue
            k, _, v = entry.partition("=")
            if k in _FILTER_ENV_KEYS:
                continue
            if any(k.startswith(p) for p in _FILTER_ENV_PREFIXES):
                continue
            env_dict[k] = v
    except docker.errors.NotFound:
        pass

    # Derive a slug-safe name suggestion from the image
    raw = sb["image"].split("/")[-1].split(":")[0]
    name_suggestion = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")[:40]

    return {
        "image": sb["image"],
        "name": name_suggestion,
        "port": sb["port"],
        "environment": env_dict,
        "fqdn": sb["fqdn"],
    }


def cleanup_expired():
    now = int(time.time())
    with _lock:
        expired = [sid for sid, sb in _sandboxes.items() if sb["expires_at"] <= now]
    for sid in expired:
        destroy_sandbox(sid)


def start_cleanup_thread():
    def _loop():
        while True:
            time.sleep(60)
            try:
                cleanup_expired()
            except Exception:
                pass
    threading.Thread(target=_loop, daemon=True).start()
