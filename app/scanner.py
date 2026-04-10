"""
Scan the local Docker environment to pre-populate the setup wizard.
All results are best-effort — nothing here is guaranteed to be correct.
"""

import re
import docker

# Networks that are never the user's reverse-proxy network
_SYSTEM_NETWORKS = {"bridge", "host", "none"}

# Image/name patterns for known services
_TRAEFIK_PATTERNS  = ("traefik/traefik", "traefik:")
_NPM_PATTERNS      = ("jc21/nginx-proxy-manager",)
_CADDY_PATTERNS    = ("caddy:", "caddy/caddy", "lucaslorentz/caddy-docker-proxy")
_AUTOKUMA_PATTERNS = ("autokuma",)
_UPTIME_KUMA_PATTERNS = ("louislam/uptime-kuma",)
_HOMEPAGE_PATTERNS = ("gethomepage/homepage",)
_HOMARR_PATTERNS   = ("homarr",)
_HEIMDALL_PATTERNS = ("linuxserver/heimdall", "lscr.io/linuxserver/heimdall")
_PORTAINER_PATTERNS = ("portainer/portainer", "portainer/portainer-ce")


def _match(haystack, patterns):
    return any(p in haystack for p in patterns)


def scan():
    """
    Return a dict describing what was detected in the Docker environment.

    Shape:
    {
        "docker_available": bool,
        "traefik": {
            "detected": bool,
            "network": str | None,
            "networks_available": [str],
            "entrypoint": str | None,
            "cert_resolver": str | None,
        },
        "npm":        {"detected": bool},
        "caddy":      {"detected": bool},
        "autokuma":   {"detected": bool},
        "uptime_kuma":{"detected": bool},
        "homepage":   {"detected": bool},
        "homarr":     {"detected": bool},
        "heimdall":   {"detected": bool},
        "portainer":  {"detected": bool},
    }
    """
    result = {
        "docker_available": False,
        "traefik": {
            "detected": False,
            "network": None,
            "networks_available": [],
            "entrypoint": None,
            "cert_resolver": None,
        },
        "npm":         {"detected": False},
        "caddy":       {"detected": False},
        "autokuma":    {"detected": False},
        "uptime_kuma": {"detected": False},
        "homepage":    {"detected": False},
        "homarr":      {"detected": False},
        "heimdall":    {"detected": False},
        "portainer":   {"detected": False},
    }

    try:
        client = docker.from_env()
        client.ping()
        result["docker_available"] = True
    except Exception:
        return result

    # Collect non-system networks as candidates for the Traefik network field
    try:
        for net in client.networks.list():
            if net.name not in _SYSTEM_NETWORKS:
                result["traefik"]["networks_available"].append(net.name)
    except Exception:
        pass

    try:
        for container in client.containers.list():
            tags = [t.lower() for t in (container.image.tags or [])]
            image_str = " ".join(tags)
            name = container.name.lower()

            # ── Traefik ──────────────────────────────────────────────────────
            if _match(image_str, _TRAEFIK_PATTERNS) or name == "traefik":
                result["traefik"]["detected"] = True

                # Network: prefer the first non-system network Traefik is on
                nets = list(container.attrs["NetworkSettings"]["Networks"].keys())
                custom = [n for n in nets if n not in _SYSTEM_NETWORKS]
                if custom:
                    result["traefik"]["network"] = custom[0]

                # Args: try to extract entrypoint and cert resolver names
                args = " ".join(container.attrs.get("Args", []))

                # Entrypoint: --entrypoints.NAME.address=:443
                m = re.search(r"--entrypoints?\.(\w+)\.address=:443", args, re.I)
                if m:
                    result["traefik"]["entrypoint"] = m.group(1)
                elif "websecure" in args:
                    result["traefik"]["entrypoint"] = "websecure"

                # Cert resolver: --certificatesresolvers.NAME.*
                m = re.search(r"--certificatesresolvers?\.(\w+)", args, re.I)
                if m:
                    result["traefik"]["cert_resolver"] = m.group(1)

            # ── Nginx Proxy Manager ───────────────────────────────────────────
            if _match(image_str, _NPM_PATTERNS) or "nginx-proxy-manager" in name:
                result["npm"]["detected"] = True

            # ── Caddy ─────────────────────────────────────────────────────────
            if _match(image_str, _CADDY_PATTERNS) or name == "caddy":
                result["caddy"]["detected"] = True

            # ── AutoKuma ─────────────────────────────────────────────────────
            if _match(image_str, _AUTOKUMA_PATTERNS) or "autokuma" in name:
                result["autokuma"]["detected"] = True

            # ── Uptime Kuma ───────────────────────────────────────────────────
            if _match(image_str, _UPTIME_KUMA_PATTERNS) or "uptime-kuma" in name:
                result["uptime_kuma"]["detected"] = True

            # ── Homepage ─────────────────────────────────────────────────────
            if _match(image_str, _HOMEPAGE_PATTERNS) or name == "homepage":
                result["homepage"]["detected"] = True

            # ── Homarr ───────────────────────────────────────────────────────
            if _match(image_str, _HOMARR_PATTERNS) or name == "homarr":
                result["homarr"]["detected"] = True

            # ── Heimdall ──────────────────────────────────────────────────────
            if _match(image_str, _HEIMDALL_PATTERNS) or name == "heimdall":
                result["heimdall"]["detected"] = True

            # ── Portainer ─────────────────────────────────────────────────────
            if _match(image_str, _PORTAINER_PATTERNS) or name in ("portainer", "portainer-ce"):
                result["portainer"]["detected"] = True

    except Exception:
        pass

    return result
