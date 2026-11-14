from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

pwa_router = APIRouter()

ICON_SVG = """<svg xmlns="http://w3.org" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="110" fill="#00b875"/>
  <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle"
        font-family="system-ui, sans-serif" font-weight="900" font-size="260" fill="#ffffff">₦</text>
</svg>"""

SW_JS = """
self.addEventListener("install", (event) => {
    self.skipWaiting();
});
self.addEventListener("activate", (event) => {
    event.waitUntil(self.clients.claim());
});
self.addEventListener("fetch", (event) => {
    event.respondWith(fetch(event.request));
});
"""

@pwa_router.get("/manifest.json")
def pwa_manifest():
    return JSONResponse({
        "name": "NairaPay Microfinance Bank",
        "short_name": "NairaPay",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b131e",
        "theme_color": "#00b875",
        "icons": [
            {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}
        ],
    })

@pwa_router.get("/icon.svg")
def pwa_icon():
    return Response(content=ICON_SVG, media_type="image/svg+xml")

@pwa_router.get("/sw.js")
def pwa_service_worker():
    return Response(content=SW_JS, media_type="application/javascript")
