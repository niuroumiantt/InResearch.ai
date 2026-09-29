# 系统检查 1 · infra：现状、配置与网络（2026-09-29）

> 检查记录，不是规范。范围：`niuroumiantt/infra`（`inresearch-host/`、`hosts/aws/`、`hosts/apps.json`、`docs/production-state.md`、`hosts/production-inventory.json`）与本仓库 `deploy/`、`framework/09_software_contracts.md`、`framework/storage_contract.json`、`docs/local_setup/README.md`、`docs/local_reader/SPARK_OPERATIONS.md`。只读，不改任何仓库。凡写"未核实"的，都是仓库里读不到、要在实机跑命令才能确认的事实；本文不猜实机状态。凭证只写落点与权限，不写值。

## 一、现状（从仓库核实）

| 项 | 现状 | 依据 |
|---|---|---|
| 发布链 | 只有一条：`inresearch-only-deploy.timer` 每 2 分钟跑 `deploy-inresearch.sh`：fetch `origin/main` → 干净检查 → `checkout --detach` → 构建镜像 `inresearch-app:<40 位 SHA>` → `compose up --no-build` → 等 healthy → 写 `applied`。构建或健康失败则用上一镜像 ID 原样拉起，状态写 `FAILED: …`。旧整机 `autopull.sh` / `ops-deploy.timer` 已禁用，`hosts/apps.json` 登记 `managed_by: inresearch-only-deploy`。 | infra `hosts/aws/deploy-inresearch.sh`、`hosts/aws/systemd/inresearch-only-deploy.*`、`hosts/apps.json` |
| 回滚 | 不能指定提交。脚本把 `BRANCH=main` 写死，没有 pin 变量；自动回退只回到"上一次成功的镜像 ID"。要回到某个提交只能在 main 上 revert。旧镜像 `inresearch-app:<sha>` 留在本机，手工 `compose up` 可临时回去，但下一轮 timer 又拉回 main 头。 | 同上 |
| 源码根与运行卷 | 生产编排是 `hosts/aws/inresearch.compose.yml`：`read_only: true`、`/tmp` tmpfs 256m、只挂三个卷 `/srv/inresearch.ai/{data,reports,logs}` → `/runtime/{data,reports,logs}`，`INRESEARCH_RUNTIME_ROOT=/runtime`。`storage_contract.json` 声明的全部运行文件都落在这三个目录下（含 `framework/indicators.json` → `data/projections/`），源码根 `/app` 由镜像提供。边界落实。 | `hosts/aws/inresearch.compose.yml`、本仓库 `framework/storage_contract.json`、`deploy/Dockerfile` |
| 同名服务两份定义 | `inresearch-host/docker-compose.yml`（旧整机编排，caddy / inews / openapi / glocal 容器仍标着它）和 `inresearch.compose.yml` 都是 `name: inresearch-host`，都定义 `services.inresearch`，前者 `build:` 后者 `image: ${INRESEARCH_IMAGE}`。README 只写了一句"不可整份重新 up"。 | `inresearch-host/docker-compose.yml:87–107`、`hosts/aws/README.md` |
| 健康检查 | 三处不一致：compose 探 `/healthz`；Dockerfile 探 `/index.html`；`apps.json` 探 `/` 期待 200/302。`/healthz` 在本仓库没有路由（`interfaces/http.py`、`public.py` 都没有），匿名 GET 走 `_gate()` → 302 到 `/login` → `urllib` 跟随重定向拿到 200，所以探针"通过"的是登录页能渲染，不是一个健康端点。 | 本仓库 `src/inresearch/interfaces/http.py:134–162`、`public.py`；infra 三个文件 |
| 凭证落点 | `$KIT/.env.inresearch`（`HUB_ADMIN_PASSWORD`，root 600，`ensure_env.sh` 生成骨架，`docs/secrets.md` 登记）；`/srv/inresearch.ai/data/.reader_sync_token`（≥32 字节，`hmac.compare_digest`，三个接收接口共用）；Spark `~/.local/state/inresearch.ai/reader-sync.token`（0600）；M5 的 `publish-pilot-progress` 凭证按 `supply_contract.temporary_execution.publish_credential_host = m5` 登记，用的是不是同一个 token 仓库里读不到；GitHub 凭证 `/root/.config/inresearch/git-credentials`（root 600），`spark_watch.py` 开 issue、旧 autopull、`/srv/sources/inresearch.ai/.git/config` 的 credential helper 三处共用同一个 PAT。 | infra `ensure_env.sh`、`docs/secrets.md`、`spark_watch.py`、`autopull.sh`；本仓库 `http.py:212,487,524`、`SPARK_OPERATIONS.md` |
| 轮换 | `HUB_ADMIN_PASSWORD` 有流程（改 env 等下一轮发布）；serverops basic_auth 有 `--rotate-password`；`.reader_sync_token` / Spark token / PAT 三者没有任何轮换步骤或记录。 | 同上 |
| 网络暴露面 | 只有 caddy 映射 80/443；inresearch 只 `expose 8000`，不映射宿主端口。Caddy 用 `{remote_host}` 覆盖 `X-Forwarded-For`，应用限速取末项，配套正确。`/admin/serverops/*` 由 Caddy basic_auth 挡门。inresearch 站点块没有 HSTS / nosniff / frame 头（静态站块有）。没有 `robots.txt`（匿名请求 302 到登录页）。Caddyfile 与 compose 里没有 Cloudflare 回源残留（2026-09-14 已归档）；inresearch.ai 的 DNS zone 按 infra 文档在 Lightsail，`www.inews.today` 2026-09-05 探测曾落在 Cloudflare 代理——两条都要 `dig` 复核。Tailscale 只放行 AWS → Spark `:11434`（翻译）与 阿里云 → Spark `:4000`。 | infra `inresearch-host/Caddyfile`、`docs/infrastructure-review-2026-09-08.md:161–169`、`hosts/tailscale/policy.json`；本仓库 `auth.py:13,358` |
| 日志 | Caddy 访问日志 20 MiB × 3；容器 stdout `local` 10m × 3；`/srv/inresearch.ai/logs` 由应用自写，仓库里没有轮换声明；`/var/log/inresearch-deploy.log` 只由旧 autopull 写。 | `Caddyfile`、两份 compose、`ensure_env.sh:28–30` |
| 磁盘 | `ops-docker-prune`：`builder prune --filter until=24h` + `image prune -f`。后者只删悬空镜像，每次发布新建的带标签 `inresearch-app:<sha>` 不会被删；`release_guard.py retire --keep 10` 管的是旧整机发布清单，是否覆盖这些标签未核实。 | `systemd/ops-docker-prune.service`、`ops-release-retire.service`、`deploy-inresearch.sh` |
| 备份 | `ops-backup`（每日 03:30）只按 SQLite 文件头扫 `/srv/inews-data` 与 `/var/lib/inresearch-ops`；`/srv/inresearch.ai/data` 全是 JSON / CSV / token（账号表、价格、派工、产品资料计划、候选快照、上传原件），不在任何备份源里；每周恢复演练也不覆盖它。infra 总图第 2 条已写明"既无异机备份也无快照"。Lightsail 自动快照是否开启未核实。 | `inresearch-host/backup.py:29–32`、`README.md`「数据与备份」、`docs/2026-09-22-infra-overview.md` §8 第 2 条 |
| 监控与告警 | `spark_watch` 每 5 分钟探 Spark，连续 3 次失败开 GitHub issue；`ops-collect` 每 5 分钟生成 serverops 静态页。研究站发布失败只写 `/var/lib/inresearch-ops/inresearch-only/status`，没有任何推送。 | `spark_watch.py`、`ops-collect.timer`、`deploy-inresearch.sh` |
| 成本 | AWS Lightsail 2 vCPU / 7.6 GiB / 154 GB；套餐月费未在 infra 登记；阿里云、Spark 电费与 Tailscale 不在本次范围。未核实。 | `hosts/aws/README.md`、`docs/inventory.md` |
| 遗骸 | inventory 仍列出 `inresearch-deploy.service`（failed）、`inresearch-autopull.service`、六张 `oa-*` 网络、`inresearch-yidian-*`；不影响运行，但"顺手清理"或"重开旧 timer"会打到现网。 | `hosts/production-inventory.json` `nodes/0/runtime/units`、`docs/2026-09-22-infra-overview.md` §8 第 10 条 |

