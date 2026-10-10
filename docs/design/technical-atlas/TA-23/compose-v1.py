from pathlib import Path
import base64,json,hashlib,html
w=Path(__file__).resolve().parents[4];o=Path(__import__('os').environ.get('TA23_ASSET_DIR','/private/tmp/ta23-offline-assets'));o.mkdir(parents=True,exist_ok=True)
items=[
 {'id':'coldplate','file':'coldplate-v1.png','x':54,'y':208,'w':370,'h':247,'crop':[0,0,1536,1024],'anchor':[500,450],'title':'冷板与虚拟剖口','number':'01','label_x':54,'notes':['虚拟剖口展示液路；接触面在下方','右下为同类快接配合端重复放大']},
 {'id':'manifold','file':'system/manifold-v2.png','x':445,'y':195,'w':180,'h':260,'crop':[560,5,415,1000],'anchor':[785,430],'title':'机柜分配歧管','number':'03','label_x':445,'notes':['单根八支路外形示例','供回成对功能见下图']},
 {'id':'cdu','file':'system/cdu-v2.png','x':665,'y':195,'w':225,'h':260,'crop':[385,35,755,910],'anchor':[650,450],'title':'液—液CDU','number':'04','label_x':665,'notes':['封闭柜外形，不补内部剖面','端口供回分工未认证']},
 {'id':'chilled-water-loop','file':'system/chilled-water-loop-v2.png','x':925,'y':215,'w':235,'h':235,'crop':[50,60,1460,905],'anchor':[760,290],'title':'设施供回管路','number':'05','label_x':925,'notes':['两段封闭管外形示例','供回分配由功能图说明']},
 {'id':'chiller','file':'system/chiller-v2.png','x':1190,'y':213,'w':290,'h':240,'crop':[75,40,1420,940],'anchor':[800,220],'title':'室外风冷冷水机','number':'06','label_x':1190,'notes':['本例选定冷源，向空气排热','制冷剂与泵阀内部不补造']}
]
imgs=[]
for d in items:
 raw=(w/'web/assets/technical-atlas'/d['file']).read_bytes();d['sha256']=hashlib.sha256(raw).hexdigest();d['bytes']=len(raw)
 cx,cy,cw,ch=d['crop'];scale=min(d['w']/cw,d['h']/ch);tx=d['x']+(d['w']-cw*scale)/2-cx*scale;ty=d['y']+(d['h']-ch*scale)/2-cy*scale
 d['affine']={'scale':scale,'translate':[tx,ty]};d['display_anchor']=[d['anchor'][0]*scale+tx,d['anchor'][1]*scale+ty]
 imgs.append(f'<svg data-component="{d["id"]}" x="{d["x"]}" y="{d["y"]}" width="{d["w"]}" height="{d["h"]}" viewBox="{cx} {cy} {cw} {ch}" preserveAspectRatio="xMidYMid meet"><image href="data:image/png;base64,{base64.b64encode(raw).decode()}" width="1536" height="1024"/></svg>')
head='<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024" viewBox="0 0 1536 1024"><defs>'
for n,c in [('TCS','#09689B'),('FWS','#087B78'),('heat','#AF613A')]:head+=f'<marker id="{n}-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8Z" fill="{c}"/></marker>'
head+='</defs><rect width="1536" height="1024" fill="#FAF9F2"/>'
(o/'thermal-base.svg').write_text(head+''.join(imgs)+'</svg>')
text=[];callouts=[]
def txt(x,y,s,size=17,weight=400,color='#454641',anchor=None):
 a=f' text-anchor="{anchor}"' if anchor else '';text.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}"{a}>{html.escape(s)}</text>')
def leader(n,ob,cx,cy,ax,ay):
 callouts.append(f'<g class="callout" data-label="{n}" data-object="{ob}"><path d="M{cx},{cy+15} L{ax:.4f},{ay:.4f}" fill="none" stroke="#09689B" stroke-width="1.6"/><circle cx="{ax:.4f}" cy="{ay:.4f}" r="3" fill="#09689B"/><circle cx="{cx}" cy="{cy}" r="14" fill="#FAF9F2" stroke="#09689B"/></g>');txt(cx,cy+5,n,14,400,'#09689B','middle')
txt(54,59,'冷却链路 · 两个流体域，只跨换热器传热',33,700,'#193B4E')
txt(54,94,'选定功能示例：冷板液冷 + 液—液CDU + 风冷冷水机；非所有数据中心通用方案',20)
txt(54,123,'通用示意 · 非OEM/CAD/施工管线图；设备不共比例，温压/流量/液体/材料/冗余及现场安装未核实',15)
for d in items:
 cx=d['label_x']+13;leader(d['number'],d['id'],cx,169,*d['display_anchor']);txt(cx+22,175,d['title'],17,600,'#193B4E')
 txt(d['x'],480,d['notes'][0],15);txt(d['x'],503,d['notes'][1],15)
