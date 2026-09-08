// Shake-Flask kLa Estimator — client-side interactivity.
//
// The actual kLa formula lives ONLY in kla.py (server-side). This script
// never reimplements it: every recompute — the main panel and every
// Scenario Table row — calls POST /api/calculate and renders whatever the
// server returns, so the browser and the server can never disagree about
// the numbers.
(function () {
  "use strict";

  function fmt(n, d) {
    if (n === null || n === undefined || !isFinite(n)) return "—";
    d = d === undefined ? 2 : d;
    return Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  async function calculate(params) {
    const res = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    return res.json();
  }

  // ---------------- Main panel ----------------
  const form = document.getElementById("calcForm");
  const flaskTypeHidden = document.getElementById("flask_type");
  const orbitHidden = document.getElementById("orbit");
  const sizeSelect = document.getElementById("size");
  const customDiaField = document.getElementById("customDiaField");
  const customDiaInput = document.getElementById("custom_dia");
  const baffleBlock = document.getElementById("baffleBlock");

  let unit = "h";

  function wireSegmented(container, hiddenInput, onChange) {
    container.addEventListener("click", function (e) {
      const btn = e.target.closest("button");
      if (!btn) return;
      container.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", "false"));
      btn.setAttribute("aria-pressed", "true");
      if (hiddenInput) hiddenInput.value = btn.dataset.value;
      if (onChange) onChange(btn.dataset.value);
      refreshMain();
    });
  }

  document.querySelectorAll('.segmented[data-name="flask_type"]').forEach((el) =>
    wireSegmented(el, flaskTypeHidden, (v) => {
      baffleBlock.style.display = v === "baffled" ? "block" : "none";
    })
  );
  document.querySelectorAll('.segmented[data-name="orbit"]').forEach((el) => wireSegmented(el, orbitHidden));
  document.querySelectorAll('.segmented[data-name="unit"]').forEach((el) =>
    wireSegmented(el, null, (v) => { unit = v; })
  );

  sizeSelect.addEventListener("change", function () {
    customDiaField.style.display = this.value === "custom" ? "block" : "none";
    refreshMain();
  });

  function currentParams() {
    return {
      flask_type: flaskTypeHidden.value,
      size: sizeSelect.value,
      custom_dia: customDiaInput.value,
      vol: form.vol.value,
      rpm: form.rpm.value,
      orbit: orbitHidden.value,
      temp: form.temp.value,
      factor: form.factor.value,
    };
  }

  let mainDebounce;
  function scheduleRefreshMain() {
    clearTimeout(mainDebounce);
    mainDebounce = setTimeout(refreshMain, 200);
  }
  ["vol", "rpm", "temp", "factor"].forEach((name) => {
    const el = form.elements[name];
    if (el) el.addEventListener("input", scheduleRefreshMain);
  });
  customDiaInput.addEventListener("input", scheduleRefreshMain);

  async function refreshMain() {
    const data = await calculate(currentParams());
    if (!data.ok) return;
    renderMain(data.result);
  }

  function chip(label, ok) {
    if (ok === null || ok === undefined) return "";
    return `<span class="chip ${ok ? "ok" : "bad"}"><span class="dot"></span>${label} — ${ok ? "OK" : "OUTSIDE RANGE"}</span>`;
  }

  function renderMain(r) {
    const mainVal = unit === "h" ? r.kla_adjusted_h : r.kla_adjusted_h / 3600;
    document.getElementById("klaMain").innerHTML =
      fmt(mainVal, unit === "h" ? 1 : 6) + `<span>${unit === "h" ? "h⁻¹" : "s⁻¹"}</span>`;
    document.getElementById("klaSubline").textContent =
      r.flask_type === "baffled"
        ? `Base × user calibration factor (${fmt(r.applied_factor, 2)}×)`
        : "Base correlation (non-baffled, validated)";

    const lowShown = unit === "h" ? r.band_low_h : r.band_low_h / 3600;
    const highShown = unit === "h" ? r.band_high_h : r.band_high_h / 3600;
    document.getElementById("bandLow").textContent = fmt(lowShown, unit === "h" ? 1 : 6) + " " + (unit === "h" ? "h⁻¹" : "s⁻¹");
    document.getElementById("bandHigh").textContent = fmt(highShown, unit === "h" ? 1 : 6) + " " + (unit === "h" ? "h⁻¹" : "s⁻¹");

    document.getElementById("diaLookup").textContent = fmt(r.diameter_cm, 1) + " cm";
    document.getElementById("statDia").textContent = fmt(r.diameter_cm, 1) + " cm";
    document.getElementById("statOrbit").textContent = fmt(r.orbit_cm, 2) + " cm";
    document.getElementById("statFill").textContent = r.fill_fraction === null ? "n/a" : fmt(r.fill_fraction * 100, 1) + "%";
    document.getElementById("statAccel").textContent = fmt(r.max_accel_g, 2) + " g";

    const c = r.checks;
    const chips = [
      chip("Flask size 50–1000 mL", c.flask_size_in_range),
      chip("Fill fraction 4–20%", c.fill_fraction_in_range),
      chip("Shaking speed 50–500 rpm", c.rpm_in_range),
      chip("Orbit diameter 1.25–10 cm", c.orbit_in_range),
      `<span class="chip ${r.flask_type === "baffled" ? "bad" : "ok"}"><span class="dot"></span>${
        r.flask_type === "baffled" ? "Baffled — user-calibrated, not validated" : "Base equation domain — validated"
      }</span>`,
    ];
    document.getElementById("validityChips").innerHTML = chips.join("");

    document.getElementById("equationBox").innerHTML =
      `kLa [s⁻¹] = 6.67e-6 × <span class='filled'>${fmt(r.rpm, 0)}</span>^1.16 × <span class='filled'>${fmt(
        r.working_volume_ml, 0
      )}</span>^-0.83 × <span class='filled'>${fmt(r.orbit_cm, 2)}</span>^0.38 × <span class='filled'>${fmt(
        r.diameter_cm, 1
      )}</span>^1.92 = <span class='filled'>${fmt(r.kla_base_s, 6)} s⁻¹</span> = <span class='filled'>${fmt(
        r.kla_base_h, 2
      )} h⁻¹</span>` +
      (r.flask_type === "baffled"
        ? `  ×  ${fmt(r.baffle_factor, 2)}  =  <span class='filled'>${fmt(r.kla_adjusted_h, 2)} h⁻¹ (baffled, user-calibrated)</span>`
        : "");
  }

  // ---------------- Scenario table ----------------
  const scenarioBody = document.getElementById("scenarioBody");
  let scenarios = [];
  let seq = 0;

  function addScenario(overrides) {
    seq += 1;
    scenarios.push(
      Object.assign(
        { id: seq, name: "Condition " + seq, flask_type: "unbaffled", size: 500, vol: 50, rpm: 250, orbit: 1, factor: 1.0 },
        overrides || {}
      )
    );
    renderScenarios();
  }

  document.getElementById("addFromCurrent").addEventListener("click", function () {
    addScenario({
      flask_type: flaskTypeHidden.value,
      size: sizeSelect.value === "custom" ? 500 : Number(sizeSelect.value),
      vol: Number(form.vol.value),
      rpm: Number(form.rpm.value),
      orbit: Number(orbitHidden.value),
      factor: Number(form.factor.value),
    });
  });
  document.getElementById("addBlankRow").addEventListener("click", () => addScenario());

  async function renderScenarios() {
    const rows = await Promise.all(
      scenarios.map(async (sc) => {
        const data = await calculate({
          flask_type: sc.flask_type,
          size: sc.size,
          vol: sc.vol,
          rpm: sc.rpm,
          orbit: sc.orbit,
          factor: sc.factor,
        });
        return { sc, r: data.ok ? data.result : null };
      })
    );

    scenarioBody.innerHTML = "";
    rows.forEach(({ sc, r }) => {
      const tr = document.createElement("tr");
      const sizeOpts = [50, 100, 250, 500, 1000]
        .map((v) => `<option value="${v}" ${sc.size === v ? "selected" : ""}>${v}</option>`)
        .join("");
      const typeOpts = `
        <option value="unbaffled" ${sc.flask_type === "unbaffled" ? "selected" : ""}>Non-baffled</option>
        <option value="baffled" ${sc.flask_type === "baffled" ? "selected" : ""}>Baffled</option>`;
      const orbitOpts = `
        <option value="1" ${sc.orbit === 1 ? "selected" : ""}>1</option>
        <option value="2" ${sc.orbit === 2 ? "selected" : ""}>2</option>`;

      const allOk = r ? Object.values(r.checks).every((v) => v !== false) : false;

      tr.innerHTML = `
        <td><input data-field="name" value="${sc.name}" style="width:110px;"></td>
        <td><select data-field="flask_type">${typeOpts}</select></td>
        <td><select data-field="size">${sizeOpts}</select></td>
        <td><input type="number" data-field="vol" value="${sc.vol}" style="width:64px;"></td>
        <td><input type="number" data-field="rpm" value="${sc.rpm}" style="width:64px;"></td>
        <td><select data-field="orbit">${orbitOpts}</select></td>
        <td><input type="number" step="0.05" data-field="factor" value="${sc.factor}" style="width:64px;" ${sc.flask_type === "baffled" ? "" : "disabled"}></td>
        <td class="num">${r ? fmt(r.diameter_cm, 1) : "—"}</td>
        <td class="num">${r && r.fill_fraction !== null ? fmt(r.fill_fraction * 100, 1) + "%" : "—"}</td>
        <td class="num">${r ? fmt(r.kla_base_h, 1) : "—"}</td>
        <td class="num">${r ? fmt(r.kla_adjusted_h, 1) : "—"}</td>
        <td><span class="validity-pill ${allOk ? "ok" : "bad"}">${allOk ? "OK" : "CHECK"}</span></td>
        <td class="row-actions"><button type="button" title="Remove row" data-remove="${sc.id}">✕</button></td>`;

      tr.querySelectorAll("[data-field]").forEach((input) => {
        input.addEventListener("change", function () {
          const f = this.dataset.field;
          let v = this.value;
          if (["size", "orbit", "vol", "rpm", "factor"].includes(f)) v = Number(v);
          sc[f] = v;
          renderScenarios();
        });
      });
      tr.querySelector("[data-remove]").addEventListener("click", function () {
        scenarios = scenarios.filter((s) => s.id !== sc.id);
        renderScenarios();
      });

      scenarioBody.appendChild(tr);
    });
  }

  // Seed two example rows so the table isn't empty on first load.
  addScenario({ flask_type: "unbaffled", size: 500, vol: 50, rpm: 250, orbit: 1, factor: 1.0, name: "Condition 1" });
  addScenario({ flask_type: "baffled", size: 500, vol: 75, rpm: 200, orbit: 2, factor: 1.0, name: "Condition 2" });
})();
