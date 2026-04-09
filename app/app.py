import json
from flask import Flask, render_template, jsonify, request
from config_loader import load_config
from generator import validate_input, generate_compose, generate_homepage, build_checklist

app = Flask(__name__)


def get_config():
    return load_config()


@app.route("/")
def index():
    cfg = get_config()
    return render_template(
        "index.html",
        config_json=json.dumps(cfg),
        homelab_name=cfg["homelab"]["name"],
    )


@app.route("/api/config")
def api_config():
    return jsonify(get_config())


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True) or {}
    cfg = get_config()

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
    app.run(host="0.0.0.0", port=7842, debug=False)
