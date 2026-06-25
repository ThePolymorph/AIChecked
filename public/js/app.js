import { quickCheck } from "./heuristics.js?v=11";

const $ = (sel) => document.querySelector(sel);

const MAX_WORDS = 5000;

const inputText = $("#inputText");
const textareaWrap = $("#textareaWrap");
const wordCount = $("#wordCount");
const btnQuick = $("#btnQuick");
const btnClear = $("#btnClear");
const btnCopyPrompt = $("#btnCopyPrompt");
const copyPromptFeedback = $("#copyPromptFeedback");
const scanLine = $("#scanLine");
const results = $("#results");
const emptyState = $("#emptyState");
const scanner = $("#scanner");
const scanHint = $("#scanHint");

const shareFeedback = $("#shareFeedback");

const SHARE_PAGE_URL = "https://aichecked.com/#humanizer-prompt";
const SHARE_TEXT =
  "Free LLM humaniser prompt — paste into ChatGPT or Claude before you write. Helps drafts read more human. Then check at AIChecked.com.";

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

/** Plain-text version of the humanizer prompt for clipboard */
const HUMANIZER_PROMPT_PLAIN = `Write in a natural human voice. Follow every rule:

- Use contractions where a real person would (don't, can't, it's).
- Vary sentence length. Mix short lines with longer ones.
- No parallel lists of three (avoid "fast, reliable, and scalable").
- Skip AI buzzwords: delve, landscape, crucial, seamless, foster, leverage, pivotal, tapestry, multifaceted, palpable.
- No essay transitions: furthermore, moreover, in conclusion, it's important to note.
- Limit em dashes. Prefer commas or a new sentence.
- Avoid participial tag-ons (, watching the tide, , feeling the weight).
- Avoid filler like "the way she", "as if", and "something about".
- No throat-clearing openers (In today's world, Throughout history).
- Don't stack sentences that all start the same way. Avoid line after line opening with Sometimes, Often, And, But, or So.
- Drop the reader into a scene with "you" or "I", not only flat observations about "they" or "it".
- Use specific details (a grey tabby, two seconds, the top of the fridge) instead of tidy generic similes.
- Plain doesn't mean every line is a short subject-verb sentence. One longer, messier sentence is fine.

When done, check the draft at AIChecked.com before you submit.`;

const VERDICT_COPY = {
  likely_human: "Some surface patterns lean human. Still not proof, especially on short or literary text.",
  uncertain: "Mixed or weak signals. Could be human, could be polished AI (Claude, GPT-4). Read critically.",
  uncertain_low:
    "Very few patterns detected. Polished AI often scores this low. Not enough signal to call it human.",
  likely_ai: "Multiple AI surface patterns detected. Still not proof. Use judgement.",
};

