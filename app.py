"""MediaOpt — a five-step wizard over the calculation engine.

The app holds a draft in temporary server-side storage, one per browser session, and
does no science of its own: every number on the results page comes from
mediaopt.calculations, which is unit-tested against the source workbook.

It starts EMPTY. There is no worked example loaded - the user enters their own medium.
"""
from __future__ import annotations
import os
from flask import (Flask, render_template, request, redirect, url_for, session,
                   jsonify, flash)

from mediaopt import session_store as store
from mediaopt import webforms as F
from mediaopt.calculations import full_report

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32))

STEP_ORDER = [s[0] for s in F.STEPS]


@app.template_filter("nice")
def nice(v):
    """Render a number the way the user typed it: 80, not 80.0; 0.2156 unchanged."""
    if v is None or v == "":
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return v


def _sid() -> str:
    if "sid" not in session:
        session["sid"] = store.new_id()
    return session["sid"]


def _draft() -> dict:
    d = store.get(_sid())
    if not d:
        d = F.blank_draft()
        store.put(_sid(), d)
    return d


def _save(**parts) -> None:
    d = _draft()
    d.update(parts)
    store.put(_sid(), d)


def _nav(step: str) -> dict:
    i = STEP_ORDER.index(step)
    return {"steps": F.STEPS, "current": step, "index": i,
            "prev": STEP_ORDER[i - 1] if i else None,
            "next": STEP_ORDER[i + 1] if i + 1 < len(STEP_ORDER) else None}


@app.route("/")
def index():
    return render_template("index.html", nav=_nav("organism"), draft=_draft())


@app.route("/start")
def start():
    store.clear(session.get("sid"))
    session.pop("sid", None)
    return redirect(url_for("step_organism"))


@app.route("/reset")
def reset():
    store.clear(session.get("sid"))
    session.pop("sid", None)
    flash("Draft cleared.")
    return redirect(url_for("index"))


@app.route("/step/organism", methods=["GET", "POST"])
def step_organism():
    if request.method == "POST":
        _save(organism=F.parse_organism(request.form))
        return redirect(url_for("step_media"))
    return render_template("step_organism.html", nav=_nav("organism"), draft=_draft(),
                           organisms=F.ORGANISMS, minerals=F.MINERALS)


@app.route("/step/media", methods=["GET", "POST"])
def step_media():
    if request.method == "POST":
        _save(**F.parse_media(request.form))
        return redirect(url_for("step_process"))
    return render_template("step_media.html", nav=_nav("media"), draft=_draft(),
                           compounds=sorted(F.COMPOUNDS))


@app.route("/step/process", methods=["GET", "POST"])
def step_process():
    if request.method == "POST":
        _save(process=F.parse_process(request.form))
        return redirect(url_for("step_product"))
    return render_template("step_process.html", nav=_nav("process"), draft=_draft())


@app.route("/step/product", methods=["GET", "POST"])
def step_product():
    if request.method == "POST":
        _save(**F.parse_products(request.form))
        return redirect(url_for("results"))
    return render_template("step_product.html", nav=_nav("product"), draft=_draft(),
                           compounds=sorted(F.COMPOUNDS))


@app.route("/results")
def results():
    draft = _draft()
    try:
        r = full_report(**F.build(draft))
    except ValueError as e:
        return render_template("results.html", nav=_nav("results"), r=None,
                               problem=str(e), draft=draft)
    except KeyError as e:
        return render_template("results.html", nav=_nav("results"), r=None,
                               problem=str(e).strip('"'), draft=draft)
    return render_template("results.html", nav=_nav("results"), r=r, problem=None,
                           draft=draft)


@app.route("/api/report")
def api_report():
    try:
        return jsonify(full_report(**F.build(_draft())))
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e).strip('"')}), 400


@app.route("/api/compounds")
def api_compounds():
    return jsonify([{"name": c.name, "mw": c.mw, "carbon_fraction": c.carbon_fraction,
                     "gamma": c.gamma, "gamma_per_cmol": c.gamma_per_cmol}
                    for c in F.COMPOUNDS.values()])


@app.route("/healthz")
def healthz():
    return {"status": "ok", "compounds": len(F.COMPOUNDS), "organisms": len(F.ORGANISMS)}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
