"""Price-series feedback from the 2026-09-27 profit study into data/prices.json.

Every record traces to a research card in
outputs/geluoke-research/2026-09-27-datacenter-profit/work/research/cards.json
(card id in `card`) or to the report excerpt file work/report_facts.md.
Run `python3 price_records.py --apply` to append records that are not yet in
the price file (series_id + as_of unique); without --apply it only reports.
Grades follow framework/data_contract.json: regulatory / company / research /
media / estimate (estimate requires assumptions). Author-derived numbers are
estimate with the derivation in assumptions.
"""
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from inresearch.knowledge.policy import price_errors  # noqa: E402

SEMI = 'https://gpu-index.semianalysis.com/'
SD_H100 = 'https://www.silicondata.com/products/silicon-index/h100'
SD_INDEX = 'https://www.silicondata.com/products/silicon-index'
SD_BLOG = 'https://www.silicondata.com/blog/h100-rental-price-over-time'
SD_SPIKE = 'https://www.silicondata.com/blog/h100-price-spike'
DG = 'https://www.datagravity.dev/p/how-much-does-an-nvidia-nvl72-cost'
CW_GUIDE = 'https://ir.cushmanwakefield.com/news/press-release-details/2026/Cushman--Wakefield-Releases-2026-Data-Center-Development-Cost-Guide-Citing-21-Rise-in-Per-MW-Construction-Costs/default.aspx'
CBRE_GLOBAL = 'https://www.cbre.com/insights/reports/global-data-center-trends-2026'
CBRE_NA_H1 = 'https://www.cbre.com/insights/books/north-america-data-center-trends-h1-2026'
CBRE_NOVA = 'https://www.cbre.com/insights/books/north-america-data-center-trends-h1-2026/northern-virginia-data-center-market'
CBRE_EU_WHOLESALE = 'https://www.cbre.com/press-releases/data-centre-capacity-pricin'
EIA = 'https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_06_a'
EIA_B = 'https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_06_b'
EUROSTAT = 'https://ec.europa.eu/eurostat/web/products-eurostat-news/w/ddn-20260508-2'
PJM_2627 = 'https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2026-2027/2026-2027-bra-report.pdf'
PJM_2728 = 'https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2027-2028/2027-2028-bra-report.pdf'
GDS_CALL = 'https://www.fool.com/earnings/call-transcripts/2026/08/14/gds-gds-q2-2026-earnings-call-transcript/'
VNET_Q2 = 'https://www.prnewswire.com/news-releases/vnet-reports-unaudited-second-quarter-2026-financial-results-302853949.html'
SMM = 'https://news.smm.cn/news/104113796'
MS_NOTE = '摩根士丹利 2026 年 9 月《AI 指南》（PDF 2026-09-07）；研报原件不入库，见 work/report_facts.md A1/A2'

R = []


def add(series, as_of, value, unit, grade, source, category, module, region='global', assumptions=None, note='', card='', frequency=None):
    rec = dict(series_id=series, category=category, module=module, as_of=as_of, value=float(value), unit=unit,
               region=region, assumptions=assumptions, grade=grade, source_url=source,
               note=(note + ('；研究卡 ' + card if card else '') + '；反哺自 2026-09-27 盈利专题').strip('；'))
    if frequency:
        rec['frequency'] = frequency
    R.append(rec)


# ---------------------------------------------------------------- GPU rents
# SemiAnalysis one-year contract index: public page gives 25–75 percentile bands; we store the midpoint.
CONTRACT = [('2023-06-30', 2.70, 3.40), ('2023-12-31', 2.65, 3.30), ('2024-03-31', 2.50, 3.10), ('2024-06-30', 2.20, 2.50),
            ('2024-09-30', 2.15, 2.45), ('2024-12-31', 1.90, 2.10), ('2025-03-31', 1.80, 2.10), ('2025-06-30', 1.80, 2.10),
            ('2025-07-31', 1.70, 2.00), ('2025-08-31', 1.50, 2.00), ('2025-09-30', 1.50, 2.00), ('2025-10-31', 1.45, 1.95),
            ('2025-11-30', 1.45, 2.00), ('2025-12-31', 1.45, 2.00), ('2026-01-31', 1.50, 2.05), ('2026-02-28', 1.80, 2.35),
            ('2026-03-31', 2.00, 2.70), ('2026-04-30', 2.10, 2.70)]
for d, lo, hi in CONTRACT:
    add('gpu-hourly-h100-contract-1y', d, round((lo + hi) / 2, 3), '$/hr', 'research', SEMI, 'gpu-rental', 'M13',
        assumptions=f'SemiAnalysis 一年期合约指数 25–75 分位区间 {lo:.2f}–{hi:.2f} 的中值；100+ 市场参与者月度调查，非单一成交价',
        note='H100 一年期合约；公开页面最新期 2026-04，之后未公开，更新不定期', card='gpu-rental-prices', frequency='default')
