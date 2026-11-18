"""
extra.py - Download-manager helper for the SARKER downloader API.
Added as a Flask Blueprint so main.py's existing code stays untouched.

Endpoint:
  /proxy?url=URL&filename=NAME&referer=URL
      Streams a file through the server with Range/resume support.
      Used by the new index.html download manager when a direct browser
      download is blocked by CORS.
"""
import socket
import ipaddress
from urllib.parse import urlparse, quote

import requests
from flask import Blueprint, request, jsonify, Response, stream_with_context
from user_agent import generate_user_agent

extra_bp = Blueprint("extra", __name__)

DEV = {"Developer": "M. Sarker", "Owner": "SARKER"}

# DRM-protected services: video is encrypted, cannot be downloaded.
DRM_DOMAINS = (
    "netflix.com", "crunchyroll.com", "primevideo.com", "disneyplus.com",
    "hotstar.com", "hbomax.com", "max.com", "hulu.com", "peacocktv.com",
    "paramountplus.com", "tv.apple.com", "spotify.com",
)


def _err(msg, code=200):
    return jsonify({"status": "error", "message": msg, **DEV}), code


def _host(url):
    return (urlparse(url).hostname or "").lower()


def _is_drm_site(url):
    h = _host(url)
    return any(h == d or h.endswith("." + d) for d in DRM_DOMAINS)


def _is_safe_url(url):
    """Block SSRF: only http(s) to public IPs."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        for info in socket.getaddrinfo(p.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast):
                return False
        return True
    except Exception:
        return False


# ============================================================
# PROXY (stream + Range/resume, used by the download manager UI)
# ============================================================
@extra_bp.route("/proxy", methods=["GET", "HEAD"])
def proxy():
    url = request.args.get("url", "").strip()
    referer = request.args.get("referer", "").strip()
    filename = request.args.get("filename", "download").strip() or "download"
    if not url or not _is_safe_url(url) or _is_drm_site(url):
        return _err("Invalid or blocked URL", 400)

    headers = {"User-Agent": generate_user_agent()}
    if referer and _is_safe_url(referer):
        headers["Referer"] = referer
    if request.headers.get("Range"):
        headers["Range"] = request.headers["Range"]

    try:
        up = requests.get(url, headers=headers, stream=True, timeout=20, allow_redirects=True)
        # re-check final URL after redirects
        if not _is_safe_url(up.url):
            up.close()
            return _err("Blocked redirect target", 400)

        out = {
            "Content-Type": up.headers.get("Content-Type", "application/octet-stream"),
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename),
            "Accept-Ranges": up.headers.get("Accept-Ranges", "bytes"),
        }
        for h in ("Content-Length", "Content-Range"):
            if up.headers.get(h):
                out[h] = up.headers[h]
        out["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Accept-Ranges"

        if request.method == "HEAD":
            up.close()
            return Response(status=up.status_code, headers=out)

        def gen():
            try:
                for chunk in up.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        yield chunk
            finally:
                up.close()

        return Response(stream_with_context(gen()), status=up.status_code, headers=out)
    except Exception as e:
        return _err(f"Proxy failed: {e}", 502)


# ============================================================
# PWA (install as an app on phone / desktop)
#   /manifest.json   app name, colours, icons
#   /sw.js           service worker (caches the page only, never the API)
#   /icon-*.png      icons (embedded in pwa_icons.py)
# ============================================================
import base64
import json
from pwa_icons import ICONS

_MANIFEST = {
    "id": "/",
    "name": "MiMo Video Downloader",
    "short_name": "MiMo",
    "description": "Download videos from Facebook, Instagram, TikTok, Pinterest and YouTube.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#0b0f17",
    "theme_color": "#0b0f17",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}

_SW_JS = """
// MiMo service worker: caches ONLY the app page. API calls are never cached.
const CACHE = 'mimo-shell-v1';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.add('/')).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || req.mode !== 'navigate') return;   // pages only
  e.respondWith(
    fetch(req).then(res => {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put('/', copy));
      return res;
    }).catch(() => caches.match('/'))
  );
});
"""


@extra_bp.route("/manifest.json")
def pwa_manifest():
    return Response(json.dumps(_MANIFEST), mimetype="application/manifest+json")


@extra_bp.route("/sw.js")
def pwa_sw():
    return Response(_SW_JS, mimetype="application/javascript",
                    headers={"Cache-Control": "no-cache"})


@extra_bp.route("/<name>.png")
def pwa_icon(name):
    data = ICONS.get(name + ".png")
    if not data:
        return Response(status=404)
    return Response(base64.b64decode(data), mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})
