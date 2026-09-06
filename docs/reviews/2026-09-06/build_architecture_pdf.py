#!/usr/bin/env python3
"""Build the complete adopted Chinese architecture document as an external PDF.

Requires reportlab; uses an embedded Chinese TrueType font, never remote assets.
Example:
  python3 build_architecture_pdf.py --output ~/.local/share/inresearch.ai/artifacts/research-architecture-v2.pdf
Override fonts with --font and --bold-font on systems without macOS STHeiti.
Rendering QA: pdftoppm -r 120 -png OUTPUT.pdf /tmp/inresearch-pdf-qa/page
No binary artifact is written into the repository by default.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import math
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    Flowable, KeepTogether,
)

NAVY = colors.HexColor('#123349')
TEAL = colors.HexColor('#087E8B')
INK = colors.HexColor('#243543')
MUTED = colors.HexColor('#617583')
RULE = colors.HexColor('#D9E4E9')
PALE = colors.HexColor('#EEF5F7')
FONT = 'CJK'
BOLD = 'CJK-Bold'
WIDTH = A4[0] - 92


def inline(value: str) -> str:
    """Escape Markdown while retaining visible text and clickable link targets."""
    stash = []
    def link(m):
        target = html.unescape(m.group(2))
        # A PDF link may target a relative repository document; preserve it.
        text = f'<a href="{escape(target, {chr(34): "&quot;"})}" color="#087E8B">{escape(m.group(1))}</a>'
        stash.append(text)
        return f'LINKTOKEN{len(stash)-1}END'
    value = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, value)
    value = escape(value)
    value = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', value)
    value = re.sub(r'`([^`]+)`', r'<font color="#386574">\1</font>', value)
    value = value.replace('&lt;br&gt;', '<br/>').replace('&lt;br/&gt;', '<br/>')
    for index, replacement in enumerate(stash):
        value = value.replace(f'LINKTOKEN{index}END', replacement)
    return value


def styles():
    common = dict(fontName=FONT, textColor=INK, wordWrap='CJK', splitLongWords=True,
                  allowWidows=0, allowOrphans=0)
    body = ParagraphStyle('Body', fontSize=10, leading=16.1, spaceAfter=8, **common)
    return {
        'body': body,
        'h1': ParagraphStyle('H1', parent=body, fontName=BOLD, fontSize=23, leading=33,
                             textColor=NAVY, spaceAfter=16, keepWithNext=True),
        'h2': ParagraphStyle('H2', parent=body, fontName=BOLD, fontSize=15, leading=23,
                             textColor=NAVY, spaceBefore=18, spaceAfter=9, keepWithNext=True),
        'h3': ParagraphStyle('H3', parent=body, fontName=BOLD, fontSize=11.8, leading=18.5,
                             textColor=TEAL, spaceBefore=12, spaceAfter=7, keepWithNext=True),
        'cell': ParagraphStyle('Cell', parent=body, fontSize=8.8, leading=14, spaceAfter=0),
        'th': ParagraphStyle('TH', parent=body, fontName=BOLD, fontSize=9, leading=14,
                             textColor=colors.white, spaceAfter=0),
        'quote': ParagraphStyle('Quote', parent=body, fontSize=9.4, leading=15.5,
                                leftIndent=11, rightIndent=9, textColor=MUTED,
                                borderPadding=9, backColor=PALE),
        'bullet': ParagraphStyle('Bullet', parent=body, leftIndent=12, firstLineIndent=-11),
        'small': ParagraphStyle('Small', parent=body, fontSize=8.2, leading=13, textColor=MUTED),
        'cover': ParagraphStyle('Cover', parent=body, fontName=BOLD, fontSize=31, leading=44,
                                textColor=NAVY, spaceAfter=26),
        'cover_sub': ParagraphStyle('CoverSub', parent=body, fontSize=13, leading=22,
                                    textColor=TEAL, spaceAfter=20),
    }


class ArchitectureMap(Flowable):
    """Vector equivalent of the sole Mermaid graph, with every edge retained."""
    def __init__(self, width):
        super().__init__()
        self.width, self.height = width, 330
        self.nodes = {
            'P': (16, 258, 218, 43, '物理与空间：3D / 设备 / 装配'),
            'F': (270, 258, 218, 43, '系统：电 / 热 / 数据 / 控制'),
            'V': (16, 188, 218, 43, '产业：制造 / 持有 / 运营 / 交易'),
            'D': (270, 188, 218, 43, '需求：应用 / 工作负载 / 部署'),
            'R': (89, 111, 326, 45, '研究问题 → 证据与事实 → 判断与交付'),
            'T': (16, 28, 218, 43, '缺口任务：搜集 / 访谈 / 实测 / 复核'),
            'E': (270, 28, 218, 43, '统一原件与证据台账'),
        }
        self.scale = width / 504

    def draw(self):
        c = self.canv
        c.saveState()
        c.scale(self.scale, self.scale)
        def arrow(points, directed=True, dashed=False):
            c.setStrokeColor(MUTED)
            c.setLineWidth(.85)
            c.setDash(3, 2) if dashed else c.setDash()
            path = c.beginPath()
            path.moveTo(*points[0])
            for point in points[1:]: path.lineTo(*point)
            c.drawPath(path)
            c.setDash()
            if directed:
                x0,y0=points[-2]; x1,y1=points[-1]
                angle=math.atan2(y1-y0,x1-x0)
                path=c.beginPath(); path.moveTo(x1,y1)
                for offset in (-.48,.48):
                    path.lineTo(x1-6*math.cos(angle+offset),y1-6*math.sin(angle+offset))
                path.close(); c.setFillColor(MUTED); c.drawPath(path,fill=1,stroke=0)
        # Undirected relationships: P-F, P-V, F-D, V-D.
        for a,b in [((234,279),(270,279)),((125,258),(125,231)),
                    ((379,258),(379,231)),((234,209),(270,209))]:
            arrow([a,b],False)
        # Four knowledge inputs, routed separately.
        arrow([(30,258),(4,258),(4,166),(130,166),(130,156)])
        arrow([(474,258),(500,258),(500,166),(374,166),(374,156)])
        arrow([(180,188),(180,156)])
        arrow([(324,188),(324,156)])
        arrow([(180,111),(180,90),(125,90),(125,71)]) # R -> T
        arrow([(234,49),(270,49)]) # T -> E
        arrow([(379,71),(379,90),(324,90),(324,111)]) # E -> R
        # Bottom-up taxonomy feedback E -> P, drawn as a labelled perimeter path.
        arrow([(488,49),(502,49),(502,315),(125,315),(125,301)],True,True)
        c.setFont(FONT,8.5); c.setFillColor(MUTED)
        c.drawString(183,319,'新对象 / 新问题 / 分类提案')
        for key,(x,y,w,h,label) in self.nodes.items():
            c.setFillColor(NAVY if key=='R' else PALE)
            c.setStrokeColor(TEAL if key=='R' else RULE)
            c.roundRect(x,y,w,h,7,fill=1,stroke=1)
            c.setFont(FONT,10)
            c.setFillColor(colors.white if key=='R' else NAVY)
            c.drawCentredString(x+w/2,y+h/2-3,label)
        c.restoreState()


def make_table(lines, st):
    rows = [[part.strip() for part in row.strip().strip('|').split('|')] for row in lines]
    rows = [r for r in rows if not all(re.fullmatch(r'[:\- ]+', x) for x in r)]
    n = len(rows[0])
    if any(len(r) != n for r in rows):
        raise ValueError('Inconsistent Markdown table column count')
    if n==2: ratios=[.29,.71]
    elif n==3: ratios=[.22,.37,.41]
    elif n==4: ratios=[.16,.28,.28,.28]
    else: ratios=[1/n]*n
    cells=[]
    for j,row in enumerate(rows):
        cells.append([Paragraph(inline(cell),st['th'] if j==0 else st['cell']) for cell in row])
    t=Table(cells,colWidths=[WIDTH*x for x in ratios],repeatRows=1,hAlign='LEFT',splitByRow=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),NAVY),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
        ('LINEBELOW',(0,0),(-1,0),.6,TEAL),
        ('LINEBELOW',(0,1),(-1,-1),.3,RULE),
    ]))
    return t


def blocks(text, st):
    lines=text.splitlines(); out=[]; i=0; seen_title=False
    while i<len(lines):
        line=lines[i]
        if not line.strip(): i+=1; continue
        if line.startswith('```'):
            lang=line[3:].strip(); content=[]; i+=1
            while i<len(lines) and not lines[i].startswith('```'):
                content.append(lines[i]); i+=1
            if i==len(lines): raise ValueError('Unclosed code block')
            i+=1
            if lang=='mermaid':
                # Refuse silent diagram loss if the source graph changes.
                expected_hash='07276f15db149254f26e99158b55f667d6a5e4c22b75b25466102ffed1c404a6'
                if hashlib.sha256('\n'.join(content).encode()).hexdigest() != expected_hash:
                    raise ValueError('Unknown Mermaid graph; update the vector equivalent')
                out.append(ArchitectureMap(WIDTH))
                out.append(Paragraph('图 1　五个视角共享研究与证据；虚线为材料驱动的框架修订。',st['small']))
            else:
                content_html='<br/>'.join(inline(x.strip()) for x in content)
                out.append(KeepTogether([Paragraph(content_html,st['quote'])]))
            out.append(Spacer(1,8)); continue
        if line.startswith('|'):
            table=[]
            while i<len(lines) and lines[i].startswith('|'):
                table.append(lines[i]); i+=1
            out.append(make_table(table,st)); out.append(Spacer(1,9)); continue
        if line.startswith('# '):
            if not seen_title: seen_title=True; i+=1; continue # exact title appears on cover
            out.append(Paragraph(inline(line[2:]),st['h1'])); i+=1; continue
        if line.startswith('## '):
            out.append(Paragraph(inline(line[3:]),st['h2'])); i+=1; continue
        if line.startswith('### '):
            out.append(Paragraph(inline(line[4:]),st['h3'])); i+=1; continue
        if line.startswith('> '):
            para=[]
            while i<len(lines) and lines[i].startswith('>'):
                para.append(lines[i].lstrip('> ').strip()); i+=1
            out.append(Paragraph(inline(' '.join(para)),st['quote'])); continue
        if line.startswith('- ') or re.match(r'^\d+\. ',line):
            out.append(Paragraph(inline(line),st['bullet'])); i+=1; continue
        para=[line]; i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||>|```|- |\d+\. )',lines[i]):
            para.append(lines[i]); i+=1
        out.append(Paragraph(inline(' '.join(para)),st['body']))
    return out


def draw_page(c, doc):
    c.saveState()
    if doc.page>1:
        c.setStrokeColor(RULE); c.setLineWidth(.55)
        c.line(46,A4[1]-38,A4[0]-46,A4[1]-38)
        c.setFont(FONT,8.2); c.setFillColor(MUTED)
        c.drawString(46,A4[1]-28,'INRESEARCH.AI  /  全行业研究架构')
        c.drawRightString(A4[0]-46,A4[1]-28,'V2 · 2026-09-06 用户采用')
    c.setFont(FONT,8); c.setFillColor(MUTED)
    c.drawString(46,28,'研究实施基准 · 原文、口径与采用状态分别可追溯')
    c.drawRightString(A4[0]-46,28,f'{doc.page:02d}')
    c.restoreState()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).with_name('RESEARCH_ARCHITECTURE_V2.md'))
    parser.add_argument('--output',type=Path,default=Path.home()/'.local/share/inresearch.ai/artifacts/research-architecture-v2.pdf')
    parser.add_argument('--font',type=Path,default=Path('/System/Library/Fonts/STHeiti Light.ttc'))
    parser.add_argument('--bold-font',type=Path,default=Path('/System/Library/Fonts/STHeiti Medium.ttc'))
    args=parser.parse_args()
    for name,path in [(FONT,args.font),(BOLD,args.bold_font)]:
        if not path.exists(): raise SystemExit(f'Chinese font missing: {path}; provide --font / --bold-font')
        pdfmetrics.registerFont(TTFont(name,str(path),subfontIndex=0))
    pdfmetrics.registerFontFamily(FONT,normal=FONT,bold=BOLD,italic=FONT,boldItalic=BOLD)
    source=args.source.read_text()
    # Ensure every source glyph is present in at least the regular font.
    required=set(source)-set('\n\r\t')
    missing=sorted(c for c in required if ord(c) not in pdfmetrics.getFont(FONT).face.charToGlyph)
    if missing: raise SystemExit(f'Font lacks source glyphs: {missing}')
    st=styles(); sha=hashlib.sha256(args.source.read_bytes()).hexdigest()
    title=source.splitlines()[0].removeprefix('# ')
    story=[Spacer(1,62),Paragraph('INRESEARCH.AI  /  RESEARCH ARCHITECTURE',st['cover_sub']),
           Paragraph(inline(title),st['cover']),
           Paragraph('2026-09-06 用户采用<br/>完整内容 · 正式实施基准',st['cover_sub']),
           Spacer(1,26),
           Paragraph('本文件完整收入架构主稿，不作摘要删节。Mermaid 源码转换为等价关系图；表格保留全部行列并按页续排。',st['body']),
           Paragraph('原稿形成时的“提案、建议、尚未实施”等语句保留其历史语境。用户已采用本架构并授权推进；采用不代表全部代码、数据与服务已经完成部署，具体状态以验收记录为准。',st['body']),
           Paragraph('原件保留、现行数据口径与 C3 研究采用要求保持不变。',st['body']),
           Spacer(1,42),Paragraph('正文来源：docs/reviews/2026-09-06/RESEARCH_ARCHITECTURE_V2.md',st['small']),
           Paragraph('来源 SHA-256：'+sha,st['small']),PageBreak()]
    story.extend(blocks(source,st))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(args.output),pagesize=A4,rightMargin=46,leftMargin=46,
                          topMargin=54,bottomMargin=48,title=title,author='InResearch.ai',
                          subject='2026-09-06 用户采用的全行业研究架构与实施基准',
                          pageCompression=1)
    doc.build(story,onFirstPage=draw_page,onLaterPages=draw_page)
    print(f'Created {args.output}\nSource SHA-256 {sha}')

if __name__=='__main__': main()
