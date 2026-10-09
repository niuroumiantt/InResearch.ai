"""Register actual primary map bytes and the constrained web response separately."""
from pathlib import Path
import hashlib,json,datetime
OUT=Path(__file__).resolve().parents[2]
RAW=Path('/Users/m5/.local/share/inresearch.ai/geluoke-research/2026-10-09-us-datacenter-power/raw/visual-v3')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
rows=[
 ('v3-eia-map','EIA',1,'Electric power regions overview','https://www.eia.gov/energyexplained/electricity/images/elect_power_regions.jpg','eia-interconnections.jpg','官方概览图：核对三大互联与有限联络的地理含义'),
 ('v3-ercot-map','ERCOT',6,'US Interconnections map','https://www.ercot.com/files/assets/2022/12/13/ERCOT-Maps_Interconnection-Map.jpg','ercot-interconnections.jpg','完整图面与图例：西部包含El Paso/Far West Texas；东部包含East Texas与Panhandle部分'),
 ('v3-ercot-counties','ERCOT',6,'ERCOT area by county','https://www.ercot.com/files/assets/2022/12/13/ERCOT-Maps_Area-by-county.jpg','ercot-counties.jpg','完整图面：用于交叉核对得州覆盖并非全州，不据此推定具体客户接入'),
 ('v3-census','US Census Bureau',19,'ACS2025 generalized state polygons, 20M layer 9','https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_ACS2025/State_County/MapServer/9/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson','census-state-polygons.geojson','解析全部52份州/地区多边形；仅使用本土48州与DC共49份。几何用于州形状，不提供电网分界。'),
 ('v3-doe-fuelcells','DOE',3,'Fuel Cell Systems','https://www.energy.gov/cmei/fuels/fuel-cell-systems','doe-fuelcells.html','Fuel Cell Stack、Fuel Processor、Power Conditioners；仅采用DC、电化学、处理与电力转换机制，不套用PEM加湿/交通压缩参数到SOFC。'),
 ]
records=[]
for id,org,group,title,url,name,scope in rows:
 p=RAW/name;txt=RAW/(p.stem+'.txt')
 r=dict(id=id,org=org,citation_group=group,published=None,title=title,url=url,retrieved_at=now,status='downloaded',raw_file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,read_scope=scope,adoption_status='research_input_only',originals_package_path='originals/visual-v3/'+name)
 if txt.exists():r['extracted_text']=str(txt)
 records.append(r)
p=RAW/'sofc-web-response.json'
records.append(dict(id='v3-bloom',org='Bloom Energy',citation_group=None,published=None,title='Bloom Energy Server Data Sheet landing page',url='https://www.bloomenergy.com/resource/bloom-energy-server/',retrieved_at=now,status='web_tool_extract',original_download_status='failed',error='HTTP Error 403: Forbidden',raw_file=None,original_bytes_sha256=None,retrieval_artifact=str(p),retrieval_artifact_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),extracted_text=str(p),read_scope='已读原站工具响应L104–110；SOFC非燃烧电化学、天然气与现场模块化。未采用厂商零用水、可靠性、排放或装机数量宣传；未读落地页PDF全文。SHA只标识工具响应。',adoption_status='research_input_only',originals_package_path='originals/visual-v3/sofc-web-response.json'))
manifest=dict(revision=3,records=records,derived_geography='work/v3/map-geography.json',region_boundary_method='人工按EIA/ERCOT概览重绘，不是下载的电网GIS或站点接入边界',failures_retained=['census-states.geojson','census-states-v2.geojson'],failure_meaning='前两次REST层号错误返回400，84字节错误响应保留，未作为地图依据',generated_original={'file':str(RAW/'sofc-generated-original.png'),'sha256':hashlib.sha256((RAW/'sofc-generated-original.png').read_bytes()).hexdigest(),'prompt':'work/v3/illustration-prompt.txt','evidence_role':'通用设备讲解插画，不是项目事实证据'})
(OUT/'work/v3/visual-sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
src=json.loads((OUT/'sources.json').read_text());src['records']=[r for r in src['records'] if not r['id'].startswith('v3-')]+records
(OUT/'sources.json').write_text(json.dumps(src,ensure_ascii=False,indent=2))
(OUT/'research/sources.json').write_text(json.dumps(src,ensure_ascii=False,indent=2))
supplement='''\n\n## 第三版图文修订的原始资料补充\n\n2026-10-09：地图改为根据US Census州多边形重绘，三大互联范围对照EIA/ERCOT官方图；州界与概览系统分界分别处理。得州覆盖不是全州，有限直流联络的位置仅示意，不用于站点接入判断。配套身份和读取范围见work/v3/visual-sources.json及本包sources.json。\n\n现场电源图改为AEP披露案例采用的固体氧化物燃料电池；DOE材料补充了电化学产生DC、燃料处理与电力转换的基本机制。Bloom原站工具响应仅作设备路线核对，原始HTML下载403和响应身份分别保留，不采用厂商性能或排放宣传。新图不构成新项目投运证据。\n\n原有23件submission与50条候选保持原版本和阶段；本补充资料尚未进入额外submission、深读/C3、远程数据库或模型采用。正式问题覆盖和缺口仍按已有快照，插画与来源数量不自动关闭问题。\n'''
p=OUT/'research/research.md';base=p.read_text().split('\n\n## 第三版图文修订的原始资料补充')[0];p.write_text(base+supplement)
p=OUT/'research/research.txt';base=p.read_text().split('\n\n## 第三版图文修订的原始资料补充')[0];p.write_text(base+supplement)
print(json.dumps({'new_primary_inputs':len(records),'total_source_records':len(src['records'])}))
