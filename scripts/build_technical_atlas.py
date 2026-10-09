"""Typeset an editable SVG label layer over an unchanged native PNG master.

This script does not generate or alter the raster image. Output embeds the original
PNG bytes, so the downloaded SVG also works without adjacent files or a server.
"""
from pathlib import Path
import base64
import json
import struct
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)


def build(spec_path, preview=False):
    spec = json.loads(spec_path.read_text())
    raster = (ROOT / spec['master']).read_bytes()
    if raster[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Master must be an original PNG')
    width, height = struct.unpack('>II', raster[16:24])
    if [width, height] != spec['pixels']:
        raise ValueError('Declared pixels do not match the master')
    media_type = 'image/png'
    if preview:
        raster = (ROOT / spec['preview_raster']).read_bytes()
        if raster[:2] != b'\xff\xd8':
            raise ValueError('Preview must be a JPEG encoding of the same master')
        media_type = 'image/jpeg'
    svg = ET.Element(f'{{{NS}}}svg', {
        'width': str(width), 'height': str(height), 'viewBox': f'0 0 {width} {height}',
        'role': 'img', 'aria-labelledby': 'title description',
    })
    ET.SubElement(svg, f'{{{NS}}}title', {'id': 'title'}).text = spec['title']
    ET.SubElement(svg, f'{{{NS}}}desc', {'id': 'description'}).text = spec['description']
    ET.SubElement(svg, f'{{{NS}}}image', {
        'width': str(width), 'height': str(height),
        'href': 'data:' + media_type + ';base64,' + base64.b64encode(raster).decode('ascii'),
    })
    leaders = ET.SubElement(svg, f'{{{NS}}}g', {
        'id': 'editable-leaders', 'fill': 'none', 'stroke': '#09689B',
        'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    })
    for row in spec['leaders']:
        group = ET.SubElement(leaders, f'{{{NS}}}g', {'id': row['id']})
        ET.SubElement(group, f'{{{NS}}}path', {'d': row['path']})
        ET.SubElement(group, f'{{{NS}}}circle', {
            'cx': str(row['target'][0]), 'cy': str(row['target'][1]), 'r': '5',
            'fill': '#09689B', 'stroke': '#FAF9F2', 'stroke-width': '1.5',
        })
    labels = ET.SubElement(svg, f'{{{NS}}}g', {
        'id': 'editable-labels', 'fill': '#263540',
        'font-family': 'Inter, Noto Sans SC, sans-serif', 'font-size': '22',
    })
    for row in spec['labels']:
        text = ET.SubElement(labels, f'{{{NS}}}text', {
            'id': row['id'], 'x': str(row['x']), 'y': str(row['y']),
            'text-anchor': row.get('anchor', 'start'),
        })
        text.text = row['text']
    output = ROOT / spec['preview_output' if preview else 'output']
    ET.ElementTree(svg).write(output, encoding='utf-8', xml_declaration=True)
    return output


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    parser.add_argument('--preview', action='store_true', help='Embed a lightweight JPEG; master remains unchanged')
    args = parser.parse_args()
    print(build(args.spec, preview=args.preview).relative_to(ROOT))