add('gpu-hourly-h100-ondemand-index', '2026-04-30', 2.82, '$/hr', 'research', SEMI, 'gpu-rental', 'M13',
    assumptions='Spot-Contract Composite Index，供应商价格加权均值，超大规模云权重高于市场平台与新兴云', note='H100 按需加权指数（Bloomberg SAH100SC）', card='gpu-rental-prices', frequency='default')
add('gpu-hourly-b200-ondemand-index', '2026-04-30', 3.68, '$/hr', 'research', SEMI, 'gpu-rental', 'M13',
    assumptions='同上，B200', note='B200 按需加权指数', card='gpu-rental-prices', frequency='default')

# Silicon Data indices (daily standardized hourly price, segment readings).
add('gpu-hourly-h100-neocloud-index', '2025-05-27', 2.37, '$/hr', 'research', 'https://spectrum.ieee.org/gpu-prices', 'gpu-rental', 'M13',
    note='SDH100RT 读数（IEEE Spectrum 转述）；2025-12-03 方法修订并重述 2024-09-01 起历史，与后续读数未必可比', card='gpu-rental-prices')
add('gpu-hourly-h100-neocloud-index', '2025-12-09', 2.00, '$/hr', 'research', SD_SPIKE, 'gpu-rental', 'M13', note='SDH100RT 日度读数', card='gpu-rental-prices')
add('gpu-hourly-h100-neocloud-index', '2026-01-06', 2.20, '$/hr', 'research', SD_SPIKE, 'gpu-rental', 'M13', note='SDH100RT 日度读数，较 12 月 +10%', card='gpu-rental-prices')
add('gpu-hourly-h100-neocloud-index', '2026-09-26', 2.72, '$/hr', 'research', SD_H100, 'gpu-rental', 'M13', note='Silicon Data H100 Neo-Cloud 分段日度读数，7 日 +2.6%', card='gpu-rental-prices')
add('gpu-hourly-h100-hyperscaler-index', '2026-09-26', 7.18, '$/hr', 'research', SD_INDEX, 'gpu-rental', 'M13', note='Silicon Data H100-hyperscaler 分段读数，7 日 −0.3%', card='gpu-rental-prices')
BLOG = {'gpu-hourly-h100-hyperscaler-index': [('2024-12-31', 9.34, '2024-06~12'), ('2025-05-31', 8.96, '2025-01~05'), ('2025-06-30', 6.94, '2025-06'), ('2025-12-31', 6.26, '2025-07~12')],
        'gpu-hourly-h100-marketplace-index': [('2024-12-31', 2.58, '2024-06~12'), ('2025-05-31', 2.29, '2025-01~05'), ('2025-06-30', 2.00, '2025-06'), ('2025-12-31', 1.95, '2025-07~12')],
        'gpu-hourly-h100-neocloud-index': [('2024-12-31', 2.99, '2024-06~12'), ('2025-05-31', 3.50, '2025-01~05'), ('2025-06-30', 3.29, '2025-06')]}
for series, pts in BLOG.items():
    for d, v, period in pts:
        add(series, d, v, '$/hr', 'research', SD_BLOG, 'gpu-rental', 'M13', assumptions=f'Silicon Data 博客分段期间中位数（{period}），记在期末',
            note='H100 分段中位数（超大规模云 / 市场平台 / 新兴云）', card='gpu-rental-prices')
add('gpu-hourly-h200-index', '2026-09-24', 3.30, '$/hr', 'research', 'https://www.silicondata.com/products/silicon-index/h200', 'gpu-rental', 'M13', note='Silicon Data H200 指数（2026-07-15 生效），7 日 −0.3%', card='gpu-rental-prices')
add('gpu-hourly-b200-index', '2026-09-27', 5.87, '$/hr', 'research', SD_INDEX, 'gpu-rental', 'M13', note='Silicon Data B200 Composite（2025-12-04 生效），7 日 +2.4%', card='gpu-rental-prices')
add('gpu-hourly-b300-index', '2026-09-27', 6.80, '$/hr', 'research', SD_INDEX, 'gpu-rental', 'M13', note='Silicon Data B300 Composite（2026-09-14 生效），7 日 −2.2%', card='gpu-rental-prices')
add('gpu-hourly-mi300x-index', '2026-09-27', 2.62, '$/hr', 'research', SD_INDEX, 'gpu-rental', 'M13', note='Silicon Data MI300X Composite', card='gpu-rental-prices')
add('gpu-hourly-h100-ornn-index', '2026-09-07', 3.17, '$/hr', 'media', 'https://www.tradingkey.com/analysis/stocks/us-stocks/262155850-nvidia-h100-ornn-rental-surge-22-percent-jensen-huang-gpu-asset-tradingkey', 'gpu-rental', 'M13',
    note='Ornn 平台 9 月 7 日结算价（公告值 3.28）；平台内交易价，非全球租价', card='gpu-rental-prices')
