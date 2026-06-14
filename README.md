# 🚀 GitHub Tools — 项目批量上传管理工具

一键将本地多个项目批量上传到 GitHub，仓库不存在则自动创建，已存在则更新推送。

---

## ✨ 功能

- 📦 **批量上传** — 一个配置文件管理多个项目的上传
- 🔍 **智能检测** — 自动检查 GitHub 仓库是否存在
- 🆕 **自动创建** — 仓库不存在则通过 API 自动创建
- 🔄 **增量更新** — 仓库已存在则在原有基础上 push 新 commit
- 🙈 **排除列表** — 每个项目可自定义不上传的文件（自动写入 `.gitignore`）
- 🛡️ **安全保护** — 自动将配置文件 `projects.json` 加入排除，防止 Token 泄露
- 🏃 **Dry-run** — 预检查模式，只看结果不实际推送

---

## 📋 环境要求

| 依赖 | 说明 |
|------|------|
| Python | ≥ 3.8 |
| Git | 任意版本 |
| GitHub Token | [创建 Classic Token](#获取-github-token) |
| 国内用户 | 需要代理（Clash / Watt Toolkit） |

---

## 🔧 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/github-tools.git
cd github-tools
```

### 2. 复制配置文件

```bash
cp projects.example.json projects.json
```

### 3. 编辑 `projects.json`

```json
{
    "github": {
        "username": "你的GitHub用户名",
        "token": "ghp_xxxxxxxxxxxxxxxxxxxx",
        "email": "your-email@example.com"
    },
    "projects": [
        {
            "path": "E:/my-project",
            "repo": "my-project",
            "description": "项目描述",
            "private": false,
            "branch": "main",
            "commit_message": "更新代码",
            "exclude": [
                ".env",
                "node_modules/",
                "*.log"
            ]
        }
    ]
}
```

### 4. 运行

```bash
# 预检查（不实际推送）
python 1_Github项目上传.py --dry-run

# 正式上传
python 1_Github项目上传.py
```

---

## 📖 配置说明

### GitHub 账号配置

| 字段 | 必填 | 说明 |
|------|------|------|
| `username` | ✅ | GitHub **用户名**（英文，非昵称） |
| `token` | ✅ | GitHub Personal Access Token (classic) |
| `email` | ✅ | 用于 git commit 的邮箱 |

### 项目配置

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | ✅ | — | 项目本地路径 |
| `repo` | ✅ | — | GitHub 仓库名（英文） |
| `description` | ❌ | — | 仓库描述 |
| `private` | ❌ | `false` | `true` = 私有仓库 |
| `branch` | ❌ | `main` | 推送目标分支 |
| `commit_message` | ❌ | `自动更新` | 提交说明 |
| `exclude` | ❌ | `[]` | 不上传的文件/目录列表 |

### exclude 支持的写法

```json
"exclude": [
    "文件名.txt",       // 精确匹配
    "*.log",            // 通配符
    "node_modules/",    // 整个目录
    ".env"              // 点开头文件
]
```

写法规则与 `.gitignore` 完全一致。脚本会自动把 `projects.json` 追加进去，防止 Token 泄露。

---

## 🚀 命令行参数

```bash
# 指定配置文件
python 1_Github项目上传.py --config my_config.json

# 只处理第 0 个项目
python 1_Github项目上传.py --project 0

# 预检查模式
python 1_Github项目上传.py --dry-run
```

---

## 🔑 获取 GitHub Token

1. 打开 https://github.com/settings/tokens
2. **Generate new token** → **Generate new token (classic)** ← 必须选 classic
3. 勾选 ✅ **repo**（整个组全勾）
4. 生成后复制 `ghp_` 开头的 token
5. 填入 `projects.json`

> ⚠️ 不要用 Fine-grained token，它不支持创建仓库。

---

## 🌐 国内网络配置

GitHub 在国内直连不稳定，需要给 Git 配代理。

### Clash 用户（端口 7897）

```bash
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
```

### Watt Toolkit / Steam++ 用户（端口 26595）

```bash
git config --global http.proxy http://127.0.0.1:26595
git config --global https.proxy http://127.0.0.1:26595
```

### 取消代理

```bash
git config --global --unset http.proxy
git config --global --unset https.proxy
```

---

## 📁 项目结构

```
github-tools/
├── 1_Github项目上传.py      # 主脚本
├── projects.json            # 配置文件（不上传，需自行创建）
├── projects.example.json    # 配置文件模板
└── README.md                # 本文件
```

---

## 🔄 工作流程

```
读取 projects.json
    │
    ▼
逐个处理每个项目 ──────────┐
    │                     │
    ├─ 检查 GitHub 仓库   │
    │   ├─ 存在 → 更新    │
    │   └─ 不存在 → 创建  │
    │                     │
    ├─ git init（如需）    │
    ├─ 同步 .gitignore    │  ← 下一项
    ├─ git add .          │
    ├─ git commit         │
    └─ git push ──────────┘
```