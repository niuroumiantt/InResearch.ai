# 首页地图交互与容量核对（2026-10-03，m5）

## 目标与已定规则
用户授权实现、测试、合并和现有网站发布。替代首页园区/玩家直接跳页；桌面首屏地图及手机布局保留。主工作区 catalog-series-browser-test 未动；独立工作树 `~/.worktrees/inresearch.ai/homepage-map-audit-20261003`。

## 实现与核对
- 园区点打开可固定浮窗，详情独立链接；固定后空白、其他点、缩放和新闻刷新不替换，关闭/Escape 退出，筛选移除该点则关闭。首页玩家按钮只高亮当前范围对应点；主体下拉仍筛选。
- 95GW：事实 `hsbc2026-global-it-load-2025`，汇丰 2026-03-25 报告第32页登记引文，2025年全部IT负载估算；2030年205GW是预测。原件SHA `db10dd836b9d7a8bba841cb0bb4b10b9ca35395c5bf3e1c8070350b5d6266d0b`。本次核对事实记录；公开转载正文也写2025→2030，但摘要误写2026，未据摘要改年份。未重新取得内部PDF与机构底层统计表，仍为待交叉验证。转载入口 https://www.fxbaogao.com/detail/5320488 （不作为独立验证）。
- 样本核验2026-07-23—08-15，非统一2025年存量。120条原记录保留，2条portfolio排除，Frontier重复1条排除：117条项目记录，39条有容量、78条未知，103条定位、14条未定位。投运5918.2MW、建设1711.8MW、筹备21164MW；展示GW四舍五入。含云厂商集群，不冒充117个唯一物理园区。
- Frontier：`us-tx-shackelford-frontier` 指向 `us-tx-shackelford`，同县、同主体、同1.4GW与同官方公告，原字段/日期/阶段矛盾保留。官方日期2025-08-19、十栋、已动工但全容量不等于在建分期；不因后条较新自动覆盖主分期。官网 https://vantage-dc.com/news/vantage-data-centers-unveils-plans-for-frontier-a-25b-mega-campus-in-texas-to-meet-unprecedented-ai-demand/ 。去重仅令筹备22.564→21.164GW，开发/租户关系及来源并列保留，旧详情可读。
- 主键无重复、名称无完全重复；相同坐标两组（Equinix Ashburn/Google Loudoun、Google Papillion/Meta Sarpy）为不同主体的粗坐标，不自动合并。未穷尽全部集群/子园区边界。既有阿布扎比4GW是5GW减单列1GW的余额，已明示推导，未声称独立披露。既有容量字段未逐条重新核实额定/实际/设施定义或当前投运状态。
- 全球与样本年份、定义、覆盖及去重方法不齐，页面禁止相减和计算覆盖率，没有新增全球差额。

## 验收与发布
本地完成：全量1659单测通过（39.195s）；industry、datacenter_news、ui_skin浏览器套件通过；三档桌面与390/320手机完整viewBox/无横溢，浮窗固定/取消/关闭/Escape/新闻重绘与玩家仅高亮均通过。另实际鼠标点选、深色与手机浮窗截图已查看；玩家矩形样式已修正。严格数据校验0 warnings、registry 344对象/458问题、governance检查通过（1059文件）。CI、发布版本与线上验收完成后补记。截图/运行回执在 `~/.local/state/inresearch.ai/homepage-map-audit-20261003/`，不进Git。现行规范01/05与验收映射已逐项复审，不把清单刷新当审阅。

## 下一步与边界
完成最终测试、CI和发布后核对网站实际版本及Spark服务；不升级与本功能无关的Spark reader。无待用户决定项。真实触屏硬件、其他浏览器引擎和全球容量穷尽核验不在已有测试证明范围。
