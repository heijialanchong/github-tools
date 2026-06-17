"""
删除 GitHub 仓库中的某个文件夹

原理：GitHub API 没有直接"删除文件夹"的接口，但可以通过 git 操作实现：
  1. 拉取仓库到本地（或使用已有克隆）
  2. git rm -r <文件夹>  删除并暂存
  3. git commit + git push  提交并推送

用法:
    python 4_Github删除仓库文件夹.py --repo github-tools --folder old-docs
    python 4_Github删除仓库文件夹.py --repo my-project --folder dist --branch develop
    python 4_Github删除仓库文件夹.py --repo my-project --folder "path/to/folder"

交互模式（不带参数运行）:
    python 4_Github删除仓库文件夹.py
"""

import os
import sys
import json
import subprocess
import argparse
import shutil

from config import HTTP_PROXY, HTTPS_PROXY

# Windows 中文环境修复 emoji 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPOS_DIR = os.path.join(SCRIPT_DIR, "repos")


# ============================================================
# 工具函数
# ============================================================

def run(cmd, cwd=None):
    """运行命令，实时打印输出"""
    print(f"    ➤ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=cwd)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            print(f"    ✗ {stderr}")
    else:
        output = result.stdout.strip()
        if output:
            for line in output.split("\n"):
                print(f"      {line}")
    return result


def load_github_config():
    """从 projects.json 读取 GitHub 账号信息"""
    path = os.path.join(SCRIPT_DIR, "projects.json")
    if not os.path.isfile(path):
        print("✗ projects.json 不存在，请先创建")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    github = config.get("github", {})
    username = github.get("username", "")
    token = github.get("token", "")
    email = github.get("email", f"{username}@users.noreply.github.com")

    if not username or "你的GitHub用户名" in username:
        print("✗ 请在 projects.json 中填写真实的 GitHub 用户名")
        sys.exit(1)
    if not token or "ghp_xxx" in token:
        print("✗ 请在 projects.json 中填写真实的 GitHub Token")
        print("  获取 token: https://github.com/settings/tokens → Generate new token (classic)")
        print("  勾选权限: repo (全部)")
        sys.exit(1)

    return username, token, email


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


def apply_git_proxy():
    """将 config.py 的代理设置同步到 git global config"""
    if HTTP_PROXY:
        subprocess.run(["git", "config", "--global", "http.proxy", HTTP_PROXY], check=False)
        subprocess.run(["git", "config", "--global", "https.proxy", HTTPS_PROXY or HTTP_PROXY], check=False)
        print(f"  🔗 代理已设置: {HTTP_PROXY}")
    else:
        subprocess.run(["git", "config", "--global", "--unset", "http.proxy"], check=False)
        subprocess.run(["git", "config", "--global", "--unset", "https.proxy"], check=False)


# ============================================================
# 核心操作
# ============================================================

def ensure_repo_local(username, token, repo_name, branch):
    """确保仓库在本地存在且是最新：存在则 pull，不存在则 clone"""
    target_dir = os.path.join(REPOS_DIR, repo_name)
    git_dir = os.path.join(target_dir, ".git")
    clone_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"

    if os.path.isdir(git_dir):
        # 已存在 → 拉取最新
        print(f"  📥 拉取最新代码...")

        # 切换到目标分支
        current = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=target_dir
        ).stdout.strip()

        if current != branch:
            # 尝试切换到目标分支
            r = run(["git", "checkout", branch], cwd=target_dir)
            if r.returncode != 0:
                # 分支不存在本地，从远程拉取
                r = run(["git", "checkout", "-b", branch, f"origin/{branch}"], cwd=target_dir)
                if r.returncode != 0:
                    print(f"  ✗ 无法切换到分支: {branch}")
                    return None

        # git pull
        result = subprocess.run(
            ["git", "pull", "origin", branch],
            capture_output=True, text=True, cwd=target_dir
        )
        if result.returncode == 0:
            print(f"  ✓ 已是最新")
        else:
            print(f"  ✗ 拉取失败: {result.stderr.strip()}")
            return None
    else:
        # 不存在 → 克隆
        print(f"  📥 克隆仓库 {username}/{repo_name} ...")
        result = subprocess.run(
            ["git", "clone", "-b", branch, clone_url, target_dir],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  ✗ 克隆失败: {result.stderr.strip()}")
            return None
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"      {line}")
        print(f"  ✓ 克隆完成")

    return target_dir


def delete_folder(repo_dir, folder_path, branch, commit_message):
    """删除文件夹 → 提交 → 推送"""
    folder_abs = os.path.join(repo_dir, folder_path)

    # 1. 检查文件夹是否存在
    if not os.path.isdir(folder_abs):
        print(f"  ✗ 文件夹不存在: {folder_path}")
        print(f"    完整路径: {folder_abs}")
        return False

    # 显示将要删除的内容
    file_count = 0
    for root, dirs, files in os.walk(folder_abs):
        file_count += len(files)
    print(f"  📂 目标文件夹: {folder_path}")
    print(f"  📄 包含文件: {file_count} 个")

    # 2. git rm -r 删除并暂存
    print(f"\n  🗑️  删除文件夹...")
    result = run(["git", "rm", "-r", folder_path], cwd=repo_dir)
    if result.returncode != 0:
        print(f"  ✗ 删除失败（可能文件夹已被删除或不受版本控制）")
        # 尝试用系统命令删除再 git add
        if os.path.isdir(folder_abs):
            print(f"  ⚠ 尝试先删除文件再 git add...")
            shutil.rmtree(folder_abs)
            run(["git", "add", "."], cwd=repo_dir)

    # 3. 检查是否有暂存的更改
    diff_check = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        capture_output=True, cwd=repo_dir
    )
    if diff_check.returncode == 0:
        print(f"  ℹ 没有需要提交的更改")
        return True

    # 4. 提交
    print(f"  💾 提交: \"{commit_message}\"")
    result = run(["git", "commit", "-m", commit_message], cwd=repo_dir)
    if result.returncode != 0:
        print(f"  ✗ 提交失败")
        return False

    # 5. 推送
    print(f"  🚀 推送到 origin/{branch} ...")
    result = run(["git", "push", "-u", "origin", branch], cwd=repo_dir)

    if result.returncode != 0:
        # 尝试 pull --rebase 后再 push
        print("  ⚠ 推送被拒，尝试 git pull --rebase ...")
        pull_result = run(["git", "pull", "origin", branch, "--rebase"], cwd=repo_dir)
        if pull_result.returncode != 0:
            print("  ✗ 合并失败，请手动处理冲突")
            return False
        result = run(["git", "push", "-u", "origin", branch], cwd=repo_dir)
        if result.returncode != 0:
            return False

    print(f"\n  ✅ 文件夹 \"{folder_path}\" 已从 GitHub 仓库删除!")
    return True


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="删除 GitHub 仓库中的某个文件夹",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python 4_Github删除仓库文件夹.py --repo github-tools --folder old-docs
    python 4_Github删除仓库文件夹.py --repo my-project --folder dist --branch develop
    python 4_Github删除仓库文件夹.py --repo my-project --folder "path/to/folder"
        """
    )
    parser.add_argument("--repo", "-r", help="GitHub 仓库名（如 github-tools）")
    parser.add_argument("--folder", "-f", help="要删除的文件夹路径（相对于仓库根目录，如 old-docs）")
    parser.add_argument("--branch", "-b", default="main", help="分支名（默认: main）")
    parser.add_argument("--message", "-m", default=None, help="自定义提交信息（默认自动生成）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际删除")

    # 如果没有传参数（比如 PyCharm 直接运行），则交互式输入
    if len(sys.argv) == 1:
        print("=" * 60)
        print("  🗑️  GitHub 仓库文件夹删除工具")
        print("=" * 60)
        repo_name = input("\n📦 请输入仓库名: ").strip()
        if not repo_name:
            print("✗ 未输入仓库名，退出")
            sys.exit(1)
        folder_path = input("📂 要删除的文件夹路径 (相对路径): ").strip()
        if not folder_path:
            print("✗ 未输入文件夹路径，退出")
            sys.exit(1)
        branch = input("🌿 分支名 (直接回车=main): ").strip() or "main"
        args = argparse.Namespace(
            repo=repo_name,
            folder=folder_path,
            branch=branch,
            message=None,
            dry_run=False
        )
    else:
        args = parser.parse_args()

        if not args.repo:
            print("✗ 请指定仓库名: --repo <仓库名>")
            sys.exit(1)
        if not args.folder:
            print("✗ 请指定要删除的文件夹: --folder <路径>")
            sys.exit(1)

    # 自动生成提交信息
    if args.message is None:
        args.message = f"删除文件夹: {args.folder}"

    # 加载配置
    username, token, email = load_github_config()

    print("=" * 60)
    print("  🗑️  GitHub 仓库文件夹删除工具")
    print(f"  账号: {username}")
    print(f"  仓库: {username}/{args.repo}")
    print(f"  分支: {args.branch}")
    print(f"  删除: {args.folder}")
    print(f"  消息: {args.message}")
    if args.dry_run:
        print("  ⚠ DRY RUN 模式 - 不会实际删除")
    print("=" * 60)

    # 配置 Git 用户和代理
    configure_git_user(username, email)
    apply_git_proxy()

    # Dry run 模式
    if args.dry_run:
        target_dir = os.path.join(REPOS_DIR, args.repo)
        folder_abs = os.path.join(target_dir, args.folder)
        if os.path.isdir(folder_abs):
            file_count = sum(1 for _ in os.walk(folder_abs) for __ in _[2])
            print(f"\n  🔍 文件夹存在: {folder_abs}")
            print(f"  📄 包含文件: {file_count} 个")
            print(f"  ⚠ 以上文件将被删除（dry-run，未实际执行）")
        else:
            print(f"\n  ℹ 文件夹不存在: {folder_abs}")
            print(f"    仓库可能尚未克隆到本地，本地路径仅供参考")
        return

    # 1. 确保仓库在本地
    repo_dir = ensure_repo_local(username, token, args.repo, args.branch)
    if repo_dir is None:
        sys.exit(1)

    # 2. 删除文件夹
    ok = delete_folder(repo_dir, args.folder, args.branch, args.message)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()