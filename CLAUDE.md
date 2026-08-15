# CLAUDE.md — 会话协议（每个会话自动加载）

## 会话记忆规则（最高优先级）

会话是隔离且易失的，仓库才是持久层。因此：

1. **开场必读** `docs/DECISIONS.md` —— 用户已确立的原则和历史决策都在里面，不要重新发明或违背。
2. **收尾必写**：会话中用户提出的要求、拍板的决策、否决的方案，追加到 `docs/DECISIONS.md`
   的会话决策记录（倒序区）并 commit。**用户的想法丢一条都算事故。**
3. commit 信息延续现有风格：中文、一句话战报 + 要点列表，本身就是项目日志的一部分。

## 铁律（详见 docs/DECISIONS.md 与 framework/01_data_standards.md）

- 四种口径（GW/TWh/美元/需求模型）永不混加；只有 L8+ 通电投运计入当期供给。
- 官方未披露的容量**不许推算**——留白是纪律不是缺口；理由写进 notes。
- 知识层 research/Mxx.md 是项目主体；改数据必须过 `python3 pipeline/validate.py`（0 warnings 才算过）。
- 零依赖：纯 Python 标准库，前端单文件 HTML，不引入 npm/pip 依赖；第三方库本地化到 assets/vendor。
- 二进制不进 git；研报库只进索引和打分表。

## 常用命令

```bash
python3 pipeline/validate.py    # 改完数据必跑
python3 pipeline/verify.py      # 核验队列（今天该查什么）
python3 pipeline/reading_queue.py  # 精读队列（该读什么文献）
python3 -m http.server 8000     # 本地看仪表盘
```

## 环境注意

- 云端会话网络策略屏蔽 sec.gov：update_ciks.py / fetch_sec.py 只能在用户本机（launchd）跑。
- 研报库本体（docs/library/）不在 git 里，云端会话只能用 LIBRARY_SCORES.csv 的摘要工作。
- 文献打分用 framework/04_reading_scoring_standard.md（标准 v2，七维度）；逐篇精读由本地
  datacenter-reader 项目执行（计划与启动指令见 docs/local_reader/），批次产物回传
  docs/inbox/scored_batches/ 与 digest_drafts/，云端会话负责审计合并与消化。
