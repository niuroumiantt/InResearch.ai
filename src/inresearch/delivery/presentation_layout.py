"""Bounded, model-free PPTX typography and conservative v0.2 page layout.

Edit existing OOXML, never reconstruct a presentation through a lossy object
model. Unedited package members (including charts, notes and media) keep their
exact bytes. Complex pages keep their geometry; the report describes that limit.
"""
from __future__ import annotations

from collections import Counter
from copy import copy
from hashlib import sha256
from io import BytesIO
import json
import math
import posixpath
import time
import unicodedata
from xml.dom import Node, minidom
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
MAX_UPLOAD = 20 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
MAX_SLIDES = 100
MAX_XML = 2 * 1024 * 1024
PPTX_MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
MONO = ('consolas', 'courier', 'menlo', 'monaco', 'ibm plex mono', 'cascadia', 'source code')
SYMBOL = ('wingdings', 'webdings', 'symbol', 'cambria math')


class LayoutError(ValueError):
    pass


def children(node, ns=None, name=None):
    return [n for n in node.childNodes if n.nodeType == Node.ELEMENT_NODE
            and (ns is None or n.namespaceURI == ns)
            and (name is None or n.localName == name)]


def descendants(node, ns, name):
    return list(node.getElementsByTagNameNS(ns, name))


def text(node):
    return ''.join(n.data for n in node.childNodes if n.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE))


def element(parent, ns, name, attrs=None):
    prefix = 'a' if ns == A else 'p'
    node = parent.ownerDocument.createElementNS(ns, prefix + ':' + name)
    for key, value in (attrs or {}).items():
        node.setAttribute(key, str(value))
    parent.appendChild(node)
    return node


def ensure(parent, ns, name, first=False):
    found = children(parent, ns, name)
    if found:
        return found[0]
    node = element(parent, ns, name)
    if first and parent.firstChild is not node:
        parent.insertBefore(node, parent.firstChild)
    return node


def parse(raw):
    if len(raw) > MAX_XML:
        raise LayoutError('单个 XML 超过 2 MB，暂不支持此文件。')
    try:
        decoded = raw.decode('utf-8-sig')
        if '<!DOCTYPE' in decoded.upper() or '<!ENTITY' in decoded.upper():
            raise LayoutError('文件含不支持的 XML 实体声明。')
        return minidom.parseString(decoded)
    except LayoutError:
        raise
    except Exception as exc:
        raise LayoutError('文件的 XML 结构无效；请用 PowerPoint 另存为 PPTX 后重试。') from exc


def content_signature(doc):
    """Paragraphs, fields, breaks, hyperlink destinations, and non-text IDs.

    Adjacent text runs may be split only to assign Chinese/Latin fonts. Every
    paragraph's exact Unicode string and its linked spans remain identical.
    """
    result = []
    for para in descendants(doc, A, 'p'):
        tokens = []
        for node in children(para):
            if node.localName in ('r', 'fld') and node.namespaceURI == A:
                value = ''.join(text(t) for t in children(node, A, 't'))
                links = tuple(n.toxml() for k in ('hlinkClick', 'hlinkMouseOver')
                              for n in descendants(node, A, k))
                field = tuple(sorted(node.attributes.items())) if node.localName == 'fld' else ()
                key = (node.localName, links, field)
                if tokens and tokens[-1][0] == key:
                    tokens[-1] = (key, tokens[-1][1] + value)
                else:
                    tokens.append((key, value))
            elif node.localName == 'br' and node.namespaceURI == A:
                tokens.append((('break', (), ()), '\n'))
        result.append(tokens)
    # These structures must never be regenerated or dropped by a text edit.
    preserved = [(ns, name, [n.toxml() for n in descendants(doc, ns, name)])
                 for ns, name in ((P, 'timing'), (P, 'transition'), (P, 'cNvPr'),
                                  (A, 'blip'), (A, 'srcRect'), (A, 'tbl'),
                                  (P, 'graphicFrame'), (P, 'oleObj'))]
    return result, preserved


def font_kind(char, mono=False):
    if unicodedata.east_asian_width(char) in ('W', 'F') and ord(char) < 0x1F000 or char in '“”‘’—…':
        return 'FangSong'
    if ord(char) < 0x0250 or char in '–−€¥°':
        return 'IBM Plex Mono' if mono else 'Source Serif 4'
    return None  # Preserve symbol, emoji, math and other-script font assignments.


