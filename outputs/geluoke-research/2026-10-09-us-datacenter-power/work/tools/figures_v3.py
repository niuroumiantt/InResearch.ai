"""Question-led geography, charts and engineering annotations for article revision 3."""
from pathlib import Path
from html import escape
import math,json,base64,hashlib,shutil
from shapely.geometry import shape,Polygon
from shapely.ops import unary_union
OUT=Path(__file__).resolve().parents[2];A=OUT/'assets'
RAW=Path('/Users/m5/.local/share/inresearch.ai/geluoke-research/2026-10-09-us-datacenter-power/raw/visual-v3')
BLUE='#07517c';INK='#18364a';MUTE='#547083';GOLD='#b77916';GREEN='#0d8074';WHITE='#ffffff'
FONT='Arial,PingFang SC,Microsoft YaHei,sans-serif'
W=640
records=[]
def t(x,y,s,size=25,color=INK,weight=400,anchor='start'):
 return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(s))}</text>'
def ls(x,y,ss,size=24,color=INK,step=34,weight=400):return ''.join(t(x,y+i*step,s,size,color,weight) for i,s in enumerate(ss))
def rect(x,y,w,h,fill='#f0f5f8',stroke='none',radius=10):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'
def ln(x,y,xx,yy,color=BLUE,width=2,dash=False,arrow=False):return f'<path d="M{x},{y} L{xx},{yy}" stroke="{color}" stroke-width="{width}" fill="none"'+(' stroke-dasharray="6 5"' if dash else '')+(' marker-end="url(#arr)"' if arrow else '')+'/>'
def dot(x,y,label,color=BLUE):return f'<circle cx="{x}" cy="{y}" r="15" fill="{color}"/>'+t(x,y+6,label,19,'white',700,'middle')
def head(title,sub):return t(22,42,title,31,BLUE,700)+t(22,82,sub,23,MUTE)
def footer(y,source):return t(22,y,source,16,MUTE)
def save(n,name,h,b,question,sources,kind):
 filename=f'v3-{n:02}-{name}'
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{h}" viewBox="0 0 640 {h}"><defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="{BLUE}"/></marker></defs><rect width="640" height="{h}" fill="white"/><g font-family="{FONT}">{b}</g></svg>'
 (A/(filename+'.svg')).write_text(svg)
 records.append({'number':n,'asset':'assets/'+filename+('.jpg' if kind=='engineering' else '.png'),'editable':'assets/'+filename+'.svg','question':question,'source_ids':sources,'kind':kind,'design_width':640,'design_height':h,'annotation_layer':'editable SVG; important meaning in main image, not caption','review_status':'pending'})
 return filename
# Census polygons are geographical data; interconnection split is an explicitly
# approximate regional overview checked against EIA/ERCOT maps, not utility GIS.
raw=json.loads((RAW/'census-state-polygons.geojson').read_text());states={f['properties']['STUSAB']:shape(f['geometry']).simplify(.025,preserve_topology=True) for f in raw['features'] if f['properties']['STUSAB'] not in ['AK','HI','PR','GU','VI','AS','MP']}
assert len(states)==49 and 'DC' in states
us=unary_union(list(states.values()))
phi1=math.radians(29.5);phi2=math.radians(45.5);n=(math.sin(phi1)+math.sin(phi2))/2;C=math.cos(phi1)**2+2*n*math.sin(phi1);rho0=math.sqrt(C-2*n*math.sin(math.radians(37.5)))/n
def project(lon,lat):
 rho=math.sqrt(C-2*n*math.sin(math.radians(lat)))/n;theta=n*math.radians(lon+96)
 return rho*math.sin(theta),rho0-rho*math.cos(theta)
