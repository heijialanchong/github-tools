"""
从 GitHub 批量下载仓库到本地

仓库名配置在 config.py 的 DOWNLOAD_REPOS 列表中。
详细参数（路径、分支等）从 projects.json 读取。
下载位置: projects.json 中配置的 path 字段

用法:
    python 2_Github项目下载.py                  # 下载全部
    python 2_Github项目下载.py --project 0      # 只下载第 0 个
    python 2_Github项目下载.py --dry-run        # 仅预览
"""

import os
import sys
import json
import subprocess
import argparse

from config import DOWNLOAD_REPOS

# Windows 中文环境修复 emoji 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 工具函数
# ============================================================

def run(cmd, cwd=None):
    """运行命令，实时打印输出"""
    print(f"    ➤ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
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

def process_repo(proj, github, index, total):
    """处理单个仓库"""
    username, token, _, proxy = github
    repo_name = proj["repo"]
    target_dir = proj["path"]
    branch = proj.get("branch", "main")
    depth = proj.get("depth", 0)

    print(f"\n{'=' * 60}")
    print(f"  [{index + 1}/{total}] {username}/{repo_name}")
    print(f"  分支: {branch}")
    if depth > 0:
        print(f"  浅克隆深度: {depth}")
    print(f"  本地: {target_dir}")
    print(f"{'=' * 60}")

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

    if success:
        print(f"\n  ✅ [{index + 1}/{total}] {repo_name} - {action}成功!")
    else:
        print(f"\n  ❌ [{index + 1}/{total}] {repo_name} - 失败")

    return success


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="从 GitHub 批量下载仓库到本地")
    parser.add_argument("--project", "-p", type=int, default=None,
                        help="只下载指定索引的仓库 (从 0 开始)")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅预览，不实际执行")
    args = parser.parse_args()

    # 1. 检查 config.py
    if not DOWNLOAD_REPOS:
        print("✗ config.py 中 DOWNLOAD_REPOS 为空，请先添加要下载的仓库名")
        sys.exit(1)

    # 2. 加载 projects.json
    github, all_projects = load_config()

    # 3. 按 DOWNLOAD_REPOS 筛选匹配的项目
    repo_set = set(DOWNLOAD_REPOS)
    matched = [p for p in all_projects if p.get("repo") in repo_set]
    missing = repo_set - {p.get("repo") for p in all_projects}
    if missing:
        print(f"⚠ projects.json 中未找到: {', '.join(missing)}")
    if not matched:
        print("✗ 没有匹配的项目可以下载")
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
        if args.dry_run:
            target = proj["path"]
            git_dir = os.path.join(target, ".git")
            action = "拉取最新" if os.path.isdir(git_dir) else "克隆"
            print(f"\n  [{i + 1}/{len(repos)}] 🔍 {proj['repo']} → {action} → {target}")
            results.append(True)
        else:
            ok = process_repo(proj, github, i, len(repos))
            results.append(ok)

    # 8. 报告
    print(f"\n{'=' * 60}")
    print(f"  📊 完成: {sum(results)} 成功 / {len(results) - sum(results)} 失败")
    print(f"{'=' * 60}")

    sys.exit(0 if sum(results) == len(results) else 1)


if __name__ == "__main__":
    main()