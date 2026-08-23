// Unilog Product Intelligence — frontend SPA (no build step, talks to the
// FastAPI backend in app/api/main.py). All data shown is live pipeline
// output; nothing here is precomputed or sample-specific.

const API = "";
const state = { uploadId: null, summary: null, currentView: "dashboard" };

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return e;
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

function pill(status) {
  const map = {
    SUCCESS: "success", PARTIAL: "warn", REVIEW_REQUIRED: "warn",
    UNRESOLVED: "danger", VALIDATION_FAILED: "danger", PROCESSING_FAILED: "danger",
    RESOLVED: "success", LOW_CONFIDENCE: "warn",
  };
  return el("span", { class: `pill ${map[status] || "neutral"}` }, status || "—");
}

function confBar(value) {
  const pct = Math.round((value || 0) * 100);
  return el("span", {}, [
    el("span", { class: "confbar" }, el("span", { style: `width:${pct}%` })),
    el("span", { class: "mono muted" }, `${pct}%`),
  ]);
}

// ---------------------------------------------------------------- Nav ----
function setView(view) {
  state.currentView = view;
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.getElementById("view-title").textContent = {
    dashboard: "Dashboard", enrichment: "Product Enrichment", upload: "Batch Upload",
    review: "Review Queue", evidence: "Evidence Explorer", evaluation: "Evaluation", health: "System Health",
  }[view];
  render(view);
}
document.getElementById("nav").addEventListener("click", (e) => {
  const btn = e.target.closest(".nav-item");
  if (btn) setView(btn.dataset.view);
});

function updateRunIndicator() {
  const ind = document.getElementById("run-indicator");
  ind.textContent = state.uploadId
    ? `Batch ${state.uploadId} — ${state.summary ? state.summary.total + " rows processed" : "uploaded, not processed"}`
    : "No batch loaded";
}

// ------------------------------------------------------------ Dashboard --
async function renderDashboard(container) {
  if (!state.summary) {
    container.appendChild(el("div", { class: "empty-state" }, [
      el("div", {}, "No batch processed yet."),
      el("div", { style: "margin-top:10px" }, el("button", { class: "btn", onclick: () => setView("upload") }, "Go to Batch Upload")),
    ]));
    return;
  }
  const s = state.summary;
  container.appendChild(el("div", { class: "grid cols-4" }, [
    statCard("Products Processed", s.total),
    statCard("Avg. Confidence", `${Math.round(s.avg_confidence * 100)}%`),
    statCard("Review Required", s.review_required, `${Math.round((s.review_required / s.total) * 100)}% of batch`),
    statCard("LOV Compliance", `${Math.round(s.lov_compliance_rate * 100)}%`),
  ]));
  container.appendChild(el("div", { class: "grid cols-4", style: "margin-top:16px" }, [
    statCard("Groundedness", `${Math.round(s.groundedness_rate * 100)}%`, "claims backed by evidence, not UNKNOWN"),
    statCard("Duplicate Groups", s.duplicate_groups),
    statCard("Processing Time", `${s.processing_time_s}s`, `${(s.total / Math.max(s.processing_time_s, 0.01)).toFixed(0)} rows/sec`),
    statCard("Statuses", Object.keys(s.status_counts).length, "distinct outcome buckets"),
  ]));

  container.appendChild(el("div", { class: "section-title" }, "Status distribution"));
  const table = el("table", {}, [
    el("tr", {}, [el("th", {}, "Status"), el("th", {}, "Count"), el("th", {}, "% of batch")]),
    ...Object.entries(s.status_counts).map(([k, v]) =>
      el("tr", {}, [el("td", {}, pill(k)), el("td", {}, String(v)), el("td", {}, `${Math.round((v / s.total) * 100)}%`)])
    ),
  ]);
  container.appendChild(table);
}
function statCard(title, value, sub) {
  return el("div", { class: "card" }, [
    el("h3", {}, title),
    el("div", { class: "stat-value" }, String(value)),
    sub ? el("div", { class: "stat-sub" }, sub) : null,
  ]);
}