for gpu, v in [('h100', 3.25), ('h200', 4.40), ('b200', 6.52), ('b300', 7.87)]:
    add(f'gpu-hourly-{gpu}-ondemand-median', '2026-09-22', v, '$/hr', 'media', 'https://aimultiple.com/gpu-index', 'gpu-rental', 'M13',
        assumptions='AIMultiple 75 家供应商挂牌价中位数，排除议价合同与“联系销售”', note=f'{gpu.upper()} 按需挂牌中位数', card='gpu-rental-prices')

# Vendor list prices (per GPU-hour, on demand), captured 2026-09-27.
VENDORS = {
    'lambda': ('https://lambda.ai/pricing', {'h100': (3.99, '8×H100 SXM 按需'), 'b200': (6.69, '8×B200 SXM6 按需')}),
    'nebius': ('https://nebius.com/prices', {'h100': (3.85, '按需；2026-10-01 起 4.50'), 'h200': (4.50, '按需；2026-10-01 起 5.40'), 'b200': (7.15, '按需；2026-10-01 起 8.50'), 'b300': (7.85, '按需；2026-10-01 起 9.50')}),
    'runpod': ('https://www.runpod.io/pricing', {'h100': (3.49, 'Secure Cloud H100 SXM 按需'), 'h200': (4.59, 'Secure Cloud 按需'), 'b200': (6.79, 'Secure Cloud 按需'), 'b300': (7.89, 'Secure Cloud 按需')}),
    'verda': ('https://verda.com/pricing', {'h100': (3.52, 'H100 SXM 按需；Spot 1.76、1 年 3.24、2 年 2.64'), 'h200': (4.59, '按需；Spot 2.30、1 年 4.22、2 年 3.44'), 'b200': (6.82, '按需；Spot 3.41、1 年 6.27、2 年 5.12'), 'b300': (8.37, '按需；Spot 4.18、1 年 7.70、2 年 6.28'), 'gb300': (9.62, 'GB300 NVL72 按需；Spot 4.81、1 年 8.85、2 年 7.22；聚合站显示缺货')}),
    'coreweave': ('https://www.coreweave.com/pricing', {'h100': (6.16, 'HGX H100 按需 49.24/实例÷8；Spot 2.46'), 'h200': (6.31, 'HGX H200 按需 50.44/实例÷8；Spot 2.62'), 'b200': (8.60, 'HGX B200 按需 68.80/实例÷8；Spot 4.26'), 'gb200': (10.50, 'GB200 NVL72 4 卡实例 42.00÷4；北美区')}),
}
for vendor, (url, table) in VENDORS.items():
    for gpu, (v, desc) in table.items():
        add(f'gpu-hourly-{gpu}-ondemand-{vendor}', '2026-09-27', v, '$/hr', 'company', url, 'gpu-rental', 'M13',
            note=f'{vendor} 价目页 2026-09-27 抓取；{desc}', card='gpu-rental-prices')
add('gpu-hourly-h100-ondemand-aws', '2026-09-27', 6.88, '$/hr', 'company', 'https://instances.vantage.sh/aws/ec2/p5.48xlarge', 'gpu-rental', 'M13', region='north-america',
    note='p5.48xlarge 按需 55.04/实例÷8，us-east-1（Vantage 镜像）；2025-06 起 P5 按需降 44%', card='gpu-rental-prices')
add('gpu-hourly-b200-ondemand-aws', '2026-09-27', 14.24, '$/hr', 'company', 'https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge', 'gpu-rental', 'M13', region='north-america',
    note='p6-b200.48xlarge 按需 113.933/实例÷8（Vantage 镜像）', card='gpu-rental-prices')
add('gpu-hourly-gb200-ondemand-azure', '2026-09-27', 27.04, '$/hr', 'company', "https://prices.azure.com/api/retail/prices?$filter=contains(armSkuName,'GB200')%20and%20priceType%20eq%20'Consumption'", 'gpu-rental', 'M13', region='north-america',
    note='ND GB200 v6 VM 108.16/小时÷4，US East Consumption；聚合站列 12 个月预留 17.31、36 个月 11.90', card='gpu-rental-prices')
for gpu, v, inst in [('h100', 5.191, 'p5.48xlarge 41.528/8'), ('h200', 5.97, 'p5e 47.76/8'), ('b200', 12.355, 'p6-b200 98.84/8'), ('b300', 14.04, 'p6-b300 112.32/8'), ('gb200', 10.582, 'u-p6e-gb200x72 761.904/72')]:
    add(f'gpu-hourly-{gpu}-capacity-block-aws', '2026-09-27', v, '$/hr', 'company', 'https://aws.amazon.com/ec2/capacityblocks/pricing/', 'gpu-rental', 'M13', region='north-america',
        note=f'EC2 Capacity Blocks 预留时段价，{inst}', card='gpu-rental-prices')