coords=[project(x,y) for g in states.values() for poly in ([g] if g.geom_type=='Polygon' else g.geoms) for x,y in poly.exterior.coords]
minx=min(x for x,y in coords);maxx=max(x for x,y in coords);miny=min(y for x,y in coords);maxy=max(y for x,y in coords)
scale=588/(maxx-minx);mapheight=(maxy-miny)*scale
MAPTOP=150
def xy(lon,lat,top=MAPTOP):
 x,y=project(lon,lat);return 26+(x-minx)*scale,top+(maxy-y)*scale
def pathgeom(g,top=MAPTOP):
 if g.is_empty:return ''
 parts=[]
 for poly in ([g] if g.geom_type=='Polygon' else g.geoms):
  if poly.geom_type!='Polygon':continue
  for ring in [poly.exterior,*poly.interiors]:
   pts=[xy(x,y,top) for x,y in ring.coords];parts.append('M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in pts)+' Z')
 return ' '.join(parts)
def geo(g,color,stroke='white',sw=.8,top=MAPTOP):return f'<path d="{pathgeom(g,top)}" fill="{color}" stroke="{stroke}" stroke-width="{sw}" fill-rule="evenodd"/>'
def statemap(selected=None,top=MAPTOP):return ''.join(geo(g,(selected or {}).get(k,'#e8eef1'),'white',.8,top) for k,g in states.items())
westline=[(-109.3,49),(-109.3,47.7),(-106.8,47.7),(-104.8,46.2),(-106.0,45.6),(-105.7,45),(-104,45),(-104,44),(-103.3,43),(-103.8,41),(-102,41),(-102,37),(-103.2,37),(-103.2,34),(-106.4,31.9),(-105.7,30.8)]
westmask=Polygon([(-180,0),(-180,90),(-109.3,90),*westline,(-105.7,0)])
west=us.intersection(westmask)
# Broad ERCOT footprint excludes the top Panhandle, eastern edge and El Paso.
ercotmask=Polygon([(-103.05,34.4),(-103.05,35.6),(-100.4,35.6),(-100.0,34.6),(-99.0,34.6),(-94.8,33.6),(-94.8,32.2),(-95.2,31.8),(-95.2,30.4),(-94.8,29.5),(-96.0,27.8),(-97.0,25),(-101,25),(-105.2,29.5),(-105.7,30.8),(-106.4,31.9),(-103.6,31.8),(-103.6,33.4)])
ercot=states['TX'].intersection(ercotmask).difference(west)
east=us.difference(west.union(ercot))
# 1. The physical map the opening text actually promises.
b=head('美国本土：三大异步互联','每个区域内部同步；跨区域交换能力有限')
b+=t(26,125,'向北连接加拿大部分电网（东部、西部）',23,MUTE)
b+=geo(west,'#a3c8e7')+geo(east,'#b6dcd3')+geo(ercot,'#f0c878')
b+=''.join(f'<path d="{pathgeom(g)}" fill="none" stroke="white" stroke-width=".75"/>' for g in states.values())
x,y=xy(-115,40);b+=t(x,y,'西部互联',28,BLUE,700,'middle')
x,y=xy(-88,40);b+=t(x,y,'东部互联',28,GREEN,700,'middle')
x,y=xy(-99.8,31.1);b+=t(x,y,'得州互联',22,GOLD,700,'middle')
x,y=xy(-99.4,29.5);b+=t(x,y,'ERCOT',23,GOLD,700,'middle')
# Interface arrows indicate relationships, never exact tie station locations.
x,y=xy(-103,40);b+=ln(x-25,y,x+25,y,BLUE,3,True,True)+ln(x+25,y+8,x-25,y+8,BLUE,3,True,True)
x,y=xy(-95.1,32.6);b+=ln(x-14,y+8,x+14,y-8,BLUE,3,True,True)
base=MAPTOP+mapheight+28
b+=ls(22,base,['虚线箭头：有限直流联络，位置仅示意','得州并非全属ERCOT：西端、北部和东部','还有其他互联覆盖；本图只画本土48州。'],23,INK,33)
b+=rect(22,base+87,596,71,'#f3f6f8')+ls(36,base+116,['细线为州界；互联分界按官方图概览绘制。','不能用这张概览图确定具体园区的接入点。'],22,MUTE,30)
b+=footer(base+188,'依据：EIA电力输送说明、ERCOT互联图；州形状：US Census')
save(1,'interconnections-map',math.ceil(base+212),b,'美国本土的三大互联分别在哪里，有哪些跨系统边界？',['eia-grid','v3-ercot-map','v3-census'], 'map')
# 2. Explain roles, without confusing the physical map with institutions.
b=head('三大互联之下，谁管哪件事','数据中心接电，要找对三个不同层次')
rows=[(125,'物理互联','东部 / 西部 / ERCOT',['规定电力能在什么网络中流动','跨系统交换受联络设备限制'],BLUE),(310,'区域调度与市场','七家RTO/ISO',['PJM、MISO、SPP、CAISO','NYISO、ISO-NE、ERCOT'],GREEN),(505,'客户供电合同','电力公司 ↔ 数据中心',['接入点、扩建工程、交付日期','最低付款、服务等级、信用担保'],GOLD)]
for y,title,sub,ss,c in rows:
 b+=rect(22,y,596,158,'#f1f6f8')+rect(22,y,8,158,c,radius=0)+t(43,y+37,title,28,c,700)+t(43,y+74,sub,25,INK,700)+ls(43,y+110,ss,23,INK,31)
 if y<505:b+=ln(320,y+164,320,y+178,BLUE,2,False,True)
b+=ls(22,710,['RTO/ISO负责调度或市场，不是七家包办','发电、输电、配电、零售的垄断电力公司。'],24)
b+=footer(797,'来源：EIA；FERC RTO/ISO介绍与大负荷改革资料')
save(2,'roles',825,b,'物理电网、调度机构和客户合同，分别解决什么？',['eia-grid','ferc-rto'], 'diagram')
# 3. Historical and forecast demand in distinct visual domains.
b=head('需求已经增长，未来仍是一个区间','美国数据中心全年用电量｜TWh')
for y,yr,v,lab in [(140,'2014',58,'历史估算'),(235,'2023',176,'历史估算')]:
 b+=t(22,y+23,yr,26)+rect(150,y,430*v/600,32,'#3e83ba',radius=4)+t(157+430*v/600,y+26,v,26,BLUE,700)+t(150,y+65,lab,23,MUTE)
b+=rect(22,335,596,223,'#fff6e6')+t(40,375,'2028预测：325—580 TWh',29,GOLD,700)
b+=rect(150,408,430*325/600,38,'#d99138',radius=4)+rect(150+430*325/600,408,430*(580-325)/600,38,'#f1d4a5',radius=0)
b+=t(150,483,'325',25,GOLD,700)+t(150+430*580/600,483,'580',25,GOLD,700,'end')+t(40,531,'该预测在2024年提出，不是2026年实测。',23)
b+=ln(150,594,580,594,'#839cae')
for v in [0,200,400,600]:b+=t(150+430*v/600,625,v,21,MUTE,anchor='middle')
b+=ls(22,676,['2023：约占美国总用电量4.4%','2028预测：约占6.7%—12%','年度电量TWh与园区接入功率MW分开看。'],25,INK,37)
b+=footer(813,'来源：LBNL 2024报告，PDF第6—7页；柱长从零起算')
save(3,'demand',840,b,'实际用电增长与未来预测，分别有多大？',['lbnl-full'], 'chart')
# Shared engineering illustration, with actual object callouts.
def embedded(asset,x,y,w,h):
 p=A/asset;uri='data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode();return f'<image href="{uri}" x="{x}" y="{y}" width="{w}" height="{h}"/>'
# 4. Pinpoint the three bottlenecks on the actual equipment path.
b=head('电到园区，要过三道关','增加发电、修线路、扩变电站，解决不同缺口')
b+=embedded('scene-bottleneck.jpg',0,102,640,427)
b+=dot(95,230,'1')+dot(310,195,'2')+dot(245,385,'3')
b+=t(95,156,'发电资源',24,BLUE,700,'middle')+ln(95,165,95,211,BLUE,2)
b+=t(310,141,'输电通道',24,BLUE,700,'middle')+ln(310,150,310,176,BLUE,2)
b+=t(128,483,'变电接入',24,BLUE,700,'middle')+ln(178,468,231,403,BLUE,2)
for y,num,title,desc in [(563,'1','关键时段的发电能力','电厂能否在需要的时段提供可靠出力'),(665,'2','输电通道','有电源，还要能跨线路送到负荷区'),(767,'3','园区接入工程','主变、开关及地方线路需按期完成')]:
 b+=dot(38,y-8,num)+t(66,y,title,27,BLUE,700)+t(66,y+38,desc,23)
b+=t(22,859,'施工中的间隔不能当作已经释放的新增容量。',23,GOLD,700)
b+=footer(909,'机制依据：EIA、JLARC、NERC；通用工程示意，非项目照片')
save(4,'bottlenecks',936,b,'发电、输电、接入三种电不够，卡在哪个实际设施？',['eia-grid','jlarc','nerc'], 'engineering')
# 5. Regional examples on their real geographical locations.
selected={'VA':'#f0c878','TX':'#a3c8e7','OH':'#b6dcd3','GA':'#ddc2df'}
b=head('地区不同，约束和应对办法也不同','色块标所在州，圆点为案例位置索引')+statemap(selected,top=116)
casepts=[('A',-77.5,39.0),('B',-99,31),('C',-82.8,40),('D',-83.5,32)]
for label,lo,la in casepts:
 x,y=xy(lo,la,116);b+=dot(x,y,label)
y=116+mapheight+40
for k,title,ss,c in [('A','北弗吉尼亚',['成熟集群继续吸引需求','扩建发电、输电与接入设施'],GOLD),('B','得州 ERCOT',['大负荷共同批次研究','自供电或可中断服务路径'],BLUE),('C','俄亥俄州',['最低容量付款义务','部分项目获批现场燃料电池'],GREEN),('D','佐治亚州',['大负荷合同与扩建责任','OpenAI提出灵活需求承诺'],'#81598a')]:
 b+=dot(39,y+10,k,c)+t(68,y+18,title,27,c,700)+ls(68,y+55,ss,24,INK,34);y+=135
b+=footer(y+8,'来源：JLARC、ERCOT、Ohio Consumers’ Counsel、AEP、Georgia Power')
save(5,'regional-cases',math.ceil(y+34),b,'北弗吉尼亚、得州、俄亥俄和佐治亚的案例在哪里？',['jlarc','ercot-batch','ohio','aep-onsite','ga-contract','v3-census'], 'map')
# 6. Evidence steps, not generic vacant plots.
b=head('公告容量，怎样走到电表上的负荷','每往前一步，需要不同的可核实证据')
steps=[('接入意向','地点、规模、申请主体','开发意向还可能变化'),('系统研究','接入点、网络影响、扩建范围','说明为接入需要做哪些工程'),('有约束的合同','分期容量、最低付款、担保','看客户愿意承担哪些义务'),('建设与调试','设备到货、施工、验收','工程进展不等同实际负荷'),('送电与运行','首期送电、实际峰值、后续爬坡','最终看电表和持续业务')]
for i,(title,one,two) in enumerate(steps):
 y=128+i*145;b+=dot(40,y+17,i+1)+t(76,y+24,title,28,BLUE,700)+ls(76,y+61,[one,two],24,INK,34)
 if i<4:b+=ln(40,y+37,40,y+119,'#97afbe',2,True)
b+=rect(22,874,596,91,'#fff6e6')+ls(38,908,['申请MW、合同MW、设施MW、IT MW','记录的是不同对象，不能直接相加。'],24,INK,34)
b+=footer(1011,'来源：PJM与ERCOT流程；作者整理，非全国统一法定程序')
save(6,'project-evidence',1038,b,'一项接入申请需要怎样的合同和工程证据才能算真实负荷？',['pjm-forecast','ercot-batch'], 'diagram')
# 7. Two actual institutional timelines / methods.
b=head('电网开始筛选“什么时候真用电”','PJM预测与ERCOT接入研究的两种做法')
b+=rect(22,122,596,320,'#f0f7f4')+t(42,160,'PJM：把确定性写入预测',29,GREEN,700)
b+=ls(42,205,['2026版近期预测','要求较明确的服务义务或建设承诺','远期项目承诺较弱时，提高折减','2032年前预测低于2025版','还包含电动车、经济因素与负荷调整'],24,INK,42)
b+=rect(22,467,596,320,'#f0f5fa')+t(42,505,'ERCOT：多个大项目一起研究',29,BLUE,700)
b+=ls(42,550,['2026年6月公布Batch Zero','符合资格的75MW及以上大负荷','按共同基准研究相互影响和输电需求','首批最终输电计划：预计2027年秋季','研究完成后仍有工程与送电环节'],24,INK,42)
b+=t(22,833,'预测下调≠实际用电下降；研究计划≠已送电。',24,GOLD,700)
b+=footer(880,'来源：PJM 2026负荷报告第6页；ERCOT 2026-06-18公告')
save(7,'planning-rules',908,b,'为什么申请清单与电网负荷预测不应是同一个数？',['pjm-forecast','ercot-batch'], 'timeline')
# 8. Put every crucial fee qualifier directly inside comparison.
b=head('两地都是85%，收的却不是同一笔钱','固定网络/容量付款，与实际电能费分开')
for y,title,c,main,ss in [(125,'弗吉尼亚 Dominion / GS-5',BLUE,'85% 输电与配电成本',['每月最低承担比例，与实际用电量无关','新合同：2027-01-01起，至少14年义务','2016年前已开始服务者有豁免','信用不足新客户：担保最高60%最低费用']),(460,'俄亥俄 AEP Ohio',GREEN,'85% 合同容量相关付款',['新大型数据中心的最低付款义务','期限最长12年','2025-07-09决定；行业在同年11月上诉'])]:
 b+=rect(22,y,596,305,'#f2f6f8')+t(42,y+39,title,27,c,700)+t(42,y+93,main,30,c,700)
 b+=rect(42,y+113,480*.85,20,c,radius=3)+rect(42+480*.85,y+113,480*.15,20,'#dae4e9',radius=0)
 b+=ls(42,y+174,ss,23,INK,33)
b+=ls(22,822,['85%不是“85%的未使用电量”。','条款保护的是为客户预留的网络/容量费用。'],26,GOLD,36,700)
b+=footer(923,'来源：SCC 2026-02-24说明第2页；Ohio Consumers’ Counsel')
save(8,'cost-contracts',950,b,'两地85%的分母、合同期限与生效条件分别是什么？',['scc','ohio'], 'comparison')
# 9. Non-comparable forecasts are explicitly shown as separate panels.
b=head('客户成本会怎样变，要看地区与合同','两种不同情景，不能拼成一个全国结论')
b+=rect(22,125,596,268,'#fff4ec')+t(42,167,'弗吉尼亚 · JLARC情景研究',28,GOLD,700)+t(42,226,'+14—37 美元 / 月',42,GOLD,700)
b+=ls(42,276,['到2040年，典型Dominion居民客户','发电与输电相关月成本增量，不变价','2024年研究估计，并非现时账单涨幅'],24,INK,35)
b+=rect(22,420,596,268,'#eef7f3')+t(42,463,'佐治亚 · Georgia Power公司预测',27,GREEN,700)+t(42,522,'约9.5 亿美元 / 年',42,GREEN,700)
b+=ls(42,572,['预计从2029年起，客户整体节省','大负荷客户组合口径，非单一项目','2026年公司测算，并非已实现收益'],24,INK,35)
b+=ls(22,745,['决定分摊结果的是新增支出、客户收入、','合同履约与剩余风险，不能只看项目大小。'],25)
b+=footer(850,'来源：JLARC 2024报告；Georgia Power 2026-08公告')
save(9,'customer-costs',879,b,'为什么两个地区能分别预测居民成本压力和客户节省？',['jlarc','ga-contract'], 'comparison')
# 10. Nuclear graphic addresses the actual two cases, not just a nuclear landscape.
b=head('买既有核电，与重启机组是两条路线','长期合同、新增发电与园区接入分别判断')
b+=embedded('scene-nuclear-grid.jpg',0,104,640,427)
b+=dot(115,255,'1')+dot(335,300,'2')+dot(524,409,'3')
b+=t(115,159,'电源',24,BLUE,700,'middle')+ln(115,168,115,236,BLUE,2)
b+=t(335,166,'公共电网',24,BLUE,700,'middle')+ln(335,175,335,281,BLUE,2)
b+=t(524,198,'园区接入',24,BLUE,700,'middle')+ln(524,207,524,390,BLUE,2)
b+=t(22,563,'1 电源　→　2 公共网络　→　3 园区接入',25,BLUE,700)
b+=rect(22,593,596,190,'#f0f5fa')+t(42,631,'Talen / Amazon：既有电厂购电',27,BLUE,700)
b+=ls(42,674,['合同全规模1920MW，至2042年','建成电网连接后转表前零售','过渡期部分表后；合同不是新建装机'],24,INK,35)
b+=rect(22,806,596,190,'#eef7f3')+t(42,844,'Crane / Microsoft：停运机组重启',27,GREEN,700)
b+=ls(42,887,['重启原三哩岛一号机组','目标2027年；2026年披露关键批准','批准与目标，不等同机组已经复运'],24,INK,35)
b+=t(22,1039,'上半为电网供电机制示意，不是两项目现场。',23,MUTE)
b+=footer(1085,'来源：Talen 2025-06材料第4页；Constellation公司资料；FERC')
save(10,'nuclear-routes',1114,b,'Talen合同与Crane重启，分别改变合同分配还是发电供给？',['talen-sec','crane-q2','crane-pdf','ferc-colocation'], 'engineering')
# 11. Fuel cell, matching the AEP example; no engine in this illustration.
rawsofc=Path('/Users/m5/.codex/generated_images/01a11dcd-34f5-79f0-837e-2345c274c075/exec-5a565b55-154a-499a-93be-d6091cfc41bd.png')
kept=RAW/'sofc-generated-original.png'
if not kept.exists():shutil.copy2(rawsofc,kept)
from PIL import Image
with Image.open(kept) as im:
 im=im.convert('RGB');im.thumbnail((1280,1280),Image.Resampling.LANCZOS);im.save(A/'v3-sofc-base.jpg',quality=85,optimize=True)
b=head('俄亥俄案例：燃料电池现场发电','天然气经电化学反应发电，再转换后送入机房')
b+=embedded('v3-sofc-base.jpg',0,104,640,427)
b+=dot(142,315,'1')+dot(320,319,'2')+dot(468,349,'3')+dot(570,371,'4')
b+=t(93,176,'燃气预处理',24,BLUE,700,'middle')+ln(124,187,141,296,BLUE,2)
b+=t(319,148,'燃料电池',24,BLUE,700,'middle')+ln(319,160,319,298,BLUE,2)
b+=t(466,193,'电力转换',24,BLUE,700,'middle')+ln(466,204,468,330,BLUE,2)
b+=t(551,487,'园区供配电',24,BLUE,700,'middle')+ln(551,466,570,390,BLUE,2)
for i,(title,desc) in enumerate([('管道来气与预处理','现场电源仍依赖燃料供应条件'),('固体氧化物燃料电池','电化学反应产生直流电，区别于燃烧机组'),('电力转换与调节','将输出转换为设备需要的供电形式'),('园区供配电','向机柜送电；备用与冗余仍需单独设计')]):
 y=566+i*92;b+=dot(38,y-8,i+1)+t(66,y,title,27,BLUE,700)+t(66,y+37,desc,23)
b+=rect(22,947,596,108,'#eef7f3')+ls(40,984,['AEP披露：AWS与Cologix承担全部成本','2025年批准部署，不等于已经投运。'],25,INK,37)
b+=t(22,1100,'设备为通用机制示意，不是具体Bloom型号或现场。',23,MUTE)
b+=footer(1149,'来源：AEP 2025-06-05；DOE Fuel Cell Systems；Bloom技术资料')
save(11,'onsite-sofc',1176,b,'AEP案例采用何种现场发电设备，燃料与电力分别怎样流动？',['aep-onsite','v3-doe-fuelcells','v3-bloom'], 'engineering')
# 12. Author mechanism drawing, no invented measured curve or hours.
b=head('全年绿电匹配，与每小时有电不同','年度能源、时段出力、储能时长分别安排')
b+=t(22,137,'年度采购账',29,GREEN,700)
b+=rect(22,158,282,108,'#e7f3ee')+ls(42,194,['全年采购绿电量','按合同进行年度匹配'],24,INK,35)
b+=t(320,224,'≈',42,GREEN,700,'middle')+rect(336,158,282,108,'#f0f5fa')+ls(354,194,['全年用电量','不告诉你哪一小时缺电'],24,INK,35)
b+=t(22,334,'运行时段账',29,BLUE,700)+t(22,373,'下图是原理示意，不是实测出力曲线。',23,MUTE)
b+=rect(45,415,145,147,'#e9eff6')+rect(190,415,260,147,'#fff4d9')+rect(450,415,145,147,'#e9eff6')
b+=ln(45,530,595,530,'#8aa4b5',2)
b+='<path d="M45,525 Q180,525 200,500 Q320,345 440,500 Q460,525 595,525" fill="none" stroke="#d99138" stroke-width="5"/>'
b+=ln(45,465,595,465,BLUE,4)
b+=t(67,590,'夜间',25,BLUE,700)+t(298,590,'白天',25,GOLD,700)+t(490,590,'夜间',25,BLUE,700)
b+=ls(22,645,['蓝线：持续用电需求；橙线：太阳能出力示意','低出力时段要由其他电源、电网或储能补齐','储能MW看功率，MWh看能量，两者缺一不可'],24,INK,39)
b+=footer(820,'机制依据：IEA 2026报告、NERC；未给出特定项目实测值')
save(12,'annual-hourly',848,b,'为什么年度可再生能源采购不能独自保证全天可靠运行？',['iea','nerc'], 'diagram')
# 13. Real geographic state prices, all qualifiers in main image.
prices={'TX':('得州',6.72),'VA':('弗吉尼亚',10.08),'AZ':('亚利桑那',7.66),'GA':('佐治亚',7.99),'OH':('俄亥俄',10.32),'OR':('俄勒冈',8.33)}
b=head('州工业均价：便宜电在哪些位置','2026年1—7月｜美分/kWh｜EIA初步统计')
b+=statemap({k:'#aacfe6' for k in prices},top=126)
for k in prices:
 center=states[k].representative_point();x,y=xy(center.x,center.y,126);b+=dot(x,y,k)
 # Chinese names sit on the map; abbreviations alone assume US-state knowledge.
 offsets={'OR':(24,5,'start'),'AZ':(-8,41,'middle'),'TX':(28,5,'start'),'GA':(26,31,'start'),'OH':(-22,-30,'end'),'VA':(-7,52,'middle')}
 dx,dy,anchor=offsets[k];b+=t(x+dx,y+dy,prices[k][0],22,BLUE,700,anchor)
 if abs(dy)>20:b+=ln(x,y+(16 if dy>0 else -16),x+dx,y+dy-(8 if dy>0 else -5),BLUE,1.4)
y=126+mapheight+40
for i,(k,(name,v)) in enumerate(sorted(prices.items(),key=lambda kv:kv[1][1])):
 yy=y+i*66;b+=t(22,yy,name,26,BLUE,700)+rect(178,yy-25,345*v/12,29,'#3987b7',radius=3)+t(192+345*v/12,yy,v,26,BLUE,700)
b+=t(22,y+424,'全国参考：9.03 美分/kWh',27,GOLD,700)
b+=ls(22,y+481,['这是州工业客户平均值，不是园区合同报价。','下一步要查服务区、接入时间和实际费率。'],25,INK,38)
b+=footer(y+583,'来源：EIA 2026-09-24月报表5.6.B；州形状：US Census')
save(13,'state-prices-map',math.ceil(y+613),b,'文中比较的州在哪里，工业均价与具体合同电价如何区分？',['eia-ytd','v3-census'], 'map')
# 14. Flexible work example with commitment plainly labelled.
b=head('有些计算可以等一等，实时业务要继续','负荷灵活性，需要工作负载和合同一起落实')
b+=t(22,140,'系统紧张时段',27,BLUE,700)+rect(22,163,596,133,'#f0f5fa')
b+=t(42,209,'实时服务',27,BLUE,700)+t(42,258,'保留必要供电与运行能力',25)
b+=rect(22,323,260,127,'#fff5e3')+ls(42,365,['可延后的计算任务','安排到其他时段'],24,INK,36)
b+=ln(286,384,332,384,BLUE,3,False,True)+rect(344,323,274,127,'#eaf5ef')+ls(364,365,['高峰之后','再执行部分任务'],24,INK,36)
b+=ls(22,508,['Google公布的合作：I&M、TVA','调整部分机器学习工作负载参与需求响应','能下调多久、通知多久、怎样恢复，','都要在调度与运行中落实。'],25,INK,39)
b+=rect(22,704,596,188,'#edf7f3')+t(42,747,'Georgia Power / OpenAI合同',27,GREEN,700)
b+=ls(42,791,['3200MW新增需求安排','最高1000MW灵活需求响应承诺','合同与承诺，不是实测运行曲线'],25,INK,37)
b+=footer(942,'来源：Google 2025-08-04；Georgia Power 2026-08-26')
save(14,'flexible-load',970,b,'数据中心怎样把部分工作调整到其他时段，哪些只是合同承诺？',['google-flex','ga-contract'], 'diagram')
# Preserve portable, derived drawing paths, not original downloaded files in Git.
(OUT/'work/v3/map-geography.json').write_text(json.dumps({'source':'US Census ACS2025 generalized states 20M','scope':'48 continental states and DC','projection':'Albers: parallels29.5,45.5; lon0=-96; lat0=37.5','geometry_source':'v3-census','interconnection_boundaries':'概览示意，人工按EIA/ERCOT图核对；非运营商接入GIS','states':{k:pathgeom(v) for k,v in states.items()},'region_paths':{'western':pathgeom(west),'eastern':pathgeom(east),'ercot':pathgeom(ercot)}},ensure_ascii=False,indent=2)+'\n')
(OUT/'work/v3/figure-plan.json').write_text(json.dumps({'revision':3,'principle':'图回答紧邻正文的具体问题；先信息功能，再选择画法；关键限定直接标注','body_images':len(records),'figures':records},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'figures':len(records),'state_shapes':len(states),'mapheight':round(mapheight)},ensure_ascii=False))
