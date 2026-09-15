# deploy/ —— 本仓库保留的部署产物

现网部署由 **niuroumiantt/infra** 仓库的 `inresearch-host/` 统辖（Caddy 按域名分流、autopull 自动上站、健康检查）。改现网配置去改 infra 仓库；本目录只保留 infra 与 CI 仍引用的产物：

| 文件 | 用途 | 引用方 |
|---|---|---|
| `Dockerfile` | 网站镜像：Python 标准库、只读源码根，运行状态由 `INRESEARCH_RUNTIME_ROOT` 指向持久卷（见 [09 软件契约](../framework/09_software_contracts.md)） | infra compose、`tests/container_storage.py`、CI `storage-container` |
| `models.json` | 模型角色与后端配置 | `inresearch.adapters.models`，见 [08 模型执行](../framework/08_model_execution.md) |
| `spark-reader/` | Spark 常驻阅读、发布、新闻同步与材料接收的 systemd 单元 | [Spark 操作手册](../docs/local_reader/SPARK_OPERATIONS.md)、[采集运维](../docs/local_reader/ACQUISITION_OPERATIONS.md) |

账号由管理员在服务器容器内创建：`sudo docker exec inresearch-host-inresearch-1 python3 manage.py users add <用户名>`（首个用户自动 admin，角色与权限见 `src/inresearch/interfaces/auth.py` 模块说明）。本地开发见 [docs/local_setup/README.md](../docs/local_setup/README.md)。

## 管理员密码由部署声明（2026-09-15）

容器环境 `HUB_ADMIN_PASSWORD` 非空时，`manage.py serve` 启动即保证 `HUB_ADMIN_USERNAME`（缺省 `admin`）存在、角色为 admin、密码等于该值：已一致不写文件；不一致就重置；留空则完全不碰账号表，网页 `/account` 与 CLI 改的密码继续有效。autopull 每次 push 都重建容器，所以声明值就是长期有效的管理员密码。值只放在服务器的 `$KIT/.env.inresearch`（infra 仓库 `inresearch-host/ensure_env.sh` 生成骨架、`docs/secrets.md` 登记、compose `env_file` 注入），不进 git、不打印、不写日志；启动日志与 `logs/task_auth.log` 只记结果（`created` / `password` / `role`）。

账号表只有一个：`INRESEARCH_RUNTIME_ROOT` 指向的 `data/users.json`，现网即 `/srv/inresearch.ai/data/users.json`。`manage.py users` 因此必须在容器内执行；在宿主机 `/srv/sources/inresearch.ai` 直接运行会写进源码目录自己的 `data/users.json`，网站不读那个文件，改了等于没改。`users list` 打印实际文件位置，先看再改。密码哈希参数（PBKDF2-SHA256、200,000 轮）与账号表格式自 2026-08-18 起未变，部署、初始化、回退与 reader 快照都不写账号表；登录提示「用户名或密码不对」只说明账号表里没有这个用户名，或其哈希与输入不符。

2026-08 的 AWS 手册、Cloudflare 回源 Caddyfile 与单机 compose 编排已归档至 `docs/archive/2026-09-14/`，仅作历史参考。
