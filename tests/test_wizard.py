"""Drive the five steps the way a user does, and check the draft survives each hop."""
import pytest
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_app_starts_empty(client):
    """No worked example is loaded - it is the user's medium from the first screen."""
    r = client.get("/step/media")
    assert r.status_code == 200
    assert b"Glucose anhydrous" in r.data          # the option exists in the dropdown
    assert b'selected' not in r.data.split(b'name="substrate"')[1][:4000]


def test_results_before_anything_explains_itself(client):
    r = client.get("/results")
    assert r.status_code == 200
    assert b"Not enough entered yet" in r.data
    assert b"Traceback" not in r.data


def _walk(client):
    client.post("/step/organism", data={
        "organism_name": "Escherichia coli", "source": "library",
        "C_pct": "48.0510154482554", "H_C": "1.77", "O_C": "0.49", "N_C": "0.24",
        "Yxs": "0.40", "min_N": "12.5", "min_P": "3.0303", "min_S": "1.0",
        "min_K": "1.0", "min_Mg": "0.34965"})
    client.post("/step/media", data={
        "batch_compound": ["Glucose anhydrous, C6H12O6", "Ammonium sulfate, (NH4)2SO4",
                           "Potassium dihydrogen phosphate, KH2PO4"],
        "batch_g_per_L": ["40", "5", "5"], "batch_is_substrate": ["0"],
        "feed_compound": ["Glucose anhydrous, C6H12O6"], "feed_g_per_L": ["102.078"],
        "feed_is_substrate": ["0"],
        "substrate": "Glucose anhydrous, C6H12O6", "fs_include": ""})
    client.post("/step/process", data={
        "V_batch": "80", "V_feed": "136", "V_base": "28.2", "V_acid": "2.15",
        "target_CDW": "25", "mu": "0.08", "mS": "0.02", "kLa_available": "870",
        "aerobic": "aerobic", "C_star": "0.2156", "DO_setpoint_fraction": "0.3",
        "CDW_assay": "23.5", "residual_substrate": "0.15",
        "V_sampled": "22", "CDW_sampled": "5.1", "residual_sampled": "0.15",
        "titre_sampled": "3.0"})
    client.post("/step/product", data={
        "p_compound": ["Succinic acid, C4H6O4", "Acetic acid, C2H4O2"],
        "p_target": ["25", "2.854"], "p_Yps": ["0.51", "0.40"],
        "p_productivity": ["0.9", ""], "p_measured": ["15", "3"],
        "p_is_target": ["0"], "p_intracellular": [],
        "co2_mmol_L": "1250", "o2_mmol_L": "1500"})


def test_five_steps_produce_results(client):
    _walk(client)
    r = client.get("/results")
    assert r.status_code == 200
    assert b"Not enough entered yet" not in r.data
    assert b"Carbon recovery" in r.data
    assert b"kLa required" in r.data


def test_draft_persists_between_steps(client):
    """Go forward, then back - what you typed is still in the fields."""
    _walk(client)
    r = client.get("/step/process")
    assert b'value="80"' in r.data and b'value="136"' in r.data
    r = client.get("/step/media")
    assert b'value="102.078"' in r.data


def test_engine_numbers_reach_the_page(client):
    _walk(client)
    j = client.get("/api/report").get_json()
    assert j["shared"]["carbon_efficiency"] == pytest.approx(0.480486, abs=1e-5)
    assert j["measured"]["carbon"]["carbon_recovery"] is not None
    assert j["design"]["kla"]["kLa_required"] > 0


def test_clearing_the_draft_empties_it(client):
    _walk(client)
    client.get("/reset")
    j = client.get("/api/report")
    assert j.status_code == 400          # nothing entered any more


def test_missing_yield_is_explained_not_crashed(client):
    """Each missing input is named in turn, in the order the engine needs them."""
    _walk(client)
    client.post("/step/organism", data={"organism_name": "Escherichia coli",
                                        "source": "library", "Yxs": ""})
    r = client.get("/results")
    assert b"Yx/s" in r.data and b"Traceback" not in r.data


def test_whole_numbers_do_not_come_back_as_floats(client):
    """A volume typed as 80 must not reappear as 80.0 - it looks like a bug to the user."""
    _walk(client)
    r = client.get("/step/process")
    assert b'value="80"' in r.data
    assert b'value="80.0"' not in r.data
    assert b'value="0.2156"' in r.data          # a real decimal is untouched
