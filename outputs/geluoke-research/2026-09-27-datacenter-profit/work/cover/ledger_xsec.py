#!/usr/bin/env python3
"""Cover centrepiece: 1GW ledger cross-section (capital in → revenue → costs → NOPAT), engineering-blueprint style. Output SVG 1088x520."""
import sys, json, os
INK='#F4F6FA'; MUTE='#9FB3CC'; GOLD='#E0B45C'; CYAN='#7FD3FF'; GRID='rgba(244,246,250,0.22)'
BLUE='#3987e5'; ORANGE='#d95926'; AQUA='#199e70'; YEL='#c98500'
F='"Noto Sans SC","WenQuanYi Zen Hei",sans-serif'
L=json.load(open(sys.argv[1])) if len(sys.argv)>1 and os.path.isfile(sys.argv[1]) and os.path.getsize(sys.argv[1])>0 else {'capex':'390','it_capex':'230','non_it_capex':'160','revenue':'229','opex':'76','tax':'32','nopat':'121','roic':'31%'}
W,H=1088,520
s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family=\'{F}\'>']
# left: capital stack (building cross-section)
bx,by,bw=40,70,300
s.append(f'<text x="{bx}" y="{by-24}" font-size="24" fill="{CYAN}" letter-spacing="2">投入：1GW GB300 数据中心资本开支</text>')
# ground line
s.append(f'<line x1="{bx-10}" y1="{by+330}" x2="{bx+bw+10}" y2="{by+330}" stroke="{GRID}" stroke-width="2"/>')
# non-IT shell: 160/390 of height
tot=390; hgt=300; h_nonit=hgt*160/tot; h_it=hgt*230/tot
y_it=by+330-hgt; y_nonit=y_it+h_it
s.append(f'<rect x="{bx}" y="{y_it}" width="{bw}" height="{h_it}" fill="rgba(57,135,229,0.22)" stroke="{BLUE}" stroke-width="2"/>')
# racks pattern inside IT block
for i in range(6):
    xx=bx+16+i*47
    s.append(f'<rect x="{xx}" y="{y_it+18}" width="30" height="{h_it-36}" fill="none" stroke="{BLUE}" stroke-width="1.5" opacity="0.9"/>')
    for k in range(5):
        s.append(f'<line x1="{xx}" y1="{y_it+18+(k+1)*(h_it-36)/6:.1f}" x2="{xx+30}" y2="{y_it+18+(k+1)*(h_it-36)/6:.1f}" stroke="{BLUE}" stroke-width="1" opacity="0.6"/>')
s.append(f'<rect x="{bx}" y="{y_nonit}" width="{bw}" height="{h_nonit}" fill="rgba(25,158,112,0.20)" stroke="{AQUA}" stroke-width="2"/>')
# shell details: transformer, chiller, cables
s.append(f'<rect x="{bx+18}" y="{y_nonit+22}" width="70" height="44" fill="none" stroke="{AQUA}" stroke-width="1.5"/><text x="{bx+53}" y="{y_nonit+50}" font-size="15" fill="{AQUA}" text-anchor="middle">变电</text>')
s.append(f'<rect x="{bx+110}" y="{y_nonit+22}" width="70" height="44" fill="none" stroke="{AQUA}" stroke-width="1.5"/><text x="{bx+145}" y="{y_nonit+50}" font-size="15" fill="{AQUA}" text-anchor="middle">冷却</text>')
s.append(f'<rect x="{bx+202}" y="{y_nonit+22}" width="80" height="44" fill="none" stroke="{AQUA}" stroke-width="1.5"/><text x="{bx+242}" y="{y_nonit+50}" font-size="15" fill="{AQUA}" text-anchor="middle">楼宇/土地</text>')
s.append(f'<line x1="{bx}" y1="{y_nonit+84}" x2="{bx+bw}" y2="{y_nonit+84}" stroke="{AQUA}" stroke-width="1" stroke-dasharray="6 5"/>')
# labels on left blocks
s.append(f'<text x="{bx+bw+14}" y="{y_it+h_it/2-4}" font-size="22" font-weight="700" fill="{INK}">IT 资本 {L["it_capex"]}</text><text x="{bx+bw+14}" y="{y_it+h_it/2+22}" font-size="16" fill="{MUTE}">服务器与网络 · 5年折旧</text>')
s.append(f'<text x="{bx+bw+14}" y="{y_nonit+h_nonit/2-2}" font-size="22" font-weight="700" fill="{INK}">非IT资本 {L["non_it_capex"]}</text><text x="{bx+bw+14}" y="{y_nonit+h_nonit/2+22}" font-size="16" fill="{MUTE}">带电壳 · 15年折旧</text>')
s.append(f'<text x="{bx}" y="{by+360}" font-size="26" font-weight="700" fill="{GOLD}">合计 {L["capex"]} 亿美元</text><text x="{bx+228}" y="{by+360}" font-size="16" fill="{MUTE}">一次性投入</text>')
# arrow to right
ax=560
s.append(f'<path d="M{ax-20},{by+150} h40" stroke="{GOLD}" stroke-width="3"/><path d="M{ax+14},{by+141} l12,9 l-12,9" fill="none" stroke="{GOLD}" stroke-width="3"/>')
s.append(f'<text x="{ax+10}" y="{by+128}" font-size="15" fill="{MUTE}" text-anchor="middle">每年</text>')
# right: annual ledger waterfall (vertical bars)
rx=620; rw=430; base=by+300; scale=300/240
def bar(x,val,col,label,sub,y0=None,w=68):
    h=val*scale; y=(base-h) if y0 is None else y0
    s.append(f'<rect x="{x}" y="{y:.1f}" width="{w}" height="{h:.1f}" fill="{col}" opacity="0.92"/>')
    s.append(f'<text x="{x+w/2}" y="{base+26}" font-size="17" fill="{INK}" text-anchor="middle">{label}</text>')
    s.append(f'<text x="{x+w/2}" y="{base+46}" font-size="14" fill="{MUTE}" text-anchor="middle">{sub}</text>')
    return y
