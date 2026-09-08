# Shake-Flask kLa Estimator

A small Flask web app that estimates the volumetric oxygen transfer
coefficient (kLa) for orbitally shaken Erlenmeyer flasks, using the
validated Seletzky/Maier correlation. Includes a scenario comparison table
and an explicit, honest treatment of baffled flasks (see **Method &
limitations** below).

Live calculation logic lives in one place only — [`kla.py`](kla.py) — and
is called by both the server-rendered page and its `/api/calculate` JSON
endpoint, so the browser and the server can never disagree about a number.

## Project layout

```
.
├── app.py              Flask routes (/, /api/calculate, /healthz)
├── kla.py              Pure-Python calculation core (framework-independent)
├── templates/
│   └── index.html      Server-rendered page (Jinja2)
├── static/
│   ├── style.css
│   └── app.js           Calls /api/calculate for live recompute; no formula logic here
├── tests/
│   └── test_kla.py      Unit tests for kla.py
├── requirements.txt
├── Procfile              gunicorn start command (Render/Heroku-style)
├── render.yaml           Render Blueprint (optional one-click config)
└── runtime.txt            Pinned Python version
```

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py            # http://localhost:5000
```

Or with gunicorn, the same server Render uses:

```bash
pip install -r requirements.txt
gunicorn app:app
```

## Run the tests

```bash
pip install pytest
pytest -q
```

## Deploy to Render

1. Push this folder to a new GitHub repository.
2. In the Render dashboard: **New +** → **Web Service** → connect the repo.
   Render will detect `render.yaml` and pre-fill the settings; otherwise
   set them manually:
   - **Environment**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn app:app`
   - **Health check path**: `/healthz`
3. Deploy. Render assigns a `https://<service-name>.onrender.com` URL.

No environment variables, database, or secrets are required — the app is
fully stateless (the Scenario Table lives only in the browser tab).

## API

`POST /api/calculate` accepts JSON (or form-encoded) fields and returns the
full result object computed by `kla.py`:

```bash
curl -X POST https://<your-app>.onrender.com/api/calculate \
  -H "Content-Type: application/json" \
  -d '{"flask_type":"baffled","size":500,"vol":50,"rpm":250,"orbit":1,"factor":2.2}'
```

`GET /` accepts the same fields as query parameters, so any calculation is
shareable as a link, e.g.:
`https://<your-app>.onrender.com/?flask_type=baffled&size=500&vol=50&rpm=250&orbit=1&factor=2.2`

## Method & limitations

- **Base correlation** (non-baffled, standard glass Erlenmeyer flasks):
  kLa [s⁻¹] = 6.67×10⁻⁶ · n¹·¹⁶ · V_L⁻⁰·⁸³ · d₀⁰·³⁸ · d¹·⁹², validated for
  50–500 rpm, 4–20% fill, orbit diameter 1.25–10 cm, nominal flask size
  50–1000 mL, reported accuracy ≈ ±30%.
  Source: Seletzky, J. — dissertation, RWTH Aachen
  ([PDF](https://publications.rwth-aachen.de/record/50532/files/Seletzky_Juri.pdf));
  reproduced and discussed in Brauneck et al., 2025, *Engineering in Life
  Sciences* ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11773345/));
  foundational characterization in Maier & Büchs, 2001
  ([DOI](https://doi.org/10.1016/S1369-703X(00)00107-8)).
- **Baffled flasks**: no universal correlation exists for baffled shake
  flasks as a function of baffle geometry (Klöckner & Büchs,
  *Comprehensive Biotechnology* —
  [sciencedirect.com](https://www.sciencedirect.com/topics/engineering/shake-flask)).
  This app therefore never predicts a baffled kLa from first principles —
  it multiplies the base estimate by a correction factor the user supplies,
  which should come from their own calibration (sulfite oxidation, dynamic
  gassing-out, RAMOS/OTR, or similar). Selecting "Non-baffled" always forces
  the applied factor to 1.0, regardless of what is entered in the factor
  field — see `kla.compute_kla`.
- Generic flask diameters (50/100/250/500/1000 mL → 5/7/8/10/12 cm) are
  illustrative values reproduced from the original workbook this project is
  based on. Supply a manufacturer-specific diameter via `custom_dia` /
  `custom_diameter_cm` whenever it is known, for a more accurate estimate.
- All results are engineering estimates, not direct measurements.
