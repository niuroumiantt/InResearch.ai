#!/usr/bin/env bash
# 把一个本地原文库产出推到 inews.today/rawarticle/<site>/。
#
# 为什么是 rsync 而不是 git push:
#   服务器上的其它站都走「push 到 GitHub → autopull 拉取」,但那条路对这里不适用——
#   正文来自站长个人订阅,**不能进公开仓库**。所以内容只在两个地方存在:
#   自己的机器,和服务器上那个只读挂载的目录。仓库里只有生成它的代码。
#
# 服务器侧由 infra 仓库定义 `/srv/rawarticle` 的只读容器挂载；Node 的
# `/rawarticle/*` 路由直接执行 requireStaff，未登录或非 staff 都读不到正文。
#
#   bash tools/publish.sh                 # 默认推 out/FT.COM
#   RAW_OUT=out/FT.COM bash tools/publish.sh
#   RAW_HOST=ubuntu@32.193.21.111 bash tools/publish.sh   # 不走 ssh 配置时写全
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

OUT=${RAW_OUT:-$ROOT/out/FT.COM}
# 默认走 ssh 配置里的别名而不是写死 IP:公钥、用户名、端口都在 ~/.ssh/config 里,
# 写死 IP 会绕开那份配置,于是本机手敲 ssh 通、rsync 却 Permission denied。
HOST=${RAW_HOST:-inews}
DEST=${RAW_DEST:-/srv/rawarticle/ft}

[ -f "$OUT/index.html" ] || { echo "没有可发布的产出:$OUT/index.html 不存在,先跑一轮 inews" >&2; exit 1; }

# --delete:本地是唯一真源,服务器只是它的镜像。少了这个开关,几轮之后服务器上
# 会留着一堆本地已经不存在、清单里也链不到的孤儿页面。
#
# `data/` 整个不发:台账、跑批记录、正文存档都在里面,全是**抓取的内部状态**。
# 存档尤其不发 —— 它是正文的正本,只该留在本机(和本机的备份里)。
# 一条 exclude 而不是四条:多一个状态文件时,忘记加 exclude 的机会就少一次。
rsync -avz --delete \
  --exclude 'data/' \
  "$OUT/" "$HOST:$DEST/"

# 完成语从真实的 DEST 推导 —— 9-02 首轮 Bloomberg 发布时这里写死了 ft,
# rsync 推对了地方,提示语却在撒谎。日志里的每一句都得对得上事实。
echo "已发布 → https://inews.today/rawarticle/${DEST##*/}/"
