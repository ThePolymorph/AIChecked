import { quickCheck } from "./heuristics.js?v=5";

const $ = (sel) => document.querySelector(sel);

const inputText = $("#inputText");
const wordCount = $("#wordCount");
const btnQuick = $("#btnQuick");
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
const signalsEl = $("#signals");
const disclaimer = $("#disclaimer");

const GAUGE_ARC = 251.2;

const VERDICT_COPY = {
  likely_human: "Some surface patterns lean human — still not proof, especially on short or literary text.",
  uncertain: "Mixed or weak signals — could be human, could be polished AI (Claude, GPT-4). Read critically.",
  uncertain_low:
    "Very few patterns detected — polished AI often scores this low. Not enough signal to call it human.",
  likely_ai: "Multiple AI surface patterns detected. Still not proof — use judgment.",
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
}

function gaugeColor(pct) {
  if (pct < 25) return "#f5b942";
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

function verdictLabel(v, conf) {
  if (v === "uncertain" && conf === "low") return "Uncertain (low confidence)";
  return { likely_human: "Likely human", uncertain: "Uncertain", likely_ai: "Likely AI" }[v] || v;
}

function verdictCopyKey(v, conf) {
  if (v === "uncertain" && conf === "low") return "uncertain_low";
  return v;
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
  verdictBadge.textContent = verdictLabel(report.overall_verdict, report.confidence);
  verdictBadge.className = `verdict__badge ${verdictClass(report.overall_verdict)}`;
  verdictCopy.textContent = VERDICT_COPY[verdictCopyKey(report.overall_verdict, report.confidence)] || "";
  scanMode.textContent = "In-browser";
  surfaceScore.textContent = `${report.surface_score}/100 (${report.surface_verdict})`;
  confidence.textContent = report.confidence;
  renderSignals(report.signals);
  disclaimer.textContent = report.disclaimer;
  if (deepCard) deepCard.hidden = true;
}

function runQuickScan() {
  const text = inputText.value.trim();
  if (!text) {
    scanHint.textContent = "Paste some text first.";
    scanHint.style.color = "var(--coral)";
    return;
  }
  setScanning(true);
  scanHint.textContent = "Scanning…";
  scanHint.style.color = "";
  requestAnimationFrame(() => {
    try {
      renderReport(quickCheck(text));
      scanHint.textContent = "Done. Text never left your device.";
      if (typeof gtag === "function") {
        gtag("event", "scan_complete", {
          word_count: countWords(text),
          event_category: "engagement",
        });
      }
    } catch (err) {
      scanHint.textContent = err.message || "Scan failed.";
      scanHint.style.color = "var(--coral)";
    } finally {
      setScanning(false);
    }
  });
}

btnQuick.addEventListener("click", runQuickScan);

btnClear.addEventListener("click", () => {
  inputText.value = "";
  updateWordCount();
  results.hidden = true;
  emptyState.hidden = false;
  scanHint.textContent = "Runs in your browser — instant and private. Surface patterns only; polished AI may slip through.";
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

updateWordCount();