## 二、问题（按风险排序）

| # | 风险 | 问题 | 后果 |
|---|---|---|---|
| 1 | 高 | 研究站运行数据没有任何应用级备份 | 账号表、`.hub_secret`、`.reader_sync_token`、价格与派工记录、产品资料计划、候选快照与上传原件只存在于 `/srv/inresearch.ai/data`；盘坏或误删即全丢，且无法从 Git 重建。 |
| 2 | 高 | 发布失败无告警 | `FAILED` 只写状态文件；旧 autopull 曾有 17 小时无人知的先例。研究站现在也可能连续失败而站点照常服务旧版本。 |
| 3 | 高 | 回滚不能指定提交 | 出问题只能 revert main；线上没有"钉在某个 SHA"的开关。 |
| 4 | 中 | 健康检查是伪路由 | `/healthz` 不存在，探的是登录页；一旦登录页改为对匿名返回 401 或加 `/healthz` 到公开白名单但实现不当，探针语义会静默变化。三处定义也不一致。 |
| 5 | 中 | 两份编排同项目同服务名 | 谁在 `/srv/host/inresearch-host` 里 `docker compose up -d` 就会用旧 `build:` 定义重建研究站，绕过 SHA 镜像与 `applied` 记录。 |
| 6 | 中 | 三个长期凭证无轮换流程 | reader token 泄露等于任何人可向主站投快照与材料；PAT 一个值三处用，吊销时会同时打断 spark_watch、源码 fetch。 |
| 7 | 中 | 带标签镜像累积 | 每次 push 留一层 `inresearch-app:<sha>`（Python slim 约 150 MB 级），prune 不删；根盘 154 GB 曾到 63%。 |
| 8 | 低 | 安全头与 robots | 研究站块缺 HSTS / nosniff；没有 `robots.txt`，公开只读 reader 开放后爬虫会索引节点页、账本基准。 |
| 9 | 低 | 应用日志目录无轮换 | `/srv/inresearch.ai/logs` 增长上限未知。 |
| 10 | 低 | 遗骸与文档 | 失败 unit、OA 网络、旧 timer 仍在；`hosts/aws/docker-compose.yml` 是目标不是现网，README 已标但容易误用。 |
| 11 | 低 | 成本未登记 | 无法判断是否值得升配（内存 7.6 GiB 跑 5 个容器且无 cgroup 上限，见 infra 总图第 15 条）。 |

