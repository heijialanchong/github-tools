"""
克隆任意 GitHub 仓库到本地

用法:
    python 3_Github仓库克隆.py https://github.com/alchaincyf/zhangxuefeng-skill.git
    python 3_Github仓库克隆.py alchaincyf/zhangxuefeng-skill
    python 3_Github仓库克隆.py alchaincyf/zhangxuefeng-skill --dir E:/downloads/zhangxuefeng
    python 3_Github仓库克隆.py alchaincyf/zhangxuefeng-skill -b dev --depth 1

下载位置默认: repos/仓库名
"""

import os
import sys
import re
import subprocess
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_repo(target):
    """解析仓库地址 → (owner, repo_name)"""
    # https://github.com/owner/repo.git 或 https://github.com/owner/repo
    m = re.match(r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$', target)
    if m:
        return m.group(1), m.group(2)
    # git@github.com:owner/repo.git
    m = re.match(r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$', target)
    if m:
        return m.group(1), m.group(2)
    # owner/repo
    m = re.match(r'^([^/]+)/([^/]+)$', target)
    if m:
        return m.group(1), m.group(2)

    print(f"✗ 无法解析: {target}")
    print("  支持格式: https://github.com/owner/repo.git 或 owner/repo")
    sys.exit(1)


def main():
    # 如果没有传参数（比如 PyCharm 直接运行），则交互式输入
    if len(sys.argv) == 1:
        print("=" * 60)
        print("  GitHub 仓库克隆工具")
        print("=" * 60)
        repo = input("\n📥 请输入仓库地址 (URL 或 owner/repo): ").strip()
        if not repo:
            print("✗ 未输入仓库地址，退出")
            sys.exit(1)
        branch = input("🌿 分支名 (直接回车跳过): ").strip() or None
        depth_str = input("📏 克隆深度 (直接回车=完整克隆): ").strip()
        depth = int(depth_str) if depth_str else 0
        target_dir_input = input("📁 目标目录 (直接回车=默认 repos/仓库名): ").strip()
        target_dir = target_dir_input or None

        # 构造一个简易 args 对象
        class Args:
            pass
        args = Args()
        args.repo = repo
        args.branch = branch
        args.depth = depth
        args.dir = target_dir
    else:
        parser = argparse.ArgumentParser(description="克隆 GitHub 仓库到本地")
        parser.add_argument("repo", help="仓库地址 (URL 或 owner/repo)")
        parser.add_argument("--dir", "-d", default=None, help="目标目录 (默认: repos/仓库名)")
        parser.add_argument("--branch", "-b", default=None, help="分支名 (默认: 仓库默认分支)")
        parser.add_argument("--depth", type=int, default=0, help="浅克隆深度 (0=完整克隆)")
        args = parser.parse_args()

    owner, repo_name = parse_repo(args.repo)
    target_dir = args.dir or os.path.join(SCRIPT_DIR, "repos", repo_name)

    if os.path.exists(target_dir) and os.listdir(target_dir):
        print(f"✗ 目录已存在且非空: {target_dir}")
        sys.exit(1)

    clone_url = f"https://github.com/{owner}/{repo_name}.git"

    print("=" * 60)
    print(f"  📥 {owner}/{repo_name}")
    print(f"  📁 {target_dir}")
    if args.branch:
        print(f"  🌿 {args.branch}")
    if args.depth > 0:
        print(f"  📏 --depth {args.depth}")
    print("=" * 60)

    cmd = ["git", "clone"]
    if args.branch:
        cmd.extend(["-b", args.branch])
    if args.depth > 0:
        cmd.extend(["--depth", str(args.depth)])
    cmd.extend([clone_url, target_dir])

    print(f"  ➤ {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"\n✅ 完成: {target_dir}")
    else:
        print(f"\n❌ 克隆失败")
        sys.exit(1)


if __name__ == "__main__":
    main()