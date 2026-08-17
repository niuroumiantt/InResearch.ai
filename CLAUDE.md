# CLAUDE.md — 会话协议（每个会话自动加载）

## 人机互动协议（2026-08-17 用户拍板，最高优先级，所有窗口适用）

**用户没有明确拒绝 ≠ 同意，等于「他没看到」。** 用户同时在处理多条线，
提议埋在长回复末尾就是丢了。因此：

1. **未决项必须顶出来**：写在回复**开头**，不要放在结尾"要我做吗？"里。
   每次开工先报一次未决清单，哪怕上次刚报过。
2. **未决清单维护在 `docs/DECISIONS.md` 顶部的「待拍板（未决）」区**，
   开场必读、收尾必更新。已决的移进正文并注明批复日期。
3. **分两类，处置不同**：
   - **只有用户能定的**（商业/合规判断、含个人信息的删除、对外发布口径、花钱）
     → **阻塞并反复提醒**，不得默认执行、不得替他决定；
   - **其余一切** → **会话自行决断并告知**，不要攒着问。用户明确说过
     「我不想成为 bottleneck」——攒问题让他批，就是把他变成 bottleneck。
4. 会话自己做的决断要写进 DECISIONS，注明"云端判断，请复核"，
   用户日后否决即改——**先做后审，不是先问后做**。

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
python3 pipeline/workorder.py      # 工单队列（每个模块下一步该做什么；= 声明 − 现状）
python3 pipeline/blindspot.py      # 盲区体检（库里有但分类器看不见的材料）
python3 pipeline/facts.py          # 事实层校验 + 可比性判定（口径不同的数拒绝并列）
python3 -m http.server 8000     # 本地看仪表盘
```

## 环境注意

- 云端会话网络策略屏蔽 sec.gov：update_ciks.py / fetch_sec.py 只能在用户本机（launchd）跑。
- 研报库本体（docs/library/）不在 git 里，云端会话只能用 LIBRARY_SCORES.csv 的摘要工作。
- 文献打分用 framework/04_reading_scoring_standard.md（标准 v2，七维度）；逐篇精读由本地
  datacenter-reader 项目执行（计划与启动指令见 docs/local_reader/），批次产物回传
  docs/inbox/scored_batches/ 与 digest_drafts/，云端会话负责审计合并与消化。
