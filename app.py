"""
Flask web app for the shake-flask kLa estimator.

Routes
------
GET  /                shareable, server-rendered calculator page. All inputs
                       can be pre-filled via query string, e.g.
                       /?flask_type=baffled&size=500&vol=50&rpm=250&orbit=1&factor=2.2
POST /api/calculate    JSON API used by the page's own JavaScript for live
                       recompute (single condition, and each Scenario Table
                       row) without a full page reload. Also usable directly,
                       e.g. from a script or another tool.
GET  /healthz          plain-text health check for Render.
"""
from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from kla import (
    FLASK_TYPES,
    GENERIC_DIAMETER_CM,
    InputError,
    ORBIT_CHOICES_IN,
    STANDARD_SIZES_ML,
    compute_kla,
)

app = Flask(__name__)

DEFAULTS = dict(
    flask_type="unbaffled",
    size=500,
    custom_dia="",
    vol=50.0,
    rpm=250.0,
    orbit=1,
    temp=37.0,
    factor=1.00,
)


def _parse_float(value, default):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int_or_none(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _inputs_from_source(source) -> dict:
    """Build a plain-dict of calculator inputs from a Flask request.args /
    request.form / request.get_json() -like mapping, filling in defaults."""
    flask_type = source.get("flask_type", DEFAULTS["flask_type"])
    if flask_type not in FLASK_TYPES:
        flask_type = DEFAULTS["flask_type"]

    size_raw = source.get("size", DEFAULTS["size"])
    size = _parse_int_or_none(size_raw) if size_raw != "custom" else None

    custom_dia_raw = source.get("custom_dia", DEFAULTS["custom_dia"])
    custom_dia = _parse_float(custom_dia_raw, None) if custom_dia_raw not in (None, "") else None

    orbit = _parse_float(source.get("orbit", DEFAULTS["orbit"]), DEFAULTS["orbit"])
    if orbit not in ORBIT_CHOICES_IN:
        # allow custom orbit values too (not only 1"/2") — the UI defaults
        # to the two literature-validated choices but nothing stops a user
        # entering another value; validity flags will simply reflect it.
        pass

    return dict(
        flask_type=flask_type,
        flask_size_ml=size,
        custom_diameter_cm=custom_dia,
        working_volume_ml=_parse_float(source.get("vol", DEFAULTS["vol"]), DEFAULTS["vol"]),
        rpm=_parse_float(source.get("rpm", DEFAULTS["rpm"]), DEFAULTS["rpm"]),
        orbit_in=orbit,
        temperature_c=_parse_float(source.get("temp", DEFAULTS["temp"]), DEFAULTS["temp"]),
        baffle_factor=_parse_float(source.get("factor", DEFAULTS["factor"]), DEFAULTS["factor"]),
    )


@app.get("/")
def index():
    inputs = _inputs_from_source(request.args)
    error = None
    result = None
    try:
        result = compute_kla(**inputs)
    except InputError as exc:
        error = str(exc)

    return render_template(
        "index.html",
        inputs=inputs,
        result=result,
        error=error,
        standard_sizes=STANDARD_SIZES_ML,
        generic_diameters=GENERIC_DIAMETER_CM,
        orbit_choices=ORBIT_CHOICES_IN,
        raw_query=request.query_string.decode(),
    )


@app.post("/api/calculate")
def api_calculate():
    payload = request.get_json(silent=True) or request.form
    inputs = _inputs_from_source(payload)
    try:
        result = compute_kla(**inputs)
    except InputError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "result": result.to_dict()})


@app.get("/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    # Local development only. In production (Render), gunicorn serves `app`
    # directly — see Procfile.
    app.run(host="0.0.0.0", port=5000, debug=True)
