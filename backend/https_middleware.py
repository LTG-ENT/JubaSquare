"""HTTPS + canonical redirect + security-header middleware (Iter 33.6).

Adds three concerns that MUST run on every request:
  1. Redirect http:// → https://
  2. Redirect any host (jubasquare.com, apex, non-www) → www.jubasquare.com
  3. Emit HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
     Permissions-Policy on every response.

Emergent's edge already terminates TLS and typically upgrades HTTP → HTTPS at
the ingress. This middleware is a safety-net + belt-and-braces enforcement so
the app remains compliant if it's ever fronted by a different proxy or served
directly.

We deliberately EXCLUDE the following hosts from canonical redirects:
  * localhost / 127.0.0.1 (dev)
  * *.preview.emergentagent.com (preview environment)
  * *.emergent.host and internal K8s hosts
so the preview environment continues to work at whatever URL is provisioned.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse


CANONICAL_HOST = "www.jubasquare.com"
_PROD_HOSTS = {"jubasquare.com", "www.jubasquare.com"}


def _is_dev_host(host: str) -> bool:
    h = (host or "").lower().split(":")[0]
    if not h:
        return True
    if h == "localhost" or h.startswith("127.") or h == "0.0.0.0":
        return True
    if h.endswith(".preview.emergentagent.com"):
        return True
    if h.endswith(".emergent.host") or h.endswith(".emergentagent.com"):
        return True
    return False


class HTTPSAndCanonicalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Resolve the effective scheme/host through the edge proxy.
        headers = request.headers
        proto = (headers.get("x-forwarded-proto") or request.url.scheme or "").lower()
        host = (headers.get("x-forwarded-host") or headers.get("host") or "").lower()

        # Only enforce canonical redirects on production hosts. Preview and
        # local envs pass through untouched (still get headers below).
        prod = host.split(":")[0] in _PROD_HOSTS
        if prod:
            # http:// → https://  OR  apex → www  →  single 301 to the canonical origin.
            wants_https = proto != "https"
            wants_www = host.split(":")[0] != CANONICAL_HOST
            if wants_https or wants_www:
                new_url = f"https://{CANONICAL_HOST}{request.url.path}"
                if request.url.query:
                    new_url = f"{new_url}?{request.url.query}"
                return RedirectResponse(new_url, status_code=301)

        response = await call_next(request)

        # Security headers (all requests, dev + prod).
        # HSTS: only send when actually served over HTTPS so browsers don't
        # cache a bad rule for a dev host that only has HTTP.
        if proto == "https" or not _is_dev_host(host):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(self), camera=(), microphone=(), payment=(self)",
        )
        return response
