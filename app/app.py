import json
import os
import yaml
from flask import Flask, render_template, jsonify, request
from config_loader import load_config
from generator import validate_input, generate_compose, generate_homepage, build_checklist
import sandbox_manager as sm
import scanner

app = Flask(__name__)

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.yaml")


@app.route("/")
def index():
    if not os.path.exists(CONFIG_PATH):
        scan_result = scanner.scan()
        return render_template("wizard.html", scan_json=json.dumps(scan_result))
    cfg = load_config()
    auth_warning = not cfg["security"]["suppress_auth_warning"]
    return render_template(
        "index.html",
        config_json=json.dumps(cfg),
        homelab_name=cfg["homelab"]["name"],
        primary_domain=cfg["domains"][0],
        auth_warning=auth_warning,
    )


@app.route("/api/config")
def api_config():
    return jsonify(load_config())


@app.route("/api/scan")
def api_scan():
    return jsonify(scanner.scan())


@app.route("/api/setup", methods=["POST"])
def api_setup():
    if os.path.exists(CONFIG_PATH):
        return jsonify({"error": "Config already exists. Delete it to re-run the wizard."}), 409

    data = request.get_json(force=True) or {}

    homelab_name = (data.get("homelab_name") or "My Homelab").strip()
    domains_raw = data.get("domains") or []
    if isinstance(domains_raw, str):
        domains_raw = [d.strip() for d in domains_raw.split(",") if d.strip()]
    domains = [d.strip() for d in domains_raw if str(d).strip()]
    if not domains:
        domains = ["example.com"]

    traefik_network = (data.get("traefik_network") or "reverse-proxy").strip()
    traefik_entrypoint = (data.get("traefik_entrypoint") or "websecure").strip()
    traefik_cert_resolver = (data.get("traefik_cert_resolver") or "letsencrypt").strip()
    auth_middleware = (data.get("auth_middleware") or "").strip()

    autokuma_enabled = bool(data.get("autokuma_enabled", False))
    homepage_enabled = bool(data.get("homepage_enabled", False))
    homepage_groups = data.get("homepage_groups") or []
    if isinstance(homepage_groups, str):
        homepage_groups = [g.strip() for g in homepage_groups.split(",") if g.strip()]

    cfg = {
        "homelab": {"name": homelab_name},
        "traefik": {
            "network": traefik_network,
            "entrypoint": traefik_entrypoint,
            "cert_resolver": traefik_cert_resolver,
        },
        "domains": domains,
        "autokuma": {"enabled": autokuma_enabled},
        "homepage": {
            "enabled": homepage_enabled,
            "groups": homepage_groups,
        },
        "sandbox": {
            "default_ttl_hours": 4,
            "max_sandboxes": 10,
            "ttl_options": [1, 4, 8, 24],
        },
        "security": {"suppress_auth_warning": False},
    }
    if auth_middleware:
        cfg["traefik"]["auth_middleware"] = auth_middleware

    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        return jsonify({"error": f"Failed to write config: {e}"}), 500

    return jsonify({"ok": True})


# ── Sandbox routes ─────────────────────────────────────────────────────────────

@app.route("/api/sandboxes")
def api_list():
    return jsonify(sm.list_sandboxes())


@app.route("/api/sandboxes", methods=["POST"])
def api_create():
    data = request.get_json(force=True) or {}
    cfg = load_config()

    image = data.get("image", "").strip()
    if not image:
        return jsonify({"error": "Image is required."}), 400

    port_raw = data.get("port", "")
    port = None
    if port_raw not in ("", None):
        try:
            port = int(port_raw)
            if not (1 <= port <= 65535):
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "Port must be a number between 1 and 65535."}), 400

    ttl_options = cfg["sandbox"]["ttl_options"]
    try:
        ttl_hours = int(data.get("ttl_hours", cfg["sandbox"]["default_ttl_hours"]))
    except (ValueError, TypeError):
        ttl_hours = cfg["sandbox"]["default_ttl_hours"]
    if ttl_hours not in ttl_options:
        ttl_hours = ttl_options[0]

    environment = data.get("environment") or {}
    if not isinstance(environment, dict):
        return jsonify({"error": "environment must be a key/value object."}), 400

    try:
        sb = sm.create_sandbox(image=image, port=port, ttl_hours=ttl_hours, cfg=cfg, environment=environment)
        return jsonify(sb), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to start container: {e}"}), 500


@app.route("/api/sandboxes/<sid>", methods=["DELETE"])
def api_destroy(sid):
    ok = sm.destroy_sandbox(sid)
    if not ok:
        return jsonify({"error": "Sandbox not found."}), 404
    return jsonify({"ok": True})


@app.route("/api/sandboxes/<sid>/promote")
def api_promote(sid):
    data = sm.get_promote_data(sid)
    if not data:
        return jsonify({"error": "Sandbox not found."}), 404
    return jsonify(data)


# ── Generator routes ───────────────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True) or {}
    cfg = load_config()

    errors = validate_input(data)
    if errors:
        return jsonify({"compose": "", "homepage": "", "checklist": [], "errors": errors})

    compose = generate_compose(data, cfg)
    homepage = generate_homepage(data, cfg)
    checklist = build_checklist(data, cfg)

    return jsonify({
        "compose": compose,
        "homepage": homepage,
        "checklist": checklist,
        "errors": [],
    })


if __name__ == "__main__":
    sm.load_state()
    sm.start_cleanup_thread()
    app.run(host="0.0.0.0", port=7842, debug=False)
