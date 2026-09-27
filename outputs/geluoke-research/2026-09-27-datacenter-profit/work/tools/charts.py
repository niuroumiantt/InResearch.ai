#!/usr/bin/env python3
"""SVG chart helpers in the daily's blueprint style (navy surface), sized for WeChat phone width.
Design width 640 CSS px rendered at DPR 2 (1280px). Inline display on a 390px phone is ~0.56x, so body text is >=20px here (>=11px on phone).
Palette validated on #0B1F3A: #3987e5 blue, #d95926 orange, #199e70 aqua, #c98500 yellow. Gold #E0B45C for rules/titles only.
"""
import html, re
NAVY='#0B1F3A'; INK='#F4F6FA'; MUTE='#9FB3CC'; GOLD='#E0B45C'; GRID='rgba(244,246,250,0.14)'
FONT='"Noto Sans SC","WenQuanYi Zen Hei",sans-serif'
SERIES=['#3987e5','#d95926','#199e70','#c98500']
e=lambda s: html.escape(str(s), quote=False)
def tw(s, size):
    """estimated text width in px"""
    w=0
    for ch in s:
        w+= size if ord(ch)>0x2E7F else size*0.56
    return w
UNITS=set('年月日亿万千个县州项台颗人次倍级期号')
UNIT_WORDS=['令吉','卢比','美元','英亩','英里','平方','泰铢','日元','小时','升/秒']
def _tokens(s):
    """wrap units: CJK char (+trailing closing punctuation), or an ASCII run (+trailing punctuation); digits stay glued to their CJK unit"""
    raw=[]; i=0; n=len(s)
    PUNCT='，。；、：）】》”’%'
    while i<n:
        ch=s[i]
        if ord(ch)>0x2E7F and ch not in '（【《':
            t=ch; i+=1
            while i<n and s[i] in PUNCT: t+=s[i]; i+=1
            raw.append(t)
        elif ch in '（【《':
            t=ch; i+=1
            if i<n: t+=s[i]; i+=1
            raw.append(t)
        else:
            t=ch; i+=1
            while i<n and ord(s[i])<=0x2E7F and s[i]!=' ': t+=s[i]; i+=1
            while i<n and s[i] in PUNCT: t+=s[i]; i+=1
            if i<n and s[i]==' ': t+=' '; i+=1
            raw.append(t)
    toks=[]
    for t in raw:
        if toks and toks[-1] and ord(toks[-1][-1])<=0x2E7F and toks[-1][-1].isdigit() and ord(t[0])>0x2E7F and t[0] in UNITS:
            toks[-1]+=t
        elif toks and any((toks[-1][-1]+t[0])==u for u in UNIT_WORDS):
            toks[-1]+=t
        elif toks and t[0] in '/→–-%':
            toks[-1]+=t
        else: toks.append(t)
    return toks
def wrap(s, size, maxw):
    """greedy token wrap by estimated width"""
    if tw(s,size)<=maxw: return [s]
    lines=[]; cur=''
    for t in _tokens(s):
        if cur and tw(cur+t,size)>maxw:
            lines.append(cur.rstrip()); cur=t.lstrip()
        else: cur+=t
    if cur.strip(): lines.append(cur.rstrip())
    return lines

def frame(w,h,title,subtitle,source,body,unit_note=''):
    t_lines=wrap(title,28,w-66); sub_lines=wrap(subtitle,18,w-64)
    src_lines=wrap(source,16,w-48-(tw(unit_note,16)+16 if unit_note else 0))
    src_h=len(src_lines)*20; th=34*len(t_lines)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family='{FONT}'>
