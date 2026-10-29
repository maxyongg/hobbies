// Cinema — renders data/items.json (written by the scheduled scraper run).
"use strict";

const NAMES = { filmhouse: "Filmhouse", shaw: "Shaw Theatres", afa: "Asian Film Archive" };
const TZ = "Asia/Singapore";

const state = { items: [], status: null, source: "all", listedOnly: false };

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children) if (c !== null && c !== undefined) node.append(c);
  return node;
}

function sgtDate(d) {
  return d.toLocaleDateString("en-CA", { timeZone: TZ }); // YYYY-MM-DD
}

function dayLabel(isoDay) {
  const today = sgtDate(new Date());
  const yesterday = sgtDate(new Date(Date.now() - 864e5));
  if (isoDay === today) return "Today";
  if (isoDay === yesterday) return "Yesterday";
  return new Date(isoDay + "T12:00:00+08:00").toLocaleDateString("en-SG", {
    timeZone: TZ, weekday: "short", day: "numeric", month: "short", year: "numeric",
  });
}

function ago(iso) {
  const mins = Math.round((Date.now() - new Date(iso)) / 6e4);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function sourceName(key) {
  return state.status?.sources?.[key]?.name || NAMES[key] || key;
}

function card(item) {
  const poster = item.poster
    ? el("img", { class: "poster", src: item.poster, alt: "", loading: "lazy", referrerpolicy: "no-referrer" })
    : el("div", { class: "poster blank", "aria-hidden": "true" }, "🎬");
  if (item.poster) poster.addEventListener("error", () => poster.replaceWith(el("div", { class: "poster blank" }, "🎬")));
  return el("a", { class: "card" + (item.listed ? "" : " gone"), href: item.url, target: "_blank", rel: "noopener" },
    poster,
    el("div", { class: "body" },
      el("span", { class: `src ${item.source}` }, sourceName(item.source)),
      el("span", { class: "title" }, item.title),
      item.tags?.length ? el("span", { class: "meta" }, item.tags.join(" · ")) : null,
      item.listed ? null : el("span", { class: "meta" }, "No longer listed"),
    ),
  );
}

function renderFilters() {
  const nav = document.getElementById("filters");
  const keys = [...new Set([...Object.keys(state.status?.sources || {}), ...state.items.map(i => i.source)])];
  if (!keys.includes(state.source)) state.source = "all";
  nav.replaceChildren(...["all", ...keys].map(key => {
    const s = state.status?.sources?.[key];
    const btn = el("button", { type: "button", "aria-pressed": String(state.source === key) },
      key === "all" ? "All" : sourceName(key),
      s ? el("span", { class: `dot ${s.ok ? "ok" : "bad"}`, title: s.ok ? `${s.count} listed` : s.error }) : null);
    btn.addEventListener("click", () => { state.source = key; save("source", key); render(); });
    return btn;
  }));
}

function render() {
  renderFilters();
  const feed = document.getElementById("feed");
  const shown = state.items.filter(i =>
    (state.source === "all" || i.source === state.source) && (!state.listedOnly || i.listed));
  const fresh = shown.filter(i => i.alert !== "seed");
  const seeded = shown.filter(i => i.alert === "seed");

  const groups = new Map();
  for (const item of fresh) {
    const day = (item.first_seen || "").slice(0, 10);
    if (!groups.has(day)) groups.set(day, []);
    groups.get(day).push(item);
  }

  const parts = [];
  for (const [day, items] of groups) {
    parts.push(el("h2", {}, dayLabel(day)), el("div", { class: "grid" }, ...items.map(card)));
  }
  if (!fresh.length) {
    parts.push(el("p", { class: "empty" }, state.items.length
      ? "No new films since tracking began. They'll appear here as cinemas add them."
      : "No data yet — waiting for the first scheduled run."));
  }
  if (seeded.length) {
    parts.push(el("details", {},
      el("summary", {}, `Already listed when tracking began (${seeded.length})`),
      el("div", { class: "grid" }, ...seeded.map(card))));
  }
  feed.replaceChildren(...parts);
}

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

async function main() {
  state.source = load("source", "all");
  state.listedOnly = load("listedOnly", false);
  const toggle = document.getElementById("listed-only");
  toggle.checked = state.listedOnly;
  toggle.addEventListener("change", () => { state.listedOnly = toggle.checked; save("listedOnly", toggle.checked); render(); });

  const [items, status] = await Promise.allSettled([getJSON("data/items.json"), getJSON("data/status.json")]);
  state.items = items.status === "fulfilled" ? items.value.items || [] : [];
  state.status = status.status === "fulfilled" ? status.value : null;
  document.getElementById("checked").textContent = state.status
    ? `Checked ${ago(state.status.checked)}`
    : "Not checked yet";
  render();
}

main();