## 三、建议

| # | 对应问题 | 建议 | 落点 | 成本 |
|---|---|---|---|---|
| A | 1 | 把 `/srv/inresearch.ai/data`（排除 `raw/` 大原件可另计）加进 `ops-backup` 的源：JSON/CSV 用 `tar` + SHA-256 manifest，与 SQLite 走同一 30 天保留、同一恢复演练；确认 Lightsail 自动快照开启并记录到 `hosts/aws/README.md`。 | infra `backup.py`、`systemd/ops-backup.service` 的 `ReadWritePaths` | 低 |
| B | 2 | `deploy-inresearch.sh` 的 `fail()` 复用 `spark_watch.py` 的 GitHub issue 通道（连续 N 轮 FAILED 才开），或 serverops 页读 `status` 文件标红。 | infra `hosts/aws/deploy-inresearch.sh` | 低 |
| C | 3 | 加 `INRESEARCH_PIN_SHA` 文件（如 `/var/lib/inresearch-ops/inresearch-only/pin`）：存在时脚本以它代替 `origin/main`，并在 status 里标 `PINNED`；删除文件即恢复跟随 main。 | 同上 | 低 |
| D | 4 | 本仓库加一个真 `/healthz`：进 `public.py` 白名单，只返回 `{"ok":true,"release":<sha>}`，不 stat 日志；compose、Dockerfile、`apps.json` 三处统一探它。 | 本仓库 `http.py` / `public.py`；infra 三处 | 低 |
| E | 5 | 从 `inresearch-host/docker-compose.yml` 删除 `inresearch` 服务（或改成 `profiles: [retired]`），README 明确"研究站只由 `inresearch.compose.yml` 定义"。 | infra | 低 |
| F | 6 | 给 reader token 写轮换步骤（主站生成新值 → Spark 更新 → 一次发布验证 → 删旧值）并登记到 `docs/secrets.md`；PAT 拆成 fine-grained：源码只读一把、issue 写一把。 | infra `docs/secrets.md`；本仓库 `SPARK_OPERATIONS.md` | 中 |
| G | 7 | 发布成功后删除除 `applied` 与上一成功之外的 `inresearch-app:*` 标签（保留两代即可回退）。 | infra `deploy-inresearch.sh` | 低 |
| H | 8 | 研究站块加 `header { Strict-Transport-Security …; X-Content-Type-Options nosniff }`；本仓库加 `web/robots.txt` 并进公开白名单（reader 页允许，`/api/` 与 `/supply.html` 禁止）。 | infra `Caddyfile`；本仓库 `public.py`、`routes.json` | 低 |
| I | 9 | 应用日志按大小轮换或由 `ops-daily` 归档。 | 本仓库 `storage` 或 infra `opsd.py` | 低 |
| J | 10 | 按 infra 总图第 6 步清遗骸：`systemctl disable --now` 失败 unit 后 `rm` unit 文件，删六张 OA 网络。做之前先跑下面的核对命令。 | infra | 低 |
| K | 11 | 在 `hosts/aws/README.md` 登记 Lightsail bundle 与月费，给研究站与 inews 容器加 `mem_limit`。 | infra | 低 |

