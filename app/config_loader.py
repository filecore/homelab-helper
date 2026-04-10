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
    "sandbox": {
        "default_ttl_hours": 4,
        "max_sandboxes": 10,
        "ttl_options": [1, 4, 8, 24],
    },
    "security": {"suppress_auth_warning": False},
}


def load_config():
    path = os.environ.get("CONFIG_PATH", "/config/config.yaml")
    try:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    except Exception:
        raw = {}

    cfg = {}

    hl = raw.get("homelab", {})
    cfg["homelab"] = {"name": hl.get("name", DEFAULTS["homelab"]["name"])}

    tr = raw.get("traefik", {})
    dtr = DEFAULTS["traefik"]
    cfg["traefik"] = {
        "network": tr.get("network", dtr["network"]),
        "cert_resolver": tr.get("cert_resolver", dtr["cert_resolver"]),
        "entrypoint": tr.get("entrypoint", dtr["entrypoint"]),
        "auth_middleware": tr.get("auth_middleware", dtr["auth_middleware"]),
    }

    domains = raw.get("domains", DEFAULTS["domains"])
    cfg["domains"] = domains if isinstance(domains, list) and domains else DEFAULTS["domains"]

    ak = raw.get("autokuma", {})
    cfg["autokuma"] = {"enabled": bool(ak.get("enabled", DEFAULTS["autokuma"]["enabled"]))}

    hp = raw.get("homepage", {})
    cfg["homepage"] = {
        "enabled": bool(hp.get("enabled", DEFAULTS["homepage"]["enabled"])),
        "groups": hp.get("groups", DEFAULTS["homepage"]["groups"]) or [],
    }

    sb = raw.get("sandbox", {})
    dsb = DEFAULTS["sandbox"]
    ttl_options = sb.get("ttl_options", dsb["ttl_options"])
    if not isinstance(ttl_options, list) or not ttl_options:
        ttl_options = dsb["ttl_options"]
    cfg["sandbox"] = {
        "default_ttl_hours": int(sb.get("default_ttl_hours", dsb["default_ttl_hours"])),
        "max_sandboxes": int(sb.get("max_sandboxes", dsb["max_sandboxes"])),
        "ttl_options": ttl_options,
    }

    sec = raw.get("security", {})
    cfg["security"] = {
        "suppress_auth_warning": bool(sec.get("suppress_auth_warning", DEFAULTS["security"]["suppress_auth_warning"])),
    }

    return cfg
