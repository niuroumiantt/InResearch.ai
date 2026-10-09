import concurrent.futures, hashlib, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlparse

OUT=Path('/Users/m5/code/inresearch.ai/outputs/geluoke-research/2026-10-09-us-datacenter-power')
RAW=Path('/Users/m5/.local/share/inresearch.ai/geluoke-research/2026-10-09-us-datacenter-power/raw')
PLAN=[
('eia-grid','EIA',1,None,'Electricity delivery to consumers','https://www.eia.gov/energyexplained/electricity/delivery-to-consumers.php'),
('eia-glossary','EIA',1,None,'Electricity glossary: Federal Power Act','https://www.eia.gov/tools/glossary/index.php?id=Electric'),
('eia-ytd','EIA',1,'2026-09-24','EPM Table 5.6.B, January-July 2026 and 2025','https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b'),
('eia-month','EIA',1,'2026-09-24','EPM Table 5.6.A, July 2026 and 2025','https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_a'),
('ferc-market','FERC',2,None,'Energy Markets','https://www.ferc.gov/opp/energy-markets'),
('ferc-rto','FERC',2,'2026-09-29','RTOs and ISOs','https://www.ferc.gov/power-sales-and-markets/rtos-and-isos'),
('ferc-june','FERC',2,'2026-06-18','FERC Launches Targeted Action to Speed Large Load Integration','https://ferc.gov/news-events/news/ferc-launches-aggressive-targeted-action-speed-large-load-integration'),
('ferc-colocation','FERC',2,'2025-12-18','Rules for large loads co-located with generation','https://ferc.gov/news-events/news/fact-sheet-ferc-directs-nations-largest-grid-operator-create-new-rules-embrace'),
('ferc-siting','FERC',2,None,'Electric Transmission Siting','https://ferc.gov/electric-transmission-siting'),
('doe-transmission','DOE',3,None,'Transmission Siting and Permitting Efforts','https://www.energy.gov/oe/transmission-siting-and-permitting-efforts'),
('doe-transformer','DOE',3,None,'Distribution Transformer Webinar Text Alternative','https://www.energy.gov/oe/distribution-transformer-webinar-text-alternative'),
('doe-consumption','DOE',3,'2024-12-20','DOE Releases Data Center Energy Usage Report','https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers'),
('lbnl-report','LBNL',4,'2024-12','2024 United States Data Center Energy Usage Report','https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report.pdf'),
('pjm-forecast','PJM',5,'2026-01-14','2026 Long-Term Load Forecast Report','https://www.pjm.com/-/media/DotCom/library/reports-notices/load-forecast/2026-load-report.pdf'),
('pjm-accuracy','PJM',5,None,'2026 Load Forecast Accuracy Report','https://www.pjm.com/-/media/DotCom/planning/res-adeq/load-forecast/2026-load-forecast-accuracy-report.pdf'),
('pjm-large','PJM',5,None,'Large Load','https://www.pjm.com/markets-and-operations/large-load'),
('ercot-batch','ERCOT',6,'2026-06-18','PUCT Approves ERCOT Batch Zero','https://www.ercot.com/news/release/06182026-puct-approves-ercots'),
('ercot-notice','ERCOT',6,'2026-06-23','Batch Zero market notice M-B062326-03','https://www.ercot.com/services/comm/mkt_notices/M-B062326-03'),
('ercot-ties','ERCOT',6,'2025-05-12','Electricity Connection and Transfer','https://www.ercot.com/files/docs/2025/05/12/ERCOT-Grid-Insights-Electricity-Connection-and-Transfer.pdf'),
('jlarc','Virginia JLARC',7,'2024-12-09','Data Centers in Virginia, Report 598','https://jlarc.virginia.gov/pdfs/reports/Rpt598.pdf'),
('scc','Virginia SCC',8,'2026-02-24','SCC Data Center Initiatives','https://www.scc.virginia.gov/media/sccvirginiagov-home/about-the-scc/fact-sheets/scc-data-center-initiatives-02-2026.pdf'),
('ga-psc','Georgia PSC',9,None,'Data Center Fact Sheet','https://psc.ga.gov/site/downloads/datacenterfactsheet.pdf'),
('ga-contract','Georgia Power',10,None,'OpenAI contract approval and expected customer savings','https://www.georgiapower.com/news-hub/press-releases/contract-openai-approved-part-portfolio-delivering-950-million-annual-savings.html'),
('ga-rules','Georgia Power',10,None,'Data Centers and Georgia Power Bills','https://www.georgiapower.com/about/customer-pledge/data-centers.html'),
('crane','Constellation',11,'2025-09-23','Crane restart accelerated to 2027','https://constellationenergy.gcs-web.com/news-releases/news-release-details/one-year-later-crane-clean-energy-center-still-spotlight-and'),
('talen','Talen Energy',12,'2025-06-11','Talen expands nuclear energy relationship with Amazon','https://ir.talenenergy.com/news-releases/news-release-details/talen-energy-expands-nuclear-energy-relationship-amazon'),
('google-intersect','Google',13,'2025-12-22','Advancing energy innovation with Intersect','https://blog.google/innovation-and-ai/infrastructure-and-cloud/global-network/energy-innovation-intersect/'),
('google-flex','Google',13,'2025-08-04','Making data centers flexible to benefit power grids','https://blog.google/innovation-and-ai/infrastructure-and-cloud/global-network/how-were-making-data-centers-more-flexible-to-benefit-power-grids/'),
('intersect','Intersect',13,'2025-12-22','Alphabet agreement to acquire Intersect','https://www.intersect.com/news/alphabet-announces-agreement-to-acquire-intersect-to-advance-u-s-energy-innovation'),
('iea','IEA',14,'2026-04-16','Key Questions on Energy and AI','https://iea.blob.core.windows.net/assets/3179f7f8-01f6-4dd6-bffa-c9f7b73f1dc9/KeyQuestionsonEnergyandAI.pdf'),
('iea-summary','IEA',14,'2026-04-16','Key Questions on Energy and AI: Executive Summary','https://www.iea.org/reports/key-questions-on-energy-and-ai/executive-summary'),
('nerc','NERC',15,'2026-01-29','2025 Long-Term Reliability Assessment','https://www.nerc.com/globalassets/our-work/assessments/nerc_ltra_2025.pdf'),
('pledge','White House',16,'2026-03-04','Ratepayer Protection Pledge Proclamation','https://www.whitehouse.gov/presidential-actions/2026/03/ratepayer-protection-pledge-proclamation/'),
('nrc','NRC',17,None,'Crane Clean Energy Center Restart Project','https://www.nrc.gov/facilities-safety/facility-finder/reactors/ccec'),
('gallup','Gallup',18,'2026-05-13','Americans Oppose AI Data Centers in Their Area','https://news.gallup.com/poll/709772/americans-oppose-data-centers-area.aspx'),
('ohio','Ohio Consumers Counsel',19,'2025-07-09','Data Center Costs 24-0508-EL-ATA','https://occ.ohio.gov/content/data-center-costs-24-0508-el-ata'),
('aep-onsite','AEP',20,'2025-06-05','PUCO Approves Onsite Power Project for Data Centers','https://www.aep.com/news/stories/view/10262/'),
('wechat','Tencent WeChat',21,None,'Uploading article body images','https://developers.weixin.qq.com/doc/offiaccount/Asset_Management/New_temporary_materials.html'),
]

