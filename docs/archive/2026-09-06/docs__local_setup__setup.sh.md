> HISTORICAL — 已被替代。保存于 2026-09-06；下文是历史原文，不构成当前指令、授权或服务状态。现行入口：[当前基准](../../../framework/CURRENT.md)。

#!/bin/bash
# 本机一次性迁移 + 常驻服务安装（macOS）。幂等：重复跑安全。
#
# 做四件事：
#   1. 文件夹归一：~/code/datacenter → ~/code/inresearch.ai；
#      ~/code/datacenter-reader → ~/code/inresearch.ai/reader（gitignore，不进 git）
#   2. git 远端指到改名后的仓库 InResearch.ai
#   3. 旧 launchd（com.datacenterhub.*）退役，装新三件套 com.inresearch.{server,collect,sync}
#   4. 体检：本地站点、远端连通、首次拉取
#
# 用法：bash ~/code/datacenter/docs/local_setup/setup.sh   # 迁移前的老路径
#   或：bash ~/code/inresearch.ai/docs/local_setup/setup.sh # 迁移后重跑（只重装服务）
set -e
NEW="$HOME/code/inresearch.ai"
OLD="$HOME/code/datacenter"
OLD_READER="$HOME/code/datacenter-reader"
LA="$HOME/Library/LaunchAgents"

echo "── 1/4 文件夹归一 ──"
if [ -d "$OLD" ] && [ -d "$NEW" ]; then
  echo "❌ $OLD 与 $NEW 同时存在，分不清哪个是真身，请人工确认后删掉/改名其一再跑"
  exit 1
fi
if [ -d "$OLD" ]; then
  mv "$OLD" "$NEW"
  echo "已迁移 $OLD → $NEW"
fi
[ -d "$NEW" ] || { echo "❌ 找不到 $NEW（也没有 $OLD 可迁）"; exit 1; }

if [ -d "$OLD_READER" ]; then
  if [ -e "$NEW/reader" ]; then
    echo "❌ $NEW/reader 已存在，$OLD_READER 没处放，请人工确认后再跑"
    exit 1
  fi
  mv "$OLD_READER" "$NEW/reader"
  echo "已迁移 $OLD_READER → $NEW/reader"
fi

echo "── 2/4 git 远端 ──"
git -C "$NEW" remote set-url origin https://github.com/niuroumiantt/InResearch.ai.git
echo "origin → https://github.com/niuroumiantt/InResearch.ai.git"

echo "── 3/4 launchd：旧退役、新上岗 ──"
for L in com.datacenterhub.server com.datacenterhub.collect; do
  launchctl unload "$LA/$L.plist" 2>/dev/null || true
  rm -f "$LA/$L.plist"
done
mkdir -p "$LA" "$NEW/logs"

# 常驻网页服务器（本地 http://localhost:8000，开机自启、崩溃拉起）
cat > "$LA/com.inresearch.server.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.inresearch.server</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>pipeline/serve.py</string>
  </array>
  <key>WorkingDirectory</key><string>$NEW</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$NEW/logs/server.log</string>
  <key>StandardErrorPath</key><string>$NEW/logs/server.log</string>
</dict></plist>
EOF

# 每日 08:00 采集 + 采集完即推送（简报当天上站，不等下一轮同步）
cat > "$LA/com.inresearch.collect.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.inresearch.collect</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>-c</string>
    <string>cd "$NEW" &amp;&amp; /usr/bin/python3 pipeline/collect.py >> logs/collect.log 2>&amp;1; /bin/bash docs/local_setup/sync.sh --push >> logs/collect.log 2>&amp;1</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$NEW/logs/collect.log</string>
  <key>StandardErrorPath</key><string>$NEW/logs/collect.log</string>
</dict></plist>
EOF

# 每 30 分钟双向同步（拉最新 + 过闸的本机改动自动上站）
cat > "$LA/com.inresearch.sync.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.inresearch.sync</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>$NEW/docs/local_setup/sync.sh</string><string>--push</string>
  </array>
  <key>WorkingDirectory</key><string>$NEW</string>
  <key>StartInterval</key><integer>1800</integer>
  <key>StandardOutPath</key><string>$NEW/logs/sync.log</string>
  <key>StandardErrorPath</key><string>$NEW/logs/sync.log</string>
</dict></plist>
EOF

for L in com.inresearch.server com.inresearch.collect com.inresearch.sync; do
  launchctl unload "$LA/$L.plist" 2>/dev/null || true
  launchctl load "$LA/$L.plist"
done
echo "已装载：server（常驻）/ collect（每日 08:00）/ sync（每 30 分钟）"

echo "── 4/4 体检 ──"
bash "$NEW/docs/local_setup/sync.sh" || true
sleep 2
if curl -sI http://localhost:8000 2>/dev/null | head -1 | grep -q .; then
  echo "✅ 本地站点在跑：http://localhost:8000"
else
  echo "⚠️ 本地站点还没起来，稍候看 $NEW/logs/server.log"
fi
echo
echo "完成。今后："
echo "  · 本地永远最新：sync 每 30 分钟自动拉取"
echo "  · 本机改动过 validate 后自动 push，服务器 2 分钟内上线"
echo "  · 启动精读：bash $NEW/docs/local_reader/start.sh（reader 已在 $NEW/reader）"
