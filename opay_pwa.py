import struct
import zlib
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

pwa_router = APIRouter()

def build_solid_png(size: int, r: int = 0, g: int = 184, b: int = 117) -> bytes:
    row = b"\x00" + bytes([r, g, b, 255]) * size
    raw_data = zlib.compress(row * size)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack("!IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw_data) + chunk(b"IEND", b"")

PNG_192 = build_solid_png(192)
PNG_512 = build_solid_png(512)

SW_JS = """
self.addEventListener("install", (event) => { self.skipWaiting(); });
self.addEventListener("activate", (event) => { event.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", (event) => { event.respondWith(fetch(event.request)); });
"""

@pwa_router.get("/manifest.json")
def pwa_manifest():
    return JSONResponse({
        "id": "/",
        "name": "NairaPay Microfinance Bank",
        "short_name": "NairaPay",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0b131e",
        "theme_color": "#00b875",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    })

@pwa_router.get("/icon-192.png")
def pwa_icon_192():
    return Response(content=PNG_192, media_type="image/png")

@pwa_router.get("/icon-512.png")
def pwa_icon_512():
    return Response(content=PNG_512, media_type="image/png")

@pwa_router.get("/sw.js")
def pwa_service_worker():
    return Response(content=SW_JS, media_type="application/javascript")
