# 爆炸图与团队协作架构

> 两个决定项目终局形态的设计：物理爆炸图（研究的第二根轴）与 GitHub 式模块协作（团队化的基础）。

## 一、数据中心爆炸图（Exploded View）

### 设计思想

现有 15 个模块是**研究角度轴**（市场/供给/电力/资本…）。爆炸图引入第二根轴——**物理部件轴**：
把一座数据中心按 BOM（物料清单）逐层炸开，每个部件挂接它的研究模块、供应商、价格序列、
研究结论。两根轴交叉，任何问题都能从"角度"或"部件"两个方向进入。

### 五层 BOM 结构（`framework/bom.json` 机器可读）

```
L1 园区层    电网接入 ｜ 变电站 ｜ 自备电源(燃机/柴发/燃料电池/核) ｜ 储能 ｜ 水源 ｜ 土地
L2 建筑层    楼宇结构 ｜ 消防 ｜ 安防 ｜ 办公与运维区
L3 机房层    机柜列 ｜ 配电(UPS/母线/PDU) ｜ 末端散热(CRAH/风墙/CDU) ｜ 布线 ｜ DCIM
L4 机柜层    服务器 ｜ 交换机 ｜ 歧管与快接 ｜ 机柜级电源(Power Shelf/BBU)
L5 部件层    GPU/ASIC ｜ CPU ｜ HBM/内存 ｜ NIC/DPU ｜ 光模块 ｜ 冷板 ｜ 电源模块 ｜ 硬盘
```

每个 BOM 节点的档案 = `{模块归属, 关联公司(companies), 价格/交期序列(prices), 研究结论(findings),
资料(library 分类), 状态(成熟/紧缺/技术切换中)}`。

### 呈现路径（渐进式，不一步登天）

1. **v1 交互爆炸图（SVG）**：分层侧视图，点击任何部件 → 弹出该部件档案卡（数据+结论+链接）
   ——纯前端可实现，进 `bom.html`；
2. **v2 三维模型**：three.js（本地 vendor，不走 CDN）做可旋转爆炸动画，档案卡逻辑复用 v1；
3. **数据先行原则**：先把 bom.json 的挂接关系填实（部件→模块→数据），视图只是渲染——
   这样"爆炸出来的每个部分都有研究、有数据、有结果"才不是空话。

## 二、GitHub 式模块协作（团队权限与合并）

### 核心洞察：这个仓库本身就是 Git——不需要自建权限系统，用 GitHub 原生机制

```
成员工作流：
  分支/fork → 只改自己负责的文件（research/M08.md、data 记录、docs/library 对应类目）
  → 提交 PR → CI 自动跑 validate.py（口径合规）+ verify（核验状态）
  → CODEOWNERS 自动指定审查人（您）→ 您 review & merge 到 main
  → merge 触发 Actions 重算 brief/指标 → 仪表盘与报告自动更新
```

### 权限映射（GitHub 原生功能 → 我们的需求）

| 需求 | GitHub 机制 | 配置位置 |
|---|---|---|
| 每人只负责自己的模块 | `CODEOWNERS` 按路径指定负责人与审查人 | `.github/CODEOWNERS` |
| 未经您审查不得进 core | main 分支保护：必须 PR + 您批准 | 仓库 Settings → Branches |
| 提交必须口径合规 | Actions CI：validate.py 不过不能合并 | `.github/workflows/validate.yml` |
| 模块独立可扩展 | 知识层每模块一个文件、数据记录按实体行级合并——天然低冲突 | 现有结构已满足 |
| 团队成员的录入界面 | 后台表单未来改为"生成 PR"而非直写（gh api） | serve.py 二期 |

### CODEOWNERS 示例（成员加入时启用）

```
research/M08.md        @散热研究员
research/M04.md        @电力研究员
research/M14.md        @中国研究员
data/prices.json       @数据管理员
framework/             @niuroumiantt        # 方法论只有您能动
data/schema/           @niuroumiantt
```

### 分阶段启用（不为未来的问题增加今天的摩擦）

- **现在（单人）**：直接提交 main，CI 做校验兜底 —— 本次已配 Actions；
- **第一个成员加入时**：开 main 保护 + CODEOWNERS 生效，成员走 PR；
- **成员多起来后**：后台表单改为开 PR 模式；每模块可再拆出独立数据文件降低合并冲突。

### 与爆炸图的关系

BOM 节点同样有 owner——部件档案的更新责任落到对应模块负责人头上。
爆炸图是**读者的入口**，模块是**维护者的单元**，CODEOWNERS 是两者之间的映射表。
