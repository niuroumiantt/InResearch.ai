# 本机环境（macOS）——一个文件夹 + 三个常驻服务

> 2026-08-18 起，本机只有一个项目文件夹：**`~/code/inresearch.ai/`**。
> 原 `~/code/datacenter`（主仓库）与 `~/code/datacenter-reader`（精读工作区）
> 分别迁为它本体与它的 `reader/` 子目录（reader 不进 git，见 .gitignore）。

## 一次性迁移

```bash
bash ~/code/datacenter/docs/local_setup/setup.sh
```

幂等，重复跑安全。做四件事：文件夹归一 → git 远端指向改名后的 InResearch.ai
→ 旧 launchd（com.datacenterhub.*）退役并装新三件套 → 体检。
91GB 研报库（`docs/library/`）随文件夹整体平移，不复制不重传。

## 同步架构（迁移后自动生效）

```
本机 ~/code/inresearch.ai ──(sync 每 30 分钟)──▶ GitHub ──(服务器 autopull ≤2 分钟)──▶ inresearch.ai
        ▲                                          │
        └────────────(sync 拉取)◀──────────────────┘  云端会话的合并、成员的投递，本机半小时内拿到
```

- **GitHub → 本机**：`com.inresearch.sync` 每 30 分钟 `pull --rebase --autostash`，
  本地永远有最新内容；未提交的手工改动自动暂存再放回，不会丢。
- **本机 → 网站**：同一个 sync 带 `--push`——本机改动先过
  `validate.py --strict`（0 warnings），过了才 commit + push，服务器 autopull 接力上线。
  **校验不过就留在本地并记 `logs/sync.log`，绝不硬推**——铁律是闸门不是摆设。
- **冲突不自动裁决**：与远端真冲突时 sync 中止留言，人工 `git pull` 处理。

## 三个 launchd 服务

| 服务 | 作用 | 日志 |
|---|---|---|
| `com.inresearch.server` | 本地站点 http://localhost:8000 常驻（开机自启、崩溃拉起） | `logs/server.log` |
| `com.inresearch.collect` | 每日 08:00 跑 `collect.py`，采集完立即 sync --push，简报当天上站 | `logs/collect.log` |
| `com.inresearch.sync` | 每 30 分钟双向同步（上面那条链路） | `logs/sync.log` |

管理：`launchctl unload ~/Library/LaunchAgents/com.inresearch.<名>.plist` 停用，
`load` 恢复；改了 plist 先 unload 再 load。

## 手动同步

```bash
bash docs/local_setup/sync.sh          # 只拉取
bash docs/local_setup/sync.sh --push   # 拉取 + 推送（同自动逻辑）
```

## 两台机器的分工（2026-08-19 用户拍板）

**Mac mini = 主力机**：24 小时不关机，是唯一的自动同步机与下载机；launchd 三件套跑在它上面。
**MacBook** 降为移动办公机——研报库 `docs/library/` 迁到 Mac mini（原件留作冷备，
按「数据只留不删」不删），且 **MacBook 上的 sync 必须去掉 `--push` 或整个 unload**：
两台都自动推同一个 main，冲突不自动裁决只会互相顶住，而且没人知道哪台是真的。

产品官方资料库（`/admin/product/` 看板那套）落在 Mac mini 的外置卷上，
仓库里只有一个软链 `product/` 指过去 —— 落点、命令与试爬流程见
[`PRODUCT_LIBRARY.md`](PRODUCT_LIBRARY.md)。

## 注意

- 自动同步**只动 main 分支**：本机切到别的分支时 sync 自动跳过，不添乱。
- 精读工作区 `reader/` 在主文件夹里但**不进 git**（有自己的状态与缓存）；
  启动精读照旧 `bash docs/local_reader/start.sh`。
- SEC 采集（update_ciks.py / fetch_sec.py）仍须本机跑——云端网络策略屏蔽 sec.gov。
