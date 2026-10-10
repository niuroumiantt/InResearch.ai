import pathlib,json,math,base64,hashlib,html
O=pathlib.Path('/Users/m4/.local/share/inresearch.ai/technical-atlas-audit/2026-10-10/TA-20/native-v2')
p=json.loads((O/'native-render-proof.json').read_text());b=(O/'campus-plan-native.png').read_bytes();S=.88;DX=92;DY=43
c=p['camera']
# Independent review: fan guard spokes centered3.3/thickness.025 have visible top3.3125; original render-proof remains historical. StrictYprojection is unchanged.
for a in p['anchors']:
 if a['num']=='05':a['local'][1]=3.3125;a['world'][1]=3.3125
def project(w):
 q=[w[n]-c['target'][n] for n in range(3)]
 dot=lambda a,b:sum(x*y for x,y in zip(a,b))
 return [(dot(q,c['screenRight'])-c['left'])/(c['right']-c['left'])*1536,(c['top']-dot(q,c['screenUp']))/(c['top']-c['bottom'])*1024]
def display(w):
 x,y=project(w);return[x*S+DX,y*S+DY]
titles=['机柜×8 · 2行×4顶面','室内冷却×5 · 顶部风管短节','CDU×3 · 未接成完整液路','UPS一组 · 俯视仅见顶面','冷水机×3 · 共6顶置风扇','变压器×2 · 接线未知','备用发电×3 · 顶部排气示例','储能柜×2 · 容量未知','保留围护与UPS分隔墙','柱脚投影×10 · 非新增设备','上方桥架投影 · 非完整布线','同一基础/地坪 · 非地块边界']
offsets=[[0,50],[0,-44],[47,0],[0,48],[-50,0],[0,-60],[0,-48],[0,-54],[-40,-30],[-28,30],[-52,8],[34,30]]
out=['<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024" viewBox="0 0 1536 1024" role="img" aria-labelledby="title description">','<title id="title">园区与机房正交平面图 · 同一八柜示例布局</title>','<desc id="description">从严格正上方看同一组通用设备，所有设备保持原位。屋面、上部钢架与实体桥架虚拟省略；浅灰虚线只投影已有桥架位置，柱脚轮廓不是新增设备。无北向、比例尺或真实尺寸，非施工图或完整电力水路。</desc>','<rect width="1536" height="1024" fill="#FAF9F2"/>',f'<image x="{DX}" y="{DY}" width="{1536*S}" height="{1024*S}" href="data:image/png;base64,{base64.b64encode(b).decode()}"/>']
# Explicit nonphysical projected contours, no inferred electrical/fluid links.
q=[display(w)for w in [[-16,.54,-11],[16,.54,-11],[16,.54,11],[-16,.54,11]]]
out.append('<path id="source-foundation-outline" d="M '+' L '.join(f'{x:.4f},{y:.4f}'for x,y in q)+' Z" fill="none" stroke="#9FA59B" stroke-width=".8"/>')
trayrecords=[]
for n,t in enumerate(p['sourceTrayProjection']):
 x,y,z=t['center'];w=t['width'];d=t['depth'];corners=[display(a)for a in [[x-w/2,y,z-d/2],[x+w/2,y,z-d/2],[x+w/2,y,z+d/2],[x-w/2,y,z+d/2]]]
 out.append(f'<path class="tray-projection" data-source-instance="campus/overhead-service-trays" data-physical="false" d="M '+ ' L '.join(f'{x:.4f},{y:.4f}'for x,y in corners)+' Z" fill="none" stroke="#8E9D99" stroke-width="1" stroke-dasharray="5 5" opacity=".7"/>')
 trayrecords.append({**t,'display_corners':corners,'physical':False})
out+=['<g id="editable-labels" font-family="Inter, Noto Sans SC, sans-serif" fill="#293B42">','<text x="54" y="47" font-size="28" font-weight="650">园区与机房正交平面图</text>','<text x="54" y="76" font-size="16">严格正上方 · 同一设备原位 · 屋面、上部钢架与实体桥架虚拟省略</text>','<text x="54" y="99" font-size="14">灰虚线为已有上方桥架的位置投影，不表示完整电缆/水路；朝向与数量仅示意，无北向、比例尺、尺寸或现场规格。</text>','</g>']
labels=[]
for i,(a,t,offset)in enumerate(zip(p['anchors'],titles,offsets)):
 ax,ay=[a['pixel'][0]*S+DX,a['pixel'][1]*S+DY];cx,cy=ax+offset[0],ay+offset[1];dist=math.hypot(ax-cx,ay-cy);sx,sy=cx+(ax-cx)*16/dist,cy+(ay-cy)*16/dist
 out.append(f'<g class="callout" data-label="{a["num"]}" data-instance="{a["instance"]}"><path d="M {sx:.4f},{sy:.4f} L {ax:.4f},{ay:.4f}" fill="none" stroke="#09689B" stroke-width="1.6"/><circle cx="{ax:.4f}" cy="{ay:.4f}" r="2.5" fill="#09689B"/><circle cx="{cx:.4f}" cy="{cy:.4f}" r="16" fill="#FAF9F2" stroke="#09689B" stroke-width="1.6"/><text x="{cx:.4f}" y="{cy+5:.4f}" text-anchor="middle" font-size="14" font-family="Inter, Noto Sans SC, sans-serif" fill="#09689B">{a["num"]}</text></g>')
 col=i//4;row=i%4;x=54+col*490;y=855+row*36
 out.append(f'<g class="legend" data-label="{a["num"]}"><text x="{x}" y="{y}" font-size="17" font-family="Inter, Noto Sans SC, sans-serif" fill="#09689B">{a["num"]}</text><text x="{x+34}" y="{y}" font-size="17" font-family="Inter, Noto Sans SC, sans-serif" fill="#293B42">{html.escape(t)}</text></g>')
 labels.append({**a,'name':t,'anchor_role':'derived hidden-instance projection'if a['num']in['10','11']else'actual visible top surface','source_anchor':a['pixel'],'affine':[S,DX,DY],'display_anchor':[ax,ay],'circle':[cx,cy],'path_start':[sx,sy],'legend':[x,y]})
out.append('</svg>');(O/'campus-full.svg').write_text('\n'.join(out)+'\n')
(O/'labels-v1.json').write_text(json.dumps({'figure_id':'TA-20','method':'Strict vertical actual native projection with independent editable SVG labels; original PNG embedded unchanged','native_sha256':hashlib.sha256(b).hexdigest(),'pixels':[1536,1024],'labels':labels,'tray_projection':trayrecords,'foundation_outline':q},ensure_ascii=False,indent=2)+'\n')
print(O/'campus-full.svg')
