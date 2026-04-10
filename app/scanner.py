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
_AUTOKUMA_PATTERNS = ("autokuma",)
_HOMEPAGE_PATTERNS = ("gethomepage/homepage",)


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
            "network": str | None,        # best-guess reverse-proxy network
            "networks_available": [str],  # all non-system networks (dropdown hints)
            "entrypoint": str | None,
            "cert_resolver": str | None,
        },
        "autokuma": {"detected": bool},
        "homepage":  {"detected": bool},
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
        "autokuma": {"detected": False},
        "homepage":  {"detected": False},
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

            # ── AutoKuma ─────────────────────────────────────────────────────
            if _match(image_str, _AUTOKUMA_PATTERNS) or "autokuma" in name:
                result["autokuma"]["detected"] = True

            # ── Homepage ─────────────────────────────────────────────────────
            if _match(image_str, _HOMEPAGE_PATTERNS) or name == "homepage":
                result["homepage"]["detected"] = True

    except Exception:
        pass

    return result