def fetch(row):
 sid,org,group,dt,title,url=row
 r=dict(id=sid,org=org,citation_group=group,published=dt,title=title,url=url,retrieved_at=datetime.now(timezone.utc).isoformat(),status='failed')
 try:
  req=Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'*/*'})
  with urlopen(req,timeout=35) as resp: data=resp.read(); r['final_url']=resp.url;r['content_type']=resp.headers.get('Content-Type','')
  if len(data)<100:raise ValueError('response too short')
  ext='.pdf' if data.startswith(b'%PDF') else '.html'
  raw=RAW/(sid+ext);raw.write_bytes(data)
  r.update(raw_file=str(raw),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),status='downloaded')
  if ext=='.pdf':
   import fitz
   doc=fitz.open(raw)
   pages=[{'pdf_page':i+1,'text':p.get_text()} for i,p in enumerate(doc)]
   (RAW/(sid+'.pages.json')).write_text(json.dumps(pages,ensure_ascii=False,indent=2))
   txt='\n\n'.join('=== PDF page %s ===\n%s'%(x['pdf_page'],x['text']) for x in pages);r['pdf_pages']=len(pages)
  else:
   from bs4 import BeautifulSoup
   soup=BeautifulSoup(data,'html.parser')
   for x in soup(['script','style','nav','footer','header']):x.decompose()
   if soup.title:r['fetched_title']=soup.title.get_text(' ',strip=True)
   # Preserve full visible text and native table order; never execute source scripts.
   txt=soup.get_text('\n',strip=True)
  (RAW/(sid+'.txt')).write_text(txt)
  r['extracted_text']=str(RAW/(sid+'.txt'));r['extracted_chars']=len(txt)
  if any(t in txt[:1000].lower() for t in ['access denied','verify you are human','403 forbidden']):r['status']='blocked'
 except Exception as e:r['error']=str(e)[:250]
 return r

if __name__=='__main__':
 if (OUT/'sources.json').exists():
  raise SystemExit('本批来源清单已存在。新检索请另建批次与原件目录，保留旧版本，不覆盖本篇溯源。')
 OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: records=list(pool.map(fetch,PLAN))
 (OUT/'sources.json').write_text(json.dumps({'as_of':'2026-10-09','records':records},ensure_ascii=False,indent=2))
 print('Sources',len(records),'downloaded',sum(r['status']=='downloaded' for r in records))
 for r in records:
  if r['status']!='downloaded':print(r['id'],r['status'],r.get('error',''))
