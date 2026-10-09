"""Deterministic, editable engineering diagrams; no copied photos or generated text."""
from pathlib import Path
from html import escape
import json
OUT=Path(__file__).resolve().parents[2]
A=OUT/'assets';A.mkdir(exist_ok=True)
BLUE='#0B1F3A';INK='#19354c';CYAN='#3987e5';GOLD='#c98500'
def text(x,y,s,size=23,color=INK,weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(s)}</text>'
def lines(x,y,ss,size=23,color=INK,step=34):
    return ''.join(text(x,y+i*step,s,size,color) for i,s in enumerate(ss))
def box(x,y,w,h,fill='#eef5fc',stroke='#cfdeec'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}"/>'
def line(x,y,xx,yy,color=CYAN,dash=False):
    return f'<path d="M{x},{y} L{xx},{yy}" stroke="{color}" stroke-width="3" fill="none"'+(' stroke-dasharray="6 6"' if dash else '')+'/>'
def save(name,h,body,w=640,bg='white'):
    (A/(name+'.svg')).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="{bg}"/><g font-family="Arial,PingFang SC,Microsoft YaHei,sans-serif">{body}</g></svg>')
def head(n,title,sub):
    return text(24,38,f'{n:02}  {title}',28,BLUE,700)+text(24,72,sub,18)

b=head(1,'三大互联，不等于七家公司','物理层 → 市场调度层 → 园区合同层')
b+=text(24,116,'① 物理层：各互联内部同步',23,BLUE,700)
for x,title,desc in [(24,'西部互联','与加拿大相连'),(234,'东部互联','与加拿大相连'),(444,'ERCOT互联','得州大部分地区')]:
    b+=box(x,135,172,116)+text(x+12,170,title,23,BLUE,700)+text(x+12,208,desc,17)
b+=lines(24,290,['互联之间存在有限直流联络','不能把全国富余电力随意调到园区'],23)
b+=line(310,315,310,347)+text(24,390,'② 市场与调度层：七家RTO/ISO',23,BLUE,700)
b+=box(24,410,592,118)+lines(42,444,['PJM · MISO · SPP · CAISO','NYISO · ISO-NE · ERCOT','FERC大负荷改革针对其管辖的六家'],21,step=32)
b+=line(310,540,310,569)+text(24,608,'③ 园区合同层：电力公司与客户',23,BLUE,700)
b+=box(24,628,592,115)+lines(42,664,['接入点 · 扩建费用 · 交付日期','服务等级 · 最低付款 · 信用担保'],23)
b+=lines(24,780,['工程示意，非精确地理边界。','来源：EIA电力输送说明；FERC RTO/ISO页面','制度状态截至2026-10-09。'],16,step=26)
save('fig1-grid',860,b)

b=head(2,'实际增长与预测区间分开看','美国数据中心年度用电｜单位：TWh')
scale=430/600;x0=150
for y,yr,v,c,lab in [(155,'2014',58,CYAN,'历史估算'),(260,'2023',176,CYAN,'历史估算'),(365,'2028低端',325,'#d95926','2024版预测'),(470,'2028高端',580,'#d95926','2024版预测')]:
    b+=text(24,y+20,yr,22)+f'<rect x="{x0}" y="{y}" width="{v*scale:.3f}" height="34" rx="5" fill="{c}"/>'+text(x0+v*scale+7,y+25,str(v),21,c,700)+text(x0,y+68,lab,18)
b+=line(x0,565,x0+430,565,'#8899aa')
for v in [0,200,400,600]:b+=text(x0+v*scale-5,594,str(v),17)
b+=box(24,627,592,127)+lines(42,664,['2023：约占美国总用电量4.4%','2028：预测约占6.7%—12%','能量TWh、峰值GW、园区接入分开'],22)
b+=lines(24,793,['蓝＝历史估算；橙＝预测，均从零起算。','来源：LBNL 2024报告，PDF第6—7页。','预测提出于2024年，不是2026年最新实测。'],16,step=26)
save('fig2-demand',875,b)

b=head(3,'申请怎样变成真实负荷','证据门槛示意｜没有虚构项目数量与通过率')
rows=[('01  位置与接入意向','位置、规模、申请主体；仍可能变化'),('02  系统研究与供电条件','接入点、网络影响、扩建范围'),('03  具有约束力的合同','期限、最低付款、担保、分期容量'),('04  工程与设备','许可、订单、施工、调试里程碑'),('05  送电与真实负荷','首期送电、实际峰值、后续爬坡')]
for i,(title,desc) in enumerate(rows):
    y=112+i*127;b+=box(24,y,592,98)+text(42,y+34,title,25,BLUE,700)+text(42,y+73,desc,21)
    if i<4:b+=line(310,y+103,310,y+122)
b+=box(24,775,592,117,'#fff7e6','#ead4a5')+lines(42,812,['申请MW ≠ 合同MW ≠ 投运MW','设施总功率与IT功率分别登记'],24)
b+=lines(24,930,['来源：PJM 2026负荷报告PDF第6页；ERCOT','2026-06-18公告。作者整理，非统一法定流程。'],16,step=26)
save('fig3-project',997,b)

