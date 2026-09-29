"""
查看 GitHub 账号下的所有仓库

通过 GitHub API 的 GET /user/repos 拉取当前账号（含私有）的所有仓库，
按最近推送时间倒序展示。

用法:
    python 6_Github查看仓库.py                    # 默认列出全部，按最近推送排序
    python 6_Github查看仓库.py --type private     # 只看私有仓库
    python 6_Github查看仓库.py --type public      # 只看公开仓库
    python 6_Github查看仓库.py --sort stars       # 按 star 数排序
    python 6_Github查看仓库.py --sort created     # 按创建时间排序
    python 6_Github查看仓库.py --search order     # 只看名字含 order 的仓库
    python 6_Github查看仓库.py --detail           # 额外显示描述和地址
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
from urllib import request, error

from config import CONFIG

HTTP_PROXY = CONFIG["proxy"]["http"]
HTTPS_PROXY = CONFIG["proxy"]["https"]

# Windows 中文环境修复 emoji 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GITHUB_API = "https://api.github.com"

# 北京时区 UTC+8
BJT = timezone(timedelta(hours=8))


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

    if not username or "你的GitHub用户名" in username:
        print("✗ 请在 projects.json 中填写真实的 GitHub 用户名")
        sys.exit(1)
    if not token or "ghp_xxx" in token:
        print("✗ 请在 projects.json 中填写真实的 GitHub Token")
        print("  获取 token: https://github.com/settings/tokens → Generate new token (classic)")
        print("  勾选权限: repo (全部)")
        sys.exit(1)

    return username, token


def api_request(token: str, endpoint: str):
    """调用 GitHub API，返回 (status_code, response_body)"""
    url = f"{GITHUB_API}{endpoint}"
    req = request.Request(url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "github-tools")

    opener = None
    if HTTP_PROXY:
        opener = request.build_opener(request.ProxyHandler({
            "http": HTTP_PROXY,
            "https": HTTPS_PROXY or HTTP_PROXY,
        }))

    def _do(o):
        if o:
            with o.open(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        with request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())

    try:
        return _do(opener)
    except error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return None, str(e)


def fetch_all_repos(token: str, sort: str, direction: str, repo_type: str):
    """分页拉取账号下所有仓库，返回列表"""
    repos = []
    for page in range(1, 100):  # 最多 100 页 = 10000 个仓库，足够
        endpoint = f"/user/repos?per_page=100&page={page}&sort={sort}&direction={direction}"
        if repo_type and repo_type != "all":
            endpoint += f"&type={repo_type}"
        status, body = api_request(token, endpoint)
        if status != 200 or not isinstance(body, list):
            break
        repos.extend(body)
        if len(body) < 100:
            break
    return repos


def fmt_time(iso: str) -> str:
    """ISO 时间 → 北京时间 'YYYY-MM-DD HH:MM'"""
    if not iso:
        return "-"
    try:
        iso = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        return dt.astimezone(BJT).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso[:16]


def display_width(s: str) -> int:
    """计算显示宽度（中文等全角字符算 2）"""
    return sum(2 if ord(c) > 0x2E7F else 1 for c in s)


def pad(s: str, width: int) -> str:
    """按显示宽度补齐空格，使中英文表格对齐"""
    return s + " " * max(0, width - display_width(s))


def truncate(s: str, width: int) -> str:
    """按显示宽度截断，超长加 …"""
    if display_width(s) <= width:
        return s
    out = ""
    w = 0
    for c in s:
        cw = 2 if ord(c) > 0x2E7F else 1
        if w + cw > width - 1:
            break
        out += c
        w += cw
    return out + "…"


# ============================================================
# 展示
# ============================================================

def print_repos(repos, detail=False):
    """打印仓库列表 + 汇总"""
    if not repos:
        print("\n  ℹ 没有找到仓库")
        return

    # 表头
    print(f"\n  {'#':>3}  {pad('仓库名', 28)}{pad('可见性', 8)}{pad('语言', 12)}{'⭐':>5}  {pad('最近推送(北京)', 16)}")
    print(f"  {'─' * 3}  {'─' * 28}{'─' * 8}{'─' * 12}{'─' * 5}  {'─' * 16}")

    total_stars = 0
    private_count = 0
    for i, repo in enumerate(repos, 1):
        name = repo.get("name", "")
        is_private = repo.get("private", False)
        lang = repo.get("language") or "-"
        stars = repo.get("stargazers_count", 0)
        pushed = fmt_time(repo.get("pushed_at"))
        desc = repo.get("description") or "(无描述)"
        url = repo.get("html_url", "")

        total_stars += stars
        if is_private:
            private_count += 1

        vis = "🔒 私有" if is_private else "🌐 公开"
        print(f"  {i:>3}  {pad(truncate(name, 28), 28)}{pad(vis, 8)}{pad(truncate(lang, 12), 12)}{stars:>5}  {pushed}")

        if detail:
            print(f"       描述: {desc}")
            print(f"       地址: {url}")

    # 汇总
    public_count = len(repos) - private_count
    print(f"\n  {'=' * 60}")
    print(f"  📊 共 {len(repos)} 个仓库  ·  🔒 私有 {private_count}  ·  🌐 公开 {public_count}  ·  ⭐ 总计 {total_stars}")


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="查看 GitHub 账号下的所有仓库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python 6_Github查看仓库.py                    # 全部仓库，按最近推送排序
    python 6_Github查看仓库.py --type private     # 只看私有
    python 6_Github查看仓库.py --sort stars       # 按 star 排序
    python 6_Github查看仓库.py --search order     # 按名字过滤
    python 6_Github查看仓库.py --detail           # 显示描述和地址
        """
    )
    parser.add_argument("--sort", "-s", default="pushed",
                        choices=["created", "updated", "pushed", "full_name"],
                        help="排序字段 (默认: pushed)")
    parser.add_argument("--direction", "-d", default="desc", choices=["asc", "desc"],
                        help="排序方向 (默认: desc)")
    parser.add_argument("--type", "-t", default="all",
                        choices=["all", "owner", "public", "private", "member"],
                        help="仓库类型 (默认: all)")
    parser.add_argument("--search", "-q", default="", help="按仓库名子串过滤")
    parser.add_argument("--detail", "-v", action="store_true", help="显示描述和地址")

    args = parser.parse_args()

    # 加载配置
    username, token = load_github_config()

    print("=" * 60)
    print("  📋 GitHub 仓库列表")
    print(f"  账号: {username}")
    print(f"  排序: {args.sort} ({args.direction})")
    print(f"  类型: {args.type}")
    if args.search:
        print(f"  过滤: {args.search}")
    print("=" * 60)

    # 拉取仓库
    print("  🔍 正在拉取仓库列表 ...")
    repos = fetch_all_repos(token, args.sort, args.direction, args.type)

    if repos is None or (isinstance(repos, list) and not repos):
        print("  ✗ 拉取失败或没有仓库（请检查 Token 权限或代理设置）")
        sys.exit(1)

    # 名字过滤
    if args.search:
        repos = [r for r in repos if args.search.lower() in r.get("name", "").lower()]

    print_repos(repos, detail=args.detail)
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
