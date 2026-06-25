const $ = (sel) => document.querySelector(sel);

const inputText = $("#inputText");
const wordCount = $("#wordCount");
const btnQuick = $("#btnQuick");
const btnDeep = $("#btnDeep");
const btnClear = $("#btnClear");
const scanLine = $("#scanLine");
const results = $("#results");
const emptyState = $("#emptyState");
const scanner = $("#scanner");
const scanHint = $("#scanHint");

const aiPct = $("#aiPct");
const gaugeFill = $("#gaugeFill");
const verdictBadge = $("#verdictBadge");
const verdictCopy = $("#verdictCopy");
const scanMode = $("#scanMode");
const surfaceScore = $("#surfaceScore");
const confidence = $("#confidence");
const deepCard = $("#deepCard");
const binoculars = $("#binoculars");
const logPpl = $("#logPpl");
const binoLabel = $("#binoLabel");
const pplLabel = $("#pplLabel");
const deepWarning = $("#deepWarning");
const signalsEl = $("#signals");
const disclaimer = $("#disclaimer");

const GAUGE_ARC = 251.2;

const VERDICT_COPY = {
  likely_human: "Few AI surface patterns and statistical signals point toward human authorship.",
  uncertain: "Mixed signals — could be edited human prose or polished AI output. Read critically.",
  likely_ai: "Multiple AI tells detected. Still not proof — use judgment.",
};

function countWords(text) {
  const m = text.trim().match(/\b\w+(?:'\w+)?\b/g);
  return m ? m.length : 0;
}

function updateWordCount() {
  const n = countWords(inputText.value);
  wordCount.textContent = `${n} word${n === 1 ? "" : "s"}`;
  if (n > 0 && n < 100) {
    wordCount.style.color = "var(--amber)";
  } else {
    wordCount.style.color = "";
  }
}

function setScanning(on) {
  scanner.classList.toggle("is-scanning", on);
  scanLine.classList.toggle("active", on);
  btnQuick.disabled = on;
  btnDeep.disabled = on;
}

function gaugeColor(pct) {
  if (pct < 35) return "#3dd68c";
  if (pct < 60) return "#f5b942";
  return "#ff6b4a";
}

function setGauge(pct) {
  const clamped = Math.max(0, Math.min(100, pct));
  const offset = GAUGE_ARC - (GAUGE_ARC * clamped) / 100;
  gaugeFill.style.strokeDashoffset = String(offset);
  gaugeFill.style.stroke = gaugeColor(clamped);
  aiPct.textContent = `${Math.round(clamped)}%`;
  aiPct.style.color = gaugeColor(clamped);
}

function verdictClass(v) {
  if (v === "likely_human") return "verdict__badge--human";
  if (v === "likely_ai") return "verdict__badge--ai";
  return "verdict__badge--uncertain";
}

function verdictLabel(v) {
  const map = {
    likely_human: "Likely human",
    uncertain: "Uncertain",
    likely_ai: "Likely AI",
  };
  return map[v] || v;
}

function renderSignals(signals) {
  signalsEl.innerHTML = signals
    .map(
      (s) => `
    <div class="signal ${s.triggered ? "signal--on" : ""}">
      <div class="signal__head">
        <span class="signal__name">${escapeHtml(s.label)}</span>
        <span class="signal__dot" title="${s.triggered ? "Triggered" : "Clear"}"></span>
      </div>
      <p class="signal__detail">${escapeHtml(s.detail)}</p>
    </div>`
    )
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderReport(report) {
  emptyState.hidden = true;
  results.hidden = false;

  setGauge(report.ai_likelihood_pct);

  verdictBadge.textContent = verdictLabel(report.overall_verdict);
  verdictBadge.className = `verdict__badge ${verdictClass(report.overall_verdict)}`;
  verdictCopy.textContent = VERDICT_COPY[report.overall_verdict] || "";

  scanMode.textContent = report.scan_mode === "full" ? "Quick + Deep" : "Quick only";
  surfaceScore.textContent = `${report.surface_score}/100 (${report.surface_verdict})`;
  confidence.textContent = report.confidence;

  renderSignals(report.signals);
  disclaimer.textContent = report.disclaimer;

  if (report.deep) {
    deepCard.hidden = false;
    binoculars.textContent = report.deep.binoculars;
    logPpl.textContent = report.deep.log_perplexity;
    binoLabel.textContent = report.deep.binoculars_label;
    pplLabel.textContent = report.deep.perplexity_label;
    if (report.deep.warning) {
      deepWarning.hidden = false;
      deepWarning.textContent = report.deep.warning;
    } else {
      deepWarning.hidden = true;
    }
  } else {
    deepCard.hidden = true;
  }
}

async function runScan(mode) {
  const text = inputText.value.trim();
  if (!text) {
    scanHint.textContent = "Paste some text first.";
    scanHint.style.color = "var(--coral)";
    return;
  }

  setScanning(true);
  scanHint.textContent =
    mode === "quick"
      ? "Running surface scan…"
      : "Loading models & running deep scan — this may take a while on CPU…";
  scanHint.style.color = "";

  try {
    const res = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode: mode === "deep" ? "full" : "quick" }),
    });
    const data = await res.json();
    if (!res.ok) {
      const d = data.detail;
      const msg = Array.isArray(d) ? d.map((x) => x.msg || x).join("; ") : d;
      throw new Error(msg || "Scan failed");
    }
    renderReport(data.report);
    scanHint.textContent =
      mode === "quick"
        ? "Quick scan done. Try Deep scan for statistical analysis."
        : "Full scan complete.";
  } catch (err) {
    scanHint.textContent = err.message || "Something went wrong.";
    scanHint.style.color = "var(--coral)";
  } finally {
    setScanning(false);
  }
}

btnQuick.addEventListener("click", () => runScan("quick"));
btnDeep.addEventListener("click", () => runScan("deep"));

btnClear.addEventListener("click", () => {
  inputText.value = "";
  updateWordCount();
  results.hidden = true;
  emptyState.hidden = false;
  scanHint.textContent =
    "Quick scan is instant. Deep scan loads local GPT-2 models (~1.5 GB) and may take 10–30s on CPU.";
  scanHint.style.color = "";
});

inputText.addEventListener("input", updateWordCount);

// SVG gradient for gauge (injected once)
const svg = document.querySelector(".gauge__svg");
if (svg && !svg.querySelector("defs")) {
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  defs.innerHTML = `<linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
    <stop offset="0%" stop-color="#3dd68c"/>
    <stop offset="50%" stop-color="#f5b942"/>
    <stop offset="100%" stop-color="#ff6b4a"/>
  </linearGradient>`;
  svg.prepend(defs);
}

updateWordCount();

async function initSiteMode() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.quick_only) {
      btnDeep.hidden = true;
      scanHint.textContent =
        "Quick scan only on the public site — instant, no downloads. Statistical deep scan is for local/self-hosted use.";
      const deepHow = document.querySelector(".how__card:nth-child(2) p");
      if (deepHow) {
        deepHow.textContent =
          "Binoculars cross-perplexity (optional, self-hosted). Disabled on the free public site to keep hosting costs near zero.";
      }
    }
  } catch {
    /* offline / static preview */
  }
}

initSiteMode();
