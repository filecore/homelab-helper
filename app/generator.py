import re
import yaml


def slugify(name):
    """Lowercase, replace spaces/underscores with hyphens, strip non-alphanum-hyphens."""
    s = name.lower().strip()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = s.strip("-")
    return s


def validate_input(data):
    errors = []
    name = data.get("name", "").strip()
    if not name:
        errors.append("Service name is required.")
    elif slugify(name) != name:
        errors.append(
            f"Service name must be lowercase with hyphens only (e.g. '{slugify(name)}')."
        )

    image = data.get("image", "").strip()
    if not image:
        errors.append("Docker image is required.")

    domain = data.get("domain", "").strip()
    if not domain:
        errors.append("Domain is required.")

    port = data.get("port", "")
    if port not in ("", None):
        try:
            p = int(port)
            if not (1 <= p <= 65535):
                errors.append("Port must be between 1 and 65535.")
        except (ValueError, TypeError):
            errors.append("Port must be a number.")

    return errors


def _build_subdomain(data):
    override = data.get("subdomain_override", "").strip()
    return override if override else data.get("name", "").strip()


def _build_middleware_string(data, cfg):
    parts = []
    auth_mw = cfg["traefik"].get("auth_middleware", "")
    if data.get("auth") and auth_mw:
        parts.append(auth_mw)
    extras = data.get("extra_middlewares", "").strip()
    if extras:
        for m in extras.split(","):
            m = m.strip()
            if m:
                parts.append(m)
    return ",".join(parts)


def generate_compose(data, cfg):
    name = data["name"].strip()
    image = data.get("image", "").strip()
    port = data.get("port", "")
    domain = data.get("domain", "").strip()
    subdomain = _build_subdomain(data)
    network = cfg["traefik"]["network"]
    entrypoint = cfg["traefik"]["entrypoint"]
    cert_resolver = cfg["traefik"]["cert_resolver"]
    middleware_str = _build_middleware_string(data, cfg)

    labels = [
        "traefik.enable=true",
        f"traefik.http.routers.{name}.rule=Host(`{subdomain}.{domain}`)",
        f"traefik.http.routers.{name}.entrypoints={entrypoint}",
        f"traefik.http.routers.{name}.tls.certresolver={cert_resolver}",
    ]

    if middleware_str:
        labels.append(f"traefik.http.routers.{name}.middlewares={middleware_str}")

    if port not in ("", None):
        labels.append(
            f"traefik.http.services.{name}.loadbalancer.server.port={port}"
        )

    # AutoKuma labels
    if cfg["autokuma"]["enabled"] and data.get("kuma_enabled"):
        kuma_url = data.get("kuma_url", "").strip() or f"https://{subdomain}.{domain}"
        kuma_type = data.get("kuma_type", "https")
        kuma_interval = data.get("kuma_interval", 60)
        kuma_display = data.get("kuma_display_name", name)
        kuma_group = data.get("kuma_group", "").strip()

        labels.append(f"kuma.{name}.monitor.type={kuma_type}")
        labels.append(f"kuma.{name}.monitor.name={kuma_display}")
        labels.append(f"kuma.{name}.monitor.url={kuma_url}")
        labels.append(f"kuma.{name}.monitor.interval={kuma_interval}")
        if kuma_group:
            labels.append(f"kuma.{name}.monitor.parent_name={kuma_group}")

    # Build the compose dict using plain dicts so we control YAML output exactly
    service = {
        "image": image,
        "container_name": name,
        "restart": "unless-stopped",
        "networks": [network],
        "labels": [f'"{lbl}"' for lbl in labels],
    }

    # yaml.dump produces labels as a list of quoted strings, but we want
    # the block to look clean. Build the YAML manually for the labels section
    # to avoid yaml.dump's quoting choices, then assemble the full snippet.
    lines = []
    lines.append("services:")
    lines.append(f"  {name}:")
    lines.append(f"    image: {image}")
    lines.append(f"    container_name: {name}")
    lines.append("    restart: unless-stopped")
    lines.append("    networks:")
    lines.append(f"      - {network}")
    lines.append("    labels:")
    for lbl in labels:
        lines.append(f'      - "{lbl}"')
    lines.append("")
    lines.append("networks:")
    lines.append(f"  {network}:")
    lines.append("    external: true")

    return "\n".join(lines)


def generate_homepage(data, cfg):
    if not cfg["homepage"]["enabled"] or not data.get("homepage_enabled"):
        return ""

    domain = data.get("domain", "").strip()
    subdomain = _build_subdomain(data)
    display_name = data.get("homepage_display_name", "").strip() or data["name"].title()
    description = data.get("homepage_description", "").strip()
    group = data.get("homepage_group", "").strip() or "Services"
    icon = data.get("homepage_icon", "").strip()
    widget = data.get("homepage_widget", False)

    lines = [
        f"# Paste into your homepage services.yaml",
        f"- {group}:",
        f"  - {display_name}:",
        f"      href: https://{subdomain}.{domain}",
    ]
    if description:
        lines.append(f"      description: {description}")
    if icon:
        lines.append(f"      icon: {icon}")
    if widget:
        lines.append("      widget:")
        lines.append("        type: # TODO: set widget type")
        lines.append(f"        url: https://{subdomain}.{domain}")

    return "\n".join(lines)


def build_checklist(data, cfg):
    name = data.get("name", "").strip()
    domain = data.get("domain", "").strip()
    subdomain = _build_subdomain(data)
    network = cfg["traefik"]["network"]
    items = []

    items.append(f"Create the service directory on your host: mkdir -p ~/docker/{name}")
    items.append(f"Copy the compose snippet into ~/docker/{name}/docker-compose.yml")
    items.append(
        f"Ensure the Docker network exists: docker network create {network} (safe to run if it already exists)"
    )
    items.append(f"Start the service: cd ~/docker/{name} && docker compose up -d")
    items.append(
        f"Verify Traefik picked it up: check the Traefik dashboard or run "
        f"docker logs traefik | grep {name}"
    )
    items.append(
        f"Test the URL: https://{subdomain}.{domain}"
    )

    if cfg["homepage"]["enabled"] and data.get("homepage_enabled"):
        items.append(
            "Paste the Homepage YAML into your homepage services.yaml (hot-reloads automatically)"
        )

    if cfg["autokuma"]["enabled"] and data.get("kuma_enabled"):
        items.append(
            "AutoKuma will create the Uptime Kuma monitor automatically once the container starts -- "
            "verify it appears in Uptime Kuma within ~30 seconds"
        )
    else:
        items.append("Add an Uptime Kuma monitor manually for this service")

    items.append("Update your homelab wiki / documentation for this service")

    return items