s.append(f'<text x="{rx}" y="{by-24}" font-size="24" fill="{CYAN}" letter-spacing="2">产出：每年账本（亿美元/GW）</text>')
y_rev=bar(rx,229,'rgba(244,246,250,0.35)','收入','75%利用率')
s.append(f'<text x="{rx+34}" y="{y_rev-10}" font-size="24" font-weight="700" fill="{INK}" text-anchor="middle">{L["revenue"]}</text>')
# opex stacked from top of revenue downward
x2=rx+100; top=base-229*scale
s.append(f'<rect x="{x2}" y="{top:.1f}" width="68" height="{76*scale:.1f}" fill="{ORANGE}" opacity="0.92"/>')
s.append(f'<text x="{x2+34}" y="{top-10}" font-size="22" font-weight="700" fill="{INK}" text-anchor="middle">−{L["opex"]}</text>')
s.append(f'<text x="{x2+34}" y="{base+26}" font-size="17" fill="{INK}" text-anchor="middle">营业成本</text><text x="{x2+34}" y="{base+46}" font-size="14" fill="{MUTE}" text-anchor="middle">折旧57 能源等20</text>')
x3=rx+200; top3=top+76*scale
s.append(f'<rect x="{x3}" y="{top3:.1f}" width="68" height="{32*scale:.1f}" fill="{YEL}" opacity="0.92"/>')
s.append(f'<text x="{x3+34}" y="{top3-10}" font-size="22" font-weight="700" fill="{INK}" text-anchor="middle">−{L["tax"]}</text>')
s.append(f'<text x="{x3+34}" y="{base+26}" font-size="17" fill="{INK}" text-anchor="middle">税</text><text x="{x3+34}" y="{base+46}" font-size="14" fill="{MUTE}" text-anchor="middle">21%</text>')
x4=rx+300
y_np=bar(x4,121,GOLD,'税后利润','NOPAT')
s.append(f'<text x="{x4+34}" y="{y_np-10}" font-size="24" font-weight="700" fill="{GOLD}" text-anchor="middle">{L["nopat"]}</text>')
# connectors
s.append(f'<line x1="{rx+68}" y1="{top}" x2="{x2}" y2="{top}" stroke="{GRID}" stroke-dasharray="4 4"/>')
s.append(f'<line x1="{x2+68}" y1="{top3}" x2="{x3}" y2="{top3}" stroke="{GRID}" stroke-dasharray="4 4"/>')
s.append(f'<line x1="{x3+68}" y1="{top3+32*scale}" x2="{x4}" y2="{top3+32*scale}" stroke="{GRID}" stroke-dasharray="4 4"/>')
# ROIC callout
s.append(f'<rect x="{rx+236}" y="{by-6}" width="214" height="58" rx="6" fill="rgba(224,180,92,0.12)" stroke="{GOLD}"/>')
s.append(f'<text x="{rx+343}" y="{by+18}" font-size="16" fill="{MUTE}" text-anchor="middle">资本回报率 ROIC = 税后利润 ÷ 投入</text><text x="{rx+343}" y="{by+44}" font-size="22" font-weight="700" fill="{GOLD}" text-anchor="middle">{L["nopat"]} ÷ {L["capex"]} ≈ {L["roic"]}</text>')
s.append(f'<text x="{W-20}" y="{H-14}" font-size="14" fill="{MUTE}" text-anchor="end">示意剖面，非任何企业实际设施；数字为摩根士丹利2026年9月估算</text>')
s.append('</svg>')
open(sys.argv[2] if len(sys.argv)>2 else 'ledger_xsec.svg','w').write('\n'.join(s)); print('ok')
