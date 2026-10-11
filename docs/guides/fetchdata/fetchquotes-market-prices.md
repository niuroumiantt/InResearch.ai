# D 员工任务书：fetchquotes 报价与市场观察

先读 [共同交付规范](delivery-contract.md) 和 [开发与验收](implementation-and-acceptance.md)。你记录特定条件下的报价快照，不承诺成交价、可得库存或投资收益。

## 目的与对象

建立产品/服务配置在地区和时间上的价格记录，区分公开标价、按需价、承诺折扣、抢占价、二手挂牌和实际成交。报价身份包括供应商、服务 SKU/型号、配置、地区、计费条件；每次有变化的快照追加，不覆盖昨天。

## 首批来源

1. **AWS**：[官方批量价目下载说明](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api-fetching-price-list-files-manually.html) 与 [价目字段说明](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/finding-prices-in-service-price-list-files.html)。从官方服务/地区索引发现当前有效文件，先用 EC2 两个地区、少量明确 GPU 实例。不要直接拉全球完整索引到内存，也不要猜 GPU 单卡价格。
2. **第二家公开 GPU 云供应商**：先核对 [Google Cloud GPU 价格](https://cloud.google.com/products/compute/gpus-pricing?hl=en) 的实际公开 GPU SKU、地区及计费条件。页面没有完整实例成本时，只交 GPU 附加费并说明 CPU/内存等未含，不能当完整机器报价；必要时选择另一家能公开给出完整条件的供应商并登记理由。

两家、两个地区合计至少 10 个有效报价样本。地区无该产品/无公开价时记缺口，不拿其它地区补而不标。后续再接二手 GPU/机柜挂牌，先小样本验证状态和额外费用。

## 必须保留的字段

| 指标/维度 | 要求 |
|---|---|
| quote.price | 原币种、金额、计价单位、采样时刻，kind=offer；不是成交 |
| product/configuration | GPU 型号/数量、CPU/内存、本地盘、网络及租赁服务 SKU，未知留空 |
| commercial_terms | 地区、OS/租户、按需/承诺期限/抢占、最低消费、购买量、有效期、税/运费/存储/带宽/服务费是否包含 |
| availability | 页面宣称的库存/可用性及时间；未验证不能写可立即租用 |
| used_equipment | 新旧/成色、保修、含税/运费、挂牌/拍卖/成交性质、唯一 listing ID |

服务 `instance-hour` 不能直接当 `GPU-hour`。需要折算时另交 calculated 候选，包含 GPU 数量和公式，原服务价保留。官方价格列表是信息性标价，不能当实际账单、合同折扣或成交承诺。[AWS 的说明](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/finding-prices-in-service-price-list-files.html) 明确说明该性质。

## 采集步骤与周期

1. 登记供应商与官方价目入口、两个地区和配置白名单，人工验证 3 个完整样本。
2. 保存原始 JSON/HTML；动态页先找公开且合法的数据接口，没有再按实际许可使用浏览器，保存最终显示条件。不能只截图一个价格数字。
3. 提取价格、单位和条件，区分标价有效日与本次采样日。旧价目文件补历史可以，但不能把其中有效日当今天。
4. 每日一次检查公开标价；有日内需求时再明确批准频率和限速预算，不能为多产数据每分钟抓。有效期结束/下架另记状态，不删历史报价。每周抽查 10 个仍在用的 SKU 与页面一致性。

## 本队验收

交两个供应商的配置/地区清单、10 个真实报价及费用包含表、版本/下架/空库存样例。回归包含按需与承诺价不混、GPU 附加费与整机不混、挂牌与成交不混、币种和税不丢、历史价不当现价。未公开价不估成 0；价格波动不直接成为来源冲突，先比较采样时点和配置。

2026-10-11 核查公共入口；实际产品、地区和价格由员工在执行时重新确认，文档不写死价格。
