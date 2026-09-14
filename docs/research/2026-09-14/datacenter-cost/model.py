"""Independent illustrative cost model. USD, 2026-09-14 assumptions, not market quotes."""
from pathlib import Path
import json,csv,math
P=Path(__file__).resolve().parent.parent
BASE=dict(it_mw=100,devices=50000,power_load=.70,pue=1.25,productive=.65,
          energy_price=.08,billed_kw=125000,demand_rate=12,
          facility=1200e6,utility=100e6,land=50e6,servers=3000e6,network=500e6,
          facility_life=15,it_life=5,rate=.08,fixed_opex=55e6,facility_opex=35e6,
          site_water_l=0.8,water_price=2)
def crf(r,n):return 1/n if r==0 else r*(1+r)**n/((1+r)**n-1)
def calc(a):
    e_it=a['it_mw']*1000*a['power_load']*8760
    kwh=e_it*a['pue'];h=a['devices']*8760*a['productive']
    components=dict(服务器资本年化=a['servers']*crf(a['rate'],a['it_life']),
        集群网络资本年化=a['network']*crf(a['rate'],a['it_life']),
        设施与接入资本年化=(a['facility']+a['utility'])*crf(a['rate'],a['facility_life']),
        土地机会成本=a['land']*a['rate'],
        电量费=kwh*a['energy_price'],计费需量费用=a['billed_kw']*a['demand_rate']*12,
        其他运营支出=a['fixed_opex'],现场水费=e_it*a['site_water_l']/1000*a['water_price'])
    total=sum(components.values())
    return dict(total=total,per_hour=total/h,e_it=e_it,kwh=kwh,hours=h,
        water_m3=e_it*a['site_water_l']/1000,components=components,
        it_share=(components['服务器资本年化']+components['集群网络资本年化'])/total,
        energy_share=(components['电量费']+components['计费需量费用'])/total,
        capex=sum(a[k] for k in ['facility','utility','land','servers','network']),
        facility_account=sum(components[k] for k in ['设施与接入资本年化','土地机会成本','电量费','计费需量费用','现场水费'])+a['facility_opex'])
R=calc(BASE)
tests=[('有效设备时间占比','productive',.45,.85),('IT经济寿命','it_life',3,7),('服务器采购金额','servers',2400e6,3600e6),('资本成本率','rate',.05,.12),('设施建设金额','facility',900e6,1500e6),('电量单价','energy_price',.04,.12),('全年PUE','pue',1.15,1.4)]
sens=[]
for label,key,lo,hi in tests:
    for v in [lo,hi]:
        a=BASE|{key:v};out=calc(a);sens.append(dict(label=label,key=key,input=v,total=out['total'],per_hour=out['per_hour'],change=out['per_hour']/R['per_hour']-1))
matrix=[dict(productive=u,energy_price=e,per_hour=calc(BASE|dict(productive=u,energy_price=e))['per_hour']) for u in [.35,.45,.55,.65,.75,.85] for e in [.04,.08,.12]]
delay=[dict(months=m,capital_carry=2000e6*((1+BASE['rate'])**(m/12)-1)) for m in [0,3,6,9,12]]
apac=[('中国内地四城组',5.6,7.1,8.6,22),('印度五城组',5.9,7.4,9.0,24),('印尼所列市场',6.6,8.3,11.2,25),('泰国曼谷',7.0,8.8,10.5,32),('马来西亚三市场',6.9,9.6,12.0,27),('新加坡',12.0,14.4,17.9,30),('日本东京与大阪',13.0,16.0,19.2,26)]
epoch=[('服务器',5021),('设施',1387),('网络',1167),('能源',594),('税项',143),('维护',120),('人工',40),('接入',20),('土地',13),('水',6)]
out=dict(assumptions=BASE,base=R,sensitivity=sens,matrix=matrix,delay=delay,apac=apac,epoch=epoch,
    model_note='参数均为研究假设；单因素敏感性保持其他参数不变，包括平均IT功率负荷。有效设备小时只适用于同一参考硬件配置，不是GPU代际、模型或任务之间的等效计算单位。年化成本采用恒定更新/持续服务近似，非15年逐期现金流、报价、利润预测或税后估值。')
(P/'model-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
with (P/'research/chart-data.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['figure','item','value','unit','source','scope'])
    for k,v in R['components'].items():w.writerow(['model-annual',k,v,'USD/year','M1','研究假设；资本年化及运营'])
    for label,lo,mid,hi,page in apac:
        for name,v in [('low',lo),('mid',mid),('high',hi)]:w.writerow(['apac',label+' '+name,v,'USD million/MW IT','S01 PDF p'+str(page),'报告规格区间；非统计置信区间；土地另计'])
    for k,v in epoch:w.writerow(['epoch',k,v,'USD million/year','S04','1GW IT建模情景；非真实工程'])
    for s in sens:w.writerow(['sensitivity',s['label']+'='+str(s['input']),s['per_hour'],'USD/productive-device-hour','M1','单因素；非联合预测'])
    for x in matrix:w.writerow(['matrix',str(x['productive'])+' / '+str(x['energy_price']),x['per_hour'],'USD/productive-device-hour','M1','平均功率负荷固定70%；非同质量模型比较'])
    for x in delay:w.writerow(['delay',x['months'],x['capital_carry'],'USD','M1','已占用20亿美元按8%年率滚动；未加入收入延后/违约/库存折损'])
assert math.isclose(R['kwh'],766500000)
assert math.isclose(R['water_m3'],490560)
assert math.isclose(calc(BASE|{'productive':.325})['per_hour'],2*R['per_hour'])
assert math.isclose(crf(0,5),.2)
assert math.isclose(sum(v for _,v in epoch),8511) # component rounding differs from source displayed total 8514
print(json.dumps(dict(base=R,sensitivity=sens,delay=delay),ensure_ascii=False,indent=2))
