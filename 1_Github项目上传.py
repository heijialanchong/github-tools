"""
上传项目到 GitHub 的自动化脚本（基于 JSON 配置文件）

配置文件 projects.json 格式:
{
    "github": {
        "username": "你的GitHub用户名",
        "token": "ghp_xxxxxxxx",       // GitHub Personal Access Token
        "email": "your-email@example.com"
    },
    "projects": [
        {
            "path": "E:/my-project",    // 项目本地路径
            "repo": "my-repo",          // GitHub 仓库名
            "description": "描述",       // 仓库描述（可选）
            "private": false,            // 是否私有（可选，默认 false）
            "branch": "main",            // 分支名（可选，默认 main）
            "commit_message": "更新"     // 提交信息（可选，默认 "自动更新"）
        }
    ]
}

用法:
    python 上传.py                          # 使用默认 projects.json
    python 上传.py --config my_config.json  # 指定配置文件
    python 上传.py --project 0              # 只上传第 0 个项目
"""
import subprocess
import sys
import os
import json
from datetime import datetime, timezone, timedelta
from typing import List
from urllib import request, error

from config import UPLOAD_REPOS, HTTP_PROXY, HTTPS_PROXY

# Windows 中文环境修复 emoji 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ============================================================
# 常量
# ============================================================

GITIGNORE_CONTENT = """\
# Python
__pycache__/
*.py[cod]
*.so
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# 配置文件（包含敏感信息，不上传）
.env
*.local
github账号.txt
github-recovery-codes.txt
加速器.txt
projects.json

# Jupyter
.ipynb_checkpoints/

# 缓存和日志
*.log
*.cache
"""

GITHUB_API = "https://api.github.com"

# 日志目录（脚本所在目录下的 logs 文件夹）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(SCRIPT_DIR, "logs")

# 北京时区 UTC+8
BJT = timezone(timedelta(hours=8))


# ============================================================
# 工具函数
# ============================================================

def write_upload_log(repo_name: str):
    """上传成功后写入日志文件（UTC + 北京时间）"""
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"{repo_name}.log")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    now_bjt = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"上传成功 | UTC: {now_utc} | 北京时间(UTC+8): {now_bjt}\n")
    print(f"  📝 日志已写入: {log_path}")

def sync_git_proxy():
    """根据 config.py 的代理配置同步 Git 全局代理"""
    if HTTP_PROXY:
        subprocess.run(
            ["git", "config", "--global", "http.proxy", HTTP_PROXY],
            capture_output=True
        )
    if HTTPS_PROXY:
        subprocess.run(
            ["git", "config", "--global", "https.proxy", HTTPS_PROXY],
            capture_output=True
        )
    print(f"  🔗 Git 代理已同步: {HTTP_PROXY}")

