"""
删除 GitHub 上的整个仓库

通过 GitHub API 的 DELETE /repos/{owner}/{repo} 接口直接删除。
⚠️ 此操作不可逆！删除后仓库（包括所有代码、Issues、PR、Wiki）将永久丢失。

用法:
    python 5_Github删除仓库.py --repo my-old-repo
    python 5_Github删除仓库.py --repo my-old-repo --yes    # 跳过确认

交互模式（不带参数运行）:
    python 5_Github删除仓库.py
"""

import os
import sys
import json
import argparse
from urllib import request, error

from config import HTTP_PROXY, HTTPS_PROXY

# Windows 中文环境修复 emoji 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GITHUB_API = "https://api.github.com"


# ============================================================
# 工具函数
# ============================================================

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
        print("  勾选权限: repo + delete_repo (全部)")
        sys.exit(1)

    return username, token, email


def setup_proxy():
    """设置 HTTP 代理，用于 urllib"""
    if HTTP_PROXY:
        os.environ["HTTP_PROXY"] = HTTP_PROXY
        os.environ["HTTPS_PROXY"] = HTTPS_PROXY or HTTP_PROXY
    else:
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)


def api_request(method, endpoint, token):
    """调用 GitHub API，返回 (status_code, response_body)"""
    url = f"{GITHUB_API}{endpoint}"

    req = request.Request(url, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "github-tools")

    # 配置代理
    proxy_handler = None
    if HTTP_PROXY:
        from urllib import request as req_mod
        proxy_handler = req_mod.ProxyHandler({
            "http": HTTP_PROXY,
            "https": HTTPS_PROXY or HTTP_PROXY,
        })

    def _do_request(opener):
        if opener:
            with opener.open(req) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw) if raw.strip() else {}
        else:
            with request.urlopen(req) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw) if raw.strip() else {}

    try:
        return _do_request(request.build_opener(proxy_handler) if proxy_handler else None)
    except error.HTTPError as e:
        raw = e.read().decode()
        return e.code, json.loads(raw) if raw.strip() else {"message": raw}
    except Exception as e:
        return None, str(e)


# ============================================================
# 核心操作
# ============================================================

def get_repo_info(username, repo_name, token):
    """获取仓库基本信息，用于删除前展示"""
    status, body = api_request("GET", f"/repos/{username}/{repo_name}", token)

    if status == 200:
        return {
            "full_name": body.get("full_name", ""),
            "description": body.get("description", ""),
            "private": body.get("private", False),
            "stars": body.get("stargazers_count", 0),
            "forks": body.get("forks_count", 0),
            "language": body.get("language", ""),
            "created_at": body.get("created_at", ""),
            "html_url": body.get("html_url", ""),
        }
    elif status == 404:
        return None
    else:
        print(f"  ✗ 查询失败 ({status}): {body.get('message', body)}")
        return None


def delete_repo(username, repo_name, token):
    """通过 GitHub API 删除仓库"""
    print(f"\n  🗑️  正在删除 {username}/{repo_name} ...")
    status, body = api_request("DELETE", f"/repos/{username}/{repo_name}", token)

    if status == 204:
        print(f"  ✅ 仓库 {username}/{repo_name} 已成功删除")
        return True
    elif status == 404:
        print(f"  ✗ 仓库不存在（可能已被删除）")
        return False
    elif status == 403:
        print(f"  ✗ 权限不足 ({status}): {body.get('message', body)}")
        print(f"    请确认 Token 勾选了 delete_repo 权限")
        return False
    else:
        msg = body.get('message', str(body)) if isinstance(body, dict) else str(body)
        print(f"  ✗ 删除失败 ({status}): {msg}")
        return False


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="删除 GitHub 上的整个仓库（⚠️ 不可逆）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python 5_Github删除仓库.py --repo my-old-repo
    python 5_Github删除仓库.py --repo my-old-repo --yes
        """
    )
    parser.add_argument("--repo", "-r", help="要删除的仓库名")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过二次确认，直接删除")

    if len(sys.argv) == 1:
        print("=" * 60)
        print("  ⚠️  GitHub 仓库删除工具")
        print("  注意：此操作不可逆！")
        print("=" * 60)
        repo_name = input("\n📦 请输入要删除的仓库名: ").strip()
        if not repo_name:
            print("✗ 未输入仓库名，退出")
            sys.exit(1)
        args = argparse.Namespace(repo=repo_name, yes=False)
    else:
        args = parser.parse_args()
        if not args.repo:
            print("✗ 请指定仓库名: --repo <仓库名>")
            sys.exit(1)

    # 加载配置
    username, token, email = load_github_config()
    setup_proxy()

    print("=" * 60)
    print("  ⚠️  GitHub 仓库删除工具")
    print(f"  账号: {username}")
    print(f"  目标: {username}/{args.repo}")
    print("=" * 60)

    # 1. 先查询仓库信息
    print(f"\n  🔍 查询仓库信息...")
    info = get_repo_info(username, args.repo, token)

    if info is None:
        print(f"  ✗ 仓库 {username}/{args.repo} 不存在")
        print(f"    可能是拼写错误，或已被删除")
        sys.exit(1)

    # 2. 展示仓库信息
    print(f"")
    print(f"  ┌─────────────────────────────────────")
    print(f"  │ 仓库名:    {info['full_name']}")
    print(f"  │ 描述:      {info['description'] or '(无)'}")
    print(f"  │ 类型:      {'🔒 私有' if info['private'] else '🌐 公开'}")
    print(f"  │ 语言:      {info['language'] or '(未知)'}")
    print(f"  │ ⭐ Stars:  {info['stars']}")
    print(f"  │ 🍴 Forks:  {info['forks']}")
    print(f"  │ 创建时间:  {info['created_at']}")
    print(f"  │ URL:       {info['html_url']}")
    print(f"  └─────────────────────────────────────")

    # 3. 确认
    if not args.yes:
        print(f"\n  ⚠️  警告：此操作不可逆！所有代码、Issues、PR、Wiki 将永久丢失。")
        print(f"  要删除的仓库是: {username}/{args.repo}")
        confirm = input(f"\n  请输入仓库名确认删除: ").strip()
        if confirm != args.repo:
            print(f"  ❌ 仓库名不匹配，已取消删除")
            sys.exit(0)

        sure = input(f"  确定要删除吗？(输入 YES 确认): ").strip()
        if sure != "YES":
            print(f"  ❌ 已取消删除")
            sys.exit(0)

    # 4. 执行删除
    ok = delete_repo(username, args.repo, token)
    if ok:
        print(f"\n  ✅ 仓库 {username}/{args.repo} 已永久删除")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()