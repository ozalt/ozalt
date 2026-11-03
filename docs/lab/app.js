"use strict";
const data = window.RESEARCH_DATA;
const $ = (id) => document.getElementById(id);
const names = {search:"Search only",bge:"BGE",noul:"Jev",span_noul:"Span-02",liquid_noul:"D1 Ultra"};
const colors = {search:"#858e89",bge:"#247563",noul:"#4c65a2",span_noul:"#b2842d",liquid_noul:"#8a537c"};
const descriptions = {
  ndcg5:
    "Rewards putting the labeled evidence near the top. Higher is better; 1 is a perfect ranking.",
  hit5: "The share of claims with at least one labeled evidence document in the first five results.",
  recall5:
    "The average share of each claim’s labeled evidence documents recovered in the first five results.",
  mrr5: "Rewards finding the first labeled evidence document early. Rank 1 scores 1; rank 5 scores 0.2.",
};
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function pct(v) {
  return (100 * v).toFixed(1) + "%";
}
let selected = null;
if (!data) {
  document
    .querySelector("main")
    .replaceChildren(
      el("h1", null, "Results are not ready yet."),
      el(
        "p",
        null,
        "Run the benchmark and scripts/analyze.py to generate web/data.js.",
      ),
    );
} else {
  const s = data.summary;
  if (!s.methods.liquid_noul) document.querySelector(".intro").textContent = "D1 Ultra is being benchmarked. The model comparison will refresh when its full run finishes.";
  const methods = Object.keys(names).filter(k => s.methods[k]);
  let left = s.methods.liquid_noul ? "liquid_noul" : "span_noul";
  let right = "noul";
  const bgeDevice = s.bge_runtime.device === "cuda" ? "GPU" : "CPU";
  $("gpu-count").textContent = bgeDevice === "GPU" ? "1 GPU" : "0 GPUs";
  $("gpu-role").textContent =
    bgeDevice === "GPU" ? "BGE reranking · Jina on CPU" : "local CPU inference";
  $("ceiling").textContent = pct(s.candidate_hit20);
  if (s.cpu_full_run_estimate) {
    $("cpu-estimate").textContent =
      `Full CPU scoring estimate: ${(s.cpu_full_run_estimate.estimated_scoring_seconds / 60).toFixed(1)} minutes for 300 claims, based on ${s.cpu_full_run_estimate.measured_sample_queries} measured claims. Full GPU stage: ${s.bge_runtime.stage_wall_seconds.toFixed(1)} seconds measured. CPU estimate excludes setup overhead.`;
  }
  function scoreboard() {
    const metric = $("metric").value;
    $("metric-explainer").textContent = descriptions[metric];
    $("scorecards").replaceChildren();
    for (const key of methods) {
      const m = s.methods[key][metric];
      const card = el("article", "scorecard");
      card.style.setProperty("--accent", colors[key]);
      card.append(
        el("div", "method-name", names[key]),
        el(
          "div",
          "number",
          metric === "hit5" ? pct(m.mean) : m.mean.toFixed(3),
        ),
      );
      const bar = el("div", "bar");
      const fill = el("i");
      fill.style.width = pct(m.mean);
      bar.append(fill);
      card.append(
        bar,
        el(
          "p",
          null,
          `95% interval: ${m.ci95[0].toFixed(3)}–${m.ci95[1].toFixed(3)}`,
        ),
        el(
          "p",
          null,
          key === "search"
            ? "Jina v5 Small · cosine similarity"
            : key === "bge"
              ? "BGE v2 M3 · local " + bgeDevice
              : key === "noul" ? "Jev 1.13 · relevance probability" : key === "span_noul" ? "Span-02 · default reasoning" : "Liquid D1 Ultra · relevance probability",
        ),
      );
      $("scorecards").append(card);
    }
  }
  scoreboard();
  $("metric").addEventListener("change", scoreboard);
  for (const key of ["bge", "noul", "span_noul", "liquid_noul"].filter(k => s.methods[k])) {
    const t = s.methods[key].latency;
    const e = el("div");
    e.append(
      el(
        "strong",
        null,
        t ? t.median_seconds.toFixed(2) + " s" : "Unavailable",
      ),
      el("span", null, names[key] + " · median"),
      el("span", "muted", t ? "p95 " + t.p95_seconds.toFixed(2) + " s" : ""),
    );
    $("timings").append(e);
  }
  $("cost").textContent =
    "$" + ["noul", "span_noul", "liquid_noul"].filter(k => s[k]).reduce((sum,k) => sum + s[k].reported_cost_usd,0).toFixed(4);
  $("cost-note").textContent =
    ["noul", "span_noul", "liquid_noul"].filter(k => s[k]).map(k => `${names[k]}: $${s[k].reported_cost_usd.toFixed(4)}`).join(" · ") + ". 6,000 calls per run. Local electricity and hardware are not priced.";
  function comparison() {
    let d = s.paired_differences[`${left}-${right}`];
    if (left === right) d = {wins:0, losses:0, ties:s.queries, ndcg5_mean:0, ci95:[0,0]};
    if (!d) {
      const reverse = s.paired_differences[`${right}-${left}`];
      d = {...reverse, wins:reverse.losses, losses:reverse.wins, ndcg5_mean:-reverse.ndcg5_mean, ci95:[-reverse.ci95[1],-reverse.ci95[0]]};
    }
    document.querySelector('label[for="outcome"]').textContent = `Compare ${names[left]} with ${names[right]}`;
    document.querySelector('#outcome option[value="win"]').textContent = `${names[left]} ranks evidence higher`;
    document.querySelector('#outcome option[value="loss"]').textContent = `${names[right]} ranks evidence higher`;
    const decisive = d.ci95[0] > 0 || d.ci95[1] < 0;
    $("finding").textContent = `${names[left]} ranked evidence better on ${d.wins} claims; ${names[right]} on ${d.losses}; ${d.ties} tied. ${decisive ? "The paired 95% interval excludes zero on this dataset." : "The paired 95% interval crosses zero, so this run does not clearly separate their average ranking quality."}`;
    $("paired").textContent = `${names[left]} − ${names[right]} nDCG@5: ${d.ndcg5_mean.toFixed(4)}; paired 95% interval [${d.ci95[0].toFixed(4)}, ${d.ci95[1].toFixed(4)}]. Every decision model used the same relevance question and frozen candidates. Later additions and different run dates limit what the comparison proves.`;
  }
  for (const id of ["compare-left", "compare-right"]) {
    for (const k of methods) {
      const option = el("option", null, names[k]); option.value = k; $(id).append(option);
    }
    $(id).value = id === "compare-left" ? left : right;
    $(id).addEventListener("change", () => {left = $("compare-left").value; right = $("compare-right").value; comparison(); list();});
  }
  comparison();
  function filtered() {
    const term = $("query-search").value.toLowerCase(),
      outcome = $("outcome").value;
    return data.queries.filter((q) => {
      const diff =
        q.methods[left].metrics.ndcg5 - q.methods[right].metrics.ndcg5;
      return (
        (q.claim.toLowerCase().includes(term) || q.id.includes(term)) &&
        (outcome === "all" ||
          (outcome === "win" && diff > 1e-10) ||
          (outcome === "loss" && diff < -1e-10) ||
          (outcome === "tie" && Math.abs(diff) <= 1e-10) ||
          (outcome === "miss" && q.candidate_hit20 === 0))
      );
    });
  }
  function list() {
    const qs = filtered();
    $("query-count").textContent =
      `${qs.length} of ${data.queries.length} claims`;
    $("query-list").replaceChildren();
    if (!qs.some((q) => q.id === selected)) selected = qs[0]?.id ?? null;
    for (const q of qs) {
      const b = el(
        "button",
        "query-item" + (selected === q.id ? " active" : ""),
      );
      b.type = "button";
      b.setAttribute("aria-pressed", selected === q.id ? "true" : "false");
      b.append(
        el("small", null, "CLAIM " + q.id),
        document.createTextNode(q.claim),
      );
      b.addEventListener("click", () => {
        selected = q.id;
        list();
      });
      $("query-list").append(b);
    }
    detail();
  }
  function detail() {
    const q = data.queries.find((q) => q.id === selected);
    $("rankings").replaceChildren();
    if (!q) {
      $("claim-id").textContent = "NO MATCHES";
      $("claim").textContent = "Try a different search or outcome filter.";
      return;
    }
    $("claim-id").textContent =
      "CLAIM " +
      q.id +
      " / " +
      (q.candidate_hit20
        ? "EVIDENCE IN CANDIDATES"
        : "EVIDENCE MISSING FROM CANDIDATES");
    $("claim").textContent = q.claim;
    for (const key of methods) {
      const method = q.methods[key];
      const col = el("section", "ranking-col");
      col.append(
        el("h4", null, names[key]),
        el("p", "muted", "nDCG@5 " + method.metrics.ndcg5.toFixed(3)),
      );
      method.documents
        .slice(0, $("show-all").checked ? 20 : 5)
        .forEach((entry, i) => {
          const doc = { ...entry, ...data.documents[entry.id] };
          const box = el(
            "details",
            "passage" + (doc.relevant ? " relevant" : ""),
          );
          const head = el("summary");
          const rank = el("span", "rank");
          rank.append(
            el("span", null, String(i + 1).padStart(2, "0")),
            el("span", null, (key.endsWith("noul") ? "P(yes) " : "score ") + doc.score.toFixed(3)),
          );
          head.append(rank, el("span", "title", doc.title));
          if (doc.relevant)
            head.append(el("span", "badge", "● LABELED EVIDENCE"));
          head.append(el("span", "hint", "Read passage +"));
          box.append(
            head,
            el("p", null, doc.text),
            el("p", "muted", "Document " + doc.id),
          );
          col.append(box);
        });
      $("rankings").append(col);
    }
  }
  $("query-search").addEventListener("input", list);
  $("outcome").addEventListener("change", list);
  $("show-all").addEventListener("change", detail);
  list();
}
