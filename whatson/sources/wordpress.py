"""WordPress REST API helpers (/wp-json/wp/v2/...)."""

from __future__ import annotations

from .html import clean


def find_rest_base(http, base: str, candidates: list[str]) -> str | None:
    """Return the rest_base of the first post type whose key or rest_base is a candidate."""
    types = http.get_json(f"{base}/wp-json/wp/v2/types")
    for want in candidates:
        for key, t in types.items():
            if want in (key, t.get("rest_base")):
                return t.get("rest_base") or key
    return None


def latest_posts(http, base: str, rest_base: str, per_page: int = 100) -> list[dict]:
    """Most recently published posts of a type. New listings are new posts, so one page is enough."""
    return http.get_json(
        f"{base}/wp-json/wp/v2/{rest_base}",
        params={"per_page": per_page, "orderby": "date", "order": "desc", "_embed": "wp:featuredmedia,wp:term"},
    )


def title(post: dict) -> str:
    return clean((post.get("title") or {}).get("rendered"))


def featured_image(post: dict) -> str | None:
    media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
    if media and isinstance(media[0], dict) and media[0].get("source_url"):
        return media[0]["source_url"]
    og = (post.get("yoast_head_json") or {}).get("og_image") or []
    return og[0].get("url") if og else None


def term_names(post: dict, taxonomies: set[str] | None = None) -> list[str]:
    names = []
    for group in (post.get("_embedded") or {}).get("wp:term") or []:
        for term in group or []:
            if isinstance(term, dict) and (taxonomies is None or term.get("taxonomy") in taxonomies):
                name = clean(term.get("name"))
                if name and name not in names:
                    names.append(name)
    return names
