/** Browser-side quick scan (mirrors heuristics.py). No server required. */

const BUZZWORDS = new Set([
  "crucial", "delve", "delves", "delving", "tapestry", "landscape", "testament",
  "underscores", "underscore", "foster", "fosters", "fostering", "navigate",
  "navigates", "multifaceted", "robust", "comprehensive", "intricate",
  "pivotal", "seamless", "seamlessly", "ever-evolving", "game-changer",
  "holistic", "synergy", "leverage", "leveraging", "utilize", "utilizes",
  "realm", "embark", "embarks", "beacon", "bustling", "vibrant",
  "nuanced", "commendable", "noteworthy", "groundbreaking", "cutting-edge",
  "spearhead", "spearheaded", "myriad", "plethora", "interplay",
  "showcase", "showcases", "elevate", "elevates",
]);

const SIGNPOST_PATTERNS = [
  /\bit'?s important to note\b/gi,
  /\bit is worth noting\b/gi,
  /\bin today'?s (?:world|landscape|society|age)\b/gi,
  /\bin conclusion\b/gi,
  /\bto summarize\b/gi,
  /\bfurthermore\b/gi,
  /\bmoreover\b/gi,
  /\badditionally\b/gi,
  /\bthat said\b/gi,
  /\bon the other hand\b/gi,
  /\bas we (?:have )?seen\b/gi,
  /\blet'?s (?:dive|delve) (?:in|into)\b/gi,
  /\bplays a (?:crucial|vital|key|pivotal) role\b/gi,
  /\ba testament to\b/gi,
  /\bnot only .{3,40} but also\b/gi,
  /\bhere'?s (?:the thing|why|how)\b/gi,
  /\bthe bottom line\b/gi,
];

const RULE_OF_THREE = [
  /\b\w+,\s+\w+,\s+and\s+\w+/gi,
  /\bwhether\s+\w[\w\s]{0,25},\s+\w[\w\s]{0,25},\s+or\s+\w/gi,
];

const SIGNAL_LABELS = {
  em_dashes: "Em dashes",
  rule_of_three: "Rule of three",
  buzzwords: "AI buzzwords",
  signpost_phrases: "Signpost phrases",
  uniform_sentences: "Uniform rhythm",
  list_heavy: "List-heavy",
  generic_opener: "Generic opener",
  colon_opener: "Colon explanations",
  rhetorical_questions: "Rhetorical questions",
};