qd=items[0];ax=1320*qd['affine']['scale']+qd['affine']['translate'][0];ay=880*qd['affine']['scale']+qd['affine']['translate'][1]
leader('02','quick-disconnect',298,169,ax,ay);txt(321,175,'快接放大',17,600,'#193B4E')
txt(54,550,'TCS · IT侧冷却液',20,600,'#09689B');txt(900,550,'FWS · 设施侧流体',20,600,'#087B78')
txt(54,578,'下方为独立功能图；方框/圆点不认证上方照片内部或端口。',15)
shapes='<g fill="#FAF9F2" stroke="#ADB4AA" stroke-width="1.2"><rect data-functional-node="coldplate" x="110" y="610" width="190" height="110" rx="3"/><rect data-functional-node="CDU-HX" x="700" y="595" width="140" height="160" rx="3"/><rect data-functional-node="outdoor-cold-source" x="1240" y="610" width="170" height="110" rx="3"/></g><path data-separator="fluid-wall" d="M770,603 L770,747" fill="none" stroke="#777A72" stroke-width="2"/>'
flows=[
 ('TCS','return','M300,625 L700,625'),('TCS','HX','M700,625 L750,625 L750,705 L700,705'),('TCS','supply','M700,705 L300,705'),('TCS','load','M300,705 L155,705 L155,625 L300,625'),
 ('FWS','return','M840,625 L1240,625'),('FWS','source','M1240,625 L1385,625 L1385,705 L1240,705'),('FWS','supply','M1240,705 L840,705'),('FWS','HX','M840,705 L790,705 L790,625 L840,625')]
functional=''
for domain,n,d in flows:
 color='#09689B' if domain=='TCS' else '#087B78';functional+=f'<path data-flow="{domain}-{n}" data-fluid-domain="{domain}" d="{d}" fill="none" stroke="{color}" stroke-width="2.5" marker-end="url(#{domain}-arrow)"/>'
for domain,xx in [('TCS',[365,470]),('FWS',[1010])]:
 for x in xx:
  for y in [625,705]:functional+=f'<circle data-fluid-node="{domain}" cx="{x}" cy="{y}" r="3.5" fill="'+('#09689B' if domain=='TCS' else '#087B78')+'"/>'
functional+='<path data-heat="chip-to-coldplate" d="M132,783 L132,720" fill="none" stroke="#AF613A" stroke-width="2.5" marker-end="url(#heat-arrow)"/><path data-heat="TCS-to-FWS" d="M755,665 L785,665" fill="none" stroke="#AF613A" stroke-width="2.5" marker-end="url(#heat-arrow)"/><path data-heat="to-outdoor-air" d="M1410,665 L1480,665" fill="none" stroke="#AF613A" stroke-width="2.5" marker-end="url(#heat-arrow)"/>'
txt(180,665,'冷板吸热',18,500,'#193B4E');txt(315,608,'回液 → CDU',16,400,'#09689B');txt(315,738,'供液 → 冷板',16,400,'#09689B');txt(340,665,'QD',15);txt(445,665,'供回歧管',15)
txt(700,580,'CDU换热功能',17,600,'#193B4E');txt(680,784,'只传热，不混液',18,600,'#AF613A');txt(915,608,'设施回流 → 冷源',16,400,'#087B78');txt(915,738,'设施供流 → CDU',16,400,'#087B78');txt(1268,665,'冷源功能',18,500,'#193B4E')
txt(158,781,'芯片热量 → 冷板',16,400,'#AF613A');txt(1230,781,'→ 室外空气排热',16,400,'#AF613A')
txt(54,820,'TCS循环为CDU功能；照片未展开内部泵阀。',15);txt(900,820,'设施侧循环动力/阀件按方案，未展开。',15)
txt(54,853,'蓝/绿线及箭头：各自液体循环；棕色箭头：热量传递；细蓝引线：设备定位，不是管道。',15)
text.append('<path d="M54,875 L1482,875" stroke="#D5D7CE"/>')
txt(54,908,'其它方案 · 独立入口',19,600,'#193B4E');txt(54,937,'干冷器、液—气CDU、浸没、后门换热器不全串入本例。',15)
txt(54,965,'风冷冷机内部制冷剂未展开；不增加冷却塔/冷凝水回路。',15)
txt(825,908,'配套与残余热',19,600,'#193B4E');txt(825,937,'水处理/冷却液/泄漏检测按系统核；空气冷却占比未知。',15)
txt(825,965,'不是TA18八柜实际接管；不承诺100%热量进入液体。',15)
txt(54,1001,'功能依据：ASHRAE TC9.9 Water-Cooled Servers / Vertiv CDU说明；五幅外形原图保持，微通道与快接局部沿用TA10同类示例。',14)
full=head+'<image href="__TA23_NATIVE_PNG__" width="1536" height="1024"/>'+shapes+functional+''.join(callouts)+'<g id="editable-labels" font-family="Inter, Noto Sans SC, sans-serif">'+''.join(text)+'</g></svg>'
(o/'thermal-full.svg').write_text(full)
(o/'component-manifest.json').write_text(json.dumps({'figure_id':'TA-23','method':'controlled original-byte adopted5photo composition with independent editable vector functions and locators','components':items,'quick_disconnect_repeat_anchor':{'source_anchor':[1320,880],'display_anchor':[ax,ay],'affine':qd['affine'],'source_component':'coldplate'},'originals_modified':False,'public_or_local_product_access':False},ensure_ascii=False,indent=2)+'\n')
print(o)
