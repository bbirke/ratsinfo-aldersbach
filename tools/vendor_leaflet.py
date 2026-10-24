"""Vendor Leaflet + Leaflet.markercluster into archive/vendor/ (local copies).

Removes the unpkg CDN dependency so the map works behind restrictive proxies
(the earlier 403 report). Licenses permit redistribution (Leaflet BSD-2,
Leaflet.markercluster MIT); attribution stays in the map.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

V = net.ROOT / "archive/vendor"
FILES = {
    "leaflet/leaflet.css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "leaflet/leaflet.js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "leaflet/images/layers.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers.png",
    "leaflet/images/layers-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png",
    "leaflet/images/marker-icon.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    "leaflet/images/marker-icon-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    "leaflet/images/marker-shadow.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    "markercluster/leaflet.markercluster.js": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js",
    "markercluster/MarkerCluster.css": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css",
    "markercluster/MarkerCluster.Default.css": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css",
    "markercluster/images/MarkerCluster.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/MarkerCluster.png",
    "markercluster/images/MarkerClusterShadow.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/MarkerClusterShadow.png",
    "markercluster/images/marker-cluster.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/marker-cluster.png",
    "markercluster/images/marker-cluster-small.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/marker-cluster-small.png",
    "markercluster/images/marker-cluster-small@2x.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/marker-cluster-small@2x.png",
    "markercluster/images/marker-cluster-medium.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/marker-cluster-medium.png",
    "markercluster/images/marker-cluster-medium@2x.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/marker-cluster-medium@2x.png",
    "markercluster/images/marker-cluster-large.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/marker-cluster-large.png",
    "markercluster/images/marker-cluster-large@2x.png": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/images/marker-cluster-large@2x.png",
}

ok = 0
for rel, url in FILES.items():
    dest = V / rel
    if dest.exists() and dest.stat().st_size > 0:
        print("skip (exists):", rel)
        ok += 1
        continue
    st, h, b = net.fetch(url, timeout=120)
    if st == 200 and b:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b)
        print(f"downloaded {len(b):>8} B  {rel}")
        ok += 1
    else:
        print(f"FAILED {st} {rel}")
print(f"{ok}/{len(FILES)} vendored under {V}")
