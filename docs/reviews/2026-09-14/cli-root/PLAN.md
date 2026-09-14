# CLI 目录与调用边界：实施前交付

此文是本批审计快照，不是新增规范入口。基线 a37364d；先登记再修改代码。

## 已复现的现状

实际执行 `python3 manage.py --root <空临时目录> asset-check` 返回 0，却检查仓库里的 server_v2_console.glb；临时目录为空。现场结果见 baseline.json。静态确认 interfaces/cli.py 将全局 --root 解析后，对 COMMANDS 中每一个委派命令都丢弃该参数，包括会写文件的命令。因此不能把全局 --root 当成统一隔离机制。没有对写命令做破坏性反例。

委派还会永久替换进程 sys.argv，使同进程下一次调用继承别的命令参数。仓库两个启动器及测试直接调用此入口；委派、调用引用、操作指南全量检索见 consumers-before.csv 和 dispatch.csv。reader/L2 测试里的循环变量 cli 指向各自子接口，不误计为此入口消费者。

## 目标职责与权威

interfaces.cli 仅负责一级命令选择与参数所有权。全局 --root 只适用于 add-price、assign、receive-snapshot 三个统一 JSON 用例。它们缺省仍取 project_root；业务事务、稳定键、失败/重试/版本规则继续由 workflow.commands 与 storage 提供。COMMANDS 中每个子命令继续拥有自己的目录选项，参数位于命令名之后原样传入；不向不支持的子命令强加统一路径。

显式全局 --root 搭配委派命令须在导入/执行前报用法错误，退出码 2，明确适用的三个命令。统一入口借用 sys.argv 时必须在成功、导入失败和执行失败后恢复原对象。它是进程入口及顺序调用边界，不宣称支持多个线程同时修改进程参数。独立进程业务并发仍由既有锁验证。

INRESEARCH_PROJECT_ROOT 决定源码/作者工作区；INRESEARCH_RUNTIME_ROOT 按 storage_contract 决定网站运行数据；reader/M4 自有目录参数决定原件/catalog 位置。全局 --root 不替代这几种权威，也不移动任何资料。模型仍默认 Claude CLI。

## 全文件处置与旧实现退出

file-plan.csv 覆盖基线全部 752 个文件及本批审计文件。原路径保持；只改一个接口及其测试、现行规则和操作指南。所有未列变更文件保留；不以目录改名充当边界修复。退出项见 legacy-removal.csv：静默丢弃全局目录参数、过宽帮助文案、永久污染 sys.argv。委派表、子接口目录选项、三用例和私有数据保留并说明理由。

## 验收计划与限制

逐个委派命令验证不支持的全局 root 在导入前拒绝；成功/执行失败/导入失败后恢复 argv；真实 inventory 的本地 --root 继续工作。统一 JSON 命令保持真实写入、重复、失败后重试、12 进程竞争；快照版本替换由既有用例测试验证。重新运行规范、严格数据、全单元和 CI，不因测试全绿声称整个架构完成。

实施后的 file-results、consumers-after、统计及 DELIVERY 分别说明完成/实测/剩余。库外临时脚本无法穷尽枚举；已知生产部署、人工终端和 Python -m 入口一并登记，未接触 Spark/M4。