def set_font(rpr, font):
    semibold = rpr.getAttribute('b') in ('1', 'true') or any('semibold' in n.getAttribute('typeface').lower() for n in children(rpr, A, 'latin'))
    for name in ('latin', 'ea', 'cs'):
        found = children(rpr, A, name)
        for n in found:
            rpr.removeChild(n)
    # Font children precede hyperlinks/rtl/extLst in CT_TextCharacterProperties.
    anchor = next((n for n in children(rpr) if n.localName in ('sym', 'hlinkClick', 'hlinkMouseOver', 'rtl', 'extLst')), None)
    for name in ('latin', 'ea', 'cs'):
        n = element(rpr, A, name, {'typeface': font})
        if anchor is not None:
            rpr.insertBefore(n, anchor)
    if font in ('FangSong', 'IBM Plex Mono'):
        rpr.setAttribute('b', '0')
        rpr.setAttribute('i', '0')
    elif semibold:
        # Use the actual static 600 family, not PowerPoint's synthetic Bold.
        for n in children(rpr, A, 'latin') + children(rpr, A, 'ea') + children(rpr, A, 'cs'):
            n.setAttribute('typeface', 'Source Serif 4 Semibold')
        rpr.setAttribute('b', '0')
    else:
        rpr.setAttribute('b', '0')


def typography(shape):
    count = 0
    for run in list(descendants(shape, A, 'r')):
        ts = children(run, A, 't')
        if len(ts) != 1 or any(n.localName not in ('t', 'rPr') for n in children(run)):
            continue
        value = text(ts[0])
        faces = [n.getAttribute('typeface').lower() for n in descendants(run, A, 'latin')]
        if any(s in f for s in SYMBOL for f in faces):
            continue
        mono = any(s in f for s in MONO for f in faces)
        groups = []
        for char in value:
            kind = font_kind(char, mono)
            if groups and groups[-1][0] == kind:
                groups[-1] = (kind, groups[-1][1] + char)
            else:
                groups.append((kind, char))
        for font, segment in groups:
            clone = run.cloneNode(True)
            t = children(clone, A, 't')[0]
            while t.firstChild:
                t.removeChild(t.firstChild)
            t.appendChild(t.ownerDocument.createTextNode(segment))
            if font:
                set_font(ensure(clone, A, 'rPr', first=True), font)
                count += len(segment)
            run.parentNode.insertBefore(clone, run)
        if groups:
            run.parentNode.removeChild(run)
    return count


def shape_text(shape):
    return '\n'.join(''.join(text(t) for t in descendants(p, A, 't'))
                     for p in descendants(shape, A, 'p'))


def resolve_part(source, target):
    return posixpath.normpath(target.lstrip('/') if target.startswith('/')
                              else posixpath.join(posixpath.dirname(source), target))


def has_rotation(shape):
    return any(any(n.getAttribute(k) not in ('', '0', 'false') for k in ('rot', 'flipH', 'flipV'))
               for n in descendants(shape, A, 'xfrm'))


def plain_text_shape(shape):
    if shape.localName != 'sp' or not shape_text(shape).strip() or has_rotation(shape):
        return False
    if descendants(shape, A, 'fld') or descendants(shape, A, 'custGeom') or children(shape, P, 'style'):
        return False
    sppr = children(shape, P, 'spPr')
    if sppr and any(n.localName in ('solidFill', 'gradFill', 'blipFill', 'pattFill', 'effectLst', 'effectDag') for n in children(sppr[0])):
        return False
    for body in descendants(shape, A, 'bodyPr'):
        if body.getAttribute('vert') not in ('', 'horz') or body.getAttribute('rot') not in ('', '0'):
            return False
    return True


