from pathlib import Path
import base64,json,hashlib,html
w=Path(__file__).resolve().parents[4];o=Path(__import__('os').environ.get('TA22_ASSET_DIR','/private/tmp/ta22-offline-assets'));o.mkdir(parents=True,exist_ok=True)
items=[
 {'id':'hv-switchyard','file':'system/hv-switchyard-v2.png','x':54,'y':210,'w':210,'h':210,'crop':[140,160,1250,700],'anchor':[580,300],'title':'接入开关功能','notes':['GIS外形示例','不证明接网权利']},
 {'id':'transformer','file':'system/transformer-v2.png','x':290,'y':200,'w':210,'h':230,'crop':[225,20,1100,940],'anchor':[820,230],'title':'变压与输入分配','notes':['开关与保护按方案','其它负载另路，未展开']},
 {'id':'ups','file':'system/ups-v2.png','x':530,'y':200,'w':210,'h':230,'crop':[350,15,800,960],'anchor':[660,160],'title':'UPS调理与过渡供能','notes':['本例选双变换功能','下方解释同一系统']},
 {'id':'pdu','file':'system/pdu-v2.png','x':775,'y':200,'w':210,'h':230,'crop':[275,10,1000,970],'anchor':[650,280],'title':'机房/行与机柜分配','notes':['左柜：房间/行分配','右条：机柜rPDU']},
 {'id':'psu','file':'psu-v1.png','x':1010,'y':220,'w':220,'h':200,'crop':[0,0,1536,1024],'anchor':[1120,400],'title':'服务器PSU','notes':['AC-DC供能功能','输出进入板上DC分配']},
 {'id':'vrm','file':'system/vrm-v2.png','x':1260,'y':215,'w':220,'h':205,'crop':[60,100,1410,850],'anchor':[820,400],'title':'板级稳压与负载','notes':['VRM由DC供电','中间转换可按需设置']}
]
# These are pre-adopted category illustrations. Original PNG bytes are embedded unchanged.
imgs=[];components=[]
for d in items+[{'id':'power-shelf','file':'system/power-shelf-v2.png','x':1020,'y':590,'w':430,'h':170,'crop':[15,150,1505,700],'anchor':[700,500],'title':'','notes':[]}]:
 p=w/'web/assets/technical-atlas'/d['file'];raw=p.read_bytes();d['sha256']=hashlib.sha256(raw).hexdigest();d['bytes']=len(raw)
 cx,cy,cw,ch=d['crop'];scale=min(d['w']/cw,d['h']/ch);tx=d['x']+(d['w']-cw*scale)/2-cx*scale;ty=d['y']+(d['h']-ch*scale)/2-cy*scale
 d['affine']={'scale':scale,'translate':[tx,ty]};d['display_anchor']=[d['anchor'][0]*scale+tx,d['anchor'][1]*scale+ty]
 imgs.append(f'<svg data-component="{d["id"]}" x="{d["x"]}" y="{d["y"]}" width="{d["w"]}" height="{d["h"]}" viewBox="{cx} {cy} {cw} {ch}" preserveAspectRatio="xMidYMid meet"><image href="data:image/png;base64,{base64.b64encode(raw).decode()}" width="1536" height="1024"/></svg>')
 components.append(d)
# Functional paths are in intentionally separate whitespace, never presented as verified equipment port wiring.
paths=[]
for i,(x1,x2) in enumerate([(170,360),(410,600),(650,845),(890,1090),(1140,1350)]):paths.append(f'<path data-flow="main-{i+1}" d="M{x1},510 L{x2},510" marker-end="url(#arrow)"/>')
# UPS inset main conversion chain, conditional battery and bypass are visually distinct paths.
paths+=['<path data-flow="UPS-normal-1" d="M84,691 L135,691" marker-end="url(#arrow)"/>','<path data-flow="UPS-normal-2" d="M240,691 L350,691" marker-end="url(#arrow)"/>','<path data-flow="UPS-normal-3" d="M455,691 L545,691" marker-end="url(#arrow)"/>']
conditional=['<path data-flow="UPS-bypass" d="M90,691 L90,610 L520,610 L520,691" marker-end="url(#conditional-arrow)"/>','<path data-flow="UPS-battery" d="M296,771 L296,691" marker-end="url(#conditional-arrow)"/>']
shapes='<circle cx="90" cy="691" r="3" fill="#09689B"/><circle cx="296" cy="691" r="3" fill="#09689B"/><circle cx="520" cy="691" r="3" fill="#09689B"/><rect x="135" y="662" width="105" height="58"/><rect x="350" y="662" width="105" height="58"/><rect x="232" y="771" width="128" height="48"/>'
head='<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024" viewBox="0 0 1536 1024"><defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8Z" fill="#09689B"/></marker><marker id="conditional-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8Z" fill="#777A72"/></marker></defs><rect width="1536" height="1024" fill="#FAF9F2"/>'
base=head+''.join(imgs)+'</svg>'
(o/'power-base.svg').write_text(base)
text=[]
def txt(x,y,s,size=17,weight=400,color='#454641',anchor=None):
 a=f' text-anchor="{anchor}"' if anchor else '';text.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}"{a}>{html.escape(s)}</text>')