add('gpu-hourly-gb300-ondemand-oracle', '2026-09-27', 18.00, '$/hr', 'media', 'https://getdeploying.com/gpus/nvidia-gb300', 'gpu-rental', 'M13',
    note='getdeploying 聚合站转述 4×GB300 配置按需价；Oracle 一手价目页 403 未核', card='gpu-rental-prices')
add('gpu-hourly-gb200-ondemand-oracle', '2026-09-26', 16.00, '$/hr', 'media', 'https://getdeploying.com/gpus/nvidia-gb200', 'gpu-rental', 'M13',
    note='getdeploying 聚合站转述；Oracle 一手价目页 403 未核', card='gpu-rental-prices')

# China GPU server monthly rents.
add('gpu-monthly-h100-8gpu-cn-guangzhou', '2026-09-14', 9.00, '万元/台·月', 'media', SMM, 'gpu-rental', 'M14', region='CN', note='SMM 算力日报：H100 八卡整机月租（广州，闭口三年）', card='china-policy-costs')
add('gpu-monthly-h20-8gpu-cn-southwest', '2026-09-14', 5.30, '万元/台·月', 'media', SMM, 'gpu-rental', 'M14', region='CN', note='SMM 算力日报：H20 96G 八卡整机月租（西南，含 6% 税与柜电）；华东 4.6', card='china-policy-costs')
add('gpu-monthly-ascend-910b4-8gpu-cn-bjtj', '2026-09-14', 1.55, '万元/台·月', 'media', SMM, 'gpu-rental', 'M14', region='CN', note='SMM 算力日报：昇腾 910B4 八卡整机月租（京津冀）', card='china-policy-costs')

# ---------------------------------------------------------------- benchmarks: report assumptions and TCO estimates
add('benchmark-ms-gb300-rent-baseline', '2026-09-07', 8.5, '$/hr', 'research', 'https://finance.biggo.com/news/212a6131-57b2-49c8-8ccf-20a27bcac88d', 'benchmark', 'M13',
    assumptions='摩根士丹利 1GW GB300 出租算例基准租金；情景 7–10 美元对应 ROIC 23%–39%；75% 利用率、410,256 颗 GPU/GW', note=MS_NOTE + '；预测估算，不是市场价', card='gpu-rental-prices', frequency='default')
for chip, v in [('gb300', 39), ('gb200', 35), ('vera-rubin', 49), ('rubin-ultra', 50), ('tpuv7', 27), ('trainium3', 21)]:
    add(f'benchmark-ms-capex-per-gw-{chip}', '2026-09-07', v, '$B/GW', 'research', 'https://www.morganstanley.com/', 'benchmark', 'M11',
        assumptions='摩根士丹利按芯片代际估算的 GW 级数据中心资本开支（IT + 非 IT，不含表后电力约 3 十亿）', note=MS_NOTE + f'；{chip} 代际，p22', frequency='default')
add('benchmark-gb300-nvl72-tco-hour', '2026-08-31', 2.72, '$/hr', 'estimate', DG, 'benchmark', 'M13',
    assumptions='Data Gravity 估算区间 2.56–2.88（80–90% 利用率）的中值；5 年折旧，含资本、电力、托管与融资成本；60% 利用率为 3.84；分母为已利用 GPU 小时', note='GB300 NVL72 每有效 GPU·小时全成本', card='gpu-rental-prices', frequency='default')
add('benchmark-gb300-nvl72-rack-price', '2026-08-31', 5.0, '$M/机柜', 'estimate', DG, 'benchmark', 'M06',
    assumptions='Data Gravity：机柜“略低于 500 万美元”，部署后约 570 万（含网络、电力与托管）', note='72 GPU 机柜采购价估算', card='gpu-rental-prices', frequency='default')
add('benchmark-gb200-nvl72-rack-price', '2026-08-31', 3.1, '$M/机柜', 'estimate', DG, 'benchmark', 'M06',
    assumptions='Data Gravity 估算区间 280–340 万美元的中值', note='GB200 NVL72 机柜采购价估算', card='gpu-rental-prices', frequency='default')
add('construction-cost-greenfield-na', '2026-09-03', 17.6, '$M/MW', 'research', CW_GUIDE, 'benchmark', 'M11', region='north-america',
    note='Cushman & Wakefield 2026 开发成本指南公告：绿地开发每 MW 造价，不含芯片/GPU；较 2024Q4 上一版 +21%（非严格单年同比）')

