#!/bin/bash

PROJECT_DIR="/Users/zhangzuhao/code-project/Podcast-summary"

cd "$PROJECT_DIR" || exit 1

echo "正在启动 Podcast Summary..."
echo "数据库初始化中..."
. .venv/bin/activate && PYTHONPATH=backend/src python scripts/init_db.py

echo "启动后端服务 (端口 8000)..."
. .venv/bin/activate && PYTHONPATH=backend/src uvicorn podsum.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

echo "启动前端服务 (端口 5174)..."
npm --prefix frontend-v2 run dev -- --host 127.0.0.1 --port 5174 &
FRONTEND_PID=$!

echo "等待服务启动..."
sleep 3

echo "打开浏览器..."
open "http://127.0.0.1:5174"

echo "✅ Podcast Summary 已启动"
echo "   前端: http://127.0.0.1:5174"
echo "   后端: http://127.0.0.1:8000"
echo ""
echo "关闭此窗口将停止所有服务。"

# 等待子进程，Ctrl+C 或关闭窗口时一并结束
wait $BACKEND_PID $FRONTEND_PID
