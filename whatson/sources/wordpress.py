"""WordPress REST API helpers (/wp-json/wp/v2/...)."""

from __future__ import annotations

from .html import clean


def latest_posts(http, base: str, rest_base: str, per_page: int = 100, fields: str | None = None) -> list[dict]:
    """Most recently published posts of a type. New listings are new posts, so one page is enough.

    With `fields`, ask only for those (much lighter); otherwise embed images and terms.
    """
    params = {"per_page": per_page, "orderby": "date", "order": "desc"}
    if fields:
        params["_fields"] = fields
    else:
        params["_embed"] = "wp:featuredmedia,wp:term"
    return http.get_json(f"{base}/wp-json/wp/v2/{rest_base}", params=params)


def title(post: dict) -> str:
    return clean((post.get("title") or {}).get("rendered"))


def featured_image(post: dict) -> str | None:
    media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
    if media and isinstance(media[0], dict) and media[0].get("source_url"):
        return media[0]["source_url"]
    og = (post.get("yoast_head_json") or {}).get("og_image") or []
    return og[0].get("url") if og else None


def class_terms(post: dict, prefixes: tuple[str, ...]) -> list[str]:
    """Term names from post_class() entries like "mep_cat-screening" (no _embed needed)."""
    names = []
    for prefix in prefixes:
        for c in post.get("class_list") or []:
            if c.startswith(prefix):
                name = c.removeprefix(prefix).replace("-", " ").strip().capitalize()
                if name and name not in names:
                    names.append(name)
    return names