navy='#193B4E';blue='#09689B'
txt(54,59,'电力链路 · 从交流分配到板级稳压',33,700,navy)
txt(54,94,'选定功能示例 A：服务器独立PSU；外形图不认证内部电路或现场接线',20)
txt(54,123,'通用示意 · 非OEM/CAD/单线施工图；设备不共比例，电压/功率、冗余、保护、接地与现场适用未核实',15)
for i,d in enumerate(items):
 x=d['x'];num=f'{i+1:02d}';cx=x+13;cy=169;ax,ay=d['display_anchor'];
 text.append(f'<g class="callout" data-label="{num}" data-object="{d["id"]}"><path d="M{cx},{cy+15} L{ax:.4f},{ay:.4f}" fill="none" stroke="{blue}" stroke-width="1.8"/><circle cx="{ax:.4f}" cy="{ay:.4f}" r="3" fill="{blue}"/><circle cx="{cx}" cy="{cy}" r="14" fill="#FAF9F2" stroke="{blue}"/></g>')
 txt(cx,cy+5,num,14,400,blue,'middle');txt(x+34,175,d['title'],17,600,navy)
 txt(x,451,d['notes'][0],16);txt(x,476,d['notes'][1],15)
for x,s in [(190,'AC功能供能'),(440,'AC'),(680,'AC'),(925,'AC'),(1170,'DC')]:txt(x,540,s,15,400,blue)
txt(54,578,'UPS功能解释 · 与上方03为同一系统',20,600,navy)
txt(54,603,'实线：正常转换；虚线：条件供能/旁路，非同时工况',15)
txt(98,653,'AC输入',15);txt(187,698,'整流',17,500,'#454641','middle');txt(403,698,'逆变',17,500,'#454641','middle');txt(482,716,'AC输出',15)
txt(260,678,'DC节点',15);txt(175,641,'静态旁路：绕过转换链，未调理AC',15)
txt(296,800,'UPS电池',16,500,'#454641','middle');txt(375,783,'储能支路 → DC节点',15);txt(54,845,'电池只画供能支路；充电管理/切换/隔离操作未展开。',15)
txt(650,578,'另一种末端方案 B · 共享电源架',20,600,navy)
txt(650,617,'共享AC-DC电源架 → DC分配',18,500)
txt(650,650,'→ 按需中间变换 → 板级稳压/负载',17)
txt(650,689,'BBU：该共享DC方案的备份功能',17)
txt(650,718,'UPS是否保留、BBU接入与控制须按设计。',15)
txt(650,749,'替代A的末端，不再串另一套服务器AC-DC PSU。',15)
txt(1025,789,'选定通用六模块外形 · 非数量/电压/冗余规格',15)
txt(650,821,'图示没有把B方案硬连入A的主路；中间变换是功能说明。',15)
text.append('<path d="M54,871 L1482,871" stroke="#D5D7CE" stroke-width="1"/>')
txt(54,908,'备用发电与燃料',19,600,navy);txt(54,937,'柴油储运仅是燃料支路；备用发电接入/切换另核。',15);txt(54,964,'燃机、燃气机、燃料电池、SMR为其它候选，非全串/并联。',15)
txt(650,908,'储能与分配类别各有角色',19,600,navy);txt(650,937,'BESS ≠ UPS电池 ≠ BBU；接入、转换、控制与时长未核。',15);txt(650,964,'中/低压柜、母线槽、PDU按方案选；分类排序不是电路。',15)
txt(54,1001,'功能依据：Eaton UPS Basics / Vertiv Power Train / TI SSZTDB4；原生设备图为已有独立类别示意，非同一园区配置。',14)
label=head+'<image href="__TA22_NATIVE_PNG__" width="1536" height="1024"/>'+'<g fill="none" stroke="#09689B" stroke-width="2.2">'+''.join(paths)+'</g><g fill="none" stroke="#777A72" stroke-width="1.8" stroke-dasharray="6 5">'+''.join(conditional)+'</g><g fill="#FAF9F2" stroke="#777A72" stroke-width="1.1">'+shapes+'</g><g id="editable-labels" font-family="Inter, Noto Sans SC, sans-serif">'+''.join(text)+'</g></svg>'
(o/'power-full.svg').write_text(label)
(o/'component-manifest.json').write_text(json.dumps({'figure_id':'TA-22','method':'controlled SVG composition of byte-exact adopted original PNGs; independent editable text/function layers','components':components,'originals_modified':False,'public_or_local_product_access':False},ensure_ascii=False,indent=2)+'\n')
print(o)
