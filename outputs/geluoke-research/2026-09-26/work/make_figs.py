#!/usr/bin/env python3
import sys, os, subprocess
sys.path.insert(0,'/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/tools')
import charts
F='/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/figs'
def out(name,svg):
    open(os.path.join(F,name+'.svg'),'w').write(svg)
    open(os.path.join(F,name+'.html'),'w').write('<html><body style="margin:0;background:#0B1F3A"><img src="%s.svg" style="display:block"></body></html>'%name)
    subprocess.run(['python3','/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/tools/render.py',os.path.join(F,name+'.html'),os.path.join(F,name+'.png'),'--width','640','--height','400','--dpr','2','--full'],check=True)
# Fig 1: Jupiter timeline
rows=[
 {'when':'2025-09-19','head':'规划与地方许可','text':'多纳安娜县批准最高1650亿美元工业收益债券；园区规划2.45GW，目标2028年投运','state':'done'},
 {'when':'2026-04-27','head':'供电方案改为场内燃料电池','text':'甲骨文放弃燃气轮机，改用Bloom Energy燃料电池；燃料依赖Energy Transfer约18英里天然气管道','state':'done'},
 {'when':'2026-03／07','head':'管道路权两次被州土地办公室拒批','text':'FERC文件显示管道投运由2026年8月推迟至2027年2月1日；燃料电池空气许可待裁决','state':'now'},
 {'when':'2026-09-24','head':'甲骨文向STACK发出不可抗力通知','text':'路透：合同规定供电由甲骨文负责、租约不得终止；通知意在未按期投运时推迟付款，并非退出','state':'now'},
 {'when':'2026-09-25','head':'资金侧反应','text':'Bloom转述甲骨文重申2.4GW合同；180亿美元银团贷款二级市场价低于面值90%；彭博：摩根士丹利称将拖累数据中心债务','state':'now'},
 {'when':'2026-11-23','head':'下一个可验证节点','text':'新墨西哥州环境部对燃料电池空气许可的裁决截止日；管道投运目标2027年2月1日','state':'next'},
]
out('fig_jupiter', charts.vtimeline(rows,'甲骨文木星园区：供电链条上的时间点','新墨西哥州多纳安娜县 · 阶段与日期以彭博、路透及州政府文件为准','来源：Bloomberg、Reuters、Albuquerque Journal、El Paso Matters；不可抗力条款为匿名信源转述',note_lines=['蓝点：已完成　金点：进行中／本期新增　空心点：待定']))
# Fig 2: US power cost cards
rows2=[
 {'head':'得州 · 州长／TCEQ／ERCOT／总检察长','lines':['9月21日起暂停数据中心相关许可，待ERCOT审计（报告目标12月10日）','≥75MW通电审批自8月3日暂停；9月24日起调查未申报用水项目，初步涉及18个县'],'color_index':3},
 {'head':'TVA（七州） · 数据中心专属费率10月1日生效','lines':['电费平均上调约10%；≥5MW新建或扩建负荷缴容量承诺费，约150万美元/MW（区域媒体口径，分3–5年）','现有数据中心三个财年过渡；亨茨维尔市议会9月24日审议合同修正案'],'color_index':3},
 {'head':'El Paso Electric／Meta埃尔帕索 · 366MW电厂','lines':['行政法官9月23日建议：客户免担资本与运营成本方可批准CCN','前5年专供Meta 1GW园区；PUCT表决未排期'],'color_index':3},
 {'head':'美国能源部 SPARK · 9月24日入选名单','lines':['19亿美元联邦资金，26州31个输电项目，总投资52.5亿美元，称释放逾23GW并网容量','仅为入选，正式资助协议未签'],'color_index':0},
 {'head':'俄勒冈 Pacific Power（背景：9月16日和解协议）','lines':['≥20MW新建设施自付新增电源与线路成本；>100MW另缴1美分/kWh；合同最短10年','OPUC尚未批准，目标11月13日裁定'],'color_index':1},
 {'head':'加州（背景：9月21日签署7项法案）','lines':['SB 886：输电升级费由数据中心承担，适用2027年1月1日起新签接入协议','AB 2619：申领营业执照前须向供水方提交用水估算'],'color_index':1},
]
out('fig_us_power', charts.table_cards(rows2,'美国：供电成本与时间正在转给数据中心','黄色：得州／TVA／埃尔帕索（本期）　蓝色：联邦资金　橙色：背景','来源：得州州长办公室、得州总检察长、ERCOT、WAFF／256 Today、Inside Climate News、美国能源部、俄勒冈PUC、加州州长办公室',note_lines=['容量承诺费数值来自区域媒体转述，TVA正式费率表未公开']))
# Fig 3: funding stages
items=[
 ('Akamai–Anthropic 算力合同', 11.6, 0, '7年客户付款承诺 · 9月24日公告 · 机房位置未披露'),
 ('Cipher Digital Barber Lake', 9.0, 0, '20年合同收入由38亿升至90亿以上 · 9月25日'),
 ('Nscale IPO前可转债', 3.36, 1, '其中23.6亿已交割 · 英伟达10亿11月中旬到账'),
 ('CleanSpark 优先担保票据', 2.276, 1, '9月25日交割到账 · 票息7.875% · 2031年到期'),
]
out('fig_funding', charts.hbar(items,'当日数据中心资金：合同承诺与到账口径不同','单位：十亿美元；Cipher为合同期累计收入，Akamai为客户付款承诺，其余为融资','来源：Akamai 8-K、Cipher Digital 8-K、Nscale公告、CleanSpark 8-K','单位：十亿美元',vmax=13.0,legend=[(0,'合同承诺（客户付款义务）'),(1,'融资到账／已交割')]))
# Fig 4: Asia cards
rows4=[
 {'head':'印度 · 奥里萨邦','lines':['阿达尼子公司1GW园区提案获邦级HLCA批准；投资约1.04万亿卢比，Naraj划定约250英亩','电力、水源、分期与客户未披露'],'color_index':0},
 {'head':'印度 · 特伦甘纳邦','lines':['微软海得拉巴云区域启用（三可用区）；全邦已运营约300MW、在建约2GW','目标2029年达5GW（政策目标）'],'color_index':0},
 {'head':'印度 · 安得拉邦','lines':['部长口径：数据中心用电≥70%可再生；维沙卡帕特南用水由Polavaram左岸干渠调配','尚无正式政府令'],'color_index':0},
 {'head':'泰国','lines':['0.5MW及以上须向数字经济部登记（原则通过）；≥100MW超大规模拟须进工业区','标准拟10月中旬生效 · 166个项目暂停中'],'color_index':2},
 {'head':'马来西亚 · 森美兰','lines':['Tera Data Centers有条件购入221.665英亩，总价约10.13亿令吉（绿盛世合资EBP7）','交易条件与项目容量未披露'],'color_index':2},
 {'head':'印尼 · 巴淡岛','lines':['管理局要求数据中心自建海水淡化；预计2–3年内新增产水750→1000升/秒','居民因断水多次抗议'],'color_index':2},
]
out('fig_asia', charts.table_cards(rows4,'南亚与东南亚：土地、许可、电力与水条件','按已披露事实归纳；阶段以各地政府与公司口径为准','来源：Business Standard、Telangana Today、PTI、The Nation、Kaohoon、The Star、Antara、detik',note_lines=['蓝色：印度各邦　绿色：东南亚　数字均为披露口径，非本刊测算']))
print('figs done')