function countWords(text) {
  const m = text.trim().match(/\b\w+(?:'\w+)?\b/g);
  return m ? m.length : 0;
}

function truncateToMaxWords(text, maxWords) {
  const re = /\b\w+(?:'\w+)?\b/g;
  let match;
  let count = 0;
  let cutAt = text.length;
  while ((match = re.exec(text)) !== null) {
    count += 1;
    if (count === maxWords) cutAt = re.lastIndex;
    if (count > maxWords) break;
  }
  if (count <= maxWords) return text;
  return text.slice(0, cutAt).trimEnd();
}

function updateWordCount() {
  const n = countWords(inputText.value);
  const atLimit = n >= MAX_WORDS;
  const shortWarn = n > 0 && n < 100;

  wordCount.textContent = `${n.toLocaleString()} / ${MAX_WORDS.toLocaleString()} words`;
  wordCount.classList.toggle("word-count--limit", atLimit);
  wordCount.classList.toggle("word-count--warn", shortWarn && !atLimit);

  textareaWrap?.classList.toggle("textarea-wrap--at-limit", atLimit);
  btnQuick.disabled = n === 0;
}

function enforceWordLimit() {
  const truncated = truncateToMaxWords(inputText.value, MAX_WORDS);
  if (truncated !== inputText.value) {
    inputText.value = truncated;
    scanHint.textContent = `Limited to ${MAX_WORDS.toLocaleString()} words for in-browser scanning.`;
    scanHint.style.color = "var(--amber)";
  }
  updateWordCount();
}

function setScanning(on) {
  scanner.classList.toggle("is-scanning", on);
  scanLine.classList.toggle("active", on);
  btnQuick.disabled = on || countWords(inputText.value) === 0;
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
        ${
          s.tooltip
            ? `<button type="button" class="signal__help" aria-label="About ${escapeHtml(s.label)}">
            <span class="signal__help-icon" aria-hidden="true">?</span>
            <span class="signal__tooltip" role="tooltip">${escapeHtml(s.tooltip)}</span>
          </button>`
            : ""
        }
        <span class="signal__dot" aria-hidden="true"></span>
      </div>
      <p class="signal__detail">${escapeHtml(s.detail)}</p>
    </div>`
    )
    .join("");
  bindSignalTooltips();
}

function bindSignalTooltips() {
  signalsEl.querySelectorAll(".signal__help").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const wasOpen = btn.classList.contains("is-open");
      signalsEl.querySelectorAll(".signal__help.is-open").forEach((b) => b.classList.remove("is-open"));
      if (!wasOpen) btn.classList.add("is-open");
    };
  });
}

document.addEventListener("click", () => {
  signalsEl?.querySelectorAll(".signal__help.is-open").forEach((b) => b.classList.remove("is-open"));
});

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

function trackEvent(name, params = {}) {
  if (typeof gtag === "function") {
    gtag("event", name, { event_category: "engagement", ...params });
  }
}

function runQuickScan() {
  const text = inputText.value.trim();
  if (!text) {
    scanHint.textContent = "Paste some text first.";
    scanHint.style.color = "var(--coral)";
    return;
  }
  const wc = countWords(text);
  if (wc > MAX_WORDS) {
    scanHint.textContent = `Text exceeds ${MAX_WORDS.toLocaleString()} words.`;
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
      trackEvent("scan_complete", { word_count: wc });
    } catch (err) {
      scanHint.textContent = err.message || "Scan failed.";
      scanHint.style.color = "var(--coral)";
    } finally {
      setScanning(false);
    }
  });
}

async function copyHumanizerPrompt() {
  try {
    await navigator.clipboard.writeText(HUMANIZER_PROMPT_PLAIN);
    copyPromptFeedback.hidden = false;
    copyPromptFeedback.textContent = "Copied!";
    trackEvent("copy_humanizer_prompt", { prompt_name: "surface_humanizer_v1" });
    setTimeout(() => {
      copyPromptFeedback.hidden = true;
    }, 2500);
  } catch {
    copyPromptFeedback.hidden = false;
    copyPromptFeedback.textContent = "Select the quote and copy manually.";
    trackEvent("copy_humanizer_prompt_failed");
  }
}

function showShareFeedback(msg) {
  if (!shareFeedback) return;
  shareFeedback.textContent = msg;
  shareFeedback.hidden = false;
  setTimeout(() => {
    shareFeedback.hidden = true;
  }, 2500);
}

function initShareLinks() {
  const encUrl = encodeURIComponent(SHARE_PAGE_URL);
  const encText = encodeURIComponent(SHARE_TEXT);

  const facebook = $("#shareFacebook");
  const x = $("#shareX");
  const linkedin = $("#shareLinkedIn");
  const whatsapp = $("#shareWhatsApp");
  const instagram = $("#shareInstagram");

  if (facebook) {
    facebook.href = `https://www.facebook.com/sharer/sharer.php?u=${encUrl}`;
    facebook.addEventListener("click", () => trackEvent("share_social", { platform: "facebook" }));
  }
  if (x) {
    x.href = `https://twitter.com/intent/tweet?url=${encUrl}&text=${encText}`;
    x.addEventListener("click", () => trackEvent("share_social", { platform: "x" }));
  }
  if (linkedin) {
    linkedin.href = `https://www.linkedin.com/sharing/share-offsite/?url=${encUrl}`;
    linkedin.addEventListener("click", () => trackEvent("share_social", { platform: "linkedin" }));
  }
  if (whatsapp) {
    whatsapp.href = `https://wa.me/?text=${encText}%20${encUrl}`;
    whatsapp.addEventListener("click", () => trackEvent("share_social", { platform: "whatsapp" }));
  }
  if (instagram) {
    instagram.addEventListener("click", async () => {
      const clip = `${SHARE_TEXT} ${SHARE_PAGE_URL}`;
      try {
        await navigator.clipboard.writeText(clip);
        showShareFeedback("Link copied for Instagram");
        trackEvent("share_social", { platform: "instagram", method: "copy_link" });
      } catch {
        showShareFeedback("Copy the link from your browser bar");
        trackEvent("share_social", { platform: "instagram", method: "copy_failed" });
      }
    });
  }
}

btnQuick.addEventListener("click", runQuickScan);
btnCopyPrompt?.addEventListener("click", copyHumanizerPrompt);

btnClear.addEventListener("click", () => {
  inputText.value = "";
  updateWordCount();
  results.hidden = true;
  emptyState.hidden = false;
  scanHint.textContent = "Runs in your browser. Instant and private. Surface patterns only; polished AI may slip through.";
  scanHint.style.color = "";
});

inputText.addEventListener("input", enforceWordLimit);

inputText.addEventListener("paste", () => {
  requestAnimationFrame(enforceWordLimit);
});

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
initShareLinks();
