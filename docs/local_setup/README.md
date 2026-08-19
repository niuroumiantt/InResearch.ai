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

## 从 MacBook 整体搬到 Mac mini（2026-08-19）

**路径两台保持一致**：都是 `~/code/inresearch.ai/`。所以 launchd plist、文档、脚本里的路径
一个字都不用改——这也是 08-18「一个文件夹」归一的红利。

在 Mac mini 上拉（拉取式，MacBook 中途睡眠也能续传）：

```bash
mkdir -p ~/code && rsync -aHh --info=progress2 --exclude 'logs/' \
  <MacBook主机名或IP>:~/code/inresearch.ai/  ~/code/inresearch.ai/
```

Finder 直接拖整个文件夹也行——但**要确认隐藏的 `.git/` 和 91GB 的 `docs/library/` 都跟着过来了**
（`.git` 没过来 = 拿到的是一堆文件不是仓库；`docs/library/` 是 gitignore 的，git 永远不会替你搬它）。

搬完三件事，缺一不可：

```bash
cd ~/code/inresearch.ai
git status && git pull origin main        # 1. 确认在 main、工作区干净，拉一次最新
bash docs/local_setup/setup.sh            # 2. 装 launchd 三件套（幂等，重复跑安全）
# 3. 回 MacBook：停掉它的自动推送
launchctl unload ~/Library/LaunchAgents/com.inresearch.sync.plist
```

第 3 步为什么不能省，见下节。

## 为什么只能有一台自动推送机（而多人走 PR 完全没问题）

**这两件事不是一回事，别混：**

- **多人远程通过 GitHub 提 PR —— 没问题，git 本来就是干这个的。** 谁在哪台机器上写都行，
  冲突在 PR 里显式暴露、由人解决、有 review 记录。人越多越该这么走。
- **有问题的是「两台机器同时跑无人值守的自动推送」。** `sync.sh --push` 干的是
  `git add -A` + 直接 commit 到 **main**——**绕过 PR、绕过 review、没有人看**。
  它入账的是「本机工作区当时的样子」，**包括删除**：手滑拖走一个目录、拷贝没拷完、
  rebase 中断留下半截状态，30 分钟后都会被原样提交上 main，服务器 2 分钟内跟着上线。
  两台各跑一份，最终谁说了算只取决于时序——而没人知道时序。

所以规则是**「只有一台机器开自动推送」，不是「只有一个人能提交」**。
MacBook 保留只读拉取（`sync.sh` 不带 `--push`）随便看、随便本地跑；
真要从 MacBook 改东西，就和其他人一样走分支 + PR。

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
