/** Browser-side quick scan. Tuned for literary LLM prose (Claude, ChatGPT, etc.). */

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
  // Claude / literary LLM register
  "palpable", "liminal", "etched", "weathered", "gilded", "nested",
  "unmistakable", "quietly", "gently", "tender", "stillness", "threshold",
  "particular", "increasingly", "genuine", "resonance", "poignant",
  "atmospheric", "textured", "luminous", "hushed", "crystalline",
]);

const LITERARY_PATTERNS = [
  { id: "the_way", re: /\bthe way\b/gi, label: "'The way…' phrasing" },
  { id: "as_if", re: /\bas if\b/gi, label: "'As if' constructions" },
  { id: "something_about", re: /\bsomething (?:about|in|between)\b/gi, label: "'Something about…'" },
  { id: "present_participle", re: /,\s+[a-z]+ing\b/gi, label: "Participial phrases (, watching…)" },
];

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
  literary_phrasing: "Literary LLM phrasing",
  low_contractions: "Formal / no contractions",
  participial_chains: "Participial chains",
  artificial_simplicity: "Artificial simplicity",
};

const SIGNAL_TOOLTIPS = {
  em_dashes:
    "Counts long dashes (the — character), en dashes, and double hyphens (--). ChatGPT and Claude often use them more than typical human drafts.",
  rule_of_three:
    "Parallel lists of three items, like fast, clear, and compelling. A common rhetorical pattern in LLM writing.",
  buzzwords:
    "Words overused in AI-era prose: delve, landscape, crucial, seamless, palpable, and similar.",
  signpost_phrases:
    "Essay-style transitions such as furthermore, in conclusion, and it's important to note.",
  uniform_sentences:
    "When sentence lengths stay very similar throughout. LLM prose often has a smooth, even rhythm.",
  list_heavy:
    "Many numbered or bulleted lines. LLMs frequently produce structured outlines.",
  generic_opener:
    "Opens with a broad setup, such as In today's world or Throughout history.",
  colon_opener:
    "Clauses that introduce a colon, then explain. Common in explanatory AI text.",
  rhetorical_questions:
    "Multiple questions in the passage. Sometimes used for fake engagement in AI drafts.",
  literary_phrasing:
    "Phrases like the way, as if, and something about. Frequent in polished Claude-style narrative.",
  low_contractions:
    "Very few informal contractions (don't, can't, it's) in longer text. LLMs often write more formally.",
  participial_chains:
    "Trailing phrases like , watching the tide or , feeling the air. Common in literary AI prose.",
  artificial_simplicity:
    "Many short chatty lines opening with Sometimes, Often, And, But, or So. Humanised drafts often overdo plain subject-verb sentences.",
};

const CONTRACTIONS =
  /\b(?:don't|won't|can't|it's|that's|there's|I'm|I've|you're|they're|we're|isn't|aren't|wasn't|weren't|doesn't|didn't|haven't|hasn't|couldn't|wouldn't|shouldn't|I'll|we'll|she's|he's)\b/gi;

const CHATTY_STARTERS = /^(?:Sometimes|Often|Usually|Generally|Typically|And|But|So|Then|Also|Maybe|Perhaps|Honestly|Really|Plus)\b/i;

function chattyOpeners(text) {
  const sentences = text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (sentences.length < 3) {
    return { total: 0, sometimes: 0, sentences: sentences.length, ratio: 0 };
  }

  let total = 0;
  let sometimes = 0;
  for (const s of sentences) {
    if (/^Sometimes\b/i.test(s)) {
      sometimes += 1;
      total += 1;
    } else if (CHATTY_STARTERS.test(s)) {
      total += 1;
    }
  }

  return { total, sometimes, sentences: sentences.length, ratio: total / sentences.length };
}

