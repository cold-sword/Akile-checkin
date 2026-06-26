FROM python:3.11-slim

# 安装 Chromium + cron（用于定时签到）
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    cron \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 复制 entrypoint 脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 使用 cron 模式运行（每天定时签到，容器常驻）
ENTRYPOINT ["/entrypoint.sh"]