# Powered-shell (HPC hosting) capex per critical IT MW, company expectations at announcement.
SHELL_CAPEX = [
    ('construction-cost-shell-per-it-mw-terawulf-lake-mariner', '2025-08-14', 9.0, '800–1,000 万美元/MW 区间中值', 'https://www.sec.gov/Archives/edgar/data/1083301/000110465925078084/tm2523008d2_ex99-1.htm', 'TeraWulf Lake Mariner（Fluidstack 200+MW）'),
    ('construction-cost-shell-per-it-mw-cipher-barber-lake', '2025-09-25', 10.0, '900–1,100 万美元/IT MW 区间中值', 'https://www.sec.gov/Archives/edgar/data/1819989/000095010325012168/dp234624_ex9902.htm', 'Cipher Barber Lake（Fluidstack 168MW）'),
    ('construction-cost-shell-per-it-mw-cipher-black-pearl', '2025-11-03', 9.5, '开发成本上限 950 万美元/IT MW（超出由 Amazon 报销）', 'https://www.sec.gov/Archives/edgar/data/1819989/000095010326001480/dp240991_ex9901.htm', 'Cipher Black Pearl（AWS 216MW）'),
    ('construction-cost-shell-per-it-mw-cipher-stingray', '2026-06-08', 10.5, '公司披露 1,050 万美元/IT MW（超出由 Amazon 承担）', 'https://www.sec.gov/Archives/edgar/data/1819989/000095010326008635/dp248110_ex9901.htm', 'Cipher Stingray（AWS 70MW）'),
    ('construction-cost-shell-per-it-mw-riot-rockdale-amd', '2026-01-16', 3.6, '改造 capex 8,980 万美元 ÷ 25MW', 'https://www.sec.gov/Archives/edgar/data/1167419/000110465926004551/riot-20260116xex99d1.htm', 'Riot Rockdale（AMD 25MW，改造既有矿场）'),
    ('construction-cost-shell-per-it-mw-riot-rockdale-191mw', '2026-08-10', 11.5, '投资者材料示意 1,100–1,200 万美元/IT MW 区间中值', 'https://www.sec.gov/Archives/edgar/data/1167419/000110465926093406/riot-20260810xex99d1.htm', 'Riot Rockdale（191MW 前沿实验室租约）'),
]
for s, d, v, a, u, site in SHELL_CAPEX:
    add(s, d, v, '$M/MW', 'estimate', u, 'benchmark', 'M11', region='north-america', assumptions=a + '；公司公告的预期值，非决算', note=f'带电壳建设成本，每关键 IT MW；{site}', card='shell-lease-terms', frequency='default')

# Powered-shell lease rent per critical IT MW per year, derived from disclosed nominal contract totals (author calculation).
SHELL_RENT = [
    ('2025-02-26', 10.2e9, 12, 590, 'Core Scientific–CoreWeave 六站点', 'https://www.sec.gov/Archives/edgar/data/1839341/000162828025008312/ex991-coreweavepressrelease.htm'),
    ('2025-08-14', 3.7e9, 10, 200, 'TeraWulf–Fluidstack Lake Mariner（200+MW，修正毛租约）', 'https://www.sec.gov/Archives/edgar/data/1083301/000110465925078084/tm2523008d2_ex99-1.htm'),
    ('2025-09-25', 3.0e9, 10, 168, 'Cipher–Fluidstack Barber Lake（最低合同价值）', 'https://www.sec.gov/Archives/edgar/data/1819989/000095010325012168/dp234624_ex9902.htm'),
    ('2025-10-28', 9.5e9, 25, 168, 'TeraWulf–Fluidstack Abernathy 合资（25 年）', 'https://www.sec.gov/Archives/edgar/data/1083301/000110465925102858/tm2529509d1_ex99-1.htm'),
    ('2025-11-03', 5.5e9, 15, 216, 'Cipher–AWS Black Pearl（三净，3% 递增）', 'https://www.sec.gov/Archives/edgar/data/1819989/000095010326001480/dp240991_ex9901.htm'),
    ('2025-12-17', 7.0e9, 15, 245, 'Hut 8–Fluidstack River Bend（三净，3% 递增）', 'https://www.prnewswire.com/news-releases/hut-8-signs-15-year-245-mw-ai-data-center-lease-at-river-bend-campus-with-total-contract-value-of-7-0-billion-302644600.html'),
    ('2026-01-16', 0.311e9, 10, 25, 'Riot–AMD Rockdale（修正毛租约）', 'https://www.sec.gov/Archives/edgar/data/1167419/000110465926004551/riot-20260116xex99d1.htm'),
    ('2026-05-06', 9.8e9, 15, 352, 'Hut 8 Beacon Point 第一份（三净，3% 递增）', 'https://www.sec.gov/Archives/edgar/data/1964789/000110465926055894/hut-20260506xex99d1.htm'),
    ('2026-06-08', 2.0e9, 15, 70, 'Cipher–AWS Stingray（三净，3% 递增）', 'https://www.sec.gov/Archives/edgar/data/1819989/000095010326008635/dp248110_ex9901.htm'),
    ('2026-07-06', 19.0e9, 20, 401, 'TeraWulf–Anthropic Justified Data（20 年）', 'https://www.sec.gov/Archives/edgar/data/1083301/000110465926080583/tm2619468d1_ex99-1.htm'),
    ('2026-08-10', 9.1e9, 20, 191, 'Riot Rockdale–前沿 AI 实验室（20 年）', 'https://www.sec.gov/Archives/edgar/data/1167419/000110465926093406/riot-20260810xex99d1.htm'),
]
for d, total, years, mw, deal, u in SHELL_RENT:
    v = round(total / years / mw / 1e6, 3)
    add('shell-lease-rent-per-it-mw-year', d, v, '$M/MW·年', 'estimate', u, 'rent', 'M11', region='north-america',
        assumptions=f'名义合同总额 {total/1e9:.2f} 十亿美元 ÷ {years} 年 ÷ {mw} 关键 IT MW；含年递增的期均值，非首年租金；毛租约与三净租约口径不同', note=f'带电壳租约期均租金；{deal}', card='shell-lease-terms', frequency='default')

