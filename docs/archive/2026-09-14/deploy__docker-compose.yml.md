> HISTORICAL — 已被替代。保存于 2026-09-14；下文是历史原文（原路径 deploy/docker-compose.yml），不构成当前指令、授权或服务状态。生产编排真源在 niuroumiantt/infra 的 `inresearch-host/`；整目录挂载 data/reports 的方式已退出，运行状态按 `INRESEARCH_RUNTIME_ROOT` 分离。现行入口：[当前基准](../../../framework/CURRENT.md)。

# ⚠️ 历史，勿用（2026-08-19 六站合并迁移后作废）
# 生产编排真源已迁到 infra 仓库 `inresearch-host/`：一台 Lightsail（us-east-1a，
# 非本文件假设的 AWS 新加坡）上一个 Caddy 给六站分流，dchub 只是其中一个容器，
# 不再自带 caddy/news 服务。部署走 GitHub push → autopull 每 2 分钟自动重建，
# **没有** `docker compose up` 的人工步骤。本文件保留仅作历史参照，勿据此部署。
# 真源见 infra `docs/environment.md`。本仓库仍活着的部署产物只有 deploy/Dockerfile
# （dchub 容器的构建源）。
#
# ── 以下为历史内容 ──
# Datacenter Hub 部署编排（AWS ap-southeast-1 / 新加坡）
#
# 为什么是 compose 而不是 Kubernetes：整个应用最重的脚本跑 8.3 秒、占 48MB 内存，
# 全部计算装不满一个 2 核机器。k8s 引入的运维面比应用本身还大。
# 等真的需要多机扩容再换——以现在的负载画像，那一天可能不会来。

services:
  hub:
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    restart: unless-stopped
    # **不映射端口到宿主机**：只有 caddy 能访问它。
    # 写成 "8000:8000" 就等于绕过反代与认证，把后台直接暴露到公网。
    expose: ["8000"]
    volumes:
      # 数据层与产出物挂出来，容器重建不丢；仓库本体在镜像里。
      - ../data:/app/data
      - ../reports:/app/reports
      - ../logs:/app/logs
    environment:
      HUB_HOST: 0.0.0.0

  news:
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    restart: unless-stopped
    # 新闻抓取是定时任务不是常驻服务；这里用一个简单的循环占位，
    # 真正接上 fetch_news_signals.py 后按 cadence 调整间隔。
    command: >
      sh -c "while true; do
               python3 pipeline/fetch_news_signals.py || true;
               sleep 3600;
             done"
    volumes:
      - ../data:/app/data
      - ../logs:/app/logs

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data          # ACME 证书，删了会重新签发并可能触发速率限制
      - caddy_config:/config
    depends_on: [hub]

volumes:
  caddy_data:
  caddy_config:
