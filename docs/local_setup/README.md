# 本地开发与同步 — 现行说明

现行基准见 [CURRENT](../../framework/CURRENT.md)。源码使用 `~/code/inresearch.ai/`，并行工作树使用 `~/.worktrees/inresearch.ai/<任务>/`；资料与运行状态分别使用 `~/.local/share/inresearch.ai/` 和 `~/.local/state/inresearch.ai/`。

## 本地站点

在仓库运行 `python3 pipeline/serve.py 8000`，浏览器打开 `http://127.0.0.1:8000`。研究工作台需要该 API 服务，单纯静态 HTTP 服务不提供研究数据。是否安装本机 launchd 应检查实际服务；文档不假定任何电脑已有三项常驻任务。

## 同步

`bash docs/local_setup/sync.sh` 仅在 main 且工作区干净时取远端并快进。存在未提交内容或分叉就停止；脚本不自动提交、暂存或解决冲突。带 `--push` 时只校验并推送已提交内容。新工作先在独立分支审核与提交，完成本地检查和 GitHub 检查后再合并。

修改规范、源码或在册数据后，更新相应现行定义和替代记录，运行 `python3 pipeline/governance.py --refresh` 刷新清单，再运行 `python3 pipeline/governance.py --check` 与相关测试。清单只描述 Git 在册内容，不把本地唯一资料算成代码缓存。

## 持续阅读与生产

Spark 的常驻阅读入口是 [SPARK_OPERATIONS](../local_reader/SPARK_OPERATIONS.md)。Mac 上的旧 `reader/`、外置盘和研报目录可能仍有唯一文件，只能核对后迁移；本页不授权自动搬删。一次性旧目录迁移器 `setup.sh` 已退役并显式退出。

主站由 infra 的正式部署流程跟随 GitHub main；不在此重复维护服务器发布命令。产品资料的旧外置卷操作见 `PRODUCT_LIBRARY.md`，用于已有登记位置的核查，不代表当前原件已在该卷。