# ---------------------------------------------------------------- colocation asking rents and REIT yields
COLO = [
    ('colo-asking-rent-nova-250-500kw', '2026-03-31', 212.5, '190–235 美元/kW/月区间中值', CBRE_GLOBAL, '北弗吉尼亚 250–500 kW 托管报价', 'north-america'),
    ('colo-asking-rent-chicago-250-500kw', '2026-03-31', 215.0, '200–230 美元/kW/月区间中值，同比 +14.7%', CBRE_GLOBAL, '芝加哥 250–500 kW 托管报价（北美最高）', 'north-america'),
    ('colo-asking-rent-nova-10mw-plus', '2026-06-30', 172.5, '160–185 美元/kW/月区间中值', CBRE_NOVA, '北弗吉尼亚 10 MW 以上报价', 'north-america'),
    ('colo-asking-rent-frankfurt-250-500kw', '2026-03-31', 250.0, '235–265 美元/kW/月区间中值（CBRE 美元折算，欧洲最高）', CBRE_GLOBAL, '法兰克福 250–500 kW 托管报价', 'europe'),
    ('colo-asking-rent-singapore-250-500kw', '2026-03-31', 403.0, 'CBRE 均值（区间 330–475）', CBRE_GLOBAL, '新加坡托管报价（全球最高）', 'asia-pacific'),
    ('colo-asking-rent-tokyo-250-500kw', '2026-03-31', 280.0, 'CBRE 美元口径平均报价', CBRE_GLOBAL, '东京托管报价', 'asia-pacific'),
    ('colo-asking-rent-sydney-250-500kw', '2026-03-31', 188.0, 'CBRE 美元口径平均报价', CBRE_GLOBAL, '悉尼托管报价', 'asia-pacific'),
    ('colo-asking-rent-hongkong-250-500kw', '2026-03-31', 295.0, 'CBRE 美元口径平均报价（上年 270）', CBRE_GLOBAL, '香港托管报价', 'asia-pacific'),
]
for s, d, v, a, u, label, region in COLO:
    add(s, d, v, '$/kW/月', 'research', u, 'rent', 'M01', region=region, assumptions=a, note=label + '；挂牌报价，非成交价', card='cbre-jll-pricing-europe-apac')
add('colo-wholesale-rent-flapd-20mw-plus-eur', '2026-05-14', 145.0, 'EUR/kW/月', 'research', CBRE_EU_WHOLESALE, 'rent', 'M01', region='europe',
    assumptions='CBRE：法兰克福、阿姆斯特丹、都柏林、巴黎 20 MW 以上批发定价 145 欧元/kW（伦敦 145 英镑）；2026 年均价预计 +12%', note='新闻稿未明示按月计，行业惯例为每 kW 每月', card='cbre-jll-pricing-europe-apac')
add('colo-rent-new-lease-dlr', '2026-06-30', 183.0, '$/kW/月', 'company', 'https://www.sec.gov/Archives/edgar/data/0001297996/000110465926086270/dlr-20260723xex99d1.htm', 'rent', 'M01', region='global',
    assumptions='Digital Realty 2026Q2 新签租约年化 GAAP 基础租金（100% 权益 129.8 MW，3.07 亿美元/年）折合', note='DLR 权益口径为 198 美元/kW/月', card='dlr-equinix-q2-2026')
add('vacancy-rate-na-cbre', '2026-06-30', 1.4, '%', 'research', CBRE_NA_H1, 'market', 'M01', region='north-america',
    assumptions='CBRE 北美 8 个主要市场托管空置率（库存 10,903 MW）', note='CBRE H1 2026；与 vacancy-rate-na（JLL 全北美约 1%）口径不同，另开序列', card='cbre-jll-pricing-europe-apac')
