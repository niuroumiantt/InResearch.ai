# 实机验证脚本（2026-09-29 三项检查的配套）

四个脚本，每台机器一个，全部**只读**：不改文件、不重启服务、不重跑 CI、不打印任何凭证值。每个脚本先核对主机名，不对就停；结果同时打印并写到 `~/inresearch-verify-<机器>-<日期>.txt`，把那个文件整份贴回即可。

| 机器 | 怎么跑 | 核对什么 |
|---|---|---|
| AWS `ubuntu@ip-172-26-11-47` | `ssh ubuntu@ip-172-26-11-47`，把 `aws.sh` 整段粘贴（或 `scp aws.sh ubuntu@ip-172-26-11-47:~ && ssh ubuntu@ip-172-26-11-47 bash aws.sh`） | 发布链状态、容器与卷、`/healthz` 实际落点、备份目录里有没有 inresearch、凭证权限、暴露面与 DNS、镜像累积、inews 采集统计、feed v2 命中率 |
| Spark `spark@dgx` | `ssh spark@dgx`，粘贴 `spark.sh` | 源码版本与 `READER_RELEASE`、四个 timer、发布器与新闻同步状态、token 权限、磁盘与 GPU 温度 |
| 你自己的电脑（有 aws CLI 与外网） | 粘贴 `local.sh` | 从外面看 DNS/证书（Cloudflare 遗留）、Lightsail 自动快照是否开启、套餐月费 |
| Mac mini `hermes@macmini` | `ssh hermes@macmini`，粘贴 `macmini.sh` | fetchspec 实际执行机与最近运行、inews 原文库产出 |

判读要点写在对应报告里：`../infra/README.md` §四、`../inews/README.md` §三、`../skeleton/README.md` S8。