def simple_inheritance(archive, slide):
    """Do not move text across an inherited logo, diagram or dark background."""
    current, backgrounds = slide, []
    for kind in ('slideLayout', 'slideMaster'):
        relpath = posixpath.join(posixpath.dirname(current), '_rels', posixpath.basename(current) + '.rels')
        if relpath not in archive.namelist():
            return False
        rels = parse(archive.read(relpath))
        matches = [n for n in descendants(rels, REL, 'Relationship') if n.getAttribute('Type') == R + '/' + kind and n.getAttribute('TargetMode') != 'External']
        if len(matches) != 1:
            return False
        current = resolve_part(current, matches[0].getAttribute('Target'))
        if current not in archive.namelist():
            return False
        doc = parse(archive.read(current))
        if any(descendants(doc, P, name) for name in ('pic', 'graphicFrame', 'cxnSp', 'grpSp')):
            return False
        if any(not descendants(s, P, 'ph') for s in descendants(doc, P, 'sp')):
            return False
        if descendants(doc, A, 'overrideClrMapping'):
            return False
        backgrounds.extend(n.cloneNode(True) for n in descendants(doc, P, 'bg'))
        if kind == 'slideMaster':
            colour_maps = descendants(doc, P, 'clrMap')
            colour_map = dict(colour_maps[0].attributes.items()) if colour_maps else {}
        rels.unlink()
    masterrels = posixpath.join(posixpath.dirname(current), '_rels', posixpath.basename(current) + '.rels')
    if masterrels not in archive.namelist():
        return not backgrounds
    rels = parse(archive.read(masterrels))
    themes = [n for n in descendants(rels, REL, 'Relationship') if n.getAttribute('Type') == R + '/theme' and n.getAttribute('TargetMode') != 'External']
    theme = None
    if len(themes) == 1:
        path = resolve_part(current, themes[0].getAttribute('Target'))
        if path in archive.namelist():
            theme = parse(archive.read(path))
    for bg in backgrounds:
        colours = descendants(bg, A, 'srgbClr')
        if len(colours) == 1 and colours[0].getAttribute('val').upper() in ('FFFFFF', 'F6F5F2'):
            continue
        refs, schemes = descendants(bg, P, 'bgRef'), descendants(bg, A, 'schemeClr')
        if len(refs) != 1 or refs[0].getAttribute('idx') != '1001' or len(schemes) != 1 or theme is None:
            return False
        fills = descendants(theme, A, 'bgFillStyleLst')
        if not fills or not children(fills[0]) or children(fills[0])[0].localName != 'solidFill':
            return False
        first_fill = children(fills[0])[0]
        ph = children(first_fill, A, 'schemeClr')
        if len(ph) != 1 or ph[0].getAttribute('val') != 'phClr' or children(ph[0]):
            return False
        key = schemes[0].getAttribute('val')
        scheme = descendants(theme, A, 'clrScheme')
        source = children(scheme[0], A, colour_map.get(key, key)) if scheme else []
        if len(source) != 1 or not children(source[0]):
            return False
        colour = children(source[0])[0]
        value = colour.getAttribute('lastClr' if colour.localName == 'sysClr' else 'val')
        if value.upper() not in ('FFFFFF', 'F6F5F2') or children(schemes[0]):
            return False
    return True


def fit_size(value, width, height, target, minimum):
    """Conservative estimate, not a font renderer or a visual certification."""
    for size in range(int(target), int(minimum) - 1, -1):
        capacity = max(1, (width / 12700 - 20) / size)
        lines = sum(max(1, math.ceil(sum(1.08 if unicodedata.east_asian_width(c) in ('W', 'F') else .65
                                       for c in line) / capacity)) for line in value.split('\n'))
        if lines * size * 1.35 + 12 <= height / 12700:
            return size
    return None


def position(shape, box):
    sppr = ensure(shape, P, 'spPr')
    xfrm = ensure(sppr, A, 'xfrm', first=True)
    x, y, w, h = box
    for name, attrs in (('off', {'x': x, 'y': y}), ('ext', {'cx': w, 'cy': h})):
        node = ensure(xfrm, A, name)
        for key, value in attrs.items():
            node.setAttribute(key, str(round(value)))


def style_text(shape, size, title=False):
    for rpr in descendants(shape, A, 'rPr'):
        rpr.setAttribute('sz', str(size * 100))
        for n in list(children(rpr)):
            if n.namespaceURI == A and n.localName in ('solidFill', 'gradFill', 'pattFill', 'blipFill', 'noFill', 'grpFill'):
                rpr.removeChild(n)
        fill = element(rpr, A, 'solidFill')
        element(fill, A, 'srgbClr', {'val': '0B0C0C'})
        # Fill belongs before font elements.
        first = next((n for n in children(rpr) if n is not fill and n.localName != 'ln'), None)
        if first is not None:
            rpr.insertBefore(fill, first)
    for body in descendants(shape, A, 'bodyPr'):
        for k, v in {'wrap': 'square', 'anchor': 't', 'lIns': 0, 'rIns': 0, 'tIns': 0, 'bIns': 0}.items():
            body.setAttribute(k, str(v))
        for n in list(children(body)):
            if n.localName in ('noAutofit', 'spAutoFit', 'normAutofit'):
                body.removeChild(n)
        element(body, A, 'normAutofit')
    for para in descendants(shape, A, 'p'):
        ppr = ensure(para, A, 'pPr', first=True)
        if title:
            ppr.setAttribute('algn', 'l')
        for n in list(children(ppr, A, 'lnSpc')):
            ppr.removeChild(n)
        spacing = element(ppr, A, 'lnSpc')
        element(spacing, A, 'spcPct', {'val': '115000' if title else '120000'})
        if ppr.firstChild is not spacing:
            ppr.insertBefore(spacing, ppr.firstChild)