b=head(4,'同样85%，两地收费对象不同','大型客户规则｜合同义务与适用条件一起看')
b+=box(24,111,592,274)+text(42,149,'弗吉尼亚 · Dominion / GS-5',25,BLUE,700)
b+=lines(42,193,['新客户：最低14年服务与付款义务','适用于2027-01-01及以后签约','最低85%：每月输电与配电成本','2016年前已开始服务客户有豁免','信用不足：担保最高60%最低费用'],22,step=36)
b+=box(24,410,592,205)+text(42,452,'俄亥俄 · AEP Ohio',25,BLUE,700)
b+=lines(42,495,['新大型数据中心：至少85%合同容量','相关付款义务；期限最长12年','2025-07-09决定；行业后续提起上诉'],22,step=36)
b+=box(24,646,592,111,'#fff7e6','#ead4a5')+lines(42,682,['最低网络/容量付款','不能改写成85%未使用电能费'],23)
b+=lines(24,800,['来源：Virginia SCC 2026-02-24说明PDF第2页；','Ohio Consumers’ Counsel案件24-0508页面。','适用客户、豁免及诉讼状态以原规则为准。'],16,step=26)
save('fig4-cost',891,b)

b=head(5,'供电路线，要看补哪一段缺口','合同、电量、接入、备用分别判断')
rows=[('公共电网','共享电源和备用','仍要落实本地接入与服务'),('既有核电PPA','安排长期电能与容量','合同规模不等于新增电厂'),('停运核电重启','有机会增加实际供给','恢复、监管与投运分阶段'),('现场燃气发电','改变园区供电路径','设备、燃料、冗余与许可'),('风光 + 储能','增加电量与部分时段资源','年度匹配不等于全天可靠')]
for i,(title,one,two) in enumerate(rows):
    y=116+i*140;b+=box(24,y,592,117)+text(42,y+34,title,26,BLUE,700)+text(42,y+72,one,22)+text(42,y+103,two,20)
b+=lines(24,855,['来源：IEA 2026报告第6—7章；Talen交易材料','第4页；Constellation 2025-09-23公告。','工程机制对照，未给出通用造价或施工周期。'],16,step=26)
save('fig5-routes',945,b)

b=head(6,'便宜电价，还要配上交付条件','EIA工业平均电价｜2026年1—7月｜美分/kWh')
vals=[('得州',6.72),('亚利桑那',7.66),('佐治亚',7.99),('俄勒冈',8.33),('全国',9.03),('弗吉尼亚',10.08),('俄亥俄',10.32)]
for i,(name,v) in enumerate(vals):
    y=112+i*55;b+=text(24,y+24,name,22)+f'<rect x="150" y="{y}" width="{v/12*388:.3f}" height="29" rx="4" fill="{CYAN if name != "全国" else GOLD}"/>'+text(156+v/12*388,y+23,f'{v:.2f}',21)
b+=line(150,515,538,515,'#8899aa')
for v in [0,4,8,12]:b+=text(150+v/12*388,547,str(v),17)
b+=text(24,594,'从地区筛选，走到园区合同',25,BLUE,700)
for i,ls in enumerate([['哪天送电','分期多少容量'],['怎样计费','需量与最低付款'],['什么服务','可靠或可中断']]):
    x=24+i*201;b+=box(x,619,190,121)+lines(x+13,656,ls,23)
b+=lines(24,785,['初步估计；州工业客户均价不是数据中心报价。','蓝＝州；金＝全国参考；柱长从零起算。','来源：EIA 2026-09-24月报表5.6.B。','选址条件为作者整理。'],16,step=26)
save('fig6-location',898,b)

# Cover master: 2400×3600 output from a matching 800×1200 viewBox.
b=text(44,64,'格洛可  GE LUO KE',23,'#E0B45C',700)+text(604,64,'2026.10.09',18,'#b7cedf')
b+=lines(44,135,['美国数据中心','的电力现状'],55,'white',step=70)
b+=text(44,282,'缺口在哪里，谁来补，谁付钱',30,'#E0B45C',700)
b+=text(44,326,'需求 → 地区瓶颈 → 项目 → 合同 → 电源 → 布局',20,'#bdd9ee')
b+=box(44,361,712,269,'#132d48','#318ca1')
# Explicit circuit schematic, not a geographical map or literal site wiring.
for x,title,desc in [(73,'电源','电量 / 可靠容量'),(319,'电网','输电 / 接入服务'),(565,'园区','总负荷 / IT')]:
    b+=box(x,408,161,133,'#183d5b','#4dbbd1')+text(x+18,445,title,27,'white',700)+text(x+12,482,desc,17,'#cde5f4')
    if x<500:b+=line(x+164,465,x+240,465,'#E0B45C')
b+=text(70,584,'工程示意｜资源、网络和负荷必须在同一时间表兑现',21,'#cde5f4')
cards=[('01  底图与需求','三大互联与用电增长'),('02  地区瓶颈','缺口落实到接入点'),('03  项目真实性','申请与投运分开看'),('04  谁来付钱','长期义务与最低付款'),('05  供电路线','核电、燃气、风光储'),('06  布局变化','电价之外看交付')]
for i,(title,sub) in enumerate(cards):
    x=44+(i%3)*244;y=661+(i//3)*126;b+=box(x,y,224,105,'#132d48','#318ca1')+text(x+13,y+34,title,25,'#E0B45C',700)+text(x+13,y+75,sub,18,'white')
b+=box(44,936,712,116,'#173c52','#318ca1')+text(65,976,'真正稀缺的，是能按期交付的可靠电力',29,'white',700)+text(65,1018,'年度能源 · 峰值容量 · 地方接入 · 成本责任',23,'#bdd9ee')
b+=text(44,1101,'研究截至2026年10月9日｜六章专题与溯源材料',20,'#bdd9ee')+text(44,1150,'格洛可  ·  算力基础设施研究',23,'#E0B45C',700)
save('cover-master',1200,b,w=800,bg=BLUE)