def run(cmd: List[str], cwd: str = None) -> subprocess.CompletedProcess:
    """运行命令，实时打印输出"""
    print(f"    ➤ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=cwd)
    if result.returncode != 0:
        print(f"    ✗ {result.stderr.strip()}")
    else:
        output = result.stdout.strip()
        if output:
            for line in output.split("\n"):
                print(f"      {line}")
    return result


def api_request(method: str, endpoint: str, token: str, data: dict = None):
    """调用 GitHub API，返回 (status_code, response_body)"""
    url = f"{GITHUB_API}{endpoint}"
    body = json.dumps(data).encode("utf-8") if data else None

    req = request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")

    try:
        with request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


# ============================================================
# GitHub 操作
# ============================================================

def check_repo_exists(username: str, repo_name: str, token: str) -> bool:
    """检查 GitHub 上仓库是否已存在"""
    print(f"  🔍 检查仓库是否存在: {username}/{repo_name}")
    status, body = api_request("GET", f"/repos/{username}/{repo_name}", token)

    if status == 200:
        print(f"  ✓ 仓库已存在: {body.get('html_url', '')}")
        return True
    elif status == 404:
        print(f"  ℹ 仓库不存在，将创建新仓库")
        return False
    else:
        print(f"  ✗ 查询失败 ({status}): {body.get('message', body)}")
        sys.exit(1)


def create_github_repo(username: str, repo_name: str, token: str,
                       description: str = "", private: bool = False) -> str:
    """通过 GitHub API 创建新仓库，返回 clone_url"""
    print(f"  🌐 创建仓库: {username}/{repo_name}")

    status, body = api_request("POST", "/user/repos", token, {
        "name": repo_name,
        "description": description,
        "private": private,
        "auto_init": False,
    })

    if status == 201:
        print(f"  ✓ 仓库创建成功: {body.get('html_url', '')}")
        return body["clone_url"]
    else:
        # 如果仓库已存在（可能是其他人创建的），尝试使用它
        if "already exists" in str(body.get("errors", "")) or body.get("message", "") == "Repository creation failed.":
            print(f"  ⚠ 仓库可能已存在，尝试直接使用")
            return f"https://github.com/{username}/{repo_name}.git"
        print(f"  ✗ 创建失败 ({status}): {body.get('message', body)}")
        sys.exit(1)


# ============================================================
# Git 操作
# ============================================================

def configure_git_user(username: str, email: str):
    """配置 Git 全局用户信息（如未配置）"""
    print(f"  👤 Git 用户: {username} <{email}>")

    # 检查全局配置
    global_name = subprocess.run(
        ["git", "config", "--global", "user.name"],
        capture_output=True, text=True
    ).stdout.strip()

    if not global_name:
        run(["git", "config", "--global", "user.name", username])

    global_email = subprocess.run(
        ["git", "config", "--global", "user.email"],
        capture_output=True, text=True
    ).stdout.strip()

    if not global_email:
        run(["git", "config", "--global", "user.email", email])


def init_git(project_dir: str):
    """初始化 Git 仓库"""
    git_dir = os.path.join(project_dir, ".git")
    if os.path.exists(git_dir):
        print("  ℹ Git 仓库已存在")
    else:
        result = run(["git", "init"], cwd=project_dir)
        if result.returncode != 0:
            return False
        print("  ✓ Git 初始化完成")
    return True


def sync_gitignore(project_dir: str, exclude: List[str]):
    """根据配置同步 .gitignore：基础模板 + 用户自定义排除列表

    每次运行都会读取现有 .gitignore，只更新由脚本管理的部分（标记块内），
    保留用户手动添加的其他内容。
    """
    gitignore_path = os.path.join(project_dir, ".gitignore")
    marker_start = "# >>> github-tools 自动管理 <<<"
    marker_end = "# <<< github-tools 自动管理 >>>"

    # 组合自动管理的内容
    managed_lines = [marker_start, "", "# 基础排除", ""]
    managed_lines.extend(GITIGNORE_CONTENT.strip().split("\n"))
    if exclude:
        managed_lines.append("")
        managed_lines.append("# 用户自定义排除 (来自 projects.json)")
        managed_lines.extend(exclude)
    managed_lines.append("")
    managed_lines.append(marker_end)

    managed_block = "\n".join(managed_lines) + "\n"

    # 读取现有文件
    old = ""
    existed = os.path.exists(gitignore_path)
    if existed:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            old = f.read()

        # 如果已有管理块，替换之
        if marker_start in old and marker_end in old:
            before = old[:old.index(marker_start)]
            after = old[old.index(marker_end) + len(marker_end):]
            new_content = before + managed_block + after.lstrip("\n")
        else:
            # 没有管理块，追加
            new_content = old.rstrip("\n") + "\n\n" + managed_block
    else:
        new_content = managed_block

    # 只有内容变化时才写入
    with open(gitignore_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    # 简单判断是新创建还是更新
    if existed and marker_start in old:
        print(f"  ℹ .gitignore 已同步")
    else:
        print(f"  ✓ .gitignore 已创建（含 {len(exclude)} 条自定义排除）")


def setup_remote(project_dir: str, remote_url: str):
    """设置或更新远程仓库地址"""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True, cwd=project_dir
    )

    if result.returncode == 0:
        old_url = result.stdout.strip()
        if old_url != remote_url:
            run(["git", "remote", "set-url", "origin", remote_url], cwd=project_dir)
            print(f"  ✓ 远程地址已更新")
        else:
            print(f"  ℹ 远程地址未变: {old_url}")
    else:
        run(["git", "remote", "add", "origin", remote_url], cwd=project_dir)
        print(f"  ✓ 远程地址已设置: {remote_url}")


def add_commit_push(project_dir: str, branch: str, message: str):
    """添加文件 → 提交 → 推送"""
    # 添加所有文件
    print(f"\n  📋 添加文件...")
    result = run(["git", "add", "."], cwd=project_dir)
    if result.returncode != 0:
        return None

    # 检查是否有暂存的变更
    diff_check = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        capture_output=True, cwd=project_dir
    )
    if diff_check.returncode == 0:
        # 没有需要提交的更改
        print(f"  💾 提交: \"{message}\"")
        print(f"  ℹ 没有需要提交的更改，跳过提交")
        return "no_changes"

    # 生成详细描述（变更文件列表 + 统计）
    detail_lines = []
    stat_result = subprocess.run(
        ["git", "diff", "--staged", "--stat"],
        capture_output=True, text=True, cwd=project_dir
    )
    if stat_result.stdout.strip():
        detail_lines.append(stat_result.stdout.strip())

    name_result = subprocess.run(
        ["git", "diff", "--staged", "--name-status"],
        capture_output=True, text=True, cwd=project_dir
    )
    if name_result.stdout.strip():
        detail_lines.append("\n文件变更明细:")
        detail_lines.append(name_result.stdout.strip())

    # 提交（包含详细描述）
    print(f"  💾 提交: \"{message}\"")
    detail_msg = "\n".join(detail_lines) if detail_lines else ""
    if detail_msg:
        print(f"  📝 详细描述: {len(detail_lines)} 行变更摘要")
        result = run(["git", "commit", "-m", message, "-m", detail_msg], cwd=project_dir)
    else:
        result = run(["git", "commit", "-m", message], cwd=project_dir)

    if result.returncode != 0:
        # 理论上不会走到这里（已提前检查），保留作为兜底
        if "nothing to commit" in (result.stderr + result.stdout):
            print("  ℹ 没有需要提交的更改，跳过提交")
            return "no_changes"
        return None

    # 确保在正确的分支上
    current = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, cwd=project_dir
    ).stdout.strip()

    if not current:
        run(["git", "checkout", "-b", branch], cwd=project_dir)
    elif current != branch:
        # 切换到目标分支（创建如果不存在）
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            capture_output=True, text=True, cwd=project_dir
        )
        if result.returncode != 0:
            run(["git", "checkout", "-b", branch], cwd=project_dir)
        else:
            run(["git", "checkout", branch], cwd=project_dir)

    # 推送
    print(f"  🚀 推送到 origin/{branch} ...")
    result = run(["git", "push", "-u", "origin", branch], cwd=project_dir)

    if result.returncode != 0:
        # 尝试 pull --rebase 后再 push
        print("  ⚠ 推送被拒，尝试 git pull --rebase ...")
        pull_result = run(["git", "pull", "origin", branch, "--rebase"], cwd=project_dir)
        if pull_result.returncode != 0:
            print("  ✗ 合并失败，请手动处理冲突")
            return None
        result = run(["git", "push", "-u", "origin", branch], cwd=project_dir)
        if result.returncode != 0:
            return None

    return "pushed"