def reflow(doc, width, height):
    """Only unambiguous title + 1–3 plain text blocks, no graphics or animations.

    Charts, photographs, arbitrary diagrams, full backgrounds and unsupported
    objects keep their original layout. Never guess reading order from pixels.
    """
    if descendants(doc, P, 'timing') or descendants(doc, P, 'transition'):
        return False, '含动画或转场，保留原版式。'
    tree = descendants(doc, P, 'spTree')[0]
    objects = [n for n in children(tree) if n.localName not in ('nvGrpSpPr', 'grpSpPr', 'extLst')]
    if not 2 <= len(objects) <= 4 or not all(plain_text_shape(s) for s in objects):
        return False, '复杂对象、图片、表格或非标准文字页，保留原版式。'
    titles = [s for s in objects if any(n.getAttribute('type') in ('title', 'ctrTitle') for n in descendants(s, P, 'ph'))]
    if len(titles) != 1:
        return False, '没有唯一的原生标题占位符，保留原版式。'
    title = titles[0]
    bodies = [s for s in objects if s is not title]
    if any(any(n.getAttribute('type') in ('dt', 'ftr', 'sldNum', 'hdr') for n in descendants(s, P, 'ph')) for s in bodies):
        return False, '含页眉、页脚或动态占位符，保留原版式。'
    # v0.2: 0.729in / 16.667in side margins, title starts at 0.958in / 9.375in.
    margin, gap = width * .04375, width * .025
    bodywidth = (width - 2 * margin - gap * (len(bodies) - 1)) / len(bodies)
    boxes = [(title, (margin, height * .102, width - 2 * margin, height * .13), 36, 26)]
    boxes += [(s, (margin + i * (bodywidth + gap), height * .28, bodywidth, height * .60), 22, 16)
              for i, s in enumerate(bodies)]
    factor = height / 8572500
    plans = []
    for s, box, target, minimum in boxes:
        size = fit_size(shape_text(s), box[2], box[3], max(14, target * factor), max(12, minimum * factor))
        if size is None:
            return False, '文字密度超出保守排版容量，保留原版式并请人工复核。'
        plans.append((s, box, size))
    # Do not erase an authored background or expose dark inherited text.
    if descendants(doc, P, 'bg'):
        return False, '含自定义背景，保留原版式。'
    for s, box, size in plans:
        position(s, box)
        style_text(s, size, s is title)
    cslide = descendants(doc, P, 'cSld')[0]
    bg = element(cslide, P, 'bg')
    cslide.insertBefore(bg, cslide.firstChild)
    fill = element(element(bg, P, 'bgPr'), A, 'solidFill')
    element(fill, A, 'srgbClr', {'val': 'F6F5F2'})
    return True, '按模板边距、标题与等宽正文栏重新排版；未新增或改写文字。'


def add_accent(doc, width, height):
    """The template's orange rule is decoration; no user object is replaced."""
    tree = descendants(doc, P, 'spTree')[0]
    sid = max((int(n.getAttribute('id')) for n in descendants(doc, P, 'cNvPr')), default=0) + 1
    line = element(tree, P, 'cxnSp')
    nv = element(line, P, 'nvCxnSpPr')
    element(nv, P, 'cNvPr', {'id': sid, 'name': 'inresearch-brand-accent'})
    element(nv, P, 'cNvCxnSpPr')
    element(nv, P, 'nvPr')
    sppr = element(line, P, 'spPr')
    xfrm = element(sppr, A, 'xfrm')
    element(xfrm, A, 'off', {'x': round(width * .04375), 'y': round(height * .25)})
    element(xfrm, A, 'ext', {'cx': round(width * .03), 'cy': 0})
    element(element(sppr, A, 'prstGeom', {'prst': 'line'}), A, 'avLst')
    stroke = element(sppr, A, 'ln', {'w': round(height / 225)})
    element(element(stroke, A, 'solidFill'), A, 'srgbClr', {'val': 'FD340A'})
    return line


