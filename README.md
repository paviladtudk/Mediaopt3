# MediaOpt

A fed-batch media design and mass-balance engine, ported from a large Excel workbook.

The point of the port is not to reproduce the spreadsheet cell by cell. It is to get the
science out of thousands of interlinked formulas and into a library that can be tested.

```
mediaopt/calculations/   pure functions, plain args in, plain dict out
mediaopt/models/         organism, compounds, media, process, products, feedstock
mediaopt/data/           compounds.csv, organisms.csv  (were worksheets)
mediaopt/validation/     input checks that run BEFORE the engine
app.py                   Flask; renders what the engine returns, does no science
tests/                   46 tests, incl. 25 asserting against the workbook's own numbers
```

## The engine is tested against the workbook it replaces

Every expected value in `tests/test_against_workbook.py` and the parametrised block in
`tests/test_report.py` was read out of a LibreOffice recalculation of the source workbook.
They are the spreadsheet's numbers, not numbers chosen to make the tests pass. The full
pipeline agrees to **nine significant figures**:

| | engine | workbook |
|---|---|---|
| carbon delivered | 32.881679417 g C/L | 32.881679417 |
| substrate consumed | 82.050092096 g/L | 82.050092096 |
| carbon recovery | 1.000004385 | 1.000004385 |
| O₂ predicted / measured | 0.862265805 | 0.862265805 |
| kLa required | 886.961748214 h⁻¹ | 886.961748214 |

54 tests in total: chemistry, the workbook regression, the full report, and a wizard suite
that drives all five steps the way a browser does.

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Run it

```bash
pip install -r requirements.txt
python app.py                 # http://localhost:5000
```

A five-step wizard: **Organism → Media → Process → Product → Results**, with Back and
Continue throughout. It starts **empty** — there is no example loaded, you enter your own
medium from the first screen.

Every input the spreadsheet coloured yellow or orange is a field here. Compounds and
organisms are drop-downs backed by the CSV libraries, so choosing a substrate updates its
carbon fraction, molecular weight and degree of reduction everywhere downstream.

Your draft is held in **temporary server-side memory**, keyed by a session cookie, for
eight hours after your last edit. Nothing is written to disk and there are no accounts.
Going Back re-fills every field you already typed. `Clear draft` wipes it.

Routes: `/` start · `/step/<organism|media|process|product>` · `/results` ·
`/api/report` the engine's dict as JSON · `/api/compounds` · `/api/organisms` · `/healthz`.

> Session storage is a single-process in-memory dict, which suits Render's free tier
> (one worker). Scaling to several workers means swapping `mediaopt/session_store.py`
> for Redis — the interface is `get` / `put` / `clear` and nothing else.

## Deploy to Render

`render.yaml` is a blueprint — point Render at the repo and it reads it. Or configure
manually:

| setting | value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn app:app --bind 0.0.0.0:$PORT` |
| Health check | `/healthz` |

`Procfile` is there too, so Heroku-style platforms work unchanged.

## Push it to GitHub

```bash
git init && git add -A
git commit -m "MediaOpt: calculation engine ported from the Excel workbook"
git branch -M main
git remote add origin https://github.com/<you>/mediaopt.git
git push -u origin main
```

CI runs `pytest` on every push (`.github/workflows/tests.yml`).

## Using the engine without the web app

```python
from mediaopt.models import load_compounds, load_organisms, Medium, ProcessSetup, ProductSet
from mediaopt.calculations import carbon_balance

r = carbon_balance(
    substrate_delivered_g_L=82.2, residual_substrate_g_L=0.15,
    substrate_carbon_fraction=0.400020,
    biomass_g_L=21.857, biomass_carbon_fraction=0.480510,
    product_carbon_g_L=7.306, co2_mmol_L=1250,
)
r["carbon_recovery"]     # 1.0000
```

## Things the port fixed rather than carried across

**Titre is not a rate.** The workbook computed product gas demand as `mu × (titre / Yp/s)`,
which asserts the entire product inventory is remade every `1/mu` hours. The engine takes
an instantaneous productivity `r_P` instead. On the shipped example this changed the
product substrate demand from 62.99 to 5.56 g/L/h.

**"Product can never lower oxygen demand" is not a law.** It is a property of one model.
`gas_demand()` therefore offers both, and they give opposite signs — both correct:

- `substrate_mode="additive"` — product draws *extra* substrate on top of growth. Oxygen
  demand can only rise, and reaches exactly zero effect at the stoichiometric maximum yield.
- `substrate_mode="fixed_qS"` — uptake is what it is and product diverts electrons away
  from respiration. A reduced product genuinely *lowers* oxygen demand, which is why
  ethanol and lactate can be made with little or no O₂.

`test_product_effect_on_oxygen_depends_on_the_question_asked` pins both.

**Carbon efficiency is derived, not guessed.** Enter a measured `Yx/s` and the engine
computes `η_C = Yx/s · w_C,X / w_C,S`. It round-trips exactly, which is asserted.

**Volume basis is explicit.** Assays are measured on harvest broth; substrate is defined
per delivered litre. `ProcessSetup.to_delivered_basis()` rebases, and returns the assay
unchanged when no sampling is entered.

**Intracellular product is not counted twice.** A product inside the cells is already on
the filter when you weigh dry mass. `carbon_balance(intracellular_product_g_L=...)`
subtracts it to give catalytic biomass. On the example that is the difference between a
100% and a 78% carbon recovery.

**A mismatched recipe is caught at entry.** The recipe sets the denominator of the carbon
recovery, so a feed concentration from a different experiment produces a confidently wrong
answer with no other symptom — this is exactly what happened in the spreadsheet. The
validation layer flags it before the engine runs.

## Not yet ported

`struvite.py` and `calcium_phosphate.py` raise `NotImplementedError` rather than returning
an approximation. Saturation indices need activity coefficients (Davies), pH-dependent
speciation and tabulated solubility products; a rough answer is worse than none, because
the caller cannot tell one from the other. Use the workbook's own worksheets until Phase 6.

## Roadmap

1. ~~Core engine with tests against the workbook~~ **done**
2. ~~Libraries as CSV~~ **done** — 74 compounds, 14 organisms
3. ~~Editable inputs in the browser~~ **done** — five-step wizard, blank start, session-persisted
4. ~~Results dashboard~~ **done** — overview plus full audit trail
5. ~~Design vs measured kept separate~~ **done** — the report dict splits them
6. Precipitation modules
7. Excel export, so the spreadsheet becomes the report format rather than the engine
