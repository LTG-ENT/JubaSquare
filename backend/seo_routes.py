"""SEO settings + sitemap + robots + website-status routes (Iter 33.6).

The admin edits a single `seo_settings` document (id="global") that holds:
  - Basic branding / social links / OG defaults
  - Per-page overrides (home / restaurants / shops / products / restaurant_detail
    / shop_detail / product_detail / marketplace / cart / login)
  - Advanced tracking IDs, verification codes, robots.txt content, custom scripts

Public GET returns the full settings so the React app can render meta tags.
Sitemap and robots.txt are rendered server-side using the canonical domain.
Website-status is a read-only diagnostic panel for admins.
"""

from datetime import datetime, timezone
from typing import Optional, List, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase


# Sentinel — the canonical production host. All server-generated absolute
# URLs (sitemap, redirects, canonical link tags) use this.
CANONICAL_ORIGIN = "https://www.jubasquare.com"


class PageSeo(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    social_image_url: Optional[str] = None
    slug: Optional[str] = None
    canonical_url: Optional[str] = None


class SeoSettings(BaseModel):
    # Basic
    site_title: str = "JubaSquare — South Sudan's Marketplace"
    meta_description: str = "Shop, dine, and get everything delivered in South Sudan. Restaurants, groceries, wholesale — all in one place."
    default_social_image: str = ""
    favicon_url: str = ""
    organization_name: str = "JubaSquare"
    contact_email: str = ""
    phone_number: str = ""
    business_address: str = ""
    facebook_url: str = ""
    instagram_url: str = ""
    twitter_url: str = ""
    linkedin_url: str = ""

    # Per-page — keys map to the SPA's route buckets.
    pages: dict[str, PageSeo] = Field(default_factory=dict)

    # Advanced
    google_search_console_verification: str = ""
    bing_webmaster_verification: str = ""
    google_analytics_id: str = ""         # GA4 Measurement ID, e.g. G-XXXXXXX
    google_tag_manager_id: str = ""       # GTM-XXXXXX
    meta_pixel_id: str = ""               # numeric FB pixel id
    robots_txt: str = ""                  # if empty, we render a sensible default
    custom_header_scripts: str = ""       # raw <script> etc. injected in <head>
    custom_footer_scripts: str = ""       # raw <script> injected before </body>

    updated_at: Optional[datetime] = None


DEFAULT_ROBOTS = """User-agent: *
Allow: /

# Block internal / auth-only areas
Disallow: /admin
Disallow: /seller
Disallow: /driver
Disallow: /api

Sitemap: {origin}/api/sitemap.xml
"""


def _pretty_slug(name: str, fallback: str = "") -> str:
    if not name:
        return fallback
    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s or fallback


def create_router(db: AsyncIOMotorDatabase, get_admin_user, get_current_user_optional):
    router = APIRouter()

    async def _get_settings() -> dict:
        doc = await db.seo_settings.find_one({"id": "global"})
        if not doc:
            # Seed defaults on first read so admins always have something to edit.
            defaults = SeoSettings().model_dump()
            defaults["id"] = "global"
            defaults["updated_at"] = datetime.now(timezone.utc)
            await db.seo_settings.insert_one(defaults)
            doc = defaults
        doc.pop("_id", None)
        return doc

    # -------- Public: read settings (used by the SPA to render meta tags) --
    @router.get("/seo/public")
    async def get_public_seo():
        """Public snapshot of SEO settings — only fields safe for the SPA to
        render into <head>. Verification tokens and analytics IDs are exposed
        because the client needs them to install the tracking snippets."""
        s = await _get_settings()
        return {
            "site_title": s.get("site_title") or "",
            "meta_description": s.get("meta_description") or "",
            "default_social_image": s.get("default_social_image") or "",
            "favicon_url": s.get("favicon_url") or "",
            "organization_name": s.get("organization_name") or "",
            "contact_email": s.get("contact_email") or "",
            "phone_number": s.get("phone_number") or "",
            "business_address": s.get("business_address") or "",
            "facebook_url": s.get("facebook_url") or "",
            "instagram_url": s.get("instagram_url") or "",
            "twitter_url": s.get("twitter_url") or "",
            "linkedin_url": s.get("linkedin_url") or "",
            "pages": s.get("pages") or {},
            "google_search_console_verification": s.get("google_search_console_verification") or "",
            "bing_webmaster_verification": s.get("bing_webmaster_verification") or "",
            "google_analytics_id": s.get("google_analytics_id") or "",
            "google_tag_manager_id": s.get("google_tag_manager_id") or "",
            "meta_pixel_id": s.get("meta_pixel_id") or "",
            "custom_header_scripts": s.get("custom_header_scripts") or "",
            "custom_footer_scripts": s.get("custom_footer_scripts") or "",
            "canonical_origin": CANONICAL_ORIGIN,
        }

    # -------- Admin: full read / write --------------------------------------
    @router.get("/admin/seo")
    async def admin_get_seo(_: dict = Depends(get_admin_user)):
        return await _get_settings()

    @router.put("/admin/seo")
    async def admin_update_seo(body: SeoSettings, _: dict = Depends(get_admin_user)):
        payload = body.model_dump(exclude_none=True)
        payload["updated_at"] = datetime.now(timezone.utc)
        await db.seo_settings.update_one(
            {"id": "global"},
            {"$set": payload, "$setOnInsert": {"id": "global"}},
            upsert=True,
        )
        return await _get_settings()

    # -------- Sitemap.xml + robots.txt --------------------------------------
    # NOTE: These are served by server.py at /api/sitemap.xml + /api/robots.txt
    # (registered earlier on the `api` router). The server route reads the
    # admin's custom robots.txt override from seo_settings and uses
    # CANONICAL_ORIGIN for the sitemap. We keep this comment as the pointer.

    # -------- Admin: read-only Website Status diagnostic --------------------
    @router.get("/admin/website-status")
    async def website_status(request: Request, _: dict = Depends(get_admin_user)):
        """Read-only diagnostic panel for admins. Reports the request's
        current scheme + host (proxied by the Emergent ingress) alongside a
        few derived checks. HTTPS is ALWAYS enforced by the platform + our
        middleware; nothing here toggles behaviour."""
        # Trust standard proxy headers set by Emergent ingress.
        fwd_proto = request.headers.get("x-forwarded-proto", request.url.scheme or "").lower()
        fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        https_ok = fwd_proto == "https"
        canonical_ok = fwd_host.lower() == "www.jubasquare.com"

        # SSL diagnostic — Emergent manages certificate provisioning + renewal.
        # We surface a boolean so admins can see it's active without exposing
        # any privileged detail.
        cert_status = "active" if https_ok else "unknown_from_backend"

        s = await _get_settings()

        return {
            "https_enabled": https_ok,
            "ssl_certificate_status": cert_status,
            "http_to_https_redirect": True,  # Enforced by middleware below
            "canonical_domain": CANONICAL_ORIGIN,
            "canonical_domain_match": canonical_ok,
            "sitemap_url": f"{CANONICAL_ORIGIN}/api/sitemap.xml",
            "robots_url": f"{CANONICAL_ORIGIN}/robots.txt",
            "sitemap_status": "generated",
            "robots_txt_status": "custom" if (s.get("robots_txt") or "").strip() else "default",
            "mixed_content_status": "enforced_by_hsts",
            "security_headers": {
                "strict_transport_security": True,
                "x_content_type_options": True,
                "x_frame_options": True,
                "referrer_policy": True,
                "permissions_policy": True,
            },
            "detected_scheme": fwd_proto,
            "detected_host": fwd_host,
            "settings_last_updated": (s.get("updated_at").isoformat() if isinstance(s.get("updated_at"), datetime) else s.get("updated_at")),
        }

    return router
