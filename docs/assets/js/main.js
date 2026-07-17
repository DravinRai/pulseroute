/**
 * PulseRoute web app — DOM wiring only.
 *
 * All routing lives in graph.js, all intent parsing in nlu.js, all rendering in
 * mapview.js. This module owns the page: it reads inputs, calls those modules,
 * and writes the results into the DOM.
 */
import { FeedSimulator } from "./feed.js";
import { Graph, NoRouteError } from "./graph.js";
import {
  clockIcon, flagIcon, leafIcon, modeIcon, okIcon, pinIcon,
  rulerIcon, sparkIcon, stepIcon, warnIcon,
} from "./icons.js";
import { LAYOUT, drawMap } from "./mapview.js";
import { modeVerb, parseRequest } from "./nlu.js";
import { ZONE_LABELS, buildBrief } from "./ops.js";

const $ = (selector) => document.querySelector(selector);
const SECONDS_PER_MINUTE = 60;
const HIGH_SEVERITY = 1;
const LOAD_BAR_MAX = 2; // a load index of 2.0 renders as a full bar

const feed = new FeedSimulator();
/** @type {Graph|null} */
let graph = null;

const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const shortLabel = (nodeId) => LAYOUT[nodeId]?.short ?? nodeId;
const minutesOf = (seconds) => {
  const mins = seconds / SECONDS_PER_MINUTE;
  return mins < 1 ? "<1" : String(Math.round(mins));
};

function showError(message) {
  $("#result").innerHTML = `<div class="err">${warnIcon()} ${message}</div>`;
}

/** Chips showing what the AI layer understood — makes its job visible. */
function intentChips(request) {
  const objective = request.optimize === "co2" ? "🌱 Greenest" : "⏱ Fastest";
  return [
    `<span class="ichip">🎯 ${shortLabel(request.origin)} → ${shortLabel(request.destination)}</span>`,
    request.step_free ? '<span class="ichip">♿ Step-free</span>' : "",
    `<span class="ichip">${objective}</span>`,
  ].filter(Boolean).join("");
}

function badges(result) {
  const out = [];
  if (result.stepFree) out.push(`<span class="badge b-ok">${okIcon()} Verified step-free</span>`);
  if (result.congestionApplied) out.push(`<span class="badge b-warn">${warnIcon()} Crowd-adjusted</span>`);
  if (result.optimize === "co2" || result.totalCo2) {
    out.push(`<span class="badge b-eco">${leafIcon()} ${result.totalCo2} g CO₂</span>`);
  }
  return out.join("");
}

function timeline(result, originLabel) {
  const start =
    `<li><span class="tl-node start">${pinIcon()}</span><div class="tl-body">` +
    `<span class="mode">Start at</span> <b>${originLabel}</b></div></li>`;

  const steps = result.steps.map((step, i) => {
    const isLast = i === result.steps.length - 1;
    const marker = isLast
      ? `<span class="tl-node end">${flagIcon()}</span>`
      : `<span class="tl-node">${modeIcon(step.mode)}</span>`;
    return `<li>${marker}<div class="tl-body"><span class="mode">${modeVerb(step.mode)}</span> ` +
      `to <b>${step.label}</b> <span class="dist">· ${Math.round(step.distance)} m</span></div></li>`;
  }).join("");

  return start + steps;
}

