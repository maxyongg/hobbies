// Cinema — iOS home-screen widget for Scriptable (https://scriptable.app).
//
// Setup: in Scriptable, + → paste this file (https://maxyongg.github.io/hobbies/widget.js)
// → name it "Cinema". Add a Scriptable widget to the home screen, long-press → Edit Widget
// → Script: Cinema.
// Optional widget Parameter: sources to show, comma-separated, e.g. "filmhouse,afa".
//
// Shows the newest films first seen by the scraper (data/items.json on GitHub Pages).
// Tapping a film (medium/large) opens it; tapping elsewhere opens the web app.

const SITE = "https://maxyongg.github.io/hobbies/";
const DATA_URL = SITE + "data/items.json";
const SHORT = { filmhouse: "FH", shaw: "SHAW", afa: "AFA" };
const COLORS = {
  filmhouse: Color.dynamic(new Color("#b4441f"), new Color("#f08a5d")),
  shaw: Color.dynamic(new Color("#2160a8"), new Color("#6aa5ec")),
  afa: Color.dynamic(new Color("#7a4bb0"), new Color("#b48ae8")),
};
const TEXT = Color.dynamic(new Color("#1c1b19"), new Color("#ecebe8"));
const MUTED = Color.dynamic(new Color("#6d6a63"), new Color("#9b998f"));
const BG = Color.dynamic(new Color("#f6f4ef"), new Color("#141416"));
const NEW_DAYS = 7;

async function loadData() {
  const fm = FileManager.local();
  const cache = fm.joinPath(fm.cacheDirectory(), "cinema.json");
  try {
    const req = new Request(DATA_URL);
    req.timeoutInterval = 15;
    const data = await req.loadJSON();
    fm.writeString(cache, JSON.stringify(data));
    return { data, stale: false };
  } catch (e) {
    if (fm.fileExists(cache)) return { data: JSON.parse(fm.readString(cache)), stale: true };
    throw e;
  }
}

function shortDate(iso) {
  const days = Math.floor((Date.now() - new Date(iso)) / 864e5);
  if (days < 1) return "today";
  if (days < 2) return "1d";
  return `${days}d`;
}

function build(items, family, stale) {
  const w = new ListWidget();
  w.backgroundColor = BG;
  w.url = SITE;
  w.setPadding(12, 14, 12, 14);
  w.refreshAfterDate = new Date(Date.now() + 60 * 60 * 1000);

  const fresh = items.filter(i => Date.now() - new Date(i.first_seen) < NEW_DAYS * 864e5);
  const head = w.addStack();
  head.centerAlignContent();
  const title = head.addText(family === "small" ? "New films" : "Cinema");
  title.font = Font.boldSystemFont(family === "small" ? 13 : 14);
  title.textColor = TEXT;
  head.addSpacer();
  const count = head.addText(`${fresh.length} this week${stale ? " · offline" : ""}`);
  count.font = Font.systemFont(11);
  count.textColor = MUTED;
  w.addSpacer(6);

  const rows = { small: 3, medium: 4, large: 11, extraLarge: 11 }[family] || 4;
  if (!items.length) {
    const t = w.addText("No new films yet.");
    t.font = Font.systemFont(12);
    t.textColor = MUTED;
  }
  for (const item of items.slice(0, rows)) {
    const row = w.addStack();
    row.centerAlignContent();
    if (family !== "small") row.url = item.url;
    const src = row.addText((SHORT[item.source] || item.source).padEnd(4, " "));
    src.font = Font.boldMonospacedSystemFont(10);
    src.textColor = COLORS[item.source] || MUTED;
    row.addSpacer(6);
    const t = row.addText(item.title);
    t.font = Font.mediumSystemFont(family === "small" ? 12 : 13);
    t.textColor = item.listed ? TEXT : MUTED;
    t.lineLimit = 1;
    if (family !== "small") {
      row.addSpacer();
      const d = row.addText(shortDate(item.first_seen));
      d.font = Font.systemFont(10);
      d.textColor = MUTED;
    }
    w.addSpacer(4);
  }
  w.addSpacer();
  return w;
}

async function main() {
  const only = (args.widgetParameter || "").split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
  const family = config.widgetFamily || "medium";
  let widget;
  try {
    const { data, stale } = await loadData();
    const items = (data.items || [])
      .filter(i => i.alert !== "seed" && (!only.length || only.includes(i.source)))
      .sort((a, b) => (b.first_seen || "").localeCompare(a.first_seen || ""));
    widget = build(items, family, stale);
  } catch (e) {
    widget = new ListWidget();
    widget.backgroundColor = BG;
    const t = widget.addText(`Cinema: couldn't load (${e.message || e})`);
    t.font = Font.systemFont(12);
    t.textColor = MUTED;
  }
  if (config.runsInWidget) Script.setWidget(widget);
  else await widget.presentMedium();
  Script.complete();
}

await main();