add('reit-development-yield-dlr', '2026-06-30', 11.5, '%', 'company', 'https://www.sec.gov/Archives/edgar/data/0001297996/000110465926086270/dlr-20260723xex99d1.htm', 'benchmark', 'M11',
    assumptions='Digital Realty 8-K 开发表：在建 1,402 MW 平均预期稳定现金收益率（Americas 11.8%、EMEA 10.4%），税前，按总投资与预期 NOI', note='REIT 开发项目稳定收益率', card='dlr-equinix-q2-2026', frequency='default')

# ---------------------------------------------------------------- China unit economics
add('cn-idc-ebitda-per-mw-gds', '2026-06-30', 220.0, '万元/MW·年', 'company', GDS_CALL, 'benchmark', 'M14', region='CN',
    assumptions='万国数据 CFO 电话会：在手订单平均调整后 EBITDA 每 MW', note='对应资本开支约 2,000 万元/MW，成本收益率约 11%（作者计算）', card='china-idc-companies', frequency='default')
add('cn-idc-capex-per-mw-gds', '2026-06-30', 2000.0, '万元/MW', 'company', GDS_CALL, 'benchmark', 'M14', region='CN',
    assumptions='万国数据 CFO 电话会：在建新产能平均资本开支每 MW', note='万国数据 2026Q2', card='china-idc-companies', frequency='default')
add('cn-colo-mrr-per-cabinet-vnet', '2026-06-30', 9799.0, '元/机柜/月', 'company', VNET_Q2, 'rent', 'M14', region='CN', note='世纪互联 2026Q2 零售 IDC 每机柜月收入；零售利用率 64.5%', card='china-idc-companies')
add('cn-reit-fee-per-kw-month-gds', '2026-06-30', 570.0, '元/kW/月', 'company', 'https://news.qq.com/rain/', 'rent', 'M14', region='CN',
    note='南方万国数据中心 REIT 2026 中报托管费单价（含税）；计费率 97.95%', card='china-idc-companies')
CN_POWER = [
    ('cn-dc-power-price-zhongwei', '2026-03-17', 0.36, 'https://www.news.cn/politics/20260317/7b4eb07c97554dada8ad61b69a1aeee7/c.html', '宁夏中卫数据中心用电价格（新华网）', 'company'),
    ('cn-dc-power-price-ulanqab', '2026-08-14', 0.335, 'https://news.china.com/socialgd/10000169/20260814/49675354.html', '乌兰察布到户电价 0.32–0.35 元区间中值（阿里云表述）', 'media'),
    ('cn-dc-power-price-east-south', '2026-08-14', 0.75, 'https://news.china.com/socialgd/10000169/20260814/49675354.html', '华东、华南数据中心电价 0.6–0.9 元区间中值（阿里云表述）', 'media'),
    ('cn-dc-power-price-helinger', '2024-12-10', 0.33, 'https://cnews.chinadaily.com.cn/a/202412/10/WS6757aed8a310b59111da7ec1.html', '内蒙古和林格尔新区电力交易平均到户价', 'media'),
    ('cn-dc-power-price-guian', '2022-03-13', 0.35, 'https://www.thepaper.cn/newsDetail_forward_17067828', '贵安新区直管区大型数据中心电价（招商政策）', 'media'),
]
for s, d, v, u, label, grade in CN_POWER:
    add(s, d, v, '元/kWh', grade, u, 'power-price', 'M14', region='CN', assumptions=label if '中值' in label else None, note=label, card='china-policy-costs', frequency='default')

# ---------------------------------------------------------------- power prices (US, EU, APAC) and capacity markets
EIA_STATES = {'tx': '得州', 'va': '弗吉尼亚', 'or': '俄勒冈', 'oh': '俄亥俄', 'az': '亚利桑那', 'ga': '佐治亚', 'us': '全美'}
EIA_2026_07 = dict(tx=7.07, va=10.07, **{'or': 8.92}, oh=10.95, az=9.35, ga=10.03, us=9.77)
EIA_2025 = dict(tx=6.55, va=9.45, **{'or': 8.28}, oh=8.52, az=8.10, ga=7.81, us=8.62)
EIA_2024 = dict(tx=6.12, va=8.99, **{'or': 8.05}, oh=7.10, az=7.90, ga=7.21, us=8.13)
for st, name in EIA_STATES.items():
    add(f'industrial-power-price-us-{st}', '2024-12-31', EIA_2024[st], '¢/kWh', 'regulatory', EIA_B, 'power-price', 'M04', region='north-america', note=f'EIA 表 5.6.B 工业部门平均零售价 2024 全年终值，{name}', card='power-price-benchmarks', frequency='annual')
    add(f'industrial-power-price-us-{st}', '2025-12-31', EIA_2025[st], '¢/kWh', 'regulatory', EIA_B, 'power-price', 'M04', region='north-america', note=f'EIA 表 5.6.B 工业部门平均零售价 2025 全年初步值，{name}', card='power-price-benchmarks', frequency='annual')
    add(f'industrial-power-price-us-{st}', '2026-07-31', EIA_2026_07[st], '¢/kWh', 'regulatory', EIA, 'power-price', 'M04', region='north-america', note=f'EIA 表 5.6.A 工业部门平均零售价 2026 年 7 月初步值，{name}；2025-07 对比见研究卡', card='power-price-benchmarks', frequency='annual')
