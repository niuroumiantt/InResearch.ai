#!/usr/bin/env python3
"""Long-form figures (SVG, design width 640, DPR2 render). Reuses charts.py helpers."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from charts import frame, hbar, table_cards, wrap, tw, TOP, NAVY, INK, MUTE, GOLD, GRID, SERIES, e
OUT=os.path.dirname(os.path.abspath(__file__))
W=640

def fig1():
    items=[('Rubin Ultra',500,1,'含表后自发电约30亿美元'),('Vera Rubin',490,1,''),('GB300',390,0,'IT设备230亿+非IT 160亿；带电壳约40%、加速器机架约30%'),('GB200',350,0,''),('TPUv7（谷歌）',270,2,''),('Trainium3（亚马逊）',210,2,'')]
    svg=hbar(items,'一座1GW数据中心要花多少钱','按芯片代际的GW级数据中心总资本开支（IT+非IT），亿美元/GW','摩根士丹利2026年9月《AI指南》第22、64页，预测估算；原始单位十亿美元/GW',
             '', label_w=232, vmax=580, fmt=lambda v:f'{v:g}', legend=[(1,'英伟达下一代'),(0,'英伟达当代'),(2,'自研ASIC')],
             note_lines=('对照：高盛全球研究所假设数据中心1,500万美元/MW（即150亿美元/GW，不含IT）、新电力2,500美元/kW；格洛可100MW模型capex 48.5亿美元（作者说明性计算）',))
    open(os.path.join(OUT,'fig1.svg'),'w').write(svg)

def fig2():
    """three paths: revenue bar, cost stack, NOPAT bar, ROIC label. horizontal mini-waterfalls"""
    title='同一GW，三种赚法：收入、成本与税后利润'; subtitle='摩根士丹利1GW GB300账本，十亿美元/GW/年；ROIC=NOPAT÷总资本开支390亿'
    paths=[
      {'name':'超大规模厂商出租GPU（IaaS）','rev':22.9,'cost':[('IT折旧',4.6,0),('非IT折旧',1.1,2),('能源等',2.0,3),('税',3.2,1)],'cost_total':10.8,'nopat':12.1,'roic':'31%'},
      {'name':'自有基础设施上跑模型API','rev':30.4,'cost':[('IT折旧',4.6,0),('非IT折旧',1.1,2),('能源等',2.0,3),('税',4.8,1)],'cost_total':12.4,'nopat':17.9,'roic':'46%'},
      {'name':'租第三方算力跑模型API','rev':40.5,'cost':[('算力租金',27.9,0),('税',2.6,1)],'cost_total':30.5,'nopat':10.0,'roic':'25%*'},
    ]
    y=TOP(subtitle,W,title); body=[]
    # legend
    x=24
    for ci,txt in [(0,'IT折旧/算力租金'),(2,'非IT折旧'),(3,'能源及其他'),(1,'税')]:
        body.append(f'<rect x="{x}" y="{y}" width="14" height="14" rx="2" fill="{SERIES[ci]}"/><text x="{x+20}" y="{y+13}" font-size="16" fill="{INK}">{e(txt)}</text>'); x+=20+tw(txt,16)+22
    y+=36
    px=24; pw=W-48-130; vmax=42
    for p in paths:
        body.append(f'<text x="24" y="{y+18}" font-size="20" font-weight="700" fill="{INK}">{e(p["name"])}</text>')
        body.append(f'<text x="{W-24}" y="{y+18}" font-size="22" font-weight="700" fill="{GOLD}" text-anchor="end">ROIC {e(p["roic"])}</text>')
        y+=30
        rows=[('收入',[(p['rev'],'rgba(244,246,250,0.35)')],p['rev']),('成本与税',[(v,SERIES[ci]) for _,v,ci in p['cost']],p['cost_total']),('税后利润',[(p['nopat'],GOLD)],p['nopat'])]
        for lab,segs,tot_disp in rows:
            body.append(f'<text x="{px}" y="{y+17}" font-size="16" fill="{MUTE}">{e(lab)}</text>')
            xx=px+78
            for v,col in segs:
                bw=pw*v/vmax
                body.append(f'<rect x="{xx:.1f}" y="{y}" width="{max(bw,1.5):.1f}" height="22" fill="{col}"/>')
                if bw>34 and len(segs)>1: body.append(f'<text x="{xx+bw/2:.1f}" y="{y+16}" font-size="14" fill="#0B1F3A" text-anchor="middle" font-weight="700">{v:g}</text>')
                xx+=bw
            body.append(f'<text x="{xx+8:.1f}" y="{y+17}" font-size="18" font-weight="700" fill="{INK}">{tot_disp:.1f}</text>')
            y+=28
        y+=16
    for ln in ('*第三条路径的25%为税后利润率（NOPAT÷收入），不是资本回报率；前两条为NOPAT÷总资本开支。',
               '成本口径：IT折旧=IT资本230亿÷5年；非IT折旧=160亿÷15年；能源及其他含电费、人工、维护；税率21%。收入假设75%利用率、8.5美元/GPU·小时。成本合计为营业成本（7.6）与税之和；分项为报告图中取整值，相加与合计可能相差0.1。'):
        for l in wrap(ln,16,W-48):
            body.append(f'<text x="24" y="{y+14}" font-size="16" fill="{MUTE}">{e(l)}</text>'); y+=21
    h=y+44+20
    svg=frame(W,h,title,subtitle,'摩根士丹利2026年9月《AI指南》第25–31页，预测估算','\n'.join(body),'十亿美元/GW/年')
    open(os.path.join(OUT,'fig2.svg'),'w').write(svg)

def fig4():
    title='3.21万亿美元从哪里来'; subtitle='摩根士丹利估算2026–2028年数据中心资本开支需求的资金来源，亿美元'
    y=TOP(subtitle,W,title); body=[]
    # top stacked bar equity vs credit
    total=32100; px=24; pw=W-48
    segs=[('股权资本',14600,GOLD),('信贷市场',17500,SERIES[0])]
    xx=px
    body.append(f'<text x="24" y="{y+16}" font-size="18" fill="{INK}">合计 <tspan font-weight="700">32,100</tspan> 亿美元（约3.21万亿）</text>'); y+=26
    for lab,v,col in segs:
        bw=pw*v/total
        body.append(f'<rect x="{xx:.1f}" y="{y}" width="{bw:.1f}" height="34" fill="{col}"/>')
        body.append(f'<text x="{xx+bw/2:.1f}" y="{y+23}" font-size="18" font-weight="700" fill="#0B1F3A" text-anchor="middle">{e(lab)} {v:,}</text>')
        xx+=bw
    y+=52
    body.append(f'<text x="24" y="{y+16}" font-size="18" fill="{INK}">信贷市场 17,500 亿美元的构成</text>'); y+=30
    items=[('私募信贷',7000,'其中资产支持融资约5,000、投资级私募约2,000'),('投资级公司债',6500,'超大规模厂商约6,000、非超大规模约500'),('ABS／CMBS',2000,''),('高收益债',1500,''),('银行贷款',500,'')]
    vmax=7600; label_w=150; plot_x=24+label_w; plot_w=W-plot_x-100
    for lab,v,note in items:
        bw=plot_w*v/vmax
        body.append(f'<text x="{plot_x-12}" y="{y+19}" font-size="18" fill="{INK}" text-anchor="end">{e(lab)}</text>')
        body.append(f'<rect x="{plot_x}" y="{y}" width="{bw:.1f}" height="24" rx="3" fill="{SERIES[0]}"/>')
        body.append(f'<text x="{plot_x+bw+8:.1f}" y="{y+18}" font-size="19" font-weight="700" fill="{INK}">{v:,}</text>')
        y+=28
        if note:
            for l in wrap(note,15,W-plot_x-24):
                body.append(f'<text x="{plot_x}" y="{y+12}" font-size="15" fill="{MUTE}">{e(l)}</text>'); y+=19
        y+=8
    y+=8
    for ln in ('对照：四大超大规模厂商经营现金流 2026／2027／2028 年为 7,390／9,820／12,310 亿美元，同期新增举债 2,380／2,000／900 亿美元（摩根士丹利估算）。',
               '高盛投行（2026年6月）：2025年AI相关债券发行约1,210亿美元，占美国投资级市场6.6%，2026年或升至20%；私募信贷管理资产超过2.1万亿美元。'):
        for l in wrap(ln,16,W-48):
            body.append(f'<text x="24" y="{y+14}" font-size="16" fill="{MUTE}">{e(l)}</text>'); y+=21
        y+=6
    h=y+44+20
    svg=frame(W,h,title,subtitle,'摩根士丹利2026年9月《AI指南》第55、60页（原始单位十亿美元）；高盛投行2026年6月报告第24页；均为预测估算','\n'.join(body),'')
    open(os.path.join(OUT,'fig4.svg'),'w').write(svg)


def fig5():
    """ROIC sensitivity: price (MS table), utilization and IT life (author calc on MS formula)"""
    title='什么会把31%的资本回报率拉高或拉低'; subtitle='1GW GB300账本的资本回报率（NOPAT÷390亿美元），按单一变量变化'
    chips=410256; hours=8760
    def roic(price=8.5, util=0.75, it_life=5):
        rev=chips*hours*util*price/1e9
        opex=23/it_life+16/15+2.0
        return (rev-opex)*0.79/39*100, rev
    groups=[
      ('GPU小时价（美元/GPU·小时）','摩根士丹利表格',[('7.0',23),('8.0',28),('8.5 基准',31),('9.0',34),('10.0',39)],0),
      ('利用率（收费GPU小时÷全部GPU小时）','作者按MS公式计算',[(f'{u:.0%}'+(' 基准' if u==0.75 else ''),round(roic(util=u)[0])) for u in (0.6,0.7,0.75,0.8,0.9)],2),
      ('IT设备折旧年限','作者按MS公式计算',[(f'{n}年'+(' 基准' if n==5 else ''),round(roic(it_life=n)[0])) for n in (3,4,5,6,7)],3),
    ]
    y=TOP(subtitle,W,title); body=[]
    label_w=118; plot_x=24+label_w; plot_w=W-plot_x-70; vmax=45
    for gname,gattr,rows,ci in groups:
        body.append(f'<text x="24" y="{y+18}" font-size="20" font-weight="700" fill="{INK}">{e(gname)}</text>')
        body.append(f'<text x="{W-24}" y="{y+18}" font-size="15" fill="{MUTE}" text-anchor="end">{e(gattr)}</text>'); y+=30
        for lab,v in rows:
            base=('基准' in lab)
            bw=plot_w*v/vmax
            body.append(f'<text x="{plot_x-10}" y="{y+17}" font-size="17" fill="{INK}" text-anchor="end" font-weight="{700 if base else 400}">{e(lab)}</text>')
            body.append(f'<rect x="{plot_x}" y="{y}" width="{bw:.1f}" height="22" rx="3" fill="{GOLD if base else SERIES[ci]}"/>')
            body.append(f'<text x="{plot_x+bw+8:.1f}" y="{y+17}" font-size="18" font-weight="700" fill="{INK}">{v}%</text>')
            y+=27
        y+=16
    for ln in ('公式：收入=410,256颗GPU×8,760小时×利用率×小时价；运营成本=IT资本230亿÷折旧年限+非IT资本160亿÷15年+能源及其他20亿；NOPAT=(收入−运营成本)×(1−21%)；ROIC=NOPAT÷390亿。利用率与折旧年限两组为作者按此公式的说明性计算，取整到1%。',):
        for l in wrap(ln,15,W-48):
            body.append(f'<text x="24" y="{y+13}" font-size="15" fill="{MUTE}">{e(l)}</text>'); y+=20
    h=y+58+20
    svg=frame(W,h,title,subtitle,'价格组：摩根士丹利2026年9月《AI指南》第27页，预测估算；其余两组：作者说明性计算','\n'.join(body),'')
    open(os.path.join(OUT,'fig5.svg'),'w').write(svg)
    print({g[0]:g[2] for g in groups})


def fig3():
    """shell-lease contract cards from figdata.json['fig3']"""
    d=json.load(open(os.path.join(OUT,'figdata.json')))['fig3']
    rows=[{'head':r['head'],'lines':r['lines'],'color_index':r.get('ci',0)} for r in d['rows']]
    svg=table_cards(rows,d['title'],d['subtitle'],d['source'],note_lines=d.get('notes',()),line_size=18,head_size=21)
    open(os.path.join(OUT,'fig3.svg'),'w').write(svg)

def fig6():
    """China vs overseas comparison rows from figdata.json['fig6']: rows of {metric, a, b, note}"""
    d=json.load(open(os.path.join(OUT,'figdata.json')))['fig6']
    title=d['title']; subtitle=d['subtitle']
    y=TOP(subtitle,W,title); body=[]
    colA=SERIES[0]; colB=SERIES[1]
    mx=24; cw=(W-48-150)//2; ax=24+150; bx=ax+cw+10
    body.append(f'<text x="{ax+cw/2}" y="{y+18}" font-size="20" font-weight="700" fill="{colA}" text-anchor="middle">{e(d["a_name"])}</text>')
    body.append(f'<text x="{bx+cw/2}" y="{y+18}" font-size="20" font-weight="700" fill="{colB}" text-anchor="middle">{e(d["b_name"])}</text>')
    y+=30
    for r in d['rows']:
        la=wrap(r['a'],17,cw-16); lb=wrap(r['b'],17,cw-16); lm=wrap(r['metric'],18,150-16)
        n=max(len(la),len(lb),len(lm)); rh=14+n*23+ (20*len(wrap(r.get('note',''),14,W-48-150)) if r.get('note') else 0)+10
        body.append(f'<line x1="24" y1="{y}" x2="{W-24}" y2="{y}" stroke="{GRID}"/>')
        for i,l in enumerate(lm): body.append(f'<text x="24" y="{y+14+18+i*23}" font-size="18" font-weight="700" fill="{INK}">{e(l)}</text>')
        body.append(f'<rect x="{ax}" y="{y+8}" width="{cw}" height="{n*23+12}" rx="4" fill="rgba(57,135,229,0.10)"/>')
        body.append(f'<rect x="{bx}" y="{y+8}" width="{cw}" height="{n*23+12}" rx="4" fill="rgba(217,89,38,0.10)"/>')
        for i,l in enumerate(la): body.append(f'<text x="{ax+8}" y="{y+14+18+i*23}" font-size="17" fill="{INK}">{e(l)}</text>')
        for i,l in enumerate(lb): body.append(f'<text x="{bx+8}" y="{y+14+18+i*23}" font-size="17" fill="{INK}">{e(l)}</text>')
        yy=y+14+n*23+8
        if r.get('note'):
            for l in wrap(r['note'],14,W-48-150):
                body.append(f'<text x="{ax}" y="{yy+12}" font-size="14" fill="{MUTE}">{e(l)}</text>'); yy+=20
        y+=rh
    body.append(f'<line x1="24" y1="{y}" x2="{W-24}" y2="{y}" stroke="{GRID}"/>'); y+=12
    for ln in d.get('notes',()):
        for l in wrap(ln,15,W-48):
            body.append(f'<text x="24" y="{y+13}" font-size="15" fill="{MUTE}">{e(l)}</text>'); y+=20
    h=y+58+20*len(wrap(d['source'],16,W-48))
    svg=frame(W,h,title,subtitle,d['source'],'\n'.join(body),'')
    open(os.path.join(OUT,'fig6.svg'),'w').write(svg)

if __name__=='__main__':
    which=sys.argv[1:] or ['fig1','fig2','fig4']
    for w in which: globals()[w]()
    print('done',which)