## 四、需要在实机核对的项（不猜）

以下命令都在 **AWS 主机 `ubuntu@ip-172-26-11-47`** 上跑（先确认主机名）。只读，不改任何东西。

```bash
hostname; test "$(hostname)" = ip-172-26-11-47 && echo host-ok
sudo systemctl list-timers --all --no-pager | grep -E 'inresearch|ops-|infra-'
sudo cat /var/lib/inresearch-ops/inresearch-only/status; sudo cat /var/lib/inresearch-ops/inresearch-only/applied
sudo docker inspect inresearch-host-inresearch-1 --format '{{.Config.Image}} health={{.State.Health.Status}} ro={{.HostConfig.ReadonlyRootfs}}{{range .Mounts}} {{.Source}}->{{.Destination}}{{end}}'
sudo docker inspect inresearch-host-inresearch-1 --format '{{json .Config.Healthcheck}}'
sudo docker exec inresearch-host-inresearch-1 python3 -c "import urllib.request as u;r=u.urlopen('http://127.0.0.1:8000/healthz');print(r.status,r.geturl())"
sudo docker images inresearch-app --format '{{.Tag}} {{.Size}} {{.CreatedSince}}' | wc -l; sudo docker system df
df -h /; sudo du -sh /srv/inresearch.ai/data /srv/inresearch.ai/reports /srv/inresearch.ai/logs /var/log/caddy /srv/inresearch-backups 2>/dev/null
sudo ls /srv/inresearch-backups | tail -3; sudo python3 -c "import json;print(json.load(open('/srv/inresearch-backups/last-restore-drill.json'))['status'])"
sudo ls /srv/inresearch-backups/$(ls /srv/inresearch-backups | grep -E '^20' | tail -1)/   # 应只见 inews、ops，没有 inresearch
sudo stat -c '%U %a %y %n' /srv/host/inresearch-host/.env.inresearch /srv/inresearch.ai/data/.reader_sync_token /root/.config/inresearch/git-credentials
sudo ss -tlnp | grep -E ':80 |:443 |:8000 '
curl -sI https://inresearch.ai/ | grep -iE 'strict-transport|x-content-type|x-frame|^server'
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://inresearch.ai/robots.txt
dig +short NS inresearch.ai; dig +short A inresearch.ai; dig +short A www.inresearch.ai; dig +short A www.inews.today
sudo docker network ls | grep -E 'oa-'; systemctl list-units --all --no-pager | grep -E 'inresearch-deploy|autopull|yidian'
sudo find /srv/inresearch.ai/logs -type f -size +50M -printf '%s %p\n'
```

Lightsail 自动快照与套餐月费只能在 **用户自己的机器**（有 AWS CLI 凭证处）核对，AWS 主机上没有这个凭证：

```bash
aws lightsail get-auto-snapshots --resource-name <实例名> --query 'autoSnapshots[0:3].[date,status]'
aws lightsail get-instance --instance-name <实例名> --query 'instance.[bundleId,hardware.ramSizeInGb,hardware.disks[0].sizeInGb]'
```

**Spark `spark@dgx`**：

```bash
hostname; test "$(hostname)" = dgx && echo host-ok
systemctl --user list-timers --no-pager | grep inresearch
cat ~/.local/state/inresearch.ai/publish-status.json
stat -c '%a %y' ~/.local/state/inresearch.ai/reader-sync.token
grep -E '^READER_RELEASE=' ~/.config/inresearch.ai/reader.env
```

## 五、结论一句

链路是单一且能自动回退的，卷边界是真落实的，暴露面只剩 Caddy 一个口；真正的洞是"研究站的运行数据没人备份、发布失败没人知道、回不到指定提交"三件，都是 infra 侧几十行的改动。