function wordCount(text) {
  const m = text.match(/\b\w+(?:'\w+)?\b/g);
  return m ? m.length : 0;
}

function countMatches(patterns, text) {
  let n = 0;
  for (const p of patterns) {
    const re = new RegExp(p.source, p.flags);
    const hits = text.match(re);
    if (hits) n += hits.length;
  }
  return n;
}

function countEmDashes(text) {
  const unicode = (text.match(/[\u2014\u2013]/g) || []).length;
  const doubled = (text.match(/(?<!\w)--(?!\w)/g) || []).length;
  return unicode + doubled;
}

function buzzwordHits(text) {
  const words = text.toLowerCase().match(/\b[a-z][a-z'-]*\b/g) || [];
  const found = [...new Set(words.filter((w) => BUZZWORDS.has(w)))].sort();
  return found;
}

function sentenceCv(text) {
  const sentences = text.split(/(?<=[.!?])\s+/).filter((s) => s.trim());
  const lengths = sentences.map((s) => s.split(/\s+/).filter(Boolean).length).filter((n) => n > 0);
  if (lengths.length < 3) return { cv: 0, detail: "too few sentences to measure rhythm" };
  const mean = lengths.reduce((a, b) => a + b, 0) / lengths.length;
  const variance = lengths.reduce((a, l) => a + (l - mean) ** 2, 0) / lengths.length;
  const cv = Math.sqrt(variance) / mean;
  return { cv, detail: `sentence length CV=${cv.toFixed(2)} (low < 0.35 often feels machine-smooth)` };
}

function overallVerdict(aiPct) {
  if (aiPct < 30) return ["likely_human", "low"];
  if (aiPct < 55) return ["uncertain", "medium"];
  if (aiPct < 75) return ["likely_ai", "medium"];
  return ["likely_ai", "high"];
}

export function quickCheck(text) {
  text = text.trim();
  const wc = wordCount(text);
  if (!wc) {
    return buildReport(0, "low", [], 0, "low");
  }

  const signals = [];

  const emCount = countEmDashes(text);
  const emPer100 = (emCount / wc) * 100;
  signals.push({
    id: "em_dashes",
    label: SIGNAL_LABELS.em_dashes,
    count: emCount,
    weight: 18,
    triggered: emCount >= 2 && emPer100 >= 1,
    detail: `${emCount} em/en dash(es) (${emPer100.toFixed(1)} per 100 words)`,
  });

  const tripleCount = countMatches(RULE_OF_THREE, text);
  signals.push({
    id: "rule_of_three",
    label: SIGNAL_LABELS.rule_of_three,
    count: tripleCount,
    weight: 15,
    triggered: tripleCount >= 2,
    detail: `${tripleCount} rule-of-three list pattern(s) (e.g. 'X, Y, and Z')`,
  });

  const buzz = buzzwordHits(text);
  let buzzDetail = `${buzz.length} AI-era buzzword(s)`;
  if (buzz.length) buzzDetail += `: ${buzz.slice(0, 6).join(", ")}${buzz.length > 6 ? ", …" : ""}`;
  signals.push({
    id: "buzzwords",
    label: SIGNAL_LABELS.buzzwords,
    count: buzz.length,
    weight: 12,
    triggered: buzz.length >= 2,
    detail: buzzDetail,
  });

  let signpostN = 0;
  for (const p of SIGNPOST_PATTERNS) {
    const re = new RegExp(p.source, p.flags);
    signpostN += (text.match(re) || []).length;
  }
  signals.push({
    id: "signpost_phrases",
    label: SIGNAL_LABELS.signpost_phrases,
    count: signpostN,
    weight: 14,
    triggered: signpostN >= 2,
    detail: `${signpostN} essay-like transition(s) (furthermore, in conclusion, …)`,
  });

  const { cv, detail: cvDetail } = sentenceCv(text);
  const sentenceN = text.split(/(?<=[.!?])\s+/).filter((s) => s.trim()).length;
  signals.push({
    id: "uniform_sentences",
    label: SIGNAL_LABELS.uniform_sentences,
    count: sentenceN,
    weight: 10,
    triggered: sentenceN >= 4 && cv < 0.35,
    detail: cvDetail,
  });

  const listBlocks = (text.match(/(?:^|\n)\s*(?:\d+[.)]|[-*•])\s+\S/gm) || []).length;
  signals.push({
    id: "list_heavy",
    label: SIGNAL_LABELS.list_heavy,
    count: listBlocks,
    weight: 8,
    triggered: listBlocks >= 3,
    detail: `${listBlocks} list item line(s)`,
  });

  const windup = /^(?:In (?:today's|the|an)|Throughout history|Since the dawn|When it comes to|In recent years)/i.test(text);
  signals.push({
    id: "generic_opener",
    label: SIGNAL_LABELS.generic_opener,
    count: windup ? 1 : 0,
    weight: 8,
    triggered: windup,
    detail: windup ? "starts with a broad, essay-style opener" : "no generic opener",
  });

  const colonOpeners = (text.match(/\b\w[\w\s]{0,20}:\s/g) || []).length;
  signals.push({
    id: "colon_opener",
    label: SIGNAL_LABELS.colon_opener,
    count: colonOpeners,
    weight: 7,
    triggered: colonOpeners >= 3,
    detail: `${colonOpeners} clause(s) leading with a colon setup`,
  });

  const rhetQ = (text.match(/\?/g) || []).length;
  signals.push({
    id: "rhetorical_questions",
    label: SIGNAL_LABELS.rhetorical_questions,
    count: rhetQ,
    weight: 6,
    triggered: rhetQ >= 2 && wc >= 80,
    detail: `${rhetQ} question mark(s) in text`,
  });

  const maxPts = signals.reduce((a, s) => a + s.weight, 0);
  const earned = signals.filter((s) => s.triggered).reduce((a, s) => a + s.weight, 0);
  const surfaceScore = maxPts ? Math.min(100, (earned / maxPts) * 100) : 0;
  let surfaceVerdict = "low";
  if (surfaceScore >= 55) surfaceVerdict = "high";
  else if (surfaceScore >= 25) surfaceVerdict = "medium";

  return buildReport(wc, surfaceScore, signals, surfaceScore, surfaceVerdict);
}

function buildReport(wc, aiPct, signals, surfaceScore, surfaceVerdict) {
  const rounded = Math.round(aiPct * 10) / 10;
  const [overall, confidence] = overallVerdict(rounded);
  return {
    word_count: wc,
    surface_score: rounded,
    surface_verdict: surfaceVerdict,
    ai_likelihood_pct: rounded,
    human_likelihood_pct: Math.round((100 - rounded) * 10) / 10,
    overall_verdict: overall,
    confidence,
    signals: signals.map(({ id, label, triggered, count, detail }) => ({
      id, label, triggered, count, detail,
    })),
    scan_mode: "quick",
    disclaimer:
      "Heuristic signals only — not proof. Em dashes and polished prose appear in human writing too. Runs in your browser; nothing is uploaded.",
  };
}

export function toApiShape(report) {
  return { ok: true, report };
}
