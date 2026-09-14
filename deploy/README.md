# deploy/ —— 本仓库保留的部署产物

现网部署由 **niuroumiantt/infra** 仓库的 `inresearch-host/` 统辖（Caddy 按域名分流、autopull 自动上站、健康检查）。改现网配置去改 infra 仓库；本目录只保留 infra 与 CI 仍引用的产物：

| 文件 | 用途 | 引用方 |
|---|---|---|
| `Dockerfile` | 网站镜像：Python 标准库、只读源码根，运行状态由 `INRESEARCH_RUNTIME_ROOT` 指向持久卷（见 [09 软件契约](../framework/09_software_contracts.md)） | infra compose、`tests/container_storage.py`、CI `storage-container` |
| `models.json` | 模型角色与后端配置 | `inresearch.adapters.models`，见 [08 模型执行](../framework/08_model_execution.md) |
| `spark-reader/` | Spark 常驻阅读、发布、新闻同步与材料接收的 systemd 单元 | [Spark 操作手册](../docs/local_reader/SPARK_OPERATIONS.md)、[采集运维](../docs/local_reader/ACQUISITION_OPERATIONS.md) |

账号由管理员在服务器容器内创建：`python3 manage.py users add <用户名>`（首个用户自动 admin，角色与权限见 `src/inresearch/interfaces/auth.py` 模块说明）。本地开发见 [docs/local_setup/README.md](../docs/local_setup/README.md)。

2026-08 的 AWS 手册、Cloudflare 回源 Caddyfile 与单机 compose 编排已归档至 `docs/archive/2026-09-14/`，仅作历史参考。