function wordCount(text) {
  const m = text.match(/\b\w+(?:'\w+)?\b/g);
  return m ? m.length : 0;
}

function countMatches(patterns, text) {
  let n = 0;
  for (const p of patterns) {
    const re = new RegExp(p.source, p.flags);
    n += (text.match(re) || []).length;
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
  return [...new Set(words.filter((w) => BUZZWORDS.has(w)))].sort();
}

function sentenceCv(text) {
  const sentences = text.split(/(?<=[.!?])\s+/).filter((s) => s.trim());
  const lengths = sentences.map((s) => s.split(/\s+/).filter(Boolean).length).filter((n) => n > 0);
  if (lengths.length < 3) return { cv: 1, n: lengths.length, detail: "too few sentences to measure rhythm" };
  const mean = lengths.reduce((a, b) => a + b, 0) / lengths.length;
  const variance = lengths.reduce((a, l) => a + (l - mean) ** 2, 0) / lengths.length;
  const cv = Math.sqrt(variance) / mean;
  return {
    cv,
    n: lengths.length,
    detail: `sentence length CV=${cv.toFixed(2)} (low < 0.45 → machine-smooth)`,
  };
}

function literaryPhraseHits(text) {
  let total = 0;
  const parts = [];
  for (const { re, label } of LITERARY_PATTERNS) {
    const n = (text.match(re) || []).length;
    if (n) parts.push(`${label}: ${n}`);
    total += n;
  }
  return { total, parts };
}

function overallVerdict(aiPct) {
  // Low scores are not evidence of human writing — polished AI often lands here
  if (aiPct < 25) return ["uncertain", "low"];
  if (aiPct < 35) return ["likely_human", "low"];
  if (aiPct < 52) return ["uncertain", "medium"];
  if (aiPct < 72) return ["likely_ai", "medium"];
  return ["likely_ai", "high"];
}

/** Points = weight if triggered, else weight * partial (0–1) for soft scoring */
function contribute(weight, triggered, partial = 0) {
  return triggered ? weight : weight * Math.min(1, Math.max(0, partial)) * 0.55;
}

export function quickCheck(text) {
  text = text.trim();
  const wc = wordCount(text);
  if (!wc) return buildReport(0, "low", [], 0, "low");

  const signals = [];

  const emCount = countEmDashes(text);
  const emPer100 = (emCount / wc) * 100;
  const emTriggered = emCount >= 1 && emPer100 >= 0.4;
  signals.push({
    id: "em_dashes",
    label: SIGNAL_LABELS.em_dashes,
    count: emCount,
    weight: 16,
    triggered: emTriggered,
    partial: Math.min(1, emCount / 2) * Math.min(1, emPer100 / 0.8),
    detail: `${emCount} em/en dash(es) (${emPer100.toFixed(1)} per 100 words)`,
  });

  const tripleCount = countMatches(RULE_OF_THREE, text);
  signals.push({
    id: "rule_of_three",
    label: SIGNAL_LABELS.rule_of_three,
    count: tripleCount,
    weight: 14,
    triggered: tripleCount >= 1,
    partial: Math.min(1, tripleCount / 2),
    detail: `${tripleCount} rule-of-three pattern(s) (X, Y, and Z)`,
  });

  const buzz = buzzwordHits(text);
  let buzzDetail = `${buzz.length} AI/literary buzzword(s)`;
  if (buzz.length) buzzDetail += `: ${buzz.slice(0, 6).join(", ")}${buzz.length > 6 ? ", …" : ""}`;
  signals.push({
    id: "buzzwords",
    label: SIGNAL_LABELS.buzzwords,
    count: buzz.length,
    weight: 14,
    triggered: buzz.length >= 1,
    partial: Math.min(1, buzz.length / 3),
    detail: buzzDetail,
  });

  let signpostN = 0;
  for (const p of SIGNPOST_PATTERNS) {
    signpostN += (text.match(new RegExp(p.source, p.flags)) || []).length;
  }
  signals.push({
    id: "signpost_phrases",
    label: SIGNAL_LABELS.signpost_phrases,
    count: signpostN,
    weight: 12,
    triggered: signpostN >= 1,
    partial: Math.min(1, signpostN / 2),
    detail: `${signpostN} essay-like transition(s)`,
  });

  const { cv, n: sentenceN, detail: cvDetail } = sentenceCv(text);
  signals.push({
    id: "uniform_sentences",
    label: SIGNAL_LABELS.uniform_sentences,
    count: sentenceN,
    weight: 14,
    triggered: sentenceN >= 3 && cv < 0.45,
    partial: sentenceN >= 3 ? Math.max(0, (0.55 - cv) / 0.55) : 0,
    detail: cvDetail,
  });

  const literary = literaryPhraseHits(text);
  signals.push({
    id: "literary_phrasing",
    label: SIGNAL_LABELS.literary_phrasing,
    count: literary.total,
    weight: 16,
    triggered: literary.total >= 2,
    partial: Math.min(1, literary.total / 4),
    detail: literary.parts.length ? literary.parts.join("; ") : "none detected",
  });

  const participial = (text.match(/,\s+[a-z]+ing\b/gi) || []).length;
  const partPer100 = (participial / wc) * 100;
  signals.push({
    id: "participial_chains",
    label: SIGNAL_LABELS.participial_chains,
    count: participial,
    weight: 12,
    triggered: participial >= 2 || partPer100 >= 1.2,
    partial: Math.min(1, partPer100 / 1.5),
    detail: `${participial} participial phrase(s) (, watching… / , feeling…)`,
  });

  const contractions = (text.match(CONTRACTIONS) || []).length;
  const contrPer100 = (contractions / wc) * 100;
  const lowContr = wc >= 80 && contrPer100 < 0.5;
  signals.push({
    id: "low_contractions",
    label: SIGNAL_LABELS.low_contractions,
    count: contractions,
    weight: 10,
    triggered: lowContr,
    partial: wc >= 80 ? Math.max(0, (0.6 - contrPer100) / 0.6) : 0,
    detail: `${contractions} contraction(s) (${contrPer100.toFixed(2)} per 100 words; LLM prose often avoids them)`,
  });

  const listBlocks = (text.match(/(?:^|\n)\s*(?:\d+[.)]|[-*•])\s+\S/gm) || []).length;
  signals.push({
    id: "list_heavy",
    label: SIGNAL_LABELS.list_heavy,
    count: listBlocks,
    weight: 6,
    triggered: listBlocks >= 3,
    partial: Math.min(1, listBlocks / 4),
    detail: `${listBlocks} list line(s)`,
  });

  const windup = /^(?:In (?:today's|the|an)|Throughout history|Since the dawn|When it comes to|In recent years|The (?:sun|morning|night|air|wind))/i.test(
    text
  );
  signals.push({
    id: "generic_opener",
    label: SIGNAL_LABELS.generic_opener,
    count: windup ? 1 : 0,
    weight: 8,
    triggered: windup,
    partial: windup ? 1 : 0,
    detail: windup ? "literary or essay-style opener" : "no generic opener",
  });

  const colonOpeners = (text.match(/\b\w[\w\s]{0,20}:\s/g) || []).length;
  signals.push({
    id: "colon_opener",
    label: SIGNAL_LABELS.colon_opener,
    count: colonOpeners,
    weight: 6,
    triggered: colonOpeners >= 2,
    partial: Math.min(1, colonOpeners / 3),
    detail: `${colonOpeners} colon setup(s)`,
  });

  const rhetQ = (text.match(/\?/g) || []).length;
  signals.push({
    id: "rhetorical_questions",
    label: SIGNAL_LABELS.rhetorical_questions,
    count: rhetQ,
    weight: 5,
    triggered: rhetQ >= 2 && wc >= 80,
    partial: Math.min(1, rhetQ / 3),
    detail: `${rhetQ} question mark(s)`,
  });

  const chatty = chattyOpeners(text);
  const chattyTriggered =
    chatty.sometimes >= 2 ||
    (chatty.total >= 3 && chatty.ratio >= 0.2) ||
    chatty.total >= 4;
  let chattyDetail = `${chatty.total} chatty opener(s) in ${chatty.sentences} sentence(s)`;
  if (chatty.sometimes) chattyDetail += ` (${chatty.sometimes}× Sometimes…)`;
  signals.push({
    id: "artificial_simplicity",
    label: SIGNAL_LABELS.artificial_simplicity,
    count: chatty.total,
    weight: 12,
    triggered: chattyTriggered,
    partial: Math.min(1, chatty.total / 4) * Math.min(1, chatty.ratio / 0.25),
    detail: chattyDetail,
  });

  const maxPts = signals.reduce((a, s) => a + s.weight, 0);
  const earned = signals.reduce((a, s) => a + contribute(s.weight, s.triggered, s.partial), 0);
  const surfaceScore = Math.min(100, Math.round((earned / maxPts) * 1000) / 10);

  let surfaceVerdict = "low";
  if (surfaceScore >= 50) surfaceVerdict = "high";
  else if (surfaceScore >= 22) surfaceVerdict = "medium";

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
      id,
      label,
      triggered,
      count,
      detail,
      tooltip: SIGNAL_TOOLTIPS[id] || "",
    })),
    scan_mode: "quick",
    disclaimer:
      "Surface-pattern scan only. Literary AI (Claude, etc.) often scores low. Not proof. Nothing is uploaded.",
  };
}
