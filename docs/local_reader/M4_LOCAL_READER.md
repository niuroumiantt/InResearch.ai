# M4 阅读入口已统一

旧独立预处理器的 0–100 评分与按路径生成身份已退出新任务。现行规则见 [模型执行](../../framework/08_model_execution.md) 和 [M4 任务卡](../M4_TRIAGE_TASK.md)。

通过 `python3 manage.py inventory` 清点，`python3 manage.py triage` / `python3 manage.py score` 判读，`python3 manage.py batch` 打包并接收终端结果。命令参数见各自 `--help`。已有 m4-local-reader 日志保留为历史证据，不自动换算、不删除、不冒充现行有效判读。

本次迁移的是源码与受控启动文件；M4/Spark 运行进程及旧材料是否迁移须以各机器实测为准。