function renderRoute(text) {
  if (!graph) return;

  let request;
  try {
    request = parseRequest(text);
  } catch (error) {
    showError(error.message);
    drawMap($("#map"), graph, null, null, { animate: !prefersReducedMotion });
    return;
  }

  const snapshot = feed.snapshot(Number($("#minute").value));
  let result;
  try {
    result = graph.findRoute(request, snapshot.factors);
  } catch (error) {
    if (!(error instanceof NoRouteError)) throw error;
    showError(error.message);
    drawMap($("#map"), graph, null, snapshot.factors, { animate: !prefersReducedMotion });
    return;
  }

  $("#result").innerHTML = `
    <div class="understood">
      <span class="u-label">${sparkIcon()} AI understood your request</span>${intentChips(request)}
    </div>
    <div class="route-title">${result.stepFree ? "Step-free route" : "Your route"}</div>
    <div class="stat-row">
      <div class="stat"><div class="k">${clockIcon()} Time</div>
        <div class="v">${minutesOf(result.totalTime)}<small> min</small></div></div>
      <div class="stat"><div class="k">${rulerIcon()} Distance</div>
        <div class="v">${Math.round(result.totalDistance)}<small> m</small></div></div>
      <div class="stat"><div class="k">${stepIcon()} Steps</div>
        <div class="v">${result.steps.length}</div></div>
    </div>
    <div class="badges">${badges(result)}</div>
    <ol class="timeline">${timeline(result, graph.label(result.nodeIds[0]))}</ol>
    <div class="crowd-ctx">${warnIcon()}<span>${snapshot.note}</span></div>`;

  drawMap($("#map"), graph, result, snapshot.factors, { animate: !prefersReducedMotion });
}

function renderBrief() {
  const brief = buildBrief(feed.snapshot(Number($("#ominute").value)));
  let html = `<p class="ops-note" style="margin-bottom:14px">${brief.note}</p>`;

  if (!brief.ranked.length) {
    html += `<div class="all-clear">${okIcon()} All zones free-flowing — no action required.</div>`;
  } else {
    for (const [zone, factor] of brief.ranked) {
      const severity = factor >= HIGH_SEVERITY ? "sev-hi" : "sev-md";
      const pct = Math.min(100, Math.round((factor / LOAD_BAR_MAX) * 100));
      html += `<div class="zone"><span class="zn">${ZONE_LABELS[zone]}</span>` +
        `<span class="zl">load ${factor.toFixed(1)}</span>` +
        `<span class="bar ${severity}"><span style="width:${pct}%"></span></span></div>`;
    }
    html += '<div class="ops-actions"><h4>Recommended actions</h4>';
    brief.actions.forEach((action, i) => {
      html += `<div class="action"><span class="idx">${i + 1}</span><span>${action}</span></div>`;
    });
    html += "</div>";
  }
  $("#brief").innerHTML = html;
}

function selectTab(which) {
  const fan = which === "fan";
  $("#tab-fan").setAttribute("aria-selected", String(fan));
  $("#tab-ops").setAttribute("aria-selected", String(!fan));
  $("#panel-fan").classList.toggle("hidden", !fan);
  $("#panel-ops").classList.toggle("hidden", fan);
  if (!fan) renderBrief();
}

function wireEvents() {
  $("#minute").addEventListener("input", (e) => {
    $("#minute-out").textContent = `${e.target.value}′`;
  });
  $("#ominute").addEventListener("input", (e) => {
    $("#ominute-out").textContent = `${e.target.value}′`;
    renderBrief();
  });
  $("#go").addEventListener("click", () => renderRoute($("#q").value));
  $("#q").addEventListener("keydown", (e) => {
    if (e.key === "Enter") renderRoute($("#q").value);
  });
  for (const chip of document.querySelectorAll("#examples .chip")) {
    chip.addEventListener("click", () => {
      $("#q").value = chip.textContent.trim();
      renderRoute($("#q").value);
    });
  }
  $("#tab-fan").addEventListener("click", () => selectTab("fan"));
  $("#tab-ops").addEventListener("click", () => selectTab("ops"));
}

async function init() {
  try {
    graph = await Graph.load();
  } catch (error) {
    showError(`${error.message} The venue map could not be loaded.`);
    return;
  }
  wireEvents();
  renderRoute($("#q").value);

  // Exposed for automated verification (parity checks against the Python engine).
  window.PulseRoute = { graph, parseRequest, feed, buildBrief };
  document.dispatchEvent(new CustomEvent("pulseroute:ready"));
}

init();
