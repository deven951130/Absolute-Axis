FROM python:3.11-slim

# 系統依賴：安裝網路工具與硬碟監控工具
RUN apt-get update && apt-get install -y \
    iputils-ping \
    curl \
    util-linux \
    smartmontools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先複製 requirements.txt 並安裝依賴
# 利用 Docker layer cache：只有 requirements.txt 變更時才重新安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再複製全部程式碼
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
