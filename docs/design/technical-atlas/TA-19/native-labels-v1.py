import pathlib,json,math,base64,hashlib,html,datetime
O=pathlib.Path('/Users/m4/.local/share/inresearch.ai/technical-atlas-audit/2026-10-10/TA-19/native-v3')
p=json.loads((O/'native-render-proof.json').read_text()); b=(O/'campus-exploded-native.png').read_bytes()
S=.8;DX=155;DY=90
# Reproject a visible upper-right face of the same displaced wall using the
# authored orthographic camera basis, rather than placing a point by eye.
def vsub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return [x/math.sqrt(dot(a,a)) for x in a]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
c=p['camera'];back=norm(vsub(c['position'],c['target']));right=norm(cross([0,1,0],back));up=cross(back,right)
for a in p['anchors']:
 if a['num']=='02':
  a['local']=[14,6,-10.79];a['world']=[10,6,-20.79];q=vsub(a['world'],c['target']);a['pixel']=[(dot(q,right)-c['left'])/(c['right']-c['left'])*1536,(c['top']-dot(q,up))/(c['top']-c['bottom'])*1024]
titles=['保留屋面分组 · 虚拟抬升','围护墙组 · 虚拟侧移','桥架分组 · 未绘完整布线','机柜×8 · 2行×4示例','室内冷却×5 · 外形示例','CDU×3 · 局部接口示意','UPS一组 · 4柜门示例','基础与空原位 · 灰虚线对应','室外冷水机×3','变压器×2 · 接线未知','备用发电×3 · 外排气示意','储能柜×2 · 容量未知']
offsets=[[40,-30],[36,-25],[-34,-27],[-28,28],[-29,-29],[38,-28],[-38,-25],[-34,26],[-32,-27],[35,-27],[-32,-27],[38,-28]]
out=['<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024" viewBox="0 0 1536 1024" role="img" aria-labelledby="title description">','<title id="title">园区分层爆炸图 · 通用八柜示例</title>','<desc id="description">同一组几何按虚拟装配轴平移；屋面、围护、桥架与室内设备层对应浅灰原位虚线。室外设备保持原位。非施工或拆装程序，不认证型号、规格或完整连接拓扑。</desc>','<rect width="1536" height="1024" fill="#FAF9F2"/>',f'<image x="{DX}" y="{DY}" width="{1536*S}" height="{1024*S}" href="data:image/png;base64,{base64.b64encode(b).decode()}"/>','<g id="editable-labels" font-family="Inter, Noto Sans SC, sans-serif" fill="#293B42">','<text x="54" y="47" font-size="28" font-weight="650">园区分层爆炸图</text>','<text x="54" y="76" font-size="16">同姿态、沿各组既定轴平移 · 保留钢架与室外设备 · 灰虚线对应空出的原位</text>','<text x="54" y="99" font-size="14">通用示意，非OEM/CAD或拆装程序；数量为画法选择，未认证尺寸、功率或完整电力/流体拓扑。</text>','</g>']
labels=[]
for i,(a,t,offset) in enumerate(zip(p['anchors'],titles,offsets)):
 ax,ay=[a['pixel'][0]*S+DX,a['pixel'][1]*S+DY];cx,cy=ax+offset[0],ay+offset[1];d=math.hypot(ax-cx,ay-cy);sx,sy=cx+(ax-cx)*16/d,cy+(ay-cy)*16/d
 out.append(f'<g class="callout" data-label="{a["num"]}" data-instance="{a["instance"]}"><path d="M {sx:.4f},{sy:.4f} L {ax:.4f},{ay:.4f}" fill="none" stroke="#09689B" stroke-width="1.6"/><circle cx="{ax:.4f}" cy="{ay:.4f}" r="2.5" fill="#09689B"/><circle cx="{cx:.4f}" cy="{cy:.4f}" r="16" fill="#FAF9F2" stroke="#09689B" stroke-width="1.6"/><text x="{cx:.4f}" y="{cy+5:.4f}" text-anchor="middle" font-size="14" font-family="Inter, Noto Sans SC, sans-serif" fill="#09689B">{a["num"]}</text></g>')
 col=i//4;row=i%4;x=54+col*490;y=891+row*29
 out.append(f'<g class="legend" data-label="{a["num"]}"><text x="{x}" y="{y}" font-size="17" font-family="Inter, Noto Sans SC, sans-serif" fill="#09689B">{a["num"]}</text><text x="{x+34}" y="{y}" font-size="17" font-family="Inter, Noto Sans SC, sans-serif" fill="#293B42">{html.escape(t)}</text></g>')
 labels.append({**a,'name':t,'source_anchor':a['pixel'],'affine':[S,DX,DY],'display_anchor':[ax,ay],'circle':[cx,cy],'path_start':[sx,sy],'legend':[x,y]})
out.append('</svg>');(O/'campus-full.svg').write_text('\n'.join(out)+'\n')
(O/'labels-v1.json').write_text(json.dumps({'figure_id':'TA-19','method':'Actual native orthographic geometry projection; independent editable SVG labels; original PNG embedded unchanged','native_sha256':hashlib.sha256(b).hexdigest(),'pixels':[1536,1024],'labels':labels},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'svg':str(O/'campus-full.svg'),'labels':len(labels),'native_sha256':hashlib.sha256(b).hexdigest()}))
