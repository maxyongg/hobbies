// Cinema — renders data/items.json (written by the scheduled scraper run).
//   Now showing / Coming soon: one card per film, merged across cinemas by title.
//   New: listings first seen since tracking began, by day.
"use strict";

const NAMES = {
  filmhouse: "Filmhouse", shaw: "Shaw Theatres", afa: "Asian Film Archive", gv: "Golden Village",
  carnival: "Carnival Cinemas", sfs: "Singapore Film Society",
};
const SHORT = {
  "Shaw Theatres": "Shaw", "Asian Film Archive": "AFA", "Golden Village": "GV",
  "Carnival Cinemas": "Carnival", "Singapore Film Society": "SFS",
};
const TZ = "Asia/Singapore";
const VIEWS = [["now", "Now showing"], ["soon", "Coming soon"], ["new", "New"]];

const state = { items: [], status: null, view: "now", hidden: new Set(), query: "", sort: "az" };

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
function shortName(key) {
  const name = sourceName(key);
  return SHORT[name] || name;
}

// --- Merging the same film across cinemas -------------------------------------------

const BRACKETS = /\s*[[(][^\])]*[\])]/g; // [M], (4K Restoration), (ENGLISH), [CANTO]
const STUDIO = /^(marvel studios|disney and pixars|disney pixars|disneys|dc studios|dreamworks)\s+/;
// GV appends the Chinese title ("The Violinist 沧海琴声"); ignore a CJK tail after a Latin title.
const CJK_TAIL = /([a-z0-9!?.)])\s+[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}][^a-z]*$/u;

function cleanTitle(title) {
  return title.replace(BRACKETS, "").replace(/\s+/g, " ").replace(/[\s:–-]+$/, "").trim() || title;
}

function filmKey(title) {
  return cleanTitle(title).toLowerCase()
    .replace(CJK_TAIL, "$1")
    .normalize("NFKD").replace(/[\u0300-\u036f]/g, "") // Amélie -> amelie
    .replace(/[’']/g, "")
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}]+/gu, " ").trim()
    .replace(STUDIO, "");
}

function variants(title) {
  return [...title.matchAll(/[[(]([^\])]*)[\])]/g)].map(m => m[1].trim()).filter(Boolean);
}

function groupFilms(items) {
  const groups = new Map();
  for (const item of items) {
    const key = filmKey(item.title);
    let g = groups.get(key);
    if (!g) groups.set(key, g = { key, items: [], title: cleanTitle(item.title), firstSeen: item.first_seen });
    g.items.push(item);
    if (cleanTitle(item.title).length < g.title.length) g.title = cleanTitle(item.title);
    if (item.first_seen < g.firstSeen) g.firstSeen = item.first_seen;
  }
  for (const g of groups.values()) {
    g.showing = g.items.some(i => (i.showing || "now") === "now") ? "now" : "soon";
    g.sources = [...new Set(g.items.map(i => i.source))];
    g.posters = posterCandidates(g.items);
  }
  return [...groups.values()];
}

// --- Rendering ------------------------------------------------------------------------

// Poster hosts that load reliably from another site come first; Shaw's image proxy refuses some.
const POSTER_ORDER = ["filmhouse", "gv", "sfs", "afa", "carnival", "shaw"];
const PLACEHOLDER = /noimage|no-image|placeholder/i;

function posterCandidates(items) {
  const rank = i => (POSTER_ORDER.indexOf(i.source) + POSTER_ORDER.length + 1) % (POSTER_ORDER.length + 1);
  return [...new Set([...items].sort((a, b) => rank(a) - rank(b))
    .map(i => i.poster).filter(p => p && !PLACEHOLDER.test(p)))];
}

// Try each candidate in turn; fall back to 🎬 when none loads.
function poster(candidates, href) {
  const blank = () => el("div", { class: "poster blank", "aria-hidden": "true" }, "🎬");
  const link = el("a", { href, target: "_blank", rel: "noopener", tabindex: "-1" });
  if (!candidates.length) {
    link.append(blank());
    return link;
  }
  let next = 1;
  const img = el("img", { class: "poster", src: candidates[0], alt: "", loading: "lazy", referrerpolicy: "no-referrer" });
  img.addEventListener("error", () => {
    if (next < candidates.length) img.src = candidates[next++];
    else img.replaceWith(blank());
  });
  link.append(img);
  return link;
}

function filmCard(g) {
  const where = g.sources.map(source => {
    const mine = g.items.filter(i => i.source === source);
    const labels = [...new Set(mine.flatMap(i => variants(i.title)))];
    return el("a", { class: `where src-${source}`, href: mine[0].url, target: "_blank", rel: "noopener" },
      el("span", { class: "dot-src" }), shortName(source),
      labels.length ? el("small", {}, labels.join(" · ")) : null);
  });
  return el("article", { class: "card" },
    poster(g.posters, g.items[0].url),
    el("div", { class: "body" },
      el("h3", { class: "title" }, g.title),
      el("div", { class: "wheres" }, ...where)));
}

function itemCard(item) {
  return el("article", { class: "card" + (item.listed ? "" : " gone") },
    poster(posterCandidates([item]), item.url),
    el("div", { class: "body" },
      el("span", { class: `src src-${item.source}` }, sourceName(item.source)),
      el("h3", { class: "title" }, el("a", { href: item.url, target: "_blank", rel: "noopener" }, item.title)),
      item.tags?.length ? el("span", { class: "meta" }, item.tags.join(" · ")) : null,
      item.listed ? null : el("span", { class: "meta" }, "No longer listed")));
}

function sourceKeys() {
  return [...new Set([...Object.keys(state.status?.sources || {}), ...state.items.map(i => i.source)])];
}

function renderControls(counts) {
  document.getElementById("views").replaceChildren(...VIEWS.map(([key, label]) => {
    const btn = el("button", { type: "button", "aria-pressed": String(state.view === key) },
      label, counts[key] !== undefined ? el("span", { class: "count" }, String(counts[key])) : null);
    btn.addEventListener("click", () => { state.view = key; save("view", key); render(); });
    return btn;
  }));
  document.getElementById("sort").hidden = state.view === "new";

  const keys = sourceKeys();
  const chips = keys.map(key => {
    const s = state.status?.sources?.[key];
    const btn = el("button", { type: "button", class: `src-${key}`, "aria-pressed": String(!state.hidden.has(key)),
      title: s && !s.ok ? `Last check failed: ${s.error}` : null },
    el("span", { class: "dot-src" }), shortName(key), s && !s.ok ? " ⚠︎" : null);
    btn.addEventListener("click", () => {
      state.hidden.has(key) ? state.hidden.delete(key) : state.hidden.add(key);
      save("hidden", [...state.hidden]);
      render();
    });
    return btn;
  });
  if (state.hidden.size) {
    const all = el("button", { type: "button", class: "reset" }, "Show all");
    all.addEventListener("click", () => { state.hidden.clear(); save("hidden", []); render(); });
    chips.push(all);
  }
  document.getElementById("cinemas").replaceChildren(...chips);
}

function render() {
  const visible = state.items.filter(i => !state.hidden.has(i.source));
  const films = groupFilms(visible.filter(i => i.listed));
  const fresh = visible.filter(i => i.alert !== "seed");
  renderControls({
    now: films.filter(g => g.showing === "now").length,
    soon: films.filter(g => g.showing === "soon").length,
    new: fresh.length,
  });

  const q = filmKey(state.query);
  const feed = document.getElementById("feed");
  if (!state.items.length) {
    feed.replaceChildren(el("p", { class: "empty" }, "No data yet — waiting for the first scheduled run."));
    return;
  }

  if (state.view === "new") {
    const raw = state.query.trim().toLowerCase();
    const items = fresh.filter(i => !q || filmKey(i.title).includes(q) || i.title.toLowerCase().includes(raw));
    const days = new Map();
    for (const item of items) {
      const day = (item.first_seen || "").slice(0, 10);
      if (!days.has(day)) days.set(day, []);
      days.get(day).push(item);
    }
    const parts = [];
    for (const [day, list] of days) parts.push(el("h2", {}, dayLabel(day)), el("div", { class: "grid" }, ...list.map(itemCard)));
    feed.replaceChildren(...(parts.length ? parts
      : [el("p", { class: "empty" }, "Nothing new since tracking began. New listings appear here (and as alerts).")]));
    return;
  }

  const raw = state.query.trim().toLowerCase();
  const matches = g => !q || g.key.includes(q) || g.items.some(i => i.title.toLowerCase().includes(raw));
  let shown = films.filter(g => g.showing === state.view && matches(g));
  const byTitle = (a, b) => a.title.localeCompare(b.title, "en", { sensitivity: "base" });
  if (state.sort === "new") shown.sort((a, b) => b.firstSeen.localeCompare(a.firstSeen) || byTitle(a, b));
  else if (state.sort === "most") shown.sort((a, b) => b.sources.length - a.sources.length || byTitle(a, b));
  else shown.sort(byTitle);
  feed.replaceChildren(shown.length ? el("div", { class: "grid" }, ...shown.map(filmCard))
    : el("p", { class: "empty" }, q ? "No films match your search." : "Nothing here for the selected cinemas."));
}

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

async function main() {
  state.view = load("view", "now");
  if (!VIEWS.some(([k]) => k === state.view)) state.view = "now";
  state.hidden = new Set(load("hidden", []));
  state.sort = load("sort", "az");
  const sort = document.getElementById("sort");
  sort.value = state.sort;
  sort.addEventListener("change", () => { state.sort = sort.value; save("sort", sort.value); render(); });
  const search = document.getElementById("search");
  search.addEventListener("input", () => { state.query = search.value; render(); });

  const [items, status] = await Promise.allSettled([getJSON("data/items.json"), getJSON("data/status.json")]);
  state.items = items.status === "fulfilled" ? items.value.items || [] : [];
  state.status = status.status === "fulfilled" ? status.value : null;
  document.getElementById("checked").textContent = state.status ? `Checked ${ago(state.status.checked)}` : "Not checked yet";
  render();
}

main();