// --------------------------------------------------------- Enrichment ----
function renderEnrichment(container) {
  const examples = [
    { label: "Dishwasher (Frigidaire, verified)", desc: "PDSH4816AF Dishwasher SS - Display Only", mpn: "PDSH4816AF", manuf: "Appliance Dealers Cooperative (APPDE)" },
    { label: "Cut-off disc (Diablo)", desc: 'DBD090094101F Diablo 9" - Metal Cut-Off Disc', mpn: "DBD090094101F", manuf: "Freud Inc (2435)" },
    { label: "LED retrofit lamp (unseen text)", desc: '801274 15w LED 8" Retro 30k', mpn: "801274-X", manuf: "Phillips Lighting (5831)" },
    { label: "GFCI outlet (Leviton)", desc: "R92GFWT10KW 20A GFCI Outlet Wh", mpn: "R92GFWT10KW", manuf: "Leviton Mfg Co (4927)" },
  ];

  const descInput = el("input", { class: "search-input", placeholder: "Part_Desc, e.g. PDSH4816AF Dishwasher SS - Display Only", value: examples[0].desc });
  const mpnInput = el("input", { class: "search-input", placeholder: "Mfg_Part_Num (optional)", value: examples[0].mpn });
  const manufInput = el("input", { class: "search-input", placeholder: "Part_Manuf (optional)", value: examples[0].manuf });
  const resultBox = el("div", { id: "enrich-result" });

  const exampleRow = el("div", { style: "margin-bottom:14px" }, examples.map((ex) =>
    el("button", {
      class: "btn secondary", style: "margin-right:8px;margin-bottom:8px",
      onclick: () => { descInput.value = ex.desc; mpnInput.value = ex.mpn; manufInput.value = ex.manuf; runEnrich(); },
    }, ex.label)
  ));

  async function runEnrich() {
    resultBox.innerHTML = "";
    resultBox.appendChild(el("div", { class: "muted" }, "Running pipeline…"));
    try {
      const data = await api("/api/enrich-single", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ part_desc: descInput.value, mfg_part_num: mpnInput.value, part_manuf: manufInput.value }),
      });
      resultBox.innerHTML = "";
      resultBox.appendChild(recordDetailView(data));
    } catch (err) {
      resultBox.innerHTML = "";
      resultBox.appendChild(el("div", { class: "pill danger" }, "Error: " + err.message));
    }
  }

  container.appendChild(el("p", { class: "muted" }, "Type any raw product description — including one that has never been seen before — and watch it move through entity resolution, classification, extraction, normalization, validation, and grounded description generation."));
  container.appendChild(exampleRow);
  container.appendChild(descInput);
  container.appendChild(mpnInput);
  container.appendChild(manufInput);
  container.appendChild(el("div", { style: "margin:14px 0" }, el("button", { class: "btn", onclick: runEnrich }, "Run Enrichment Pipeline")));
  container.appendChild(resultBox);
  runEnrich();
}

function pipelineFlow(item) {
  const steps = [
    { label: "Clean", done: true },
    { label: "Entity Resolution", done: !!item.manufacturer },
    { label: "Classify", done: !!(item.classification && item.classification.classpath) },
    { label: "Extract", done: item.claims && item.claims.length > 0 },
    { label: "Normalize", done: item.claims && item.claims.some((c) => c.provenance_type === "NORMALIZED") },
    { label: "Validate", done: !!item.validation },
    { label: "Score", done: !!item.confidence },
    { label: "Review?", done: !!item.review },
  ];
  const nodes = [];
  steps.forEach((s, i) => {
    nodes.push(el("span", { class: `flow-step ${s.done ? "done" : ""}` }, s.label));
    if (i < steps.length - 1) nodes.push(el("span", { class: "flow-arrow" }, "→"));
  });
  return el("div", { class: "flow" }, nodes);
}