# ============================================================
# 核心流程
# ============================================================

def process_project(proj: dict, github: dict, index: int, total: int):
    """处理单个项目：检查→创建/更新→提交→推送"""
    path = proj.get("path", "")
    repo_name = proj.get("repo", "")
    description = proj.get("description", "")
    private = proj.get("private", False)
    branch = proj.get("branch", "main")
    commit_message = proj.get("commit_message", "自动更新")
    exclude = proj.get("exclude", [])
    if "projects.json" not in exclude:
        exclude.append("projects.json")  # 自动加上，防止配置文件泄露

    username = github["username"]
    token = github["token"]
    email = github.get("email", f"{username}@users.noreply.github.com")

    print(f"\n{'=' * 60}")
    print(f"  [{index + 1}/{total}] 处理项目: {repo_name}")
    print(f"  本地路径: {path}")
    print(f"{'=' * 60}")

    # 0. 确认是否上传
    confirm = input(f"  ⚠ 确认上传? (输入 YES 确认): ").strip()
    if confirm != "YES":
        print(f"  ⏭ 已跳过: {repo_name}")
        return False

    # 1. 验证路径
    if not os.path.isdir(path):
        print(f"  ✗ 错误: 路径不存在 - {path}")
        return False

    # 2. 检查 GitHub 仓库是否存在，不存在则创建
    exists = check_repo_exists(username, repo_name, token)

    if exists:
        remote_url = f"https://github.com/{username}/{repo_name}.git"
        # 同时也支持 token 嵌入 URL 的方式来避免每次输密码
        # remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
        action = "更新"
    else:
        remote_url = create_github_repo(username, repo_name, token, description, private)
        action = "创建并上传"

    print(f"  📌 操作: {action}")

    # 3. 配置 Git 用户
    configure_git_user(username, email)

    # 4. 初始化 Git（如果未初始化）
    if not init_git(path):
        return False

    # 5. 同步 .gitignore
    sync_gitignore(path, exclude)

    # 6. 设置远程仓库
    setup_remote(path, remote_url)

    # 7. 添加 → 提交 → 推送
    result = add_commit_push(path, branch, commit_message)

    if result == "pushed":
        print(f"\n  ✅ [{index + 1}/{total}] {repo_name} - {action}成功!")
        write_upload_log(repo_name)
        return True
    elif result == "no_changes":
        print(f"\n  ✅ [{index + 1}/{total}] {repo_name} - 无需更新，已是最新")
        return True
    else:
        print(f"\n  ❌ [{index + 1}/{total}] {repo_name} - 失败")
        return False


