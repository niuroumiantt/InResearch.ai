# inews.today —— AI 新闻时间线。
#
# 零 npm 依赖:整个应用只用 Node 内置的 fetch / node:sqlite / node:http,
# 所以镜像里没有 node_modules,也没有 npm install 这一步。
# node:sqlite 需要 Node >= 22.5。
FROM node:24-alpine

# 采集器按 Google News 的 pubDate 排序,时区错了时间线会整体偏移。
ENV TZ=Asia/Shanghai \
    NODE_ENV=production \
    PORT=8789 \
    INEWS_DATA_DIR=/data
RUN apk add --no-cache tzdata curl

# 版本号在构建时以参数传入,镜像里不带 .git。
# 服务器上的仓库克隆 .git/config 里存着 GitHub 令牌 —— 把 .git 复制进镜像
# 等于把凭据焊进镜像层,之后镜像一旦被导出或推到 registry 就泄露。
ARG GIT_SHA=unknown
ENV APP_VERSION=$GIT_SHA

WORKDIR /app
COPY . .

# SQLite 落在挂载卷上,容器重建不丢。autopull 每次 push 都会重建容器 ——
# 数据库不挂出来的话,几周攒下来的域名评分每两分钟面临清零。
RUN mkdir -p /data && chown -R node:node /data /app
USER node
VOLUME ["/data"]
EXPOSE 8789

HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/version" > /dev/null || exit 1

# serve = HTTP 服务 + 常驻采集器(同一进程,见 src/cli.js)
CMD ["node", "--no-warnings", "src/cli.js", "serve"]