function recordDetailView(item) {
  const wrap = el("div", {});
  wrap.appendChild(pipelineFlow(item));
  wrap.appendChild(el("div", { class: "two-col", style: "margin-top:18px" }, [
    el("div", {}, [
      el("div", { class: "card" }, [
        el("h3", {}, "Identity"),
        el("dl", { class: "kv", style: "margin-top:10px" }, [
          el("dt", {}, "MPN"), el("dd", { class: "mono" }, item.mpn || "—"),
          el("dt", {}, "Manufacturer"), el("dd", {}, [
            item.manufacturer?.canonical_value || "—", " ",
            item.manufacturer ? pill(item.manufacturer.status) : null,
          ]),
          el("dt", {}, "Brand"), el("dd", {}, item.manufacturer?.brand_name || "—"),
          el("dt", {}, "Match method"), el("dd", { class: "mono badge-score" }, item.manufacturer?.method || "—"),
          el("dt", {}, "Classpath"), el("dd", {}, item.classification?.classpath || "—"),
          el("dt", {}, "Status"), el("dd", {}, pill(item.status)),
          el("dt", {}, "Confidence"), el("dd", {}, confBar(item.confidence?.overall)),
        ]),
      ]),
      el("div", { class: "card", style: "margin-top:16px" }, [
        el("h3", {}, "Resolution evidence"),
        el("ul", { class: "evidence-list" }, (item.manufacturer?.evidence || []).map((e) => el("li", {}, e))),
        el("ul", { class: "evidence-list" }, (item.classification?.evidence || []).map((e) => el("li", {}, e))),
      ]),
    ]),
    el("div", {}, [
      el("div", { class: "card" }, [
        el("h3", {}, "Generated descriptions"),
        ...(item.descriptions ? [
          descBlock("Invoice Desc", item.descriptions.invoice_desc, true),
          descBlock("Mobile Desc", item.descriptions.mobile_desc),
          descBlock("Product Title", item.descriptions.product_title),
          descBlock("Short Desc", item.descriptions.short_desc),
          descBlock("Long Desc", item.descriptions.long_desc),
        ] : [el("div", { class: "muted" }, "n/a")]),
      ]),
    ]),
  ]));

  wrap.appendChild(el("div", { class: "section-title" }, "Claims (attribute values, with provenance)"));
  wrap.appendChild(claimsTable(item.claims || []));

  if (item.validation) {
    wrap.appendChild(el("div", { class: "section-title" }, "Validation"));
    wrap.appendChild(el("div", {}, [
      pill(item.validation.passed ? "SUCCESS" : "VALIDATION_FAILED"),
      el("ul", { class: "evidence-list" }, item.validation.issues.map((i) =>
        el("li", {}, `[${i.severity}] ${i.check} — ${i.field || ""}: ${i.message}`)
      )),
    ]));
  }
  if (item.review && item.review.requires_review) {
    wrap.appendChild(el("div", { class: "section-title" }, "Review reasons"));
    wrap.appendChild(el("ul", { class: "evidence-list" }, item.review.reasons.map((r) => el("li", {}, `${r.code}: ${r.message}`))));
  }
  return wrap;
}

function descBlock(label, text, mono = false) {
  return el("div", { class: "desc-block" }, [
    el("div", { class: "desc-label" }, `${label} ${text ? `(${text.length} chars)` : ""}`),
    el("div", { class: `desc-text ${mono ? "invoice" : ""}` }, text || "—"),
  ]);
}

function claimsTable(claims) {
  if (!claims.length) return el("div", { class: "muted" }, "No grounded claims extracted for this record.");
  return el("table", { class: "claims-table" }, [
    el("tr", {}, [el("th", {}, "Attribute"), el("th", {}, "Value"), el("th", {}, "UOM"), el("th", {}, "Provenance"), el("th", {}, "Confidence"), el("th", {}, "Source")]),
    ...claims.filter((c) => c.value).map((c) =>
      el("tr", {}, [
        el("td", {}, c.attribute), el("td", {}, c.value), el("td", { class: "uom" }, c.uom || "—"),
        el("td", {}, el("span", { class: "tag" }, c.provenance_type)),
        el("td", {}, confBar(c.confidence)),
        el("td", { class: "mono muted" }, (c.source_ids || []).join(", ")),
      ])
    ),
  ]);
}

// -------------------------------------------------------------- Upload ---
function renderUpload(container) {
  const dz = el("div", { class: "dropzone" }, [
    el("div", {}, "Drop a CSV or XLSX file here, or"),
    el("div", { style: "margin-top:10px" }, el("input", { type: "file", id: "file-input", accept: ".csv,.xlsx" })),
  ]);
  const status = el("div", { style: "margin-top:16px" });
  container.appendChild(el("p", { class: "muted" }, "Upload the 1000-item sample, or any other CSV/XLSX with the same six input columns. Nothing about the pipeline is specific to this sample file."));
  container.appendChild(dz);
  container.appendChild(status);

  document.getElementById("file-input").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    status.innerHTML = "";
    status.appendChild(el("div", { class: "muted" }, "Uploading…"));
    const fd = new FormData();
    fd.append("file", file);
    try {
      const up = await api("/api/upload", { method: "POST", body: fd });
      state.uploadId = up.upload_id;
      updateRunIndicator();
      status.innerHTML = "";
      status.appendChild(el("div", {}, [
        el("div", { class: "pill success" }, "Uploaded"),
        ` ${up.filename} — ${up.rows} rows detected`,
      ]));
      status.appendChild(el("div", { style: "margin-top:12px" }, el("button", { class: "btn", onclick: () => processBatch(status) }, "Run Enrichment Pipeline on Full Batch")));
    } catch (err) {
      status.innerHTML = "";
      status.appendChild(el("div", { class: "pill danger" }, "Upload failed: " + err.message));
    }
  });
}

