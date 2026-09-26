#!/bin/bash
# 双击启动懂听网页版（macOS）。第一次会先安装依赖，再打开 .env 让你填 API Key。
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ] || [ ! -d frontend-v2/node_modules ]; then
  python3 scripts/web.py install || { read -r -p "安装失败，按回车关闭…"; exit 1; }
  echo
  echo "请在打开的 .env 里填好 API Key，保存后再双击 start-web.command 启动。"
  open -e .env
  read -r -p "按回车关闭…"
  exit 0
fi
exec python3 scripts/web.py
