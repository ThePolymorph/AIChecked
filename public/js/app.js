import { quickCheck, toApiShape } from "./heuristics.js";

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
  likely_human: "Few AI surface patterns detected. Still not proof of human authorship.",
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
  wordCount.style.color = n > 0 && n < 100 ? "var(--amber)" : "";
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
  gaugeFill.style.strokeDashoffset = String(GAUGE_ARC - (GAUGE_ARC * clamped) / 100);
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
  return { likely_human: "Likely human", uncertain: "Uncertain", likely_ai: "Likely AI" }[v] || v;
}

function renderSignals(signals) {
  signalsEl.innerHTML = signals
    .map(
      (s) => `
    <div class="signal ${s.triggered ? "signal--on" : ""}">
      <div class="signal__head">
        <span class="signal__name">${escapeHtml(s.label)}</span>
        <span class="signal__dot"></span>
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
  scanMode.textContent = "In-browser";
  surfaceScore.textContent = `${report.surface_score}/100 (${report.surface_verdict})`;
  confidence.textContent = report.confidence;
  renderSignals(report.signals);
  disclaimer.textContent = report.disclaimer;
  deepCard.hidden = true;
}

async function parseJsonResponse(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("Server returned an invalid response.");
  }
}

function runQuickScan() {
  const text = inputText.value.trim();
  if (!text) {
    scanHint.textContent = "Paste some text first.";
    scanHint.style.color = "var(--coral)";
    return;
  }
  setScanning(true);
  scanHint.textContent = "Running surface scan in your browser…";
  scanHint.style.color = "";
  requestAnimationFrame(() => {
    try {
      renderReport(quickCheck(text));
      scanHint.textContent = "Scan complete. Text never left your device.";
    } catch (err) {
      scanHint.textContent = err.message || "Scan failed.";
      scanHint.style.color = "var(--coral)";
    } finally {
      setScanning(false);
    }
  });
}

async function runDeepScan() {
  const text = inputText.value.trim();
  if (!text) {
    scanHint.textContent = "Paste some text first.";
    scanHint.style.color = "var(--coral)";
    return;
  }
  setScanning(true);
  scanHint.textContent = "Contacting deep scan API…";
  try {
    const res = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode: "full" }),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || "Deep scan unavailable");
    renderReport(data.report);
  } catch (err) {
    scanHint.textContent =
      err.message || "Deep scan requires self-hosted deployment. Quick scan runs locally in your browser.";
    scanHint.style.color = "var(--coral)";
  } finally {
    setScanning(false);
  }
}

btnQuick.addEventListener("click", runQuickScan);
btnDeep.addEventListener("click", runDeepScan);

btnClear.addEventListener("click", () => {
  inputText.value = "";
  updateWordCount();
  results.hidden = true;
  emptyState.hidden = false;
  scanHint.textContent = "Quick scan runs in your browser — instant, private, no server needed.";
  scanHint.style.color = "";
});

inputText.addEventListener("input", updateWordCount);

const svg = document.querySelector(".gauge__svg");
if (svg && !svg.querySelector("defs")) {
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  defs.innerHTML = `<linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
    <stop offset="0%" stop-color="#3dd68c"/>
    <stop offset="50%" stop-color="#f5b942"/>
    <stop offset="100%" stop-color="#ff6b4c"/>
  </linearGradient>`;
  svg.prepend(defs);
}

// Public site: quick scan is client-side; hide deep scan on Vercel/static hosts
btnDeep.hidden = true;
scanHint.textContent = "Quick scan runs in your browser — instant, private, no server needed.";
const deepHow = document.querySelector(".how__card:nth-child(2) p");
if (deepHow) {
  deepHow.textContent =
    "Binoculars statistical scan is available when you self-host the Python stack locally — not on the free static site.";
}

updateWordCount();
