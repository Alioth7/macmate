#!/bin/zsh

# 1. 杀掉可能的残留进程，防止端口占用
echo "🧹 清理旧进程..."
killall python3 2>/dev/null
pkill -f bridge_server.py 2>/dev/null

# 2. 定位到当前目录
DIR="/Users/itcmac/Desktop/Agent"
cd "$DIR"

# 3. 启动 Python 后端到后台，并把日志存起来方便排查
echo "🧠 正在启动 AI 大脑 (Python Backend)..."
python3 bridge_server.py > python_log.txt 2>&1 &
PYTHON_PID=$!

# 等待 2 秒让后端初始化
sleep 2

# 4. 启动 Swift 前端
echo "🎨 正在启动原生界面 (Swift UI)..."
cd "$DIR/macos-ui"
MACMATE_PYTHON=$(which python3) swift run

# 5. 当 Swift 退出时，自动杀掉后台的 Python
kill $PYTHON_PID
echo "👋 已全部退出。"
