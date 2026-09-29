"""
从 GitHub 批量下载仓库到本地

仓库配置在 config.py 的 DOWNLOAD_REPOS 字典中：
    {仓库名: 上传时间(UTC)}，时间留空 "" = 下载最新版，填时间 = 下载对应历史版本。
详细参数（分支、浅克隆深度等）从 projects.json 读取。
下载位置: 脚本目录下的 repos/<仓库名>/

用法:
    python 2_Github项目下载.py                  # 下载全部
    python 2_Github项目下载.py --project 0      # 只下载第 0 个
    python 2_Github项目下载.py --dry-run        # 仅预览
"""

import os
import sys
import json
import re
import subprocess
import argparse
from datetime import datetime, timezone
from urllib import request, error

from config import CONFIG

DOWNLOAD_REPOS = CONFIG["download_repos"]

# Windows 中文环境修复 emoji 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(SCRIPT_DIR, "repos")  # 下载的仓库统一放这里


# ============================================================
# 工具函数
# ============================================================

def run(cmd, cwd=None):
    """运行命令，实时打印输出"""
    print(f"    ➤ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=cwd)
    if result.returncode != 0:
        print(f"    ✗ {result.stderr.strip()}")
    elif result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            print(f"      {line}")
    return result


def load_config():
    """加载 projects.json，返回 (github账号, 项目列表)"""
    path = os.path.join(SCRIPT_DIR, "projects.json")
    if not os.path.isfile(path):
        print("✗ projects.json 不存在，请先创建")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    github = config.get("github", {})
    username = github.get("username", "")
    token = github.get("token", "")
    email = github.get("email", "")
    proxy = github.get("proxy", "")

    if not username or "你的GitHub用户名" in username:
        print("✗ 请在 projects.json 中填写真实的 GitHub 用户名")
        sys.exit(1)
    if not token or "ghp_xxx" in token:
        print("✗ 请在 projects.json 中填写真实的 GitHub Token")
        sys.exit(1)

    return (username, token, email, proxy), config.get("projects", [])


def configure_git_user(username, email):
    """确保 Git 全局用户信息已配置"""
    name = subprocess.run(
        ["git", "config", "--global", "user.name"],
        capture_output=True, text=True
    ).stdout.strip()
    if not name:
        run(["git", "config", "--global", "user.name", username])

    mail = subprocess.run(
        ["git", "config", "--global", "user.email"],
        capture_output=True, text=True
    ).stdout.strip()
    if not mail:
        run(["git", "config", "--global", "user.email", email])


# ============================================================
# 按上传时间下载历史版本
# ============================================================

def parse_utc_time(s: str):
    """解析日志中的 UTC 时间。

    支持直接填 "2026-09-28 07:05:45"，或整行复制日志：
    "上传成功 | UTC: 2026-09-28 07:05:45 | 北京时间(UTC+8): 2026-09-28 15:05:45"
    注意：匹配的是 UTC 时间，不是北京时间。
    """
    s = s.strip()
    if "UTC:" in s:
        s = s.split("UTC:", 1)[1]
    m = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", s)
    if not m:
        raise ValueError("未找到时间，格式应为 YYYY-MM-DD HH:MM:SS")
    return datetime.strptime(m.group(0), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def api_request(token: str, endpoint: str):
    """调用 GitHub API，返回 (status_code, body)"""
    req = request.Request(f"https://api.github.com{endpoint}")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def find_commit_by_time(username: str, token: str, repo_name: str, target_time):
    """查找与目标时间最接近的提交，返回 dict(sha, date, message, delta_seconds) 或 None"""
    all_commits = []
    for page in range(1, 4):  # 最多拉取 300 条提交
        status, commits = api_request(
            token, f"/repos/{username}/{repo_name}/commits?per_page=100&page={page}"
        )
        if status != 200 or not isinstance(commits, list) or not commits:
            break
        all_commits.extend(commits)
        if len(commits) < 100:
            break

    if not all_commits:
        print("  ✗ 仓库没有可用的提交记录")
        return None

    best = None
    for c in all_commits:
        date_str = c["commit"]["committer"]["date"].replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(date_str)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = abs((dt - target_time).total_seconds())
        if best is None or delta < best[0]:
            best = (delta, c["sha"], dt, c["commit"]["message"].split("\n")[0])
    if best is None:
        print("  ✗ 无法解析提交时间")
        return None
    return {"sha": best[1], "date": best[2], "message": best[3], "delta_seconds": best[0]}


def checkout_version(repo_name, branch, target_dir, proxy, commit_info):
    """在已克隆的仓库中检出指定提交"""
    # 浅克隆需要先补齐完整历史
    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        capture_output=True, text=True, cwd=target_dir
    ).stdout.strip()
    if shallow == "true":
        print("  ℹ 检测到浅克隆，拉取完整历史 ...")
        r = run(["git", "fetch", "--unshallow", "origin"], cwd=target_dir)
        if r.returncode != 0:
            r = run(["git", "fetch", "origin", branch], cwd=target_dir)
    else:
        run(["git", "fetch", "origin", branch], cwd=target_dir)

    sha = commit_info["sha"]
    r = run(["git", "checkout", sha], cwd=target_dir)
    if r.returncode != 0:
        print(f"  ✗ 检出提交失败: {sha}")
        return False
    print(f"  ✓ 已检出到 {commit_info['date'].strftime('%Y-%m-%d %H:%M:%S')} UTC (提交 {sha[:8]}, detached HEAD)")
    return True


# ============================================================
# 核心操作
# ============================================================

def clone_repo(username, token, repo_name, branch, depth, target_dir, proxy):
    """克隆仓库"""
    clone_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"

    env = os.environ.copy()
    if proxy:
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy

    cmd = ["git", "clone", "-b", branch]
    if depth > 0:
        cmd.extend(["--depth", str(depth)])
    cmd.extend([clone_url, target_dir])

    print(f"  📥 克隆 {username}/{repo_name} ...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR, env=env)

    if result.returncode != 0:
        print(f"    ✗ {result.stderr.strip()}")
        return False

    for line in result.stdout.strip().split("\n"):
        print(f"      {line}")
    print(f"  ✓ 克隆完成: {target_dir}")
    return True


def pull_repo(repo_name, branch, target_dir, proxy):
    """拉取最新代码"""
    print(f"  📥 拉取最新代码...")

    # 仓库级代理
    if proxy:
        subprocess.run(
            ["git", "config", "--local", "http.proxy", proxy],
            capture_output=True, text=True, cwd=target_dir
        )
        subprocess.run(
            ["git", "config", "--local", "https.proxy", proxy],
            capture_output=True, text=True, cwd=target_dir
        )

    # fetch
    result = run(["git", "fetch", "origin", branch], cwd=target_dir)
    if result.returncode != 0:
        return False

    # 切换到目标分支
    current = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, cwd=target_dir
    ).stdout.strip()

    if current != branch:
        r = run(["git", "checkout", branch], cwd=target_dir)
        if r.returncode != 0:
            r = run(["git", "checkout", "-b", branch, f"origin/{branch}"], cwd=target_dir)
            if r.returncode != 0:
                print(f"  ✗ 无法切换到分支: {branch}")
                return False
        print(f"  ✓ 已切换到: {branch}")

    # merge
    result = run(["git", "merge", f"origin/{branch}"], cwd=target_dir)
    if result.returncode != 0:
        if "Already up to date" in result.stdout or "Already up to date" in result.stderr:
            print(f"  ℹ 已是最新")
            return True
        print(f"  ⚠ 合并冲突，请手动处理")
        return False

    print(f"  ✓ 拉取完成")
    return True


# ============================================================
# 项目处理
# ============================================================

def process_repo(proj, github, index, total, target_time=None):
    """处理单个仓库（可选按上传时间检出历史版本）"""
    username, token, _, proxy = github
    repo_name = proj["repo"]
    target_dir = os.path.join(DOWNLOADS_DIR, repo_name)
    branch = proj.get("branch", "main")
    depth = proj.get("depth", 0)

    # 按时间下载需要完整历史，禁用浅克隆
    if target_time is not None:
        depth = 0

    print(f"\n{'=' * 60}")
    print(f"  [{index + 1}/{total}] {username}/{repo_name}")
    print(f"  分支: {branch}")
    if depth > 0:
        print(f"  浅克隆深度: {depth}")
    if target_time is not None:
        print(f"  目标上传时间: {target_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  本地: {target_dir}")
    print(f"{'=' * 60}")

    # 先通过 GitHub API 定位目标提交
    commit_info = None
    if target_time is not None:
        commit_info = find_commit_by_time(username, token, repo_name, target_time)
        if commit_info is None:
            return False
        print(f"  🎯 匹配提交: {commit_info['sha'][:8]}  {commit_info['date'].strftime('%Y-%m-%d %H:%M:%S')} UTC (偏差 {commit_info['delta_seconds']:.0f}s)")
        print(f"     {commit_info['message'][:60]}")
        if commit_info["delta_seconds"] > 600:
            print("  ⚠ 匹配偏差较大（>10 分钟），请确认填的是 UTC 时间而不是北京时间")

    git_dir = os.path.join(target_dir, ".git")

    if os.path.isdir(git_dir):
        print(f"  ℹ 本地已存在，拉取最新")
        action = "更新"
        success = pull_repo(repo_name, branch, target_dir, proxy)
    elif os.path.isdir(target_dir) and os.listdir(target_dir):
        print(f"  ⚠ 目录已存在且非空，非 git 仓库，跳过")
        return False
    else:
        print(f"  ℹ 本地不存在，克隆仓库")
        action = "克隆"
        success = clone_repo(username, token, repo_name, branch, depth, target_dir, proxy)

    # 检出指定历史版本
    if success and target_time is not None:
        success = checkout_version(repo_name, branch, target_dir, proxy, commit_info)

    if success:
        print(f"\n  ✅ [{index + 1}/{total}] {repo_name} - {action}成功!")
    else:
        print(f"\n  ❌ [{index + 1}/{total}] {repo_name} - 失败")

    return success


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="从 GitHub 批量下载仓库到本地（支持按上传时间下载历史版本）")
    parser.add_argument("--project", "-p", type=int, default=None,
                        help="只下载指定索引的仓库 (从 0 开始)")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅预览，不实际执行")
    args = parser.parse_args()

    # 1. 检查 config.py（兼容列表/字典两种写法：字典值 = 上传时间，留空 = 最新版）
    if isinstance(DOWNLOAD_REPOS, list):
        repos_map = {name: "" for name in DOWNLOAD_REPOS}
    else:
        repos_map = dict(DOWNLOAD_REPOS)
    if not repos_map:
        print("✗ config.py 中 DOWNLOAD_REPOS 为空，请先添加要下载的仓库名")
        sys.exit(1)

    # 2. 加载 projects.json
    github, all_projects = load_config()

    # 3. 按 DOWNLOAD_REPOS 筛选匹配的项目（未在 projects.json 中的用默认配置）
    repo_set = set(repos_map)
    matched = [p for p in all_projects if p.get("repo") in repo_set]
    present = {p.get("repo") for p in all_projects}
    missing = repo_set - present
    for name in sorted(missing):
        print(f"⚠ projects.json 中未找到 {name}，使用默认配置 (main 分支)")
        matched.append({"repo": name, "branch": "main", "depth": 0})
    if not matched:
        print("✗ 没有可下载的仓库")
        sys.exit(1)

    # 4. 筛选
    if args.project is not None:
        if 0 <= args.project < len(matched):
            repos = [matched[args.project]]
        else:
            print(f"✗ 索引 {args.project} 超出范围 (共 {len(matched)} 个)")
            sys.exit(1)
    else:
        repos = matched

    # 5. 头信息
    username, _, email, proxy = github
    print("=" * 60)
    print("  📥 GitHub 批量下载工具")
    print(f"  账号: {username}")
    print(f"  共 {len(repos)} 个仓库")
    if proxy:
        print(f"  代理: {proxy}")
    if args.dry_run:
        print("  ⚠ DRY RUN 模式")
    print("=" * 60)

    # 6. 配置 Git 用户
    configure_git_user(username, email)

    # 7. 逐个处理
    results = []
    for i, proj in enumerate(repos):
        # 解析该仓库的上传时间（若有，留空则下载最新版）
        time_str = repos_map.get(proj["repo"], "").strip()
        target_time = None
        if time_str:
            try:
                target_time = parse_utc_time(time_str)
            except ValueError:
                print(f"✗ 上传时间格式错误: {time_str}（应为 YYYY-MM-DD HH:MM:SS）")
                results.append(False)
                continue

        if args.dry_run:
            target = os.path.join(DOWNLOADS_DIR, proj["repo"])
            git_dir = os.path.join(target, ".git")
            action = "拉取最新" if os.path.isdir(git_dir) else "克隆"
            extra = f" → 检出 {target_time.strftime('%Y-%m-%d %H:%M:%S')}" if target_time else ""
            print(f"\n  [{i + 1}/{len(repos)}] 🔍 {proj['repo']} → {action}{extra} → {target}")
            results.append(True)
        else:
            ok = process_repo(proj, github, i, len(repos), target_time)
            results.append(ok)

    # 8. 报告
    print(f"\n{'=' * 60}")
    print(f"  📊 完成: {sum(results)} 成功 / {len(results) - sum(results)} 失败")
    print(f"{'=' * 60}")

    sys.exit(0 if sum(results) == len(results) else 1)


if __name__ == "__main__":
    main()