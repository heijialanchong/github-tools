# 🚀 GitHub Tools — 批量上传/下载工具

一个配置文件管理 GitHub 账号，一个配置文件列出要操作的仓库，批量上传或下载。

---

## 📁 项目结构

```
github-tools/
├── config.py                  # 要操作的仓库名（上传/下载列表）
├── projects.json              # GitHub 账号 + 每个仓库的详细参数
├── projects.example.json      # 配置文件模板
├── 1_Github项目上传.py         # 批量上传脚本
├── 2_Github项目下载.py         # 批量下载脚本
├── .gitignore                 # 防止敏感文件泄露
└── repos/                     # 下载的仓库统一放这里
```

---

## 🔧 快速开始

### 1. 创建 `projects.json`

```bash
cp projects.example.json projects.json
```

编辑 `projects.json`，填入你的 GitHub 账号和要管理的仓库详情：

```json
{
    "github": {
        "username": "你的GitHub用户名",
        "token": "ghp_xxxxxxxx",
        "email": "your-email@example.com",
        "proxy": ""
    },
    "projects": [
        {
            "path": "E:/my-project",
            "repo": "my-project",
            "description": "项目描述",
            "private": false,
            "branch": "main",
            "commit_message": "更新代码",
            "depth": 0,
            "exclude": [".env", "node_modules/"]
        }
    ]
}
```

### 2. 编辑 `config.py`，填你要操作的仓库名

```python
UPLOAD_REPOS = ["my-project"]      # 要上传的
DOWNLOAD_REPOS = ["my-project"]    # 要下载的
```

### 3. 运行

```bash
# 上传
python 1_Github项目上传.py --dry-run    # 先预览
python 1_Github项目上传.py              # 正式上传

# 下载
python 2_Github项目下载.py --dry-run    # 先预览
python 2_Github项目下载.py              # 正式下载
```

---

## 📤 上传脚本

读取 `config.py` 的 `UPLOAD_REPOS`，在 `projects.json` 中匹配同名仓库，逐个推送。

- 仓库不存在 → 通过 API 自动创建
- 仓库已存在 → push 新 commit
- 自动生成/同步 `.gitignore`
- 自动将 `projects.json`、`config.py` 加入排除列表

```bash
python 1_Github项目上传.py                   # 上传全部
python 1_Github项目上传.py --project 0       # 只上传第 0 个
python 1_Github项目上传.py --config xxx.json # 指定配置文件
python 1_Github项目上传.py --dry-run         # 仅预览
```

---

## 📥 下载脚本

读取 `config.py` 的 `DOWNLOAD_REPOS`，在 `projects.json` 中匹配同名仓库，逐个下载到 `repos/{仓库名}/`。

- 本地不存在 → `git clone`
- 本地已存在 → `git pull` 拉取最新

```bash
python 2_Github项目下载.py                   # 下载全部
python 2_Github项目下载.py --project 0       # 只下载第 0 个
python 2_Github项目下载.py --dry-run         # 仅预览
```

---

## 📖 配置说明

### `config.py` — 操作列表（极简）

| 字段 | 说明 |
|------|------|
| `UPLOAD_REPOS` | 要上传的仓库名列表，如 `["repo-a", "repo-b"]` |
| `DOWNLOAD_REPOS` | 要下载的仓库名列表 |

### `projects.json` — 账号 + 仓库详情

**github 区块：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `username` | ✅ | GitHub 用户名 |
| `token` | ✅ | GitHub Personal Access Token (classic) |
| `email` | ✅ | 用于 git commit 的邮箱 |
| `proxy` | ❌ | HTTP 代理，如 `http://127.0.0.1:7897` |

**projects 区块（每个仓库一条）：**

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | ✅ | — | 上传：本地项目路径 / 下载：无所谓（自动用 `repos/`） |
| `repo` | ✅ | — | GitHub 仓库名，与 `config.py` 中名字匹配 |
| `branch` | ❌ | `main` | 分支名 |
| `description` | ❌ | — | 仓库描述（仅上传创建时用到） |
| `private` | ❌ | `false` | 是否私有仓库（仅上传创建时用到） |
| `commit_message` | ❌ | `自动更新` | 提交信息（仅上传用） |
| `depth` | ❌ | `0` | 浅克隆深度，`1`=只拉最近一次（仅下载用） |
| `exclude` | ❌ | `[]` | 不上传的文件列表（仅上传用，写入 `.gitignore`） |

---

## 🌐 代理设置

国内用户访问 GitHub 不稳定，在 `projects.json` 的 `github.proxy` 中填写代理地址：

```json
"proxy": "http://127.0.0.1:7897"
```

常见的代理端口：Clash `7897`、Watt Toolkit `26595`。

---

## 🔑 获取 GitHub Token

1. https://github.com/settings/tokens
2. Generate new token → **Generate new token (classic)**
3. 勾选 ✅ **repo**（全组）
4. 复制 `ghp_` 开头的 token 填入 `projects.json`

---

## 🔄 工作流程

```
config.py                    projects.json
    │                             │
    │  要操作的仓库名              │  账号 + 每个仓库的详细参数
    │                             │
    └────────── 按 repo 匹配 ──────┘
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
    上传脚本                下载脚本
    clone/push             clone/pull
```
