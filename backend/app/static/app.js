const $ = (selector, root = document) => root.querySelector(selector);
const inr = new Intl.NumberFormat("en-IN");
const state = { options: null, info: null };

/* ---------- formatting ---------- */
const trim = (x) => x.toFixed(2).replace(/\.?0+$/, "");

function money(n) {
  const v = Math.round(n);
  const a = Math.abs(v);
  if (a >= 1e7) return `₹${trim(v / 1e7)} crore`;
  if (a >= 1e5) return `₹${trim(v / 1e5)} lakh`;
  return `₹${inr.format(v)}`;
}

function shortMoney(n) {
  const a = Math.abs(n);
  if (a >= 1e7) return `₹${trim(n / 1e7)}Cr`;
  if (a >= 1e5) return `₹${trim(n / 1e5)}L`;
  return `₹${inr.format(Math.round(n))}`;
}

const roundTo = (n, step) => Math.round(n / step) * step;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/* ---------- talking to the server ---------- */
async function api(path, options) {
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new Error("Cannot reach the CarWorth server. Check that it is running, then try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    if (Array.isArray(detail) && detail.length) {
      const field = detail[0].loc?.[detail[0].loc.length - 1] ?? "input";
      const reason = String(detail[0].msg).replace(/^Value error,\s*/, "").replace(/\.$/, "");
      throw new Error(`Check the ${String(field).replace("_", " ")} field: ${reason}.`);
    }
    throw new Error(typeof detail === "string" ? detail : "Something went wrong. Try again.");
  }
  return data;
}

/* ---------- the form ---------- */
function fillSelect(select, values, preferred) {
  select.replaceChildren(...values.map((v) => {
    const option = el("option", null, v);
    option.value = v;
    return option;
  }));
  select.value = values.includes(preferred) ? preferred : values[0];
}

function buildSeg(container, name, values, preferred) {
  const selected = values.includes(preferred) ? preferred : values[0];
  container.setAttribute("role", "radiogroup");
  container.replaceChildren();
  values.forEach((value, i) => {
    const input = el("input");
    input.type = "radio";
    input.name = name;
    input.id = `${name}-${i}`;
    input.value = value;
    input.checked = value === selected;
    const label = el("label", null, value);
    label.htmlFor = input.id;
    container.append(input, label);
  });
}

function buildForm() {
  const { options } = state;
  const thisYear = new Date().getFullYear();
  fillSelect($("#brand"), options.brand, "Maruti");
  fillSelect($("#seller"), options.seller_type, "Individual");
  fillSelect($("#owner"), options.owner, "First Owner");
  buildSeg($("#fuel"), "fuel", options.fuel, "Petrol");
  buildSeg($("#transmission"), "transmission", options.transmission, "Manual");

  const year = $("#year");
  year.min = Math.max(1990, options.ranges.year_min);
  year.max = thisYear;
  year.value = Math.max(Number(year.min), thisYear - 6);
  $("#km").value = 60000;
  updateHelpers();
}

function updateHelpers() {
  const km = Number($("#km").value);
  $("#km-help").textContent = km >= 0 && $("#km").value !== "" ? `${inr.format(km)} km` : "";
  const asking = Number($("#asking").value);
  $("#asking-help").textContent = asking > 0 ? money(asking) : "Add it to get a verdict.";
}

function readForm() {
  const asking = $("#asking").value;
  return {
    brand: $("#brand").value,
    year: Number($("#year").value),
    km_driven: Number($("#km").value),
    fuel: $("input[name=fuel]:checked").value,
    transmission: $("input[name=transmission]:checked").value,
    seller_type: $("#seller").value,
    owner: $("#owner").value,
    asking_price: asking ? Number(asking) : null,
  };
}

function setBusy(busy) {
  const button = $("#submit");
  button.setAttribute("aria-busy", String(busy));
  $("#submit-label").textContent = busy ? "Checking" : "Check this car";
}

function showFormError(message) {
  const box = $("#form-error");
  box.textContent = message;
  box.hidden = !message;
}

function showBanner(message) {
  const banner = $("#banner");
  banner.textContent = message;
  banner.hidden = !message;
}

/* ---------- drawing the result ---------- */
const VERDICTS = {
  good_deal: { cls: "chip chip-good", icon: "✓", text: "Good deal" },
  fair: { cls: "chip chip-fair", icon: "≈", text: "Fair price" },
  overpriced: { cls: "chip chip-over", icon: "▲", text: "Overpriced" },
};

const FACTOR_LABELS = {
  age: (v) => (v === 0 ? "Newest model year" : `${v} year${v === 1 ? "" : "s"} old`),
  km_driven: (v) => `${inr.format(v)} km driven`,
  brand: (v) => `${v} brand`,
  fuel: (v) => `${v} fuel`,
  seller_type: (v) => `Sold by ${String(v).toLowerCase()}`,
  transmission: (v) => `${v} gearbox`,
  owner: (v) => v,
};

