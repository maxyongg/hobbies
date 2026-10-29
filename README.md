# hobbies

**whats-on-sg** — A personal web app that tells me when new films are added at the Singapore cinemas I care about.

## What it does (v1)

1. Polls the listings of three cinemas on a schedule:
   - **Filmhouse** (Golden Mile Tower) — https://filmhouse.sg
   - **Shaw Theatres** — https://shaw.sg
   - **Asian Film Archive (AFA)** — Oldham Theatre — https://asianfilmarchive.org
2. Compares each listing against what it has seen before.
3. When a film is new, it:
   - sends me an alert, and
   - shows it in the web app (and, later, a home-screen widget).

## Roadmap

- **v1** — new-film alerts for Filmhouse, Shaw, AFA.
- **Later** — gallery openings and things to do in Singapore, sourced from social media posts/ads.
- **Later** — highly rated new video games (currently handled by a separate Claude routine; may be folded in here).

## Status

Scaffold only. No code yet. See [`CLAUDE.md`](CLAUDE.md) for the handover: decisions, open questions, and next steps.

Source-by-source notes on how each site lists films: [`docs/sources.md`](docs/sources.md).
