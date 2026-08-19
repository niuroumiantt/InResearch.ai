# 产品官方资料库 —— 落点、采集流程与两机分工

> 2026-08-19 用户拍板。对应看板 `/admin/product/`，脚本 `pipeline/product_library.py`。
> 采集的是**厂商官方产品资料**（datasheet / product brief / 产品册 / 参考架构 / 手册），
> 与 `docs/library/` 的**第三方付费研报库**是两套东西，别混。

## 一、两台机器的分工（这是本次变更的重心）

| | Mac mini | MacBook |
|---|---|---|
| 角色 | **主力机**：24 小时不关机，唯一自动同步与下载机 | 移动办公，时常不在线 |
| launchd 三件套 | 全开（server / collect / sync `--push`） | **必须关掉 sync 的 `--push`**，或整个 unload |
| 研报库 `docs/library/` | 迁入（本次搬） | 保留一份冷备，不再是工作副本 |
| 产品资料库 `product/` | 外置卷 + 软链 | 无 |

**为什么必须只有一台自动推**：两台都跑 `sync --push`，每 30 分钟各自 commit 同一个
main，冲突不自动裁决只会中止，久了两边都推不上去，而且谁也不知道哪台是真的。
**单一真相源不是洁癖，是让「改名/重分类」这类操作有唯一的落点。**

## 二、目录落点

```
~/code/inresearch.ai/                      ← 唯一项目文件夹（08-18 归一）
├── docs/library/                          ← 第三方研报库（91GB，不进 git；本次由 MacBook 迁入）
├── reader/                                ← 精读工作区（不进 git）
└── product  ──软链──▶ /Volumes/<卷>/inresearch-product/
                        ├── library/       ← 终态库；索引里 file_path 的根
                        ├── _inbox/        ← 下载/试爬落地口，原文件名不动
                        └── _needs_manual/ ← 登录墙 / 验证码 / 拿到的是 HTML
```

- **内置盘装得下就别用外置卷**：`--path ~/code/inresearch.ai/product` 建成真目录，
  少一层软链，盘拔了也不会断；日后不够用了再 `setup --volume` 迁过去，页面常量不用动。
- **为什么外置卷要走软链**：卷名进不了代码。页面常量 `LIB_LOCAL_ROOT` / `LIB_BASE` 只认
  `product/`，换盘只需重跑 `setup`，索引一行都不用改。
- **外置卷没挂载时所有写操作直接中止**。原因：macOS 会在内置盘上凭空造出
  `/Volumes/<卷名>/…`，文件看着写成功了，卷挂回来就"消失"。同一个理由，
  `build_library_index.py` 也加了闸门——库不在就拒绝重建，**绝不把索引写成空的**。
- 研报库若也要放外置卷，同样做成软链：`docs/library` → 卷内目录。**相对位置必须还是
  `docs/library/`**——`LIBRARY_SCORES.csv` 与 `sources.json` 里上万行路径都是照它写的。

## 三、命令

```bash
# 一次性建库，两种落点二选一：
python3 pipeline/product_library.py setup --path ~/code/inresearch.ai/product   # 内置盘装得下（推荐，少一层软链）
python3 pipeline/product_library.py setup --volume "外置卷名"                    # 内置盘装不下，落外置卷并做软链

# 生成/刷新作业计划（只补不覆盖，已填的 source_url 不会被抹掉）
python3 pipeline/product_library.py plan                 # 全量 175 单元 → 801 行
python3 pipeline/product_library.py plan --priority P0    # 只铺 P0

# 试爬期：只落 _inbox/，不归位不入索引 —— 先看资料行不行，再决定要不要入库
python3 pipeline/product_library.py fetch --stage-only --limit 20

# 看过觉得可用 → 入库（三选一）
python3 pipeline/product_library.py fetch                                   # 直接抓+归位+入索引
python3 pipeline/product_library.py adopt                                   # 扫 _inbox/，按侧车 .meta.json 归位
python3 pipeline/product_library.py adopt --row 'nvidia|训练/推理GPU|h100|DS' --file product/_inbox/x.pdf

python3 pipeline/product_library.py status --verify        # 逐份核对文件在不在、哈希对不对
python3 pipeline/validate.py                               # 改完照例过闸门
```

侧车文件 `<文件名>.meta.json`（`adopt` 裸跑时用）：

```json
{"company_id":"nvidia","product_line":"训练/推理GPU","model":"H200","doc_type":"DS"}
```

## 四、作业计划 `data/product_docs_plan.csv`

801 行 = 451 个型号各一行 DS + 175 条产品线各两行（BR 产品册 / WEB 官网页存档），
对应看板"核心达标 = DS + (PB|BR|WEB)"的判据。

- `source_url` **留空就是还没查到，不许猜链接**——留白是纪律，不是缺口。
- 抓不到的行落 `status=needs_manual` 并在 `note` 写明原因（登录墙 / 拿到 HTML / 超时），
  看板亮黄色 `!`。**不下的理由要留，别静默跳过。**
- 主键是 `company_id|产品线原文|型号slug|doc_type`。产品线用原文不用 slug：
  中文产品线 slug 化后是空串，zte 的"通用服务器"与"数据中心以太网"就这么撞过。

## 五、文件命名与索引

落盘路径与对齐包 `ALIGNMENT.md` 的约定一致：

```
library/<环节表名>/<公司英文名>/<产品线>/<型号>/<company>__<型号slug>__<类型>__<版本>__<日期>__<语言>.pdf
例：library/3-算力芯片与核心器件/NVIDIA/训练-推理GPU/H200/nvidia__h200__DS__vNA__nd__en.pdf
```

索引 `data/product_library_index.json` 进 git（文本），每条带 `sha256` 与 `size_bytes`，
`status --verify` 靠它发现文件被改名或损坏。**请勿手工重命名库内文件——文件名是索引的锚点。**

对齐包里那份 `library_index.json` 是对方交付的原件，保留不动；页面在我们自己的索引
还是空的时候拿它兜底，两份不合并（会重复计数）。
