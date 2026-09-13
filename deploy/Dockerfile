# Datacenter Hub —— 零依赖，所以镜像也该是零依赖的。
# 不装任何 pip 包：本项目是Python 标准库包 + 显式页面与共享组件。
# 镜像里出现 requirements.txt 或 pip install，说明有人破坏了那条铁律。
FROM python:3.12-slim

WORKDIR /app
COPY . /app

# 容器内需要绑 0.0.0.0 才能被反代访问；绑非本机地址时 HTTP 入口 **自动强制开启内置
# 登录认证**（auth.py，2026-08-18 起），失败模式是锁死不是敞开；前置 Caddy 只做 TLS 与分流。
ENV HUB_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# 健康检查用静态首页而不是 /api/status——后者会 stat 一堆日志文件，
# 每 30 秒跑一次没必要，而且日志目录不存在时它的行为不该决定容器存活。
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/index.html').read(1)" || exit 1

CMD ["python3", "manage.py", "serve", "8000"]
