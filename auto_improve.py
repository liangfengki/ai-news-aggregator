#!/usr/bin/env python3
"""
每20分钟自动检查并优化 AI 资讯站
功能：
1. 检查服务器状态（挂了就重启）
2. 检查数据质量（太少就刷新）
3. 检查功能是否正常
4. 用 Claude Code 自动优化代码
"""
import subprocess
import json
import os
import sys
import sqlite3
import time
from datetime import datetime

PROJECT_DIR = "/Users/liangfengki/Documents/ai信息资讯"
DB_PATH = os.path.join(PROJECT_DIR, "data/news.db")
LOG_PATH = os.path.join(PROJECT_DIR, "improve.log")
PORT = 8080

os.chdir(PROJECT_DIR)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")

def curl_json(path, method="GET"):
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", method, f"http://localhost:{PORT}{path}"],
            capture_output=True, timeout=10
        )
        return json.loads(r.stdout) if r.stdout else None
    except:
        return None

def restart_server():
    """重启服务器"""
    log("正在重启服务器...")
    subprocess.run(["pkill", "-f", "uvicorn app:app"], capture_output=True)
    time.sleep(2)
    subprocess.Popen(
        [".venv/bin/python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(PORT)],
        stdout=open(os.path.join(PROJECT_DIR, "server.log"), "a"),
        stderr=subprocess.STDOUT,
        cwd=PROJECT_DIR,
        start_new_session=True
    )
    time.sleep(5)
    if curl_json("/api/health"):
        log("✓ 服务器重启成功")
        return True
    log("✗ 服务器重启失败")
    return False

def get_improvement_task():
    """根据当前状态决定优化任务"""
    # 检查数据
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        highlights = conn.execute("SELECT COUNT(*) FROM news WHERE is_highlight=1").fetchone()[0]
        conn.close()
    else:
        total = 0
        highlights = 0

    # 检查服务器
    health = curl_json("/api/health")
    search = curl_json("/api/search?q=test&limit=1")
    trending = curl_json("/api/trending")

    tasks = []

    if not health:
        tasks.append("服务器未运行")
    if total < 50:
        tasks.append(f"新闻太少({total}条)")
    if highlights < 3:
        tasks.append(f"重要快讯太少({highlights}条)")
    if not search or search.get("count", 0) == 0:
        tasks.append("搜索功能异常")
    if not trending or len(trending.get("topics", [])) < 3:
        tasks.append("趋势话题不足")

    return tasks

def run_claude_improvement(task_desc):
    """用 Claude Code 执行优化"""
    prompt = f"""你是 AI 资讯站的自动优化工程师。项目在 {PROJECT_DIR}

当前问题：{task_desc}

请检查项目代码并修复这个问题。只修改必要的文件，不要破坏现有功能。
修改完成后重启服务器：pkill -f 'uvicorn app:app' 然后 cd {PROJECT_DIR} && .venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port {PORT}

注意：
- 不要修改数据库
- 不要删除已有数据
- 只做代码层面的修复和优化
"""

    try:
        result = subprocess.run(
            ["claude", "--permission-mode", "bypassPermissions", "--print", prompt],
            capture_output=True, text=True, timeout=300,
            cwd=PROJECT_DIR
        )
        if result.returncode == 0:
            log(f"✓ Claude 优化完成")
            return True
        else:
            log(f"⚠ Claude 优化失败: {result.stderr[:100]}")
            return False
    except subprocess.TimeoutExpired:
        log("⚠ Claude 优化超时")
        return False
    except Exception as e:
        log(f"⚠ Claude 执行错误: {e}")
        return False

def check_and_fix():
    """主检查流程"""
    log("=" * 50)
    log("开始自动检查...")

    # 1. 服务器
    health = curl_json("/api/health")
    if not health:
        if not restart_server():
            log("服务器重启失败，跳过本次")
            return
    else:
        log(f"✓ 服务器运行中")

    # 2. 数据检查
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        sources = conn.execute("SELECT COUNT(DISTINCT source) FROM news").fetchone()[0]
        conn.close()
        log(f"✓ 新闻 {total}条, 源 {sources}个")
        if total < 30:
            log("新闻太少，触发刷新...")
            curl_json("/api/refresh", "POST")

    # 3. 功能检查
    s = curl_json("/api/search?q=AI&limit=1")
    if s and s.get("count", 0) > 0:
        log(f"✓ 搜索正常")
    else:
        log("⚠ 搜索异常")

    t = curl_json("/api/trending")
    if t and t.get("topics"):
        log(f"✓ 趋势 {len(t['topics'])}个话题")
    else:
        log("⚠ 趋势异常")

    # 4. 决定是否需要优化
    tasks = get_improvement_task()
    if tasks:
        log(f"发现 {len(tasks)} 个问题，开始优化...")
        for task in tasks:
            log(f"  优化: {task}")
            run_claude_improvement(task)
    else:
        log("✓ 一切正常，无需优化")

    log("检查完成\n")

if __name__ == "__main__":
    check_and_fix()
