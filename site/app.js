// Cinema — renders data/items.json (written by the scheduled scraper run).
//   Now showing / Coming soon: one card per film, merged across cinemas by title.
//   New: listings first seen since tracking began, by day.
//   Ratings (IMDb, Letterboxd) come from data/ratings.json, keyed by "<source>:<id>".
//   Screening times (Filmhouse, AFA, SFS) come from data/showtimes.json, keyed the same way.
//   Want to see / Tickets: personal lists kept in this browser only (see "Personal lists").
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
// [key, label, short label for phones]
const VIEWS = [
  ["now", "Now showing", "Now"], ["soon", "Coming soon", "Soon"], ["new", "New"],
  ["want", "Want to see"], ["tickets", "Tickets"],
];

const state = {
  items: [], status: null, ratings: null, showtimes: null, view: "now", hidden: new Set(), query: "", sort: "az",
  byKey: new Map(), counts: {},
};

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; /* private mode, full */ }
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

// Now (or `d`) in Singapore as "YYYY-MM-DDTHH:MM", the format of showtimes.json starts and tickets.
function sgtNow(d = new Date()) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(d).map(x => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

function dayShort(isoDay) {
  const today = sgtDate(new Date());
  if (isoDay === today) return "Today";
  if (isoDay === sgtDate(new Date(Date.now() + 864e5))) return "Tomorrow";
  return new Date(isoDay + "T12:00:00+08:00").toLocaleDateString("en-SG", {
    timeZone: TZ, weekday: "short", day: "numeric", month: "short",
  });
}

function clock(start) { // "2026-10-30T16:10" -> "4:10 pm"
  const [h, m] = start.slice(11, 16).split(":").map(Number);
  return `${(h + 11) % 12 + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
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
    g.rating = ratingOf(g.items);
    g.sessions = sessionsOf(g.items);
  }
  return [...groups.values()];
}

// --- Screening times --------------------------------------------------------------------

function sessionsOf(items) {
  const now = sgtNow();
  return items.flatMap(i => (state.showtimes?.items?.[`${i.source}:${i.id}`] || []).map(s => ({ ...s, source: i.source })))
    .filter(s => s.start > now)
    .sort((a, b) => a.start.localeCompare(b.start));
}

// Collapsed: the next day's times. Open: every screening by day, each a link to book.
function times(sessions) {
  if (!sessions.length) return null;
  const days = new Map();
  for (const s of sessions) {
    const day = s.start.slice(0, 10);
    if (!days.has(day)) days.set(day, []);
    days.get(day).push(s);
  }
  const multi = new Set(sessions.map(s => s.source)).size > 1;
  const venues = [...new Set(sessions.map(s => s.venue || ""))];
  const [[firstDay, first]] = days;
  const more = sessions.length - first.length;
  const slot = s => el("a", { class: `slot src-${s.source}${/sold out/i.test(s.note || "") ? " sold" : ""}`,
    href: s.url, target: "_blank", rel: "noopener" },
    el("b", {}, clock(s.start)),
    multi ? el("small", {}, shortName(s.source)) : null,
    venues.length > 1 && s.venue ? el("small", {}, s.venue) : null,
    s.note ? el("small", {}, s.note) : null);
  return el("details", { class: "times" },
    el("summary", {}, el("b", {}, dayShort(firstDay)), " ", first.map(s => clock(s.start)).join(", "),
      more ? el("span", { class: "more" }, ` +${more} more`) : null),
    ...[...days].map(([day, list]) => el("div", { class: "day" },
      el("span", {}, dayShort(day)), el("div", { class: "slots" }, ...list.map(slot)))),
    venues.length === 1 && venues[0] ? el("p", { class: "venue" }, venues[0]) : null);
}

// --- Ratings --------------------------------------------------------------------------

function ratingOf(items) {
  const r = state.ratings;
  for (const i of items) {
    const id = r?.items?.[`${i.source}:${i.id}`];
    const film = id && r.films?.[id];
    if (film) return { id, ...film };
  }
  return null;
}

// For "Top rated": IMDb out of 10, else Letterboxd out of 5 scaled to 10; unrated last.
function score(f) {
  return f?.imdb ?? (f?.letterboxd ? f.letterboxd * 2 : -1);
}

function ratings(f) {
  if (!f || !(f.imdb || f.letterboxd)) return null;
  const link = (cls, href, label, value) => el("a", { class: `rating ${cls}`, href, target: "_blank", rel: "noopener" },
    label, " ", el("b", {}, value.toFixed(1)));
  return el("div", { class: "ratings" },
    f.imdb ? link("imdb", `https://www.imdb.com/title/${f.imdb_id}/`, "IMDb", f.imdb) : null,
    f.letterboxd ? link("lb", f.letterboxd_url || `https://letterboxd.com/tmdb/${f.id}/`, "Letterboxd", f.letterboxd) : null);
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
    el("div", { class: "art" }, poster(g.posters, g.items[0].url), actions(g.key, snapshot(g))),
    el("div", { class: "body" },
      el("h3", { class: "title" }, g.title),
      ratings(g.rating),
      booked(g.key),
      el("div", { class: "wheres" }, ...where),
      times(g.sessions)));
}

function itemCard(item) {
  const key = filmKey(item.title);
  const g = state.byKey.get(key);
  const snap = g ? snapshot(g) : { title: cleanTitle(item.title), poster: posterCandidates([item])[0] || null, url: item.url };
  return el("article", { class: "card" + (item.listed ? "" : " gone") },
    el("div", { class: "art" }, poster(posterCandidates([item]), item.url), actions(key, snap)),
    el("div", { class: "body" },
      el("span", { class: `src src-${item.source}` }, sourceName(item.source)),
      el("h3", { class: "title" }, el("a", { href: item.url, target: "_blank", rel: "noopener" }, item.title)),
      ratings(ratingOf([item])),
      item.tags?.length ? el("span", { class: "meta" }, item.tags.join(" · ")) : null,
      item.listed ? null : el("span", { class: "meta" }, "No longer listed"),
      booked(key),
      item.listed ? times(sessionsOf([item])) : null));
}

function sourceKeys() {
  return [...new Set([...Object.keys(state.status?.sources || {}), ...state.items.map(i => i.source)])];
}

function renderControls(counts) {
  counts = { ...counts, want: mine.want.size, tickets: upcomingTickets().length };
  const nav = document.getElementById("views");
  nav.replaceChildren(...VIEWS.map(([key, label, short]) => {
    const btn = el("button", { type: "button", "aria-pressed": String(state.view === key) },
      short ? el("span", { class: "long" }, label) : label, short ? el("span", { class: "short" }, short) : null,
      // Listing counts are hidden on phones to fit five tabs; personal counts show when non-zero.
      key === "want" || key === "tickets" ? (counts[key] ? el("span", { class: "count" }, String(counts[key])) : null)
        : el("span", { class: "count listing" }, String(counts[key])));
    btn.addEventListener("click", () => go(key));
    return btn;
  }));
  // On a phone the tabs scroll sideways; keep the current one in view.
  const on = nav.querySelector('[aria-pressed="true"]');
  if (on && (on.offsetLeft < nav.scrollLeft || on.offsetLeft + on.offsetWidth > nav.scrollLeft + nav.clientWidth)) {
    nav.scrollLeft = on.offsetLeft - 8;
  }
  const personal = state.view === "want" || state.view === "tickets";
  document.getElementById("sort").hidden = state.view === "new" || state.view === "tickets";
  document.getElementById("cinemas").hidden = personal; // personal lists show every cinema

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

function go(view) {
  state.view = view;
  save("view", view);
  render();
}

function render() {
  const listed = state.items.filter(i => i.listed);
  state.byKey = new Map(groupFilms(listed).map(g => [g.key, g])); // every cinema, for the personal lists
  const visible = state.items.filter(i => !state.hidden.has(i.source));
  const films = state.hidden.size ? groupFilms(visible.filter(i => i.listed)) : [...state.byKey.values()];
  const fresh = visible.filter(i => i.alert !== "seed");
  state.counts = {
    now: films.filter(g => g.showing === "now").length,
    soon: films.filter(g => g.showing === "soon").length,
    new: fresh.length,
  };
  renderControls(state.counts);

  const q = filmKey(state.query);
  const raw = state.query.trim().toLowerCase();
  const feed = document.getElementById("feed");
  if (state.view === "want") return renderWant(feed, q, raw);
  if (state.view === "tickets") return renderTickets(feed, q, raw);
  if (!state.items.length) {
    feed.replaceChildren(el("p", { class: "empty" }, "No data yet — waiting for the first scheduled run."));
    return;
  }

  if (state.view === "new") {
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

  const matches = g => !q || g.key.includes(q) || g.items.some(i => i.title.toLowerCase().includes(raw));
  const shown = sortFilms(films.filter(g => g.showing === state.view && matches(g)));
  feed.replaceChildren(shown.length ? el("div", { class: "grid" }, ...shown.map(filmCard))
    : el("p", { class: "empty" }, q ? "No films match your search." : "Nothing here for the selected cinemas."));
}

const byTitle = (a, b) => a.title.localeCompare(b.title, "en", { sensitivity: "base" });

function sortFilms(list) {
  if (state.sort === "new") return list.sort((a, b) => b.firstSeen.localeCompare(a.firstSeen) || byTitle(a, b));
  if (state.sort === "most") return list.sort((a, b) => b.sources.length - a.sources.length || byTitle(a, b));
  if (state.sort === "rated") return list.sort((a, b) => score(b.rating) - score(a.rating) || byTitle(a, b));
  if (state.sort === "next") { // films with times first, soonest screening first
    const next = g => g.sessions[0]?.start || "9999";
    return list.sort((a, b) => next(a).localeCompare(next(b)) || byTitle(a, b));
  }
  return list.sort(byTitle);
}

// --- Personal lists: Want to see and Tickets --------------------------------------------
// The site and its data files are public, so these never leave this browser: the lists are in
// localStorage, ticket images in IndexedDB. "Back up" saves both to a file, "Restore" reads it
// back (to move to another browser or device). Films are matched by filmKey, so a film on the
// list lights up at whichever cinemas list it.

const WANT = "cinema.want", TICKETS = "cinema.tickets";
const START = /^\d{4}-\d\d-\d\dT\d\d:\d\d$/; // Singapore time, like showtimes.json
const LATE = 3 * 3600e3; // a ticket counts as upcoming until 3 h after the screening starts
const mine = { want: new Map(), tickets: [] };

function loadMine() {
  const want = load(WANT, {});
  mine.want = new Map(Object.values(want && typeof want === "object" ? want : {})
    .filter(f => f && typeof f.title === "string").map(f => [filmKey(f.title), f])); // re-keyed in case filmKey changed
  const tickets = load(TICKETS, []);
  mine.tickets = Array.isArray(tickets) ? tickets.filter(validTicket) : [];
}

function validTicket(t) {
  return t && typeof t.id === "string" && typeof t.title === "string" && START.test(t.start);
}

function saveMine() {
  if (!(save(WANT, Object.fromEntries(mine.want)) && save(TICKETS, mine.tickets))) {
    alert("Couldn't save on this device (private browsing, or storage is full).");
  }
  // Ask the browser not to clear this site's storage on its own (Safari and Chrome may grant it).
  if (navigator.storage?.persist) navigator.storage.persist().catch(() => {});
}

function safeUrl(u) {
  return typeof u === "string" && /^https?:\/\//i.test(u) ? u : null;
}

function newId() {
  return crypto.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

// What to keep about a film, for when no cinema lists it any more.
function snapshot(g) {
  return { title: g.title, poster: g.posters[0] || null, url: g.items[0].url };
}

const byStart = (a, b) => a.start.localeCompare(b.start);
function upcomingTickets() {
  const cutoff = sgtNow(new Date(Date.now() - LATE));
  return mine.tickets.filter(t => t.start >= cutoff).sort(byStart);
}
function pastTickets() {
  const cutoff = sgtNow(new Date(Date.now() - LATE));
  return mine.tickets.filter(t => t.start < cutoff).sort((a, b) => byStart(b, a));
}

// --- Icons and card buttons --------------------------------------------------------------

const ICONS = {
  star: "M12 3.2l2.6 5.5 6 .7-4.4 4.1 1.2 5.9L12 16.5l-5.4 2.9 1.2-5.9-4.4-4.1 6-.7z",
  ticket: "M3.5 6.5h17v3a2.5 2.5 0 0 0 0 5v3h-17v-3a2.5 2.5 0 0 0 0-5zM14.5 8.5v1.2M14.5 11.4v1.2M14.5 14.3v1.2",
};

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", `icon icon-${name}`);
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICONS[name]);
  svg.append(path);
  return svg;
}

function button(label, onClick, cls = "btn") {
  const b = el("button", { type: "button", class: cls }, ...[label].flat());
  b.addEventListener("click", onClick);
  return b;
}

// The two round buttons on a poster: Want to see (toggle) and I have tickets.
function actions(key, snap) {
  const want = el("button", { type: "button", class: "act", "data-want": key, "aria-label": "Want to see" }, icon("star"));
  markWant(want, mine.want.has(key));
  want.addEventListener("click", () => toggleWant(key, snap));
  const has = upcomingTickets().some(t => filmKey(t.title) === key);
  const tix = el("button", { type: "button", class: "act" + (has ? " has" : ""), "aria-label": "Add tickets",
    title: "I have tickets" }, icon("ticket"));
  tix.addEventListener("click", () => ticketForm({ key, snap }));
  return el("div", { class: "acts" }, want, tix);
}

function markWant(btn, on) {
  btn.setAttribute("aria-pressed", String(on));
  btn.title = on ? "On your Want to see list (tap to remove)" : "Want to see";
}

function toggleWant(key, snap) {
  if (mine.want.has(key)) mine.want.delete(key);
  else mine.want.set(key, { ...snap, added: new Date().toISOString() });
  saveMine();
  if (state.view === "want") return render();
  for (const b of document.querySelectorAll("[data-want]")) if (b.dataset.want === key) markWant(b, mine.want.has(key));
  renderControls(state.counts);
}

// "🎟 Sat 22 Nov · 7:30 pm" on a film's card when you have tickets for it.
function booked(key) {
  const t = upcomingTickets().find(x => filmKey(x.title) === key);
  if (!t) return null;
  const b = button([icon("ticket"), ` ${dayShort(t.start.slice(0, 10))} · ${clock(t.start)}`], () => go("tickets"), "booked");
  b.title = "You have tickets — open Tickets";
  return b;
}

// --- Want to see tab ---------------------------------------------------------------------

function renderWant(feed, q, raw) {
  const showing = [], soon = [], unlisted = [];
  for (const [key, f] of mine.want) {
    if (q && !key.includes(q) && !f.title.toLowerCase().includes(raw)) continue;
    const g = state.byKey.get(key);
    if (!g) unlisted.push([key, f]);
    else (g.showing === "now" ? showing : soon).push(g);
  }
  const parts = [];
  const section = (title, cards) => { if (cards.length) parts.push(el("h2", {}, title), el("div", { class: "grid" }, ...cards)); };
  section("Showing now", sortFilms(showing).map(filmCard));
  section("Coming soon", sortFilms(soon).map(filmCard));
  section("Not listed right now", unlisted.sort((a, b) => (b[1].added || "").localeCompare(a[1].added || ""))
    .map(([key, f]) => unlistedCard(key, f)));
  if (!parts.length) {
    parts.push(el("p", { class: "empty" }, q ? "No films on your list match your search."
      : el("span", {}, "Nothing here yet. Tap ", icon("star"), " on a film's poster to keep it here, with where and when it's showing.")));
  }
  parts.push(privacyNote());
  feed.replaceChildren(...parts);
}

function unlistedCard(key, f) {
  return el("article", { class: "card gone" },
    el("div", { class: "art" }, poster(safeUrl(f.poster) ? [f.poster] : [], safeUrl(f.url)), actions(key, f)),
    el("div", { class: "body" },
      el("h3", { class: "title" }, f.title),
      el("span", { class: "meta" }, "No cinema lists it right now. It moves up when one does."),
      booked(key)));
}

// --- Tickets tab -------------------------------------------------------------------------

function renderTickets(feed, q, raw) {
  const match = t => !q || filmKey(t.title).includes(q) || t.title.toLowerCase().includes(raw);
  const upcoming = upcomingTickets().filter(match);
  const past = pastTickets().filter(match);
  const parts = [el("div", { class: "bar" }, button("+ Add tickets", () => ticketForm({}), "btn primary"))];
  const days = new Map();
  for (const t of upcoming) {
    const day = t.start.slice(0, 10);
    if (!days.has(day)) days.set(day, []);
    days.get(day).push(t);
  }
  for (const [day, list] of days) parts.push(el("h2", {}, dayShort(day)), el("div", { class: "tickets" }, ...list.map(t => ticketRow(t))));
  if (!upcoming.length) {
    parts.push(el("p", { class: "empty" }, q ? "No tickets match your search."
      : el("span", {}, "No upcoming tickets. After you book, tap ", icon("ticket"),
        " on the film's poster (or Add tickets) to keep the time, seats and booking reference here.")));
  }
  if (past.length) {
    parts.push(el("details", { class: "past" }, el("summary", {}, `Past tickets (${past.length})`),
      el("div", { class: "tickets" }, ...past.map(t => ticketRow(t, true)))));
  }
  parts.push(privacyNote());
  feed.replaceChildren(...parts);
}

function ticketRow(t, past = false) {
  const g = state.byKey.get(filmKey(t.title));
  const posters = [...new Set([safeUrl(t.poster), ...(g?.posters || [])].filter(Boolean))];
  const day = t.start.slice(0, 10);
  const when = past ? dayLabel(day) : dayShort(day);
  const link = safeUrl(t.link);
  return el("article", { class: "ticket" + (past ? " past" : "") },
    poster(posters, safeUrl(t.url) || g?.items[0].url),
    el("div", { class: "body" },
      el("h3", { class: "title" }, t.title),
      el("p", { class: "when" }, `${when} · ${clock(t.start)}`),
      t.cinema ? el("p", { class: "meta" }, t.cinema) : null,
      t.seats || t.ref ? el("p", { class: "meta" },
        [t.seats && `Seats ${t.seats}`, t.ref && `Ref ${t.ref}`].filter(Boolean).join(" · ")) : null,
      el("div", { class: "tacts" },
        t.image ? button("Show ticket", () => showImage(t), "btn primary") : null,
        link ? el("a", { class: "btn", href: link, target: "_blank", rel: "noopener" }, "Open ticket") : null,
        past ? null : button("Add to calendar", () => download(`${slug(t.title)}.ics`, "text/calendar", ics(t))),
        button("Edit", () => ticketForm({ ticket: t })))));
}

function slug(s) {
  return filmKey(s).replace(/\s+/g, "-").slice(0, 60) || "ticket";
}

function privacyNote() {
  return el("p", { class: "privacy muted" },
    "Your lists are saved in this browser only, not on the public site. ",
    button("Back up", backup, "link"), " · ", button("Restore", pickBackup, "link"));
}

// --- Ticket form -------------------------------------------------------------------------

function ticketForm({ key, snap, ticket }) {
  const input = (attrs) => el("input", { autocomplete: "off", ...attrs });
  const field = (label, control, hint) => el("label", { class: "field" }, el("span", {}, label), control,
    hint ? el("small", {}, hint) : null);

  const film = input({ name: "title", required: true, list: "film-titles", value: ticket?.title ?? snap?.title ?? "",
    placeholder: "Film" });
  const date = input({ type: "date", required: true, value: ticket?.start.slice(0, 10) ?? sgtDate(new Date()) });
  const time = input({ type: "time", required: true, value: ticket?.start.slice(11, 16) ?? "" });
  const cinema = input({ list: "cinema-names", value: ticket?.cinema ?? "", placeholder: "Cinema" });
  const seats = input({ value: ticket?.seats ?? "", placeholder: "e.g. F7, F8" });
  const ref = input({ value: ticket?.ref ?? "", placeholder: "From the confirmation" });
  const link = input({ type: "url", value: ticket?.link ?? "", placeholder: "https://…" });
  const image = el("input", { type: "file", accept: "image/*" });
  const dropImage = el("input", { type: "checkbox" });
  const picks = el("div", { class: "picks" });

  // Screening times we know for the film (Filmhouse, AFA, SFS): tap one to fill in the form.
  const filmFor = () => state.byKey.get(filmKey(film.value));
  const showPicks = () => {
    const g = filmFor();
    const multi = g && g.sources.length > 1;
    if (g && !ticket && !cinema.value && g.sources.length === 1) cinema.value = sourceName(g.sources[0]);
    picks.replaceChildren(...(g?.sessions || []).slice(0, 16).map(s => button(
      [el("b", {}, `${dayShort(s.start.slice(0, 10))} ${clock(s.start)}`), multi ? ` ${shortName(s.source)}` : null],
      e => {
        date.value = s.start.slice(0, 10);
        time.value = s.start.slice(11, 16);
        cinema.value = [sourceName(s.source), s.venue].filter(Boolean).join(" · ");
        for (const b of picks.children) b.classList.toggle("on", b === e.currentTarget);
      }, `pick src-${s.source}`)));
    picks.hidden = !picks.children.length;
  };
  film.addEventListener("input", showPicks);

  const close = () => dlg.close();
  const form = el("form", { class: "form" },
    el("h2", {}, ticket ? "Edit tickets" : "I have tickets"),
    field("Film", film),
    el("div", { class: "field" }, el("span", {}, "Screening"), picks),
    el("div", { class: "two" }, field("Date", date), field("Time", time)),
    field("Cinema", cinema),
    el("div", { class: "two" }, field("Seats", seats), field("Booking ref", ref)),
    field("Link to the e-ticket", link, "Optional: the ticket page from the cinema's email or site."),
    field("Ticket image", image, "Optional: a screenshot of the e-ticket or its QR code, to show at the door."),
    ticket?.image ? el("label", { class: "check" }, dropImage, " Remove the saved image") : null,
    el("p", { class: "muted small" }, "Saved on this device only."),
    el("div", { class: "buttons" },
      ticket ? button("Delete", () => {
        if (!confirm(`Delete your tickets for ${ticket.title}?`)) return;
        mine.tickets = mine.tickets.filter(t => t.id !== ticket.id);
        images.del(ticket.id).catch(() => {});
        saveMine();
        close();
        render();
      }, "btn danger") : null,
      button("Cancel", close),
      el("button", { type: "submit", class: "btn primary" }, "Save")),
    el("datalist", { id: "film-titles" }, ...[...state.byKey.values()].sort(byTitle).map(g => el("option", { value: g.title }))),
    el("datalist", { id: "cinema-names" }, ...sourceKeys().map(k => el("option", { value: sourceName(k) }))));

  form.addEventListener("submit", async e => {
    e.preventDefault();
    const title = film.value.trim();
    const k = filmKey(title);
    const g = state.byKey.get(k);
    const known = g ? snapshot(g) : ticket && filmKey(ticket.title) === k ? ticket : snap && k === key ? snap : {};
    const t = {
      id: ticket?.id || newId(), title, start: `${date.value}T${time.value.slice(0, 5)}`,
      cinema: cinema.value.trim(), seats: seats.value.trim(), ref: ref.value.trim(), link: link.value.trim(),
      poster: safeUrl(known.poster), url: safeUrl(known.url), image: !!ticket?.image,
      added: ticket?.added || new Date().toISOString(),
    };
    if (!START.test(t.start)) return alert("Pick a date and time.");
    try {
      if (image.files[0]) {
        await images.put(t.id, await shrink(image.files[0]));
        t.image = true;
      } else if (dropImage.checked) {
        await images.del(t.id);
        t.image = false;
      }
    } catch (err) {
      alert(`Couldn't save the ticket image (${err.message || err}). The rest is saved.`);
    }
    mine.tickets = [...mine.tickets.filter(x => x.id !== t.id), t];
    if (!ticket) mine.want.delete(k); // booked: it moves from Want to see to Tickets
    saveMine();
    close();
    render();
  });

  const dlg = el("dialog", { class: "sheet", "aria-label": ticket ? "Edit tickets" : "I have tickets" }, form);
  dlg.addEventListener("click", e => { if (e.target === dlg) close(); }); // tap outside
  dlg.addEventListener("close", () => dlg.remove());
  document.body.append(dlg);
  showPicks();
  dlg.showModal();
  if (!film.value) film.focus();
}

// --- Ticket images (IndexedDB: too big for localStorage) ---------------------------------

let imageDb;
function idb(mode, op) {
  imageDb ||= new Promise((resolve, reject) => {
    const req = indexedDB.open("cinema", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("images");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return imageDb.then(db => new Promise((resolve, reject) => {
    const tx = db.transaction("images", mode);
    const req = op(tx.objectStore("images"));
    tx.oncomplete = () => resolve(req.result);
    tx.onerror = tx.onabort = () => reject(tx.error);
  }));
}
const images = {
  get: id => idb("readonly", s => s.get(id)),
  put: (id, dataUrl) => idb("readwrite", s => s.put(dataUrl, id)),
  del: id => idb("readwrite", s => s.delete(id)),
};

// Screenshots are large; 1600 px on the long side keeps a QR code sharp.
async function shrink(file, max = 1600) {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const i = new Image();
      i.onload = () => resolve(i);
      i.onerror = () => reject(new Error("not an image"));
      i.src = url;
    });
    const scale = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
    const canvas = el("canvas", { width: Math.round(img.naturalWidth * scale), height: Math.round(img.naturalHeight * scale) });
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.9);
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function showImage(t) {
  const data = await images.get(t.id).catch(() => null);
  if (!data) return alert("This ticket's image isn't saved in this browser.");
  const dlg = el("dialog", { class: "viewer", "aria-label": `Ticket for ${t.title}` },
    el("img", { src: data, alt: `Ticket for ${t.title}` }), el("p", {}, "Tap to close"));
  dlg.addEventListener("click", () => dlg.close());
  dlg.addEventListener("close", () => dlg.remove());
  document.body.append(dlg);
  dlg.showModal();
}

// --- Calendar, backup, restore -----------------------------------------------------------

function download(name, type, text) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = el("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60e3);
}

// One calendar event: a 2-hour slot (the runtime isn't known) with a reminder an hour before.
function ics(t) {
  const stamp = d => d.toISOString().replace(/[-:]/g, "").replace(/\.\d+/, ""); // 20261122T113000Z
  const text = s => String(s).replace(/[\\;,]/g, m => `\\${m}`).replace(/\r?\n/g, "\\n");
  const fold = line => { const c = [...line], out = []; for (let i = 0; i < c.length; i += 60) out.push(c.slice(i, i + 60).join("")); return out.join("\r\n "); };
  const start = new Date(`${t.start}:00+08:00`);
  const link = safeUrl(t.link);
  const notes = [t.seats && `Seats: ${t.seats}`, t.ref && `Booking ref: ${t.ref}`, link].filter(Boolean).join("\n");
  return [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//cinema//tickets//EN", "BEGIN:VEVENT",
    `UID:${t.id}@cinema`, `DTSTAMP:${stamp(new Date())}`,
    `DTSTART:${stamp(start)}`, `DTEND:${stamp(new Date(start.getTime() + 2 * 3600e3))}`,
    `SUMMARY:${text(t.title)}`,
    t.cinema ? `LOCATION:${text(t.cinema)}` : null,
    notes ? `DESCRIPTION:${text(notes)}` : null,
    link ? `URL:${link}` : null,
    "BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${text(t.title)}`, "TRIGGER:-PT1H", "END:VALARM",
    "END:VEVENT", "END:VCALENDAR",
  ].filter(Boolean).map(fold).join("\r\n") + "\r\n";
}

async function backup() {
  const imgs = {};
  for (const t of mine.tickets) {
    if (!t.image) continue;
    const data = await images.get(t.id).catch(() => null);
    if (data) imgs[t.id] = data;
  }
  const data = { app: "cinema", version: 1, saved: new Date().toISOString(),
    want: Object.fromEntries(mine.want), tickets: mine.tickets, images: imgs };
  download(`cinema-backup-${sgtDate(new Date())}.json`, "application/json", JSON.stringify(data));
}

function pickBackup() {
  const input = el("input", { type: "file", accept: "application/json,.json" });
  input.addEventListener("change", async () => {
    if (input.files[0]) await restore(await input.files[0].text());
  });
  input.click();
}

// Adds what the backup has and this browser doesn't; never deletes anything.
async function restore(text) {
  let data;
  try { data = JSON.parse(text); } catch { data = null; }
  if (data?.app !== "cinema") return alert("That file isn't a Cinema backup.");
  let films = 0, tickets = 0;
  for (const f of Object.values(data.want || {})) {
    if (!f || typeof f.title !== "string" || mine.want.has(filmKey(f.title))) continue;
    mine.want.set(filmKey(f.title), f);
    films++;
  }
  const have = new Set(mine.tickets.map(t => t.id));
  for (const t of Array.isArray(data.tickets) ? data.tickets : []) {
    if (!validTicket(t) || have.has(t.id)) continue;
    const img = data.images?.[t.id];
    t.image = typeof img === "string" && img.startsWith("data:image/")
      && await images.put(t.id, img).then(() => true, () => false);
    mine.tickets.push(t);
    tickets++;
  }
  saveMine();
  render();
  alert(`Restored ${films} film${films === 1 ? "" : "s"} and ${tickets} ticket${tickets === 1 ? "" : "s"}.`);
}

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

async function main() {
  loadMine();
  addEventListener("storage", () => { loadMine(); render(); }); // changed in another tab
  state.view = load("view", "now");
  if (!VIEWS.some(([k]) => k === state.view)) state.view = "now";
  state.hidden = new Set(load("hidden", []));
  state.sort = load("sort", "az");
  const sort = document.getElementById("sort");
  sort.value = state.sort;
  sort.addEventListener("change", () => { state.sort = sort.value; save("sort", sort.value); render(); });
  const search = document.getElementById("search");
  search.addEventListener("input", () => { state.query = search.value; render(); });

  const [items, status, ratings, showtimes] = await Promise.allSettled(
    ["data/items.json", "data/status.json", "data/ratings.json", "data/showtimes.json"].map(getJSON));
  state.items = items.status === "fulfilled" ? items.value.items || [] : [];
  state.status = status.status === "fulfilled" ? status.value : null;
  state.ratings = ratings.status === "fulfilled" ? ratings.value : null;
  state.showtimes = showtimes.status === "fulfilled" ? showtimes.value : null;
  document.getElementById("checked").textContent = state.status ? `Checked ${ago(state.status.checked)}` : "Not checked yet";
  render();
}

main();
