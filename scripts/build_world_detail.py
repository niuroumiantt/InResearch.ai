"""Derive the zoom-only atlas from pinned Natural Earth GeoJSON (stdlib only).

Usage: python3 scripts/build_world_detail.py /path/to/downloaded/geojson
See web/assets/maps/README.md for sources, licence and precision.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'ca96624a56bd078437bca8184e78163e5039ad19'
SOURCES = ('ne_10m_admin_0_countries', 'ne_10m_admin_1_states_provinces_lines')


def simplify(points, closed=False):
    # Ramer–Douglas–Peucker, 0.01 degree tolerance; retain ring closure.
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        x, y = points[a][:2]
        dx, dy = points[b][0] - x, points[b][1] - y
        length = dx * dx + dy * dy
        maximum, index = 0, a
        for i in range(a + 1, b):
            px, py = points[i][0] - x, points[i][1] - y
            t = max(0, min(1, (px * dx + py * dy) / length)) if length else 0
            distance = (px - t * dx) ** 2 + (py - t * dy) ** 2
            if distance > maximum:
                maximum, index = distance, i
        if maximum > .01 ** 2:
            keep.add(index)
            stack.extend(((a, index), (index, b)))
    result = [points[i] for i in sorted(keep)]
    if closed and len(result) < 4:
        result = points  # Preserve small islands instead of collapsing rings.
    return [[round(p[0], 4), round(p[1], 4)] for p in result]


def geometry(g):
    kind, coordinates = g['type'], g['coordinates']
    depth = {'LineString': 0, 'MultiLineString': 1, 'Polygon': 1, 'MultiPolygon': 2}[kind]
    def walk(value, level):
        return [walk(v, level - 1) for v in value] if level else simplify(value, kind in ('Polygon', 'MultiPolygon'))
    return {'type': kind, 'coordinates': walk(coordinates, depth)}


def main(directory):
    features, sources = [], []
    for index, name in enumerate(SOURCES):
        raw = (Path(directory) / (name + '.geojson')).read_bytes()
        sources.append({'name': name, 'revision': REVISION, 'sha256': hashlib.sha256(raw).hexdigest()})
        for feature in json.loads(raw)['features']:
            if feature.get('geometry') is None:
                continue  # Natural Earth includes a few unlocated records.
            properties = feature['properties']
            features.append({'type': 'Feature', 'properties': {'layer': 'country' if index == 0 else 'admin1', 'name': properties.get('NAME') or properties.get('name') or ''}, 'geometry': geometry(feature['geometry'])})
    result = {'type': 'FeatureCollection', 'sources': sources, 'features': features}
    path = ROOT / 'web/assets/maps/world-detail.geo.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'{len(features)} features, {path.stat().st_size} bytes')


if __name__ == '__main__':
    main(sys.argv[1])
