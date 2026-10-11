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
EXPECTED_SHA256 = ('239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255', '1a1f30ccaaf4cc9c4bde34266f0b8cbb955d3a4cf254b756912255f2ec7c75b6')


def simplify(points, closed=False):
    # Ramer–Douglas–Peucker, 0.05 degree tolerance; retain ring closure.
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
        if maximum > .05 ** 2:
            keep.add(index)
            stack.extend(((a, index), (index, b)))
    result = [points[i] for i in sorted(keep)]
    if closed and len(result) < 4:
        result = [points[0], points[len(points)//3], points[2*len(points)//3], points[-1]]  # Retain a closed small-island outline.
    return [[round(p[0], 3), round(p[1], 3)] for p in result]


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
        if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256[index]:
            raise ValueError(f'{name}: input does not match the pinned revision')
        sources.append({'name': name, 'revision': REVISION, 'sha256': hashlib.sha256(raw).hexdigest()})
        for feature in json.loads(raw)['features']:
            if feature.get('geometry') is None:
                continue  # Natural Earth includes a few unlocated records.
            properties = feature['properties']
            features.append({'type': 'Feature', 'properties': {'layer': 'country' if index == 0 else 'admin1', 'name': properties.get('NAME') or properties.get('name') or ''}, 'geometry': geometry(feature['geometry'])})
    countries = [f for f in features if f['properties']['layer'] == 'country']
    strips = [[] for _ in range(12)]
    for f in features:
        if f['properties']['layer'] != 'admin1':
            continue
        lines = f['geometry']['coordinates'] if f['geometry']['type'] == 'MultiLineString' else [f['geometry']['coordinates']]
        for line in lines:
            first = max(0, min(11, int((min(p[0] for p in line) + 180) // 30)))
            last = max(0, min(11, int((max(p[0] for p in line) + 180) // 30)))
            for index in range(first, last + 1):
                strips[index].append({'type': 'Feature', 'properties': {'layer': 'admin1'}, 'geometry': {'type': 'LineString', 'coordinates': line}})
    directory = ROOT / 'web/assets/maps'
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in [('world-detail', countries), *[(f'map-admin1-{i}', rows) for i, rows in enumerate(strips)]]:
        result = {'type': 'FeatureCollection', 'sources': sources, 'features': rows}
        path = directory / (name + '.geo.json')
        path.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
        print(f'{name}: {len(rows)} features, {path.stat().st_size} bytes')


if __name__ == '__main__':
    main(sys.argv[1])