<rect width="{w}" height="{h}" fill="{NAVY}"/>
<rect x="24" y="26" width="5" height="{th+22*len(sub_lines)}" fill="{GOLD}"/>
{''.join(f'<text x="42" y="{52+i*34}" font-size="28" font-weight="700" fill="{INK}">{e(l)}</text>' for i,l in enumerate(t_lines))}
{''.join(f'<text x="42" y="{44+th+i*22}" font-size="18" fill="{MUTE}">{e(l)}</text>' for i,l in enumerate(sub_lines))}
{body}
<line x1="24" y1="{h-src_h-30}" x2="{w-24}" y2="{h-src_h-30}" stroke="{GRID}"/>
{''.join(f'<text x="24" y="{h-src_h-8+i*20}" font-size="16" fill="{MUTE}">{e(l)}</text>' for i,l in enumerate(src_lines))}
<text x="{w-24}" y="{h-src_h-8}" font-size="16" fill="{MUTE}" text-anchor="end">{e(unit_note)}</text>
</svg>'''

def TOP(subtitle,w,title=''): return 44+34*max(1,len(wrap(title,28,w-66)))+22*len(wrap(subtitle,18,w-64))+22

def hbar(items, title, subtitle, source, unit, w=640, label_w=250, bar_h=26, gap=18, vmax=None, fmt=lambda v: f'{v:g}', legend=None, note_lines=()):
    """items: (label, value, color_index, note). legend: list of (color_index, text)"""
    vmax=vmax or max(v for _,v,*r in items)*1.12
    plot_x=24+label_w; plot_w=w-plot_x-96
    y=TOP(subtitle,w,title); body=[]
    if legend:
        x=24
        for ci,txt in legend:
            body.append(f'<rect x="{x}" y="{y}" width="14" height="14" rx="2" fill="{SERIES[ci]}"/><text x="{x+20}" y="{y+13}" font-size="17" fill="{INK}">{e(txt)}</text>')
            x+=20+tw(txt,17)+26
        y+=34
    for it in items:
        label,val=it[0],it[1]; ci=it[2] if len(it)>2 and it[2] is not None else 0
        note=it[3] if len(it)>3 else ''
        bw=max(2, plot_w*val/vmax)
        lab=wrap(label,19,label_w-14)
        for j,l in enumerate(lab):
            body.append(f'<text x="{plot_x-12}" y="{y+bar_h*0.78-(len(lab)-1-j)*0 + j*21 - (len(lab)-1)*10}" font-size="19" fill="{INK}" text-anchor="end">{e(l)}</text>')
        body.append(f'<path d="M{plot_x},{y} h{bw-4} a4,4 0 0 1 4,4 v{bar_h-8} a4,4 0 0 1 -4,4 h{-(bw-4)} z" fill="{SERIES[ci]}"/>')
        body.append(f'<text x="{plot_x+bw+10}" y="{y+bar_h*0.78}" font-size="20" font-weight="700" fill="{INK}">{e(fmt(val))}</text>')
        yy=y+bar_h+6
        for l in wrap(note,16,w-plot_x-24):
            body.append(f'<text x="{plot_x}" y="{yy+14}" font-size="16" fill="{MUTE}">{e(l)}</text>'); yy+=20
        y=yy+gap
    for ln in note_lines:
        for l in wrap(ln,17,w-48):
            body.append(f'<text x="24" y="{y+14}" font-size="17" fill="{MUTE}">{e(l)}</text>'); y+=22
    h=y+40+20*len(wrap(source,16,w-48))
    return frame(w,h,title,subtitle,source,'\n'.join(body),unit)

def table_cards(rows, title, subtitle, source, w=640, top=None, note_lines=(), line_size=19, head_size=22):
    """rows: {head, lines:[...], color_index}. Single-column stacked cards, auto-wrapped."""
    top=top or TOP(subtitle,w,title)
    gap=14; cw=w-48; body=[]; y=top
    for r in rows:
        heads=wrap(r['head'],head_size,cw-30)
        lines=[l for ln in r['lines'] for l in wrap(ln,line_size,cw-30)]
        head_block=head_size*1.25*len(heads)
        ch=14+head_block+10+line_size*1.4*len(lines)+14
        body.append(f'<rect x="24" y="{y}" width="{cw}" height="{ch:.0f}" rx="6" fill="rgba(255,255,255,0.05)" stroke="{GRID}"/>')
        body.append(f'<rect x="24" y="{y+14}" width="5" height="{head_block:.0f}" fill="{SERIES[r.get("color_index",0)]}"/>')
        for i,hl in enumerate(heads):
            body.append(f'<text x="40" y="{y+14+head_size*0.95+i*head_size*1.25:.0f}" font-size="{head_size}" font-weight="700" fill="{INK}">{e(hl)}</text>')
        yy=y+14+head_block+10
        for l in lines:
            body.append(f'<text x="40" y="{yy+line_size*0.95:.0f}" font-size="{line_size}" fill="{INK}">{e(l)}</text>'); yy+=line_size*1.4
        y+=ch+gap
    y+=6
    for ln in note_lines:
        for l in wrap(ln,17,w-48):
            body.append(f'<text x="24" y="{y+14:.0f}" font-size="17" fill="{MUTE}">{e(l)}</text>'); y+=22
    h=y+40+20*len(wrap(source,16,w-48))
    return frame(w,h,title,subtitle,source,'\n'.join(body))

def vtimeline(rows, title, subtitle, source, w=640, top=None, note_lines=()):
    """rows: {when, head, text, state: done|now|next}. Vertical timeline."""
    top=top or TOP(subtitle,w,title)
    x_line=150; body=[]; y=top
    items=[]
    for r in rows:
        lines=[l for ln in r['text'].split('\n') for l in wrap(ln,18,w-x_line-22-24)]
        items.append((r,lines,34+24*len(lines)+6))
    total=sum(h for _,_,h in items)
    body.append(f'<line x1="{x_line}" y1="{top-6}" x2="{x_line}" y2="{top+total-14}" stroke="{GRID}" stroke-width="2"/>')
    for r,lines,hh in items:
        fill={'done':SERIES[0],'now':GOLD,'next':NAVY}[r['state']]
        stroke=GOLD if r['state']=='now' else (SERIES[0] if r['state']=='done' else MUTE)
        body.append(f'<circle cx="{x_line}" cy="{y+9}" r="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        body.append(f'<text x="{x_line-18}" y="{y+15}" font-size="16" fill="{MUTE}" text-anchor="end">{e(r["when"])}</text>')
        body.append(f'<text x="{x_line+22}" y="{y+16}" font-size="20" font-weight="700" fill="{INK}">{e(r["head"])}</text>')
        for j,ln in enumerate(lines):
            body.append(f'<text x="{x_line+22}" y="{y+42+j*24}" font-size="18" fill="{INK}" opacity="0.92">{e(ln)}</text>')
        y+=hh
    for ln in note_lines:
        for l in wrap(ln,17,w-48):
            body.append(f'<text x="24" y="{y+14}" font-size="17" fill="{MUTE}">{e(l)}</text>'); y+=22
    h=y+40+20*len(wrap(source,16,w-48))
    return frame(w,h,title,subtitle,source,'\n'.join(body))
