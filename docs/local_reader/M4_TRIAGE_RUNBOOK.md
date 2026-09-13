# M4 资料分拣操作手册

> CURRENT · 2026-09-12。任务与数据契约只有 [M4 任务卡](../M4_TRIAGE_TASK.md) 一处；本页列执行顺序。历史机器数量与运行结果见 [归档快照](../archive/2026-09-12/docs__local_reader__M4_TRIAGE_RUNBOOK.md)，不代表当前服务状态。

## 1. 选择数据集与清点

在实际持有原件的机器执行。默认使用 M4 数据集；更换语料时三个路径一起配置。核心入口使用 Python 标准库，PDF/Office 提取器按文件格式另行检查依赖。

```bash
export INRESEARCH_SOURCE="/path/to/raw-materials"
export INRESEARCH_LIBRARY="/path/to/library"
export INRESEARCH_DATASET="my-corpus"
python3 manage.py inventory inventory --workers 4 --limit 20
python3 manage.py inventory summary
```

确认小样后去掉 `--limit` 清点全量。源与库为同卷并列目录；独立账本放本机 `~/.local/share/inresearch.ai/<dataset>/`，移动日志放 `~/.local/state/inresearch.ai/<dataset>/`。清单命令可单独指定 `--root/--out-dir`，后续阶段仍需相同数据集配置。

旧 `rel/size` 清单已有统一读取支持，继续写入前显式迁移：

```bash
python3 manage.py inventory migrate-inventory
```

原文件完整备份后再替换，坏格式拒绝迁移。首次接手旧清单会补做精确文件签名；后续变化/失败文件重读，其他跳过。清单记录是历史观察，不把源目录后来变空解释为丢失所有资料。

## 2. 预览、模型探测与判定

```bash
python3 manage.py triage preview --limit 20 --text-only
python3 manage.py models --probe
python3 manage.py triage sample --limit 50
```

当前默认 Claude CLI；Spark 尚不可用，后续通过 [统一模型配置](../../framework/08_model_execution.md) 切换。核对模型身份、分数、分类、原文定位、命名及耗时。代表性小样质量通过后按配置并发处理：

```bash
python3 manage.py triage run --workers 2
python3 manage.py progress
```

L0 不构成已读；单次零分进入复核。CLI 客户端也可走同一 pack/record 契约：

```bash
python3 manage.py batch pack --limit 20
python3 manage.py batch record --verdicts /path/to/verdicts.txt --executor claude-code --model ACTUAL_MODEL
```

无法核实实际模型时省略 `--model`，记录为未知，不填终端名。已处理材料不因换默认模型而重新进入待办。明确要补读旧 Office 预览时使用现有 `pack --redo` 范围；它不等同于 Spark 完成材料的通用重读替换。

## 3. 计划与移动

去重可在模型判定前执行；library 需要判定。计划也会哈希核对原文，耗时取决于总字节。

```bash
python3 manage.py organize duplicates plan
python3 manage.py organize duplicates apply
python3 manage.py organize library plan
python3 manage.py organize library apply
```

apply 才移动；不会删除内容或覆盖目标。中断后再执行 apply/revert，先在同一锁内恢复日志。内容变化、路径冲突会报告并保留文件；不要手工删掉双路径中的任意一个来“修复”日志。命名规则变化用 restage；只搬不符合当前命名的位置。

```bash
python3 manage.py organize restage plan
python3 manage.py organize restage apply
python3 manage.py organize restage revert
python3 manage.py organize library revert
python3 manage.py organize duplicates revert
```

回退按依赖顺序，目标位置有人占用时保留现状并报告。回退成功后可再次 apply。

## 4. 导出与跨机器核对

```bash
python3 manage.py mapping export --out /path/to/mapping.jsonl
python3 manage.py mapping verify --mapping /path/to/mapping.jsonl
```

在另一台机器先切到独立数据集并清点自己的原件，再 verify。只有未被 reader catalog 管理的独立副本才使用物理 apply；missing/extra 须先对清。旧手册中的跨机器执行记录不表示已经实现 Spark catalog 的 apply-triage。Spark 当前不可用，恢复后按任务卡 §7.3 接元数据与链接接口。

## 5. 验收边界

程序测试使用临时合成文件，覆盖内容变化、断行、移动中断、目标冲突、重复运行及回退。真实语料的 50 份质量验收、运行完成量与主机服务状态须实机核对；源码通过不代替这些结果。L2 交付工具已有，自动全文覆盖按各自账本和证据计量。

版本冲突表示读取基线已变，不要强行重放旧判定。新终端包保存 base_revision；自动评分和人工修订也遵守同一规则。旧未版本化包可收取首次结果，若材料已有有效结果，须重新 pack 后判定。冲突不会抹掉已有成功。
