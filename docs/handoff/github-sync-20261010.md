# 本地源码与 GitHub 同步交接（2026-10-10，m5）

## 目标与范围

用户要求检查本地代码是否全部上传 GitHub，并合并 main。本轮从最新 origin/main 建立独立工作树 `~/.worktrees/inresearch.ai/github-sync-20261010`；主目录及其它工作树没有切换、reset、stash、清理或覆盖。检查所有本地分支和已登记工作树的 tracked/untracked 状态，不盘点忽略文件、原件、数据库、密钥或运行资料。

## 检查与补齐

- 初查326个本地分支，64个提交当时不被 origin 的分支引用覆盖。15个历史备份头保存这些提交，远程命名空间为 `codex/local-backup-20261010/`；每个原分支、精确SHA和备份引用见同目录审计JSON。原分支及工作树保留。
- 109个分支的提交历史不在 main 中，不代表109份遗漏功能。39个分支有已合并PR证据，其中31个完整树与相应合并提交完全相同。其余按PR、现行内容和2026-10-06整合交接核对；旧架构、OCR/Office试验与已失效研究发布不能恢复成当前规范或正式采用。
- Solidigm长文分支的21份文本、研究卡、出处、视觉方案与历史审阅记录确实缺失，连同3份独立交接补入main：editorial-delivery、publication-block-recovery、research-pr-backlog。原文保留，旧交接中的“未推送/未合并”等措辞是当时状态；本轮上传与合并状态以后续PR为准。没有修改现行功能、规范、测试或正式研究登记表。
- 7个研究发布工作树存在未提交的 `data/research_knowledge.json`。通过临时Git索引生成独立备份提交并上传，未修改原工作树/索引；备份提交明确标记未完成候选。这些旧发布含尚未入库或已被新版本替代的记录，不将备份算作C3采用。源文件SHA-256、原HEAD和远程备份分支全部登记。
- 主目录电力专题195个文件中，189个与origin/main逐字节相同，0个不同；其余6个是原件/交付ZIP、packages.json、系统文件与Python缓存，没有独有源码。它们保留本机，不上传原件包或运行产物。

## 验收与边界

合并冲突仅发生在两份生成清单，保留最新main基线后统一刷新；现行 verification_contract 未变化。本轮完成治理检查、严格数据校验、registry与相关治理/界面单测，GitHub最终head必过检查通过后才合并；精确PR与检查结果通过 `gh pr list --head codex/github-sync-20261010 --state all` 核对。

研究发布仍由既有队列所有者处理；本轮初查时#582正在CI，未重启发布服务、复活已关闭的研究PR或自行采用候选。原工作树的未提交状态保留便于原任务继续。不以源码合并声称网站或Spark已部署；本轮没有主动部署、迁移或删除数据。

## 恢复入口

审计清单：`docs/handoff/github-sync-20261010-audit.json`。GitHub备份分支用于恢复历史或候选，不用于整枝合回main。旧实验的既有归档关系见 `docs/handoff/worktree-integration-20261006.md`，研究发布按现行 `docs/local_reader/SPARK_OPERATIONS.md` 继续。