def transform(raw: bytes, *, mode='layout'):
    if mode not in ('layout', 'fonts'):
        raise LayoutError('请选择品牌排版或仅统一字体。')
    if not 0 < len(raw) <= MAX_UPLOAD:
        raise LayoutError('PPTX 文件须不超过 20 MB。')
    started = time.monotonic()
    try:
        with ZipFile(BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(infos) > 2048 or len(set(names)) != len(names):
                raise LayoutError('压缩包条目过多或存在重复路径。')
            if any(n.startswith('/') or '\\' in n or '..' in n.split('/') for n in names):
                raise LayoutError('压缩包路径无效。')
            if sum(i.file_size for i in infos) > MAX_EXPANDED or any(i.file_size > 200 * max(i.compress_size, 1) for i in infos):
                raise LayoutError('文件解压大小或压缩比超限。')
            if any(i.flag_bits & 1 for i in infos):
                raise LayoutError('暂不支持加密文件。')
            if any('vbaproject' in n.lower() or n.startswith(('ppt/activeX/', '_xmlsignatures/')) for n in names):
                raise LayoutError('暂不支持宏、ActiveX 或数字签名文件。')
            required = ('[Content_Types].xml', 'ppt/presentation.xml', 'ppt/_rels/presentation.xml.rels')
            if any(n not in names for n in required):
                raise LayoutError('请上传有效的 .pptx 文件；不支持旧版 .ppt 或 PDF。')
            types = parse(archive.read('[Content_Types].xml'))
            overrides = descendants(types, 'http://schemas.openxmlformats.org/package/2006/content-types', 'Override')
            main = [n for n in overrides if n.getAttribute('PartName') == '/ppt/presentation.xml']
            if len(main) != 1 or main[0].getAttribute('ContentType') != 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml':
                raise LayoutError('只接受无宏 PPTX 演示文稿。')
            if any(any(word in n.getAttribute('ContentType').lower() for word in ('macroenabled', 'vbaproject', 'activex', 'digital-signature')) for n in children(types.documentElement)):
                raise LayoutError('暂不支持宏、ActiveX 或数字签名文件。')
            pres = parse(archive.read('ppt/presentation.xml'))
            sizes = descendants(pres, P, 'sldSz')
            if len(sizes) != 1:
                raise LayoutError('文件缺少页面尺寸。')
            width, height = (int(sizes[0].getAttribute(k)) for k in ('cx', 'cy'))
            if not 914400 <= width <= 51206400 or not 914400 <= height <= 51206400:
                raise LayoutError('页面尺寸超出支持范围。')
            rels = parse(archive.read('ppt/_rels/presentation.xml.rels'))
            mapping = {n.getAttribute('Id'): resolve_part('ppt/presentation.xml', n.getAttribute('Target'))
                       for n in descendants(rels, REL, 'Relationship') if n.getAttribute('Type') == R + '/slide' and n.getAttribute('TargetMode') != 'External'}
            slides = [mapping.get(n.getAttributeNS(R, 'id')) for n in descendants(pres, P, 'sldId')]
            if not 1 <= len(slides) <= MAX_SLIDES or len(set(slides)) != len(slides) or any(n not in names for n in slides):
                raise LayoutError('幻灯片关系无效或超过 100 页。')
            edits, pages = {}, []
            for index, name in enumerate(slides, 1):
                if time.monotonic() - started > 20:
                    raise LayoutError('文件处理超时，请拆分文件后重试。')
                original = archive.read(name)
                doc = parse(original)
                if not descendants(doc, P, 'spTree'):
                    raise LayoutError('幻灯片缺少对象树。')
                before = content_signature(doc)
                # Only ordinary editable text shapes, never table/chart/SmartArt internals.
                editable = [s for s in descendants(doc, P, 'sp') if not descendants(s, A, 'fld')]
                changed = sum(typography(s) for s in editable)
                if mode == 'layout' and simple_inheritance(archive, name):
                    laid_out, note = reflow(doc, width, height)
                else:
                    laid_out, note = False, ('母版或布局含背景、固定图形或未知继承，保留原版式。' if mode == 'layout' else '仅统一可编辑文本框字体，保留原版式。')
                if before != content_signature(doc):
                    raise LayoutError('内容完整性校验未通过，未交付修改文件。')
                if changed or laid_out:
                    doc.documentElement.setAttribute('xmlns:a', A)
                    doc.documentElement.setAttribute('xmlns:p', P)
                    accent = add_accent(doc, width, height) if laid_out else None
                    output = doc.toxml(encoding='UTF-8')
                    roundtrip = parse(output)
                    if accent is not None:
                        restored = descendants(roundtrip, P, 'spTree')[0].lastChild
                        if restored.toxml() != accent.toxml():
                            raise LayoutError('品牌装饰写回校验未通过。')
                        restored.parentNode.removeChild(restored)
                    if before != content_signature(roundtrip):
                        raise LayoutError('写回后的内容校验未通过。')
                    roundtrip.unlink()
                    edits[name] = output
                pages.append({'page': index, 'status': 'reflowed' if laid_out else 'fonts_only' if changed else 'preserved', 'formatted_characters': changed, 'note': note})
                doc.unlink()
            output = BytesIO()
            with ZipFile(output, 'w', ZIP_DEFLATED) as target:
                for info in infos:
                    target.writestr(copy(info), edits[info.filename] if info.filename in edits else archive.read(info.filename))
            result = output.getvalue()
            # Independent round-trip check of every preserved package member.
            with ZipFile(BytesIO(result)) as check:
                if check.namelist() != names:
                    raise LayoutError('文件条目完整性校验未通过。')
                for info in infos:
                    if info.filename not in edits and check.read(info.filename) != archive.read(info.filename):
                        raise LayoutError('原件资源完整性校验未通过。')
    except LayoutError:
        raise
    except (BadZipFile, KeyError, ValueError, OverflowError, RuntimeError, NotImplementedError) as exc:
        raise LayoutError('文件无效或使用暂不支持的格式，请另存为标准 PPTX 后重试。') from exc
    report = {
        'version': 'brand-layout-v1', 'template': 'inresearch.ai v0.2', 'model_used': False,
        'input_sha256': sha256(raw).hexdigest(), 'output_sha256': sha256(result).hexdigest(),
        'content_check': 'passed', 'slides': len(slides), 'counts': dict(Counter(p['status'] for p in pages)),
        'pages': pages, 'limits': [
            '只处理 PPTX；不改写、删减、补充文字，不改页数、页序、图片、图表数据、备注或附件。',
            '常规标题与文字栏按模板比例排版并添加品牌橙色短线；复杂页面保留原版式，图表、表格、SmartArt 内部字体保持。',
            '字体切换可能影响断行。容量检查为估算，未在 PowerPoint 中逐页渲染验收；请打开后复核。',
            '请合法安装 FangSong、Source Serif 4（含 Semibold）及 IBM Plex Mono；未嵌入字体。',
            '未新增 Logo、页眉页脚或页码；未重写数字、标点、空格与单位，也未改变证据颜色。',
            '不调用模型，不读取外部链接，不提供未经字体与渲染验证的 PDF。',
        ],
    }
    return result, report


def bundle(raw, mode='layout'):
    result, report = transform(raw, mode=mode)
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('inresearch-formatted.pptx', result)
        archive.writestr('layout-report.json', json.dumps(report, ensure_ascii=False, indent=2))
        readable = ['inresearch.ai 品牌排版说明', '', *report['limits'], '', '逐页处理结果：']
        readable += [f"第 {p['page']} 页：{p['status']}；{p['note']}" for p in report['pages']]
        archive.writestr('排版说明.txt', '\n'.join(readable))
    return output.getvalue(), report


def main():
    """Private worker protocol: binary ZIP on success, bounded JSON on failure."""
    import sys
    try:
        if sys.platform == 'linux':
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (520 * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
        result, _ = bundle(sys.stdin.buffer.read(MAX_UPLOAD + 1), sys.argv[1] if len(sys.argv) > 1 else 'layout')
        sys.stdout.buffer.write(result)
    except (LayoutError, MemoryError) as exc:
        message = str(exc) if isinstance(exc, LayoutError) else '文件处理内存超限，请拆分文件。'
        sys.stdout.write(json.dumps({'error': message}, ensure_ascii=False))
        sys.exit(2)


if __name__ == '__main__':
    main()