async function processBatch(status) {
  status.appendChild(el("div", { class: "muted", style: "margin-top:10px" }, "Processing… (classification, entity resolution, extraction, normalization, validation, scoring)"));
  try {
    const res = await api(`/api/process/${state.uploadId}`, { method: "POST" });
    state.summary = res.summary;
    updateRunIndicator();
    status.appendChild(el("div", { class: "card", style: "margin-top:14px" }, [
      el("h3", {}, "Batch complete"),
      el("div", { class: "stat-value" }, `${res.summary.total} products`),
      el("div", { class: "stat-sub" }, `${res.summary.processing_time_s}s · avg confidence ${Math.round(res.summary.avg_confidence * 100)}%`),
      el("div", { style: "margin-top:14px" }, [
        el("button", { class: "btn", onclick: () => downloadOutput("xlsx") }, "Download XLSX"),
        el("button", { class: "btn secondary", style: "margin-left:8px", onclick: () => downloadOutput("csv") }, "Download CSV"),
        el("button", { class: "btn secondary", style: "margin-left:8px", onclick: () => setView("dashboard") }, "View Dashboard"),
      ]),
    ]));
  } catch (err) {
    status.appendChild(el("div", { class: "pill danger", style: "margin-top:10px" }, "Processing failed: " + err.message));
  }
}
function downloadOutput(fmt) {
  window.location = `/api/download/${state.uploadId}?fmt=${fmt}`;
}

// -------------------------------------------------------------- Review ---
async function renderReview(container) {
  if (!state.uploadId) {
    container.appendChild(el("div", { class: "empty-state" }, "Upload and process a batch first."));
    return;
  }
  container.appendChild(el("div", { class: "muted" }, "Loading review queue…"));
  const data = await api(`/api/review-queue/${state.uploadId}?limit=100`);
  container.innerHTML = "";
  container.appendChild(el("p", { class: "muted" }, `${data.total} record(s) flagged for human review out of the processed batch.`));
  if (!data.total) {
    container.appendChild(el("div", { class: "empty-state" }, "Nothing needs review."));
    return;
  }
  const table = el("table", {}, [
    el("tr", {}, [el("th", {}, "MPN"), el("th", {}, "Description"), el("th", {}, "Manufacturer"), el("th", {}, "Reasons"), el("th", {}, "Confidence"), el("th", {}, "")]),
  ]);
  data.items.forEach((item) => {
    const detailRow = el("tr", { style: "display:none" }, el("td", { colspan: "6" }, recordDetailView(item)));
    const row = el("tr", {}, [
      el("td", { class: "mono" }, item.mpn),
      el("td", {}, item.part_desc),
      el("td", {}, item.manufacturer?.canonical_value || "—"),
      el("td", {}, (item.review?.reasons || []).map((r) => el("span", { class: "tag" }, r.code))),
      el("td", {}, confBar(item.confidence?.overall)),
      el("td", {}, el("button", { class: "btn secondary", onclick: () => { detailRow.style.display = detailRow.style.display === "none" ? "table-row" : "none"; } }, "Inspect")),
    ]);
    table.appendChild(row);
    table.appendChild(detailRow);
  });
  container.appendChild(table);
}

// ------------------------------------------------------------ Evidence ---
async function renderEvidence(container) {
  if (!state.uploadId) {
    container.appendChild(el("div", { class: "empty-state" }, "Upload and process a batch first, then search for a record here."));
    return;
  }
  const search = el("input", { class: "search-input", placeholder: "Search by MPN or description text…" });
  const results = el("div", {});
  container.appendChild(el("p", { class: "muted" }, "Inspect any record's full evidence trail: source claims, provenance, and match method."));
  container.appendChild(search);
  container.appendChild(results);

  let all = [];
  const data = await api(`/api/results/${state.uploadId}?limit=1000`);
  all = data.items;

  function renderList(items) {
    results.innerHTML = "";
    items.slice(0, 25).forEach((item) => {
      const box = el("div", { class: "card", style: "margin-bottom:10px;cursor:pointer" }, [
        el("div", {}, [el("span", { class: "mono" }, item.mpn), " — ", item.part_desc]),
        el("div", { style: "margin-top:6px" }, [pill(item.status), " ", item.manufacturer ? pill(item.manufacturer.status) : null]),
      ]);
      const detail = el("div", { style: "display:none;margin:0 0 20px" });
      box.addEventListener("click", () => {
        const showing = detail.style.display !== "none";
        detail.style.display = showing ? "none" : "block";
        if (!showing) { detail.innerHTML = ""; detail.appendChild(recordDetailView(item)); }
      });
      results.appendChild(box);
      results.appendChild(detail);
    });
    if (!items.length) results.appendChild(el("div", { class: "muted" }, "No matches."));
  }
  renderList(all);
  search.addEventListener("input", () => {
    const q = search.value.toLowerCase();
    renderList(all.filter((i) => (i.mpn || "").toLowerCase().includes(q) || (i.part_desc || "").toLowerCase().includes(q)));
  });
}