add('pjm-capacity-price-bra-rto', '2025-07-22', 329.17, '$/MW-日', 'regulatory', PJM_2627, 'power-price', 'M04', region='north-america',
    note='PJM 2026/2027 交付年基础剩余拍卖 RTO 出清价（UCAP），所有区域按价格上限出清；出清总额 161 亿美元', card='power-price-benchmarks', frequency='annual')
add('pjm-capacity-price-bra-rto', '2025-12-17', 333.44, '$/MW-日', 'regulatory', PJM_2728, 'power-price', 'M04', region='north-america',
    note='PJM 2027/2028 交付年 BRA RTO 出清价（临时价格上限）；低于可靠性要求 6,516.6 MW；出清总额 164 亿美元', card='power-price-benchmarks', frequency='annual')
add('ercot-realtime-all-in-power-cost', '2025-12-31', 38.0, '$/MWh', 'research', 'https://www.potomaceconomics.com/wp-content/uploads/2026/06/2025-State-of-the-Market-Report-for-ERCOT.pdf', 'power-price', 'M04', region='north-america',
    assumptions='Potomac Economics（ERCOT IMM）2025 State of the Market：负荷加权实时能量价 + 辅助服务 + uplift，约 38（2024 约 34）', note='ERCOT 2025 年全口径实时电力成本', card='power-price-benchmarks', frequency='annual')
EU = {'ie': ('爱尔兰', 25.52), 'de': ('德国', 22.64), 'nl': ('荷兰', 19.91), 'no': ('挪威', 8.27), 'se': ('瑞典', 9.70), 'fi': ('芬兰', 7.48), 'eu': ('欧盟', 18.37)}
for cc, (name, v) in EU.items():
    add(f'industrial-power-price-{cc}-band-ic', '2025-12-31', v, '欧分/kWh', 'regulatory', EUROSTAT, 'power-price', 'M04', region='europe',
        note=f'Eurostat nrg_pc_205 非居民电价 2025 下半年，500–2,000 MWh 消费档（band IC），不含增值税及可退税项，{name}', card='power-price-benchmarks', frequency='annual')
add('industrial-power-price-my-tnb-base-tariff', '2025-07-01', 45.62, '仙/kWh', 'regulatory', 'https://www.tnb.com.my/assets/newsclip/27122024c.pdf', 'power-price', 'M04', region='asia-pacific',
    note='马来西亚半岛 TNB RP4 基础电价（RP3 为 39.95），2025-07-01 起；非居民按能量费 + 容量费 + 网络费 + 零售费 + AFA 计费', card='power-price-benchmarks', frequency='annual')
add('industrial-power-price-jp-special-hv', '2026-06-30', 17.85, '日元/kWh', 'media', 'https://pps-net.org/unit', 'power-price', 'M04', region='asia-pacific',
    note='新電力ネット汇总的特别高压平均电价（2026 年 6 月），不含消费税与可再生能源附加费；非监管机构原始页面', card='power-price-benchmarks', frequency='annual')
add('industrial-power-price-id-pln-i4', '2026-07-01', 996.74, '卢比/kWh', 'media', 'https://www.archyde.com/pln-electricity-tariffs-remain-unchanged-for-september-2026/', 'power-price', 'M04', region='asia-pacific',
    note='印尼 PLN I-4/TT（≥30,000 kVA）工业电价 2026Q3 维持不变（媒体转述能矿部）；官方页面未能核对', card='power-price-benchmarks', frequency='annual')



def main():
    apply = '--apply' in sys.argv
    problems = [(r['series_id'], r['as_of'], p) for r in R for p in price_errors(r)]
    assert not problems, problems
    path = ROOT / 'data/prices.json'
    doc = json.loads(path.read_text(encoding='utf-8'))
    keys = {(x['series_id'], x['as_of']) for x in doc['records']}
    dup = {}
    for r in R:
        k = (r['series_id'], r['as_of'])
        assert k not in dup, f'duplicate in feedback set: {k}'
        dup[k] = r
    new = [r for r in R if (r['series_id'], r['as_of']) not in keys]
    print(f'feedback records: {len(R)}; new: {len(new)}; already present: {len(R) - len(new)}; series: {len({r["series_id"] for r in R})}')
    if apply and new:
        doc['records'].extend(new)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('appended to data/prices.json')


if __name__ == '__main__':
    main()