def load_config(config_path: str) -> dict:
    """加载并验证配置文件"""
    if not os.path.isfile(config_path):
        print(f"✗ 配置文件不存在: {config_path}")
        print("  请先创建 projects.json 配置文件")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 验证必填字段
    github = config.get("github", {})
    if not github.get("username") or "你的GitHub用户名" in github.get("username", ""):
        print("✗ 请在配置文件中填写真实的 GitHub 用户名")
        sys.exit(1)
    if not github.get("token") or "ghp_xxx" in github.get("token", ""):
        print("✗ 请在配置文件中填写真实的 GitHub Token")
        print("  获取 token: https://github.com/settings/tokens → Generate new token (classic)")
        print("  勾选权限: repo (全部)")
        sys.exit(1)

    return config


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="批量上传项目到 GitHub（基于配置文件）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", "-c", default="projects.json",
        help="配置文件路径 (默认: projects.json)"
    )
    parser.add_argument(
        "--project", "-p", type=int, default=None,
        help="只上传指定索引的项目 (从 0 开始)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅检查，不实际推送"
    )

    args = parser.parse_args()

    # 查找配置文件（优先当前目录，其次脚本所在目录）
    config_path = args.config
    if not os.path.isabs(config_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(os.getcwd(), config_path),
            os.path.join(script_dir, config_path),
        ]
        for c in candidates:
            if os.path.isfile(c):
                config_path = c
                break

    # 加载配置
    config = load_config(config_path)
    github = config["github"]
    all_projects = config.get("projects", [])

    # 按 config.py 的 UPLOAD_REPOS 筛选
    repo_set = set(UPLOAD_REPOS)
    matched = [p for p in all_projects if p.get("repo") in repo_set]
    missing = repo_set - {p.get("repo") for p in all_projects}
    if missing:
        print(f"⚠ projects.json 中未找到: {', '.join(missing)}")

    if not UPLOAD_REPOS:
        print("✗ config.py 中 UPLOAD_REPOS 为空，请先添加要上传的仓库名")
        sys.exit(1)
    if not matched:
        print("✗ 没有匹配的项目可以上传")
        sys.exit(1)

    # 筛选项目
    if args.project is not None:
        if 0 <= args.project < len(matched):
            projects = [matched[args.project]]
        else:
            print(f"✗ 项目索引 {args.project} 超出范围 (共 {len(matched)} 个)")
            sys.exit(1)
    else:
        projects = matched

    print("=" * 60)
    print("  📤 GitHub 批量上传工具")
    print(f"  账号: {github['username']}")
    print(f"  配置文件: {config_path}")
    print(f"  共 {len(projects)} 个项目")
    if args.dry_run:
        print("  ⚠ DRY RUN 模式 - 不会实际推送")
    print("=" * 60)

    # 同步 Git 代理配置
    sync_git_proxy()

    # 逐个处理项目
    results = []
    for i, proj in enumerate(projects):
        if args.dry_run:
            print(f"\n  [{i + 1}/{len(projects)}] 🔍 检查: {proj.get('repo')} @ {proj.get('path')}")
            exists = check_repo_exists(github["username"], proj["repo"], github["token"])
            print(f"  仓库状态: {'已存在 → 将更新' if exists else '不存在 → 将创建'}")
            results.append(True)
        else:
            ok = process_project(proj, github, i, len(projects))
            results.append(ok)

    # 报告
    print(f"\n{'=' * 60}")
    print(f"  📊 完成报告")
    success_count = sum(results)
    print(f"  成功: {success_count} / 失败: {len(results) - success_count}")
    print(f"{'=' * 60}")

    if success_count != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()