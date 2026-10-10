"""Typeset the classification poster; embed unchanged imagegen PNG and licensed fonts.

Build-only dependency: fonttools[woff]. Runtime remains Python standard library.
The diagram's class names and parent relationships come from the current BOM.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'web/assets/bom-classification'
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
COLORS = dict(facility='#94765d', thermal='#398bbd', power='#c58a28',
              it='#9270c6', control='#58936d')


def build():
    bom = json.loads((ROOT / 'framework/bom.json').read_text())
    systems = bom['systems']
    svg = ET.Element(f'{{{NS}}}svg', dict(width='1536', height='1800',
        viewBox='0 0 1536 1800', role='img', **{'aria-labelledby': 'title description'}))

    def el(tag, parent=svg, text=None, **attrs):
        node = ET.SubElement(parent, f'{{{NS}}}{tag}',
            {k.replace('_', '-'): str(v) for k, v in attrs.items()})
        node.text = text
        return node

    el('title', id='title', text='AI 数据中心：五大类与子分类')
    el('desc', id='description', text='设施、水与散热、电、IT设施、控制与软件。'
       'IT设施分计算、存储、网络；计算处理器分CPU、GPU、其他；存储分内存与持久存储。'
       '场景为通用分类示意，编号定位类别，不表示工程连接或实际配置。')
    style = el('style')
    el('rect', width=1536, height=1800, fill='#08233e')

    def text(x, y, value, size=26, color='#e5edf4', weight=400, parent=svg, **attrs):
        return el('text', parent=parent, x=x, y=y, text=value, font_size=size,
                  fill=color, font_weight=weight, **attrs)

    text(40, 68, 'AI 数据中心', 52, '#f2d18a', 650)
    text(398, 68, '一张图读懂分类', 44, '#ffffff', 600)
    el('path', d='M40 92 H1496', stroke='#c7a05a', stroke_width=2)
    text(40, 132, '先看五大类，再沿计算、存储、网络读到设备与组件', 26, '#c3d6e5')
    raster = (OUT / 'cutaway-v1.png').read_bytes()
    el('image', x=0, y=160, width=1536, height=1024,
       href='data:image/png;base64,' + base64.b64encode(raster).decode())

    # Callouts identify visual category contexts, not physical circuit connections.
    callouts = [('facility', (190, 218), (402, 326)),
                ('thermal', (1245, 1080), (1320, 855)),
                ('power', (90, 1040), (270, 800)),
                ('it', (1030, 328), (970, 578)),
                ('control', (675, 1080), (820, 860))]
    for sid, (x, y), (tx, ty) in callouts:
        color = COLORS[sid]
        group = el('g', id='scene-' + sid, **{'data-system-id': sid})
        w = 96 + len(systems[sid]['name']) * 28
        el('path', parent=group, d=f'M{x + w/2} {y+24} L{tx} {ty}',
           fill='none', stroke=color, stroke_width=4)
        el('circle', parent=group, cx=tx, cy=ty, r=8, fill=color,
           stroke='#ffffff', stroke_width=3)
        el('rect', parent=group, x=x, y=y, width=w, height=56, rx=5,
           fill='#08233e', stroke=color, stroke_width=3)
        text(x+16, y+37, f"{systems[sid]['order']:02d}", 28, color, 700, group)
        text(x+65, y+37, systems[sid]['name'], 28, '#ffffff', 600, group)

    text(32, 1238, '五类系统，分层阅读', 34, '#f2d18a', 600)
    text(1498, 1238, '编号对应上方场景位置', 22, '#b9ccdc', text_anchor='end')
    columns = [('facility', 32, 248), ('thermal', 296, 280),
               ('power', 592, 280), ('it', 888, 352), ('control', 1256, 248)]
    for sid, x, w in columns:
        color = COLORS[sid]
        group = el('g', id='category-' + sid, **{'data-system-id': sid})
        el('rect', parent=group, x=x, y=1270, width=w, height=424,
           rx=5, fill='#0c2c49', stroke=color, stroke_width=2)
        el('rect', parent=group, x=x, y=1270, width=w, height=8, fill=color)
        text(x+18, 1313, f"{systems[sid]['order']:02d}", 24, color, 650, group)
        text(x+18, 1356, systems[sid]['name'], 32, '#ffffff', 650, group)
        el('path', parent=group, d=f'M{x+18} 1376 H{x+w-18}', stroke=color)
        if sid == 'it':
            def branch(sid2, y):
                return text(x+28, y, systems[sid2]['name'].replace('IT · ', ''),
                            29, '#d9c9f3', 650, group, **{'data-system-id': sid2})
            branch('compute', 1418)
            text(x+44, 1454, ' / '.join(g['name'] for g in systems['compute']['processor_groups']), 26, parent=group)
            text(x+44, 1486, '其他：ASIC、FPGA 等', 20, '#b9ccdc', parent=group)
            text(x+28, 1516, '配套：服务器、整机柜、BMC', 20, '#b9ccdc', parent=group)
            branch('storage-group', 1560)
            children = sorted(((k, v) for k, v in systems.items() if v['parent'] == 'storage-group'), key=lambda p:p[1]['order'])
            text(x+44, 1598, ' / '.join(v['name'].replace('IT · ', '') for _, v in children), 26, parent=group)
            branch('network', 1642)
            text(x+44, 1678, '交换、互连与数据传输', 23, parent=group)
            for y, bottom in [(1398, 1490), (1540, 1600), (1622, 1680)]:
                el('path', parent=group, d=f'M{x+19} {y} V{bottom}', stroke=color, stroke_width=2)
        else:
            rows = systems[sid]['chains']
            for i, row in enumerate(rows):
                # One current chain per line; no alternative equipment is implied mandatory.
                if row == '机柜与板级供电':
                    text(x+20, 1422+i*46, row, 25, parent=group)
                elif sid == 'control':
                    text(x+20, 1422, 'DCIM / BMS', 25, parent=group)
                    text(x+20, 1470, '固件与管理软件', 25, parent=group)
                else:
                    text(x+20, 1422+i*46, row, 27, parent=group)
            notes = {'facility': ['空间与承载', '消防与安全'],
                     'thermal': ['覆盖风冷与液冷', '从芯片到室外排热'],
                     'power': [],
                     'control': ['监控、告警与运维', '贯穿各类系统']}
            for i, line in enumerate(notes[sid]):
                text(x+20, 1638+i*32, line, 22, '#b9ccdc', parent=group)

    text(32, 1742, '读图顺序：五大类 → 子分类 → 设备与组件', 28, '#f2d18a', 500)
    text(32, 1780, '通用场景示意 · 编号表示分类定位 · 设备选型与实际连接另行核实', 21, '#aec5d7')

    # SVG images cannot load external webfonts. Embed only the used licensed glyphs.
    chars = set(ord(c) for n in svg.iter() for c in (n.text or ''))
    css = ['text{font-family:Inter,"Noto Sans SC",sans-serif}']
    proof = []
    covered = set()
    fonts = [ROOT/'web/assets/fonts/inter-variable.woff2'] + sorted((ROOT/'web/assets/fonts').glob('noto-sans-sc-*.woff2'))
    for path in fonts:
        font = TTFont(path)
        used = chars & set(font.getBestCmap())
        if not used:
            continue
        options = subset.Options()
        sub = subset.Subsetter(options=options)
        sub.populate(unicodes=used)
        sub.subset(font)
        font.flavor = 'woff2'
        output = io.BytesIO()
        font.save(output)
        family = 'Inter' if path.name.startswith('inter-') else 'Noto Sans SC'
        css.append('@font-face{font-family:"'+family+'";font-style:normal;font-weight:100 900;src:url(data:font/woff2;base64,'+base64.b64encode(output.getvalue()).decode()+') format("woff2");unicode-range:'+','.join(f'U+{c:X}' for c in sorted(used))+'}')
        covered |= used
        proof.append(dict(source=str(path.relative_to(ROOT)), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), glyphs=len(used), bytes=len(output.getvalue())))
    missing = chars - covered - {10, 13}
    if missing:
        raise ValueError('Missing font glyphs: ' + str(missing))
    style.text = '\n'.join(css)
    licenses = el('metadata', id='embedded-font-licenses')
    licenses.text = '\n'.join((ROOT/'web/assets/fonts'/name).read_text() for name in ['LICENSE-Inter.txt', 'LICENSE-NotoSansSC.txt'])
    output = OUT/'overview-v1.svg'
    ET.ElementTree(svg).write(output, encoding='utf-8', xml_declaration=True)
    manifest = dict(version='1.0', title='AI 数据中心分类总图', source='framework/bom.json',
        imagegen=dict(tool='built-in image_gen', prompt='docs/design/bom-classification/prompt-v1.txt', input_images=[], reference_role='User supplied editorial poster was viewed; composition reference only, not tool input or technical evidence'),
        scope='Generic classification illustration; not engineering topology, OEM configuration or completed TA-01–35 item',
        pixels=[1536, 1800], scene_pixels=[1536, 1024], colors=COLORS,
        categories=[dict(id=sid, name=systems[sid]['name']) for sid, _, _ in columns],
        fonts=proof, files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'cutaway-v1.png',output,OUT/'overview-v1.png',OUT/'overview-v1-preview.jpg'] if p.exists()})
    (ROOT/'docs/design/bom-classification/manifest-v1.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(output.relative_to(ROOT))


if __name__ == '__main__':
    build()
