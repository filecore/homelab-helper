import os
import yaml

DEFAULTS = {
    "homelab": {"name": "My Homelab"},
    "traefik": {
        "network": "reverse-proxy",
        "cert_resolver": "letsencrypt",
        "entrypoint": "websecure",
        "auth_middleware": "",
    },
    "domains": ["example.com"],
    "autokuma": {"enabled": False},
    "homepage": {"enabled": False, "groups": []},
}


def load_config():
    path = os.environ.get("CONFIG_PATH", "/config/config.yaml")
    try:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    except Exception:
        raw = {}

    cfg = {}

    # homelab
    hl = raw.get("homelab", {})
    cfg["homelab"] = {
        "name": hl.get("name", DEFAULTS["homelab"]["name"]),
    }

    # traefik
    tr = raw.get("traefik", {})
    dtr = DEFAULTS["traefik"]
    cfg["traefik"] = {
        "network": tr.get("network", dtr["network"]),
        "cert_resolver": tr.get("cert_resolver", dtr["cert_resolver"]),
        "entrypoint": tr.get("entrypoint", dtr["entrypoint"]),
        "auth_middleware": tr.get("auth_middleware", dtr["auth_middleware"]),
    }

    # domains
    domains = raw.get("domains", DEFAULTS["domains"])
    cfg["domains"] = domains if isinstance(domains, list) and domains else DEFAULTS["domains"]

    # autokuma
    ak = raw.get("autokuma", {})
    cfg["autokuma"] = {
        "enabled": bool(ak.get("enabled", DEFAULTS["autokuma"]["enabled"])),
    }

    # homepage
    hp = raw.get("homepage", {})
    cfg["homepage"] = {
        "enabled": bool(hp.get("enabled", DEFAULTS["homepage"]["enabled"])),
        "groups": hp.get("groups", DEFAULTS["homepage"]["groups"]) or [],
    }

    return cfg
