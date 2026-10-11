# 开发步骤、验收指标与交还清单

## 代码骨架

```text
fetchdata/
  README.md
  core/                     请求、来源身份、哈希、版本、包构建、台账
  registry/sources.json      来源唯一归属
  registry/metrics.json      指标名、单位、范围解释
  teams/fetchstat/           各队配置、适配器、入口
  teams/fetchfilings/
  teams/fetchreports/
  teams/fetchquotes/
  tests/fixtures/            少量合成或可再分发的固定样例
  scripts/                  离线验包与运维命令
  deploy/                   每队独立任务配置；凭据不入库
```

Python 公共内核用标准库；特殊 PDF/浏览器解析依赖由需要它的队隔离、锁版本并说明理由，不让所有下载器依赖浏览器。取文件与内容提取分开：同 SHA 不重复下载/提取，提取器更新可以复用原件重算派生记录。

运行数据 `~/.local/share/fetchdata/`，日志和状态 `~/.local/state/fetchdata/`，源码 `~/code/fetchdata`。Spark 存量资料仍留原目录，不能擅自搬走/删除/改名。登记 `source_id → owner_team + execution_host + cadence + adapter + public_entry + last_attempt + last_success + next_due`，研究 target_id 作为可选优先级，不是来源开工许可。

公司官方披露及 ESG 归 filings；学术/第三方研究及标准归 reports；官方地域统计/费率归 stat；商业报价归 quotes。同一 URL 由一个队取一次，其它队引用同一原件。inews 给新闻线索，不能四队各重新抓全部新闻；产品规格仍由 Fetchspec 主责。

## 必须交出可直接执行的命令

接口负责人在第 1 天统一下面命令及参数，四队实现一致接口。**以下是待建 fetchdata 的交付要求，当前 inresearch 不存在这些生产命令。**

```sh
python3 -m fetchdata check-config --team fetchstat
python3 -m fetchdata run --team fetchstat --source <source_id> --limit 3 --output <私有包目录>
python3 -m fetchdata import-existing --team fetchstat --inventory <授权只读清单> --limit 3 --output <私有包目录>
python3 -m fetchdata run --team fetchstat --incremental --output <私有包目录>
python3 -m unittest discover -s tests
python3 scripts/validate_collector_handoff.py <私有包目录>
```

其它队换 team 即可；说明运行所需 Python 版本、环境变量名、如何取得合法访问凭据、输出位置、退出码、重试/恢复方法。上传另走经联调的交付适配器，不预设一个不存在的 HTTP 接口。导入存量允许只读内容寻址引用，但第一批员工交还包要带用于验收的原件；实际 GB 级批量交付可在接收端验证已有 SHA 后复用，不二次搬运。

## 公共内核验收场景

1. 下载真实小样本，保留原生字节、响应内容类型、最终 URL；检查内容，不只看 HTTP 200。分页列表取齐或明确 partial。
2. 相同输入跑两次：内容文件不增加、候选身份稳定、首次取得/接收不被刷新；第二次运行有去重计数。
3. 同 URL 内容变动：新 SHA、新版本，旧文件可读；JSON 字段变化不能悄悄漏解析，记录解析器版本。
4. 断网、429、500、坏文件、单项解析失败：有界退避、每主机限速、失败台账、其它源继续，重启不漏未完成项。不因一个地区无数据使整队停止。
5. 身份不明、缺时间、原生区间、计划与实际、脚注改变、同口径冲突：保留为候选/线索，不填零、不伪造身份、不覆盖历史。
6. 密钥不进源码、URL 参数日志或包；受限原件不转公开服务。包路径无绝对路径、`..`、符号链接。大文件流式哈希，内存有界。
7. 真实接收取得 delivery_id/SHA 对应回执；相同包重放无重复、首次接收不变。逐条采用与网站变化另验，不能只截图上传成功页。

## 首周验收看什么

| 指标 | 算法/通过条件 |
|---|---|
| 原件可追溯 | 每条交付候选都能回到原件、来源 URL 和具体位置；100%，坏条隔离补交 |
| 字节完整性 | 原件全部通过 SHA/路径检查；100%，不要求所有来源抓取都成功 |
| 样本真实性 | 首包每队抽 10 条（不足全查）逐条核引文、对象、单位、范围和时间；发现错误修复并检查同适配器受影响记录 |
| 缺失诚实性 | 无披露不填零、无时间不造日期、身份不明不强配；100% 的抽查项符合 |
| 重放/版本 | 场景 2、3 实际通过；提供前后计数及文件 SHA |
| 运行覆盖 | 报计划到期源、实际尝试源、成功源、未变化源、失败源、受阻源、未尝试源；不得从分母删除失败，首周记录基线后定可靠性 SLO |
| 信息产出 | 分别报新原件、重复原件、新候选、身份未定、冲突、研究端已接收、已审核、已采用、已上线；下载量不等于采用量 |
| 更新延迟 | 已知披露时间到下载、下载到接收、接收到审核分别计量；未知时间不纳入伪精确均值，另报数量 |
| 资源 | 每次耗时、下载字节、峰值内存/磁盘增量、重试数；先小包实测再定扩批预算 |

首周范围是工作目标，来源没披露足够条目时附缺口即可；不能为了指标重复切碎、推断不存在的值或强绑定模型。采用率不是员工单方负责的硬门槛，研究端需要提供审核反馈及容量。

## run-report.json 与 errors.jsonl

run-report 至少包含 `run_id/team/started_at/finished_at`、`counts`（见模板）、`bytes_downloaded`、`duration_seconds`、`collector_revision`；首周由执行机实际测量。每个错误包含 source_id、阶段、错误类型、时刻、是否可重试、下次动作；不含 token/cookie 或私有正文。授权不足、无披露、解析失败分别记录，不能统称网络失败。

## 员工完成定义

交还 README、源码 PR 与提交、来源/指标登记、真实验包通过包、测试报告、实际运行台账、错误和缺口清单。负责人先签“员工交付验收”，接收端后签“原件接收”，研究端再给“逐条审核/正式采用”，发布端最后给“网站回执”。四个结果独立记录。

负责人每周反馈不超过一页：哪些源成功、哪类提取出错、什么正式采用、什么还未接通；将错误样本固化为适配器回归。不要让员工等待研究需求关联后才继续取有来源的信息。
