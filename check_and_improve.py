#!/usr/bin/env python3
"""自动检查并改进 AI 资讯站"""
import subprocess
import json
import sys
import os

os.chdir("/Users/liangfengki/Documents/ai信息资讯")

def check():
    issues = []
    
    # 1. 服务器是否运行
    try:
        r = subprocess.run(["curl", "-s", "http://localhost:8080/api/health"], capture_output=True, timeout=5)
        health = json.loads(r.stdout)
        print(f"✓ 服务器运行中, uptime: {health.get('uptime', 0):.0f}s")
    except:
        issues.append("服务器挂了，需要重启")
        print("✗ 服务器未运行")
        return issues
    
    # 2. 新闻数量
    try:
        r = subprocess.run(["curl", "-s", "http://localhost:8080/api/stats"], capture_output=True, timeout=5)
        stats = json.loads(r.stdout)
        total = stats.get("total", 0)
        sources = len(stats.get("sources", {}))
        highlights = stats.get("highlights", 0)
        print(f"✓ 新闻: {total}条, 源: {sources}个, 重要: {highlights}条")
        if total < 50:
            issues.append(f"新闻太少({total}条)")
        if sources < 5:
            issues.append(f"活跃源太少({sources}个)")
    except:
        issues.append("无法获取统计")
    
    # 3. 搜索功能
    try:
        r = subprocess.run(["curl", "-s", "http://localhost:8080/api/search?q=test&limit=1"], capture_output=True, timeout=5)
        d = json.loads(r.stdout)
        print(f"✓ 搜索正常, 结果: {d.get('count', 0)}条")
    except:
        issues.append("搜索功能异常")
    
    # 4. 趋势话题
    try:
        r = subprocess.run(["curl", "-s", "http://localhost:8080/api/trending"], capture_output=True, timeout=5)
        d = json.loads(r.stdout)
        topics = len(d.get("topics", []))
        print(f"✓ 趋势话题: {topics}个")
    except:
        issues.append("趋势话题异常")
    
    return issues

if __name__ == "__main__":
    print(f"\n=== AI 资讯站检查 {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()} ===")
    issues = check()
    if issues:
        print(f"\n⚠ 发现 {len(issues)} 个问题:")
        for i in issues:
            print(f"  - {i}")
    else:
        print("\n✓ 一切正常")
