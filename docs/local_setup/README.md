# 本地开发与同步 — 现行说明

现行基准见 [CURRENT](../../framework/CURRENT.md)。源码使用 `~/code/inresearch.ai/`，并行工作树使用 `~/.worktrees/inresearch.ai/<任务>/`；资料与运行状态分别使用 `~/.local/share/inresearch.ai/` 和 `~/.local/state/inresearch.ai/`。

## 本地站点

在仓库运行 `python3 manage.py serve 8000`，浏览器打开 `http://127.0.0.1:8000`。研究工作台需要该 API 服务，单纯静态 HTTP 服务不提供研究数据。是否安装本机 launchd 应检查实际服务；文档不假定任何电脑已有三项常驻任务。

## 命令目录参数

`python3 manage.py --help` 显示一级入口；`python3 manage.py <命令> --help` 显示该命令的选项。
命令名前的 `--root` 只支持 add-price、assign、receive-snapshot；例如
`python3 manage.py --root /path/to/workspace add-price --input price.json`。它仍受运行数据布局配置约束，
不能代替 INRESEARCH_RUNTIME_ROOT 来隔离网站状态。对其他命令使用全局 --root 会明确报错，不再静默忽略。

子命令的目录参数写在命令名之后：例如 `python3 manage.py inventory --root /path/to/originals --out-dir /path/to/index inventory`，
或 `python3 manage.py reader --data-root /path/to/reader current --sha <SHA>`。参数是否可用以该子命令帮助为准；
不存在把所有命令的目录自动换成同一个路径的约定。Python 模块入口的语义相同。

## 同步

`bash docs/local_setup/sync.sh` 仅在 main 且工作区干净时取远端并快进。存在未提交内容或分叉就停止；脚本不自动提交、暂存或解决冲突。带 `--push` 时只校验并推送已提交内容。新工作先在独立分支审核与提交，完成本地检查和 GitHub 检查后再合并。

修改规范、源码或在册数据后，更新相应现行定义和替代记录，运行 `python3 manage.py governance --refresh` 刷新清单，再运行 `python3 manage.py governance --check` 与相关测试。清单只描述 Git 在册内容，不把本地唯一资料算成代码缓存。

## 持续阅读与生产

Spark 的常驻阅读入口是 [SPARK_OPERATIONS](../local_reader/SPARK_OPERATIONS.md)。Mac 上的旧 `reader/`、外置盘和研报目录可能仍有唯一文件，只能核对后迁移；本页不授权自动搬删。一次性旧目录迁移器 `setup.sh` 已退役并显式退出。

主站由 infra 的正式部署流程跟随 GitHub main；不在此重复维护服务器发布命令。产品资料的旧外置卷操作见 `PRODUCT_LIBRARY.md`，用于已有登记位置的核查，不代表当前原件已在该卷。

## 网站发布数据边界

生产设置 `INRESEARCH_RUNTIME_ROOT=/runtime`，只把既有主机 data/reports/logs 挂到对应运行目录。
已发布研究与规范从只读镜像读取；持久状态及可重建产物按
[storage_contract](../../framework/storage_contract.json) 选择路径。旧卷内正式事实副本不删除，也不再遮住镜像。
价格、派工和产品处理计划的 Git 内容只在首次安装作种子，发布/回退不重置已有记录。

需要隔离本地运行时，先设置 `INRESEARCH_RUNTIME_ROOT` 为项目外的持久目录，再执行
`python3 manage.py storage initialize`；检查使用 `python3 manage.py storage check`，只读且不创建数据。
已有线上发布加 `--require-auth` 校验 admin 存储和会话密钥。未设置运行根的 checkout 仍是作者工作区；
使用 `serve` 或生成器可能修改本地数据和产物，修改前保持工作区职责明确。布局变更不自动迁移，
初始化中断须按同版种子恢复。原件、密钥、数据库按现有备份流程保存，不提交 Git。
