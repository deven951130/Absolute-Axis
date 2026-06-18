import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # 支援最大 2 GB 上傳（Minecraft 模組包用）
        h11_max_incomplete_event_size=2 * 1024 * 1024 * 1024,
        # 大檔案上傳時保持長連線
        timeout_keep_alive=600,
    )