// --------------------------------------------------------- Evaluation ----
async function renderEvaluation(container) {
  container.appendChild(el("p", { class: "muted" }, "Runs the pipeline against the full sample input and scores it against the verified ground-truth delivery-format rows, plus batch-wide coverage/quality metrics that need no ground truth."));
  const btn = el("button", { class: "btn", onclick: run }, "Run Evaluation");
  const out = el("div", { style: "margin-top:18px" });
  container.appendChild(btn);
  container.appendChild(out);

  async function run() {
    out.innerHTML = "";
    out.appendChild(el("div", { class: "muted" }, "Running…"));
    const report = await api("/api/evaluate", { method: "POST" });
    out.innerHTML = "";
    out.appendChild(el("div", { class: "muted", style: "margin-bottom:14px" },
      `${report.total_rows} rows processed · ${report.ground_truth_rows_matched} matched against verified ground truth`));

    out.appendChild(el("div", { class: "section-title" }, "Field accuracy (verified ground truth)"));
    out.appendChild(el("table", {}, [
      el("tr", {}, [el("th", {}, "Field"), el("th", {}, "Correct / Total"), el("th", {}, "Accuracy")]),
      ...Object.entries(report.field_accuracy).map(([k, v]) =>
        el("tr", {}, [el("td", {}, k), el("td", {}, `${v.correct}/${v.total}`), el("td", {}, v.total ? `${Math.round(v.accuracy * 100)}%` : "n/a")])
      ),
    ]));

    out.appendChild(el("div", { class: "section-title" }, "Batch coverage & quality (full input)"));
    out.appendChild(el("table", {}, [
      el("tr", {}, [el("th", {}, "Metric"), el("th", {}, "Value")]),
      ...Object.entries(report.coverage).map(([k, v]) => el("tr", {}, [el("td", {}, k), el("td", {}, String(v))])),
    ]));

    out.appendChild(el("div", { class: "section-title" }, "Status distribution"));
    out.appendChild(el("table", {}, [
      el("tr", {}, [el("th", {}, "Status"), el("th", {}, "Count")]),
      ...Object.entries(report.status_counts).map(([k, v]) => el("tr", {}, [el("td", {}, pill(k)), el("td", {}, String(v))])),
    ]));
  }
}

// ------------------------------------------------------------- Health ----
async function renderHealth(container) {
  const data = await api("/api/system-health");
  container.appendChild(el("div", { class: "grid cols-3" }, [
    statCard("APP_MODE", data.app_mode),
    statCard("LLM Provider", data.llm_provider),
    statCard("Pipeline Version", data.pipeline_version),
    statCard("Manufacturer Master Rows", data.manufacturer_master_rows),
    statCard("Classpaths Supported", data.classpaths_supported),
    statCard("LOV Attribute Rows", data.lov_attribute_rows),
  ]));
  container.appendChild(el("div", { class: "section-title" }, "Design notes"));
  container.appendChild(el("div", { class: "card" }, el("p", {}, [
    "This build seeds its master data (manufacturer/brand, LOV, UOM, fractions) from the ",
    "provided 1000-item sample plus curated, documented public knowledge — the official ",
    "27,000-row UniCat manufacturer list and 161,000-row LOV file were not supplied. Drop them into ",
    el("code", {}, "data/reference/external/"), " and every loader in this codebase prefers them automatically ",
    "with zero code changes. See docs/design-decisions.md.",
  ])));
}

// -------------------------------------------------------------- Router ---
function render(view) {
  const container = document.getElementById("view-container");
  container.innerHTML = "";
  const wrap = el("div", { class: "view active" });
  container.appendChild(wrap);
  const fns = {
    dashboard: renderDashboard, enrichment: renderEnrichment, upload: renderUpload,
    review: renderReview, evidence: renderEvidence, evaluation: renderEvaluation, health: renderHealth,
  };
  fns[view](wrap);
}

async function init() {
  try {
    const h = await api("/api/health");
    document.getElementById("mode-pill").textContent = `mode: ${h.app_mode}`;
  } catch (e) { /* backend not reachable yet */ }
  updateRunIndicator();
  render("dashboard");
}
init();