function drawVerdict(data) {
  const chip = $("#verdict");
  const note = $("#verdict-note");
  chip.replaceChildren();
  if (!data.verdict) {
    chip.className = "chip chip-fair";
    chip.textContent = "Estimate only";
    note.textContent = "Add an asking price to get a verdict.";
    return;
  }
  const v = data.verdict;
  const style = VERDICTS[v.label];
  chip.className = style.cls;
  const icon = el("span", null, style.icon);
  icon.setAttribute("aria-hidden", "true");
  chip.append(icon, document.createTextNode(style.text));

  const pct = Math.round(Math.abs(v.difference_pct) * 100);
  const where = v.difference_pct < 0 ? "below" : "above";
  const size = pct === 0 ? "right on" : `${pct}% ${where}`;
  note.textContent = v.label === "fair"
    ? `Asking ${money(v.asking)} is ${size} our estimate, inside the range similar cars sold for.`
    : `Asking ${money(v.asking)} is ${size} our estimate, ${v.label === "good_deal" ? "under" : "over"} the range similar cars sold for.`;
}

function drawMeter(data) {
  const { low, high } = data.range;
  const price = data.price;
  const asking = data.verdict?.asking ?? null;
  const min = Math.min(low, asking ?? low) * 0.82;
  const max = Math.max(high, asking ?? high) * 1.12;
  const pos = (v) => ((v - min) / (max - min)) * 100;
  const clamp = (p) => Math.min(94, Math.max(6, p));

  $("#meter-band").style.left = `${pos(low)}%`;
  $("#meter-band").style.width = `${pos(high) - pos(low)}%`;
  $("#meter-est").style.left = `${pos(price)}%`;

  const pin = $("#meter-ask");
  pin.hidden = asking === null;
  if (asking !== null) {
    pin.style.left = `${clamp(pos(asking))}%`;
    $("#meter-ask-label").textContent = `Asking ${shortMoney(asking)}`;
  }

  const scale = $("#meter-scale");
  scale.replaceChildren();
  for (const value of [low, high]) {
    const tick = el("span", null, shortMoney(value));
    tick.style.left = `${clamp(pos(value))}%`;
    scale.append(tick);
  }
  const coverage = Math.round(data.range.test_coverage * 100);
  $("#range-fine").textContent =
    `The yellow band is the range that held for ${coverage}% of cars the model had not seen during testing. The dark line is the estimate.`;
}

function drawFactors(data) {
  const list = $("#factors");
  list.replaceChildren();
  const maxEffect = Math.max(...data.factors.map((f) => Math.abs(f.effect)));
  for (const f of data.factors) {
    const effect = roundTo(f.effect, 500);
    const up = effect >= 0;
    const row = el("li", "factor");
    row.append(el("span", "factor-name", FACTOR_LABELS[f.feature](f.value)));

    const track = el("span", "diverge");
    const bar = el("span", `bar ${up ? "up" : "down"}`);
    bar.style.width = "0%";
    track.append(bar);
    row.append(track);

    const sign = up ? "+" : "−";
    const amount = el("span", "amount", `${up ? "▲" : "▼"} ${sign}₹${inr.format(Math.abs(effect))}`);
    amount.title = `${up ? "Raises" : "Lowers"} the price compared with a typical car`;
    row.append(amount);
    list.append(row);

    const width = Math.max(4, (Math.abs(f.effect) / maxEffect) * 50);
    requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.width = `${width}%`; }));
  }
  const t = state.info.typical;
  const rest = data.factors.length < 4 ? "The other details are close to the typical car, so they barely move the price. " : "";
  $("#typical-note").textContent =
    `${rest}Each line swaps one detail for the typical car in the data (${t.age} years old, ${inr.format(t.km_driven)} km, ${t.brand}, ${t.fuel}, ${t.transmission}). The amounts show how far the price moves, so they will not add up exactly.`;
}

function drawForecast(data) {
  const box = $("#forecast");
  box.replaceChildren();
  const top = data.forecast[0].price;
  for (const point of data.forecast) {
    const col = el("div", `fc${point.years === 0 ? " now" : ""}`);
    col.append(el("span", "fc-val", shortMoney(roundTo(point.price, 1000))));
    const bar = el("div", "fc-bar");
    col.append(bar, el("span", "fc-lab", point.years === 0 ? "Today" : `In ${point.years} year${point.years === 1 ? "" : "s"}`));
    box.append(col);
    const height = (point.price / top) * 120;
    requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.height = `${height}px`; }));
  }
  const kmPerYear = inr.format(roundTo(data.annual_km, 500));
  $("#forecast-note").textContent =
    `In 3 years it should hold about ${Math.round(data.retained * 100)}% of today’s estimate, assuming roughly ${kmPerYear} km a year. This comes from how older, similar cars are priced, so it is a guide, not a promise.`;
}

function drawWarnings(data) {
  const box = $("#warnings");
  box.replaceChildren(...data.warnings.map((w) => el("p", "callout", w)));
}

function render(data) {
  $("#empty").hidden = true;
  const result = $("#result");
  result.hidden = false;
  drawVerdict(data);
  $("#price").textContent = money(roundTo(data.price, 1000));
  $("#range-text").textContent = `Similar cars sold for ${money(roundTo(data.range.low, 1000))} to ${money(roundTo(data.range.high, 1000))}.`;
  drawMeter(data);
  drawFactors(data);
  drawForecast(data);
  drawWarnings(data);

  result.classList.remove("enter");
  void result.offsetWidth; // restart the entrance animation
  result.classList.add("enter");
  if (matchMedia("(max-width: 900px)").matches) {
    result.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
  result.focus({ preventScroll: true });
}

/* ---------- "How it works" ---------- */
function fillAbout() {
  const root = $("#about-content");
  root.replaceChildren();
  const info = state.info;
  if (!info) {
    root.append(el("p", null, "Train the model first (see the README). Then this page shows how well it performs."));
    return;
  }
  const pct = (x) => `${(x * 100).toFixed(1)}%`;
  root.append(el("p", null,
    `CarWorth learned from ${inr.format(info.trained_rows)} cleaned listings from ${info.source}. ${info.demo ? "This is made-up demo data, so the prices are not real." : "These are real listings."}`));

  root.append(el("h3", null, "Models compared"));
  const table = el("table", "models");
  const head = el("tr");
  ["Model", "Typical error", "Average error"].forEach((t) => head.append(el("th", null, t)));
  table.append(head);
  for (const row of info.comparison) {
    const tr = el("tr", row.model === info.model ? "chosen" : "");
    tr.append(el("td", null, row.model === info.model ? `${row.model} (chosen)` : row.model),
      el("td", null, pct(row.test_mdape)), el("td", null, money(row.test_mae)));
    table.append(tr);
  }
  root.append(table, el("p", "fine", "Measured on cars the model had never seen. Typical error is the middle value of how far off each guess was, as a share of the real price."));

  const iv = info.interval;
  root.append(el("h3", null, "The price range"),
    el("p", null, `The range covers the middle ${Math.round(iv.level * 100)}% of past errors. On unseen test cars it held for ${Math.round(iv.test_coverage * 100)}%.`),
    el("h3", null, "The verdict"),
    el("p", null, "An asking price under the range is a good deal, inside it is fair, and over it is overpriced."));

  root.append(el("h3", null, "What it cannot know"));
  const limits = el("ul");
  [
    `The prices come from listings around ${info.ref_year}, so today’s prices may differ. Use it to compare cars, not as an exact quote.`,
    "It does not see the car’s condition, accident history, city or exact variant.",
    "The later-value forecast compares cars of different ages. It does not follow one car over time.",
  ].forEach((t) => limits.append(el("li", null, t)));
  root.append(limits);

  const c = info.cleaning;
  root.append(el("p", "fine", `Cleaning removed ${c.dropped_duplicates} repeated listings, ${c.dropped_missing} with missing values and ${c.dropped_implausible} with impossible values.`));
}

/* ---------- start ---------- */
function wirePointerGlow() {
  document.addEventListener("pointermove", (e) => {
    const target = e.target instanceof Element ? e.target.closest(".reveal, .seg label") : null;
    if (!target) return;
    const box = target.getBoundingClientRect();
    target.style.setProperty("--x", `${e.clientX - box.left}px`);
    target.style.setProperty("--y", `${e.clientY - box.top}px`);
  });
}

function wireDialog() {
  const dialog = $("#about");
  $("#about-btn").addEventListener("click", () => { fillAbout(); dialog.showModal(); });
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
}

async function init() {
  wirePointerGlow();
  wireDialog();
  $("#km").addEventListener("input", updateHelpers);
  $("#asking").addEventListener("input", updateHelpers);

  try {
    const [options, info] = await Promise.all([api("/api/options"), api("/api/model-info")]);
    state.options = options;
    state.info = info;
  } catch (err) {
    showBanner(err.message);
    $("#submit").disabled = true;
    return;
  }
  buildForm();
  if (state.info.demo) {
    $("#demo-chip").hidden = false;
    showBanner("You are looking at demo data. The prices are made up, so train the model on the real CarDekho file for real results.");
  }

  $("#form").addEventListener("submit", async (e) => {
    e.preventDefault();
    showFormError("");
    setBusy(true);
    try {
      render(await api("/api/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(readForm()),
      }));
    } catch (err) {
      showFormError(err.message);
    } finally {
      setBusy(false);
    }
  });
}

init();
