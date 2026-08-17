# 部署手册 —— AWS 新加坡（ap-southeast-1）

> 实习生主要在新加坡（2026-08-17 用户确认），故选 `ap-southeast-1`：
> 完整功能区、**不需要 ICP 备案**、对东南亚延迟低，对中国大陆访问也是标准折中。

## 一、为什么配置这么小

不是省钱，是实测出来的。全部流水线脚本在 4 核容器里的表现：

| 脚本 | 耗时 | 峰值内存 |
|---|---:|---:|
| `facts.py` | 38 ms | — |
| `validate.py` | 366 ms | — |
| `workorder.py` | 778 ms | — |
| `blindspot.py`（最重，扫 13,664 行 × 关键词） | **8.3 s** | **48 MB** |

全部单线程、纯标准库、零依赖。`serve.py` 服务的是静态 HTML + JSON API。
**15 个实习生同时用，负载接近于零。**

**关键前提：精读继续在本地（Mac + Claude Code）跑。** 服务器只做协作、展示、工单。
真正吃 CPU 的是 28,759 份文档的文本提取，那是一次性、可中断的批量工作——
**为它 7×24 付大机器的钱是浪费**。以后有增量再用 spot 实例按需跑。

## 二、资源清单

| 项 | 规格 | 说明 |
|---|---|---|
| EC2 | **`t3.medium`（2 vCPU x86 / 4GB）** | **不用 ARM**：news 依赖 RSSHub 与 wewe-rss 两个第三方镜像，未验证它们发布 arm64 manifest。ARM 省约 20%（$35 账单上约 $6/月），**不值得为此在迁移里引入未知数**。全新项目 + 全部第一方镜像时才该考虑 ARM |
| EBS | **50GB gp3** | datacenter 60MB + news 数据约 1GB/年 + RSSHub 镜像 1-2GB + 日志 |
| S3 | 约 91GB（研报库本体） | **不放 EBS** |
| CloudFront | 可选 | 实习生下载研报走它，出网比 S3 直出便宜 |

**成本量级约 $35–45/月**（新加坡区比美东贵约 15–20%）。
> ⚠️ 价格随时会变，**下单前用 AWS 定价计算器核一遍**，不要拿本文档的数当准。

### 研报库为什么放 S3 而不是 EBS

91GB 这个量级，EBS 与 S3 的月成本只差几美元，**不是决策依据**。真正的两条理由：

1. **实习生用预签名 URL 单独取文件，不用登服务器**——跨地区协作这点差别很实在；
2. **不用预先给 EBS 定容量**，库长到 200GB 也不用停机扩盘。

注意**出网流量费**：S3 直出约 $0.09–0.12/GB。若实习生频繁下载，这块会超过存储费。
对策：走 CloudFront，或按工单取指定文件、不做批量同步。

## 三、认证 —— 上线前必须解决的那一件事

`pipeline/serve.py` **没有任何认证**。它原本是本地单人工具，默认只监听 `127.0.0.1`。
容器里用 `HUB_HOST=0.0.0.0` 放开是为了让反代能访问，
**不是说它可以直接见公网**——后台里有招标控制价与业主商业信息。

**推荐：Cloudflare Access**（零代码改动）

1. 域名接入 Cloudflare，A 记录指向 EC2 弹性 IP，开橙云（代理）；
2. Zero Trust → Access → 添加 Application，指向该域名；
3. 策略按邮箱或邮箱域放行实习生，登录走 Google/GitHub；
4. `Caddyfile` 里已限制**只接受 Cloudflare 回源网段**——没有这条，
   别人拿 IP 直连就绕过了 Access。

替代方案：Tailscale（更封闭，实习生要装客户端）；自建 OIDC（要动代码，
且会破坏「零依赖」铁律，不推荐）。

## 四、部署步骤

```bash
# 0) EC2 上装 docker（Amazon Linux 2023）
sudo dnf install -y docker git && sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user && newgrp docker
# compose v2 插件
mkdir -p ~/.docker/cli-plugins && curl -SL \
  https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o ~/.docker/cli-plugins/docker-compose && chmod +x ~/.docker/cli-plugins/docker-compose
# ↑ x86 用 docker-compose-linux-x86_64；若改用 ARM 机型才换 aarch64

# 1) 取仓库
git clone https://github.com/niuroumiantt/datacenter.git && cd datacenter

# 2) 改域名
vi deploy/Caddyfile        # dc.example.com → 你的真实域名

# 3) 起服务
docker compose -f deploy/docker-compose.yml up -d --build

# 4) 自检——**这三条都过了才算部署成功**
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml exec hub python3 pipeline/validate.py --strict
curl -sf http://localhost/  && echo "反代通"    # 未接 Cloudflare 时会被 403 拦，属预期
```

## 五、更新与数据流

- **代码更新**：`git pull && docker compose -f deploy/docker-compose.yml up -d --build`
- **数据更新**：`data/` `reports/` 是挂载卷，`git pull` 后容器立即看到新数据，不用重建
- **写入方向**：仓库仍是唯一持久层。服务器上的 `data/assignments.json`（派工状态）
  是服务器侧唯一会被写的文件，**需要定期 commit 回仓库**，否则容器重建会丢派工记录

  ```bash
  # 建议加进 crontab，每天一次
  cd /home/ec2-user/datacenter && git add data/assignments.json \
    && git commit -m "派工状态同步" && git push
  ```

## 六、还没解决的问题（上线前要想清楚）

1. **数据分级**：工单已区分「可派实习生」与「内部」，但**数据层没有这个区分**。
   实习生登录后默认能看到全部事实层与打分表，含标了 `sensitive` 的记录。
   要么接受，要么在 `serve.py` 加一层按角色过滤——**这是产品决策，不是技术决策**。
2. **备份**：EBS 快照要开（每日，保留 7 天）。
   仓库本身在 GitHub 有副本，真正只存在于服务器的是派工状态。
3. **news 组件**：`docker-compose.yml` 里的 `news` 服务现在是每小时跑一次的占位循环。
   接真信源前先定：**新闻存正文不存原始 HTML**（正文约 1GB/年，HTML 约 22GB/年），
   且新闻的 `depth` 默认「半自动」——**不得直接进事实层**，须有人读过并提级。
