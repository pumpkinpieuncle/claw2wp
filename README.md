# Claw2WP

用命令行把 **Markdown (.md) / Word (.docx)** 发布到 WordPress，支持 **Gutenberg 块格式**、WooCommerce 产品、更新/删除、批量发布与 CSV 导出。可以管理多站点。

- **输入**：`.md`、`.docx`
- **输出**：WordPress 文章或 WooCommerce 产品，正文为 Gutenberg 块（段落、标题、图片、列表等）
- **认证**：WordPress Application Passwords（推荐 HTTPS）

---

## 目录

- [环境要求](#环境要求)
- [安装](#安装)
- [配置](#配置)
- [使用](#使用)
- [Frontmatter 说明](#frontmatter-说明md)
- [供自动化 / Agent 使用（如 OpenClaw）](#供自动化--agent-使用如-openclaw)
- [卸载](#卸载)
- [文档](#文档)

---

## 环境要求

- **Python 3.8+**
- 依赖：`requests`、`python-frontmatter`、`markdown`、`mammoth`、`beautifulsoup4`（安装时自动安装）

---

## 安装

在项目根目录执行：

```bash
cd /path/to/claw2wp

# 安装后全局可用命令 claw2wp
pip install .

# 开发模式（改代码即时生效，无需重装）
pip install -e .
```

安装成功后执行：

```bash
claw2wp --help
```

应能正常显示帮助。改代码后：若使用 `pip install -e .` 无需重装；若使用 `pip install .` 需重新执行一次 `pip install .`。

---

## 配置

### 1. 初始化配置

```bash
claw2wp init
```

会在 **`~/.claw2wp/config.json`** 生成示例配置。编辑该文件，填入站点与凭证，下方可以填入更多站点信息：

```json
{
  "site_id_1": {
    "url": "https://你的站点.com",
    "user": "登录用户名",
    "pass": "xxxx xxxx xxxx xxxx"
  }
}
```

- **url**：站点地址，不要末尾斜杠。
- **user**：WordPress 用户名。
- **pass**：建议使用 **Application Password**（WordPress 5.6+）：后台 → 用户 → 个人资料 →「应用程序密码」→ 新建并复制（形如 `xxxx xxxx xxxx xxxx`）。

### 2. 查看已配置站点

```bash
claw2wp config
```

会列出所有 `site_id` 及其 `url`、`user`（不显示密码）。后续命令中的 `-s/--site` 即使用这里的 `site_id`。

---

## 使用

### 查看帮助

```bash
claw2wp --help
claw2wp publish --help
claw2wp validate --help
claw2wp export --help
```

### 发布（新建）

用 **`--post`** 发文章，**`--product`** 发产品。必须指定 **`-f`（单文件）** 或 **`-d`（目录）** 之一，且必须指定 **`-s` 站点 ID**。

```bash
claw2wp publish -f 文章.md -s site_id_1 --post
claw2wp publish -f 产品.md -s site_id_1 --product
claw2wp publish -d ./目录 -s site_id_1 --post
```

### 草稿与预览

```bash
# 强制以草稿发布（覆盖 frontmatter 的 status）
claw2wp publish -f 文章.md -s site_id_1 --draft

# 只解析并打印将要发布的内容，不上传、不请求 API
claw2wp publish -f 文章.md -s site_id_1 --dry-run
```

### 更新与删除

```bash
# 按 frontmatter 的 slug/标题匹配，找到则更新，找不到则新建
claw2wp publish -f 文章.md -s site_id_1 --update

# 按 slug 删除
claw2wp publish -f 文章.md -s site_id_1 --delete
# 按指定 ID 删除
claw2wp publish -f 文章.md -s site_id_1 --delete --id 42

# 目录批量更新
claw2wp publish -d ./文章目录 -s site_id_1 --update
```

### 校验与导出

```bash
# 校验 frontmatter 和解析结果（不发布、不请求 API）
claw2wp validate -f 文章.md
claw2wp validate -f 文章.md -s site_id_1

# 导出为 WooCommerce 产品导入用 CSV（会先上传图片到站点）
claw2wp export -d ./产品目录 -s site_id_1 --csv
```

### Windows 与含中文的路径

在 Windows 的 PowerShell 中，若目录或文件名包含中文等非 ASCII 字符，控制台编码可能导致路径无法正确传给程序。本工具已做以下处理：

- **自动纠正**：会尝试将传入的路径从常见乱码（如 GBK/CP936 被误解析）恢复为正确路径。
- **控制台输出**：在 Windows 下会尽量将标准输出设为 UTF-8，便于正确显示路径。

若仍无法识别路径，可先执行 `chcp 65001` 将当前控制台改为 UTF-8，再运行 `claw2wp`；或使用仅含英文的目录名/文件名。

---

## Frontmatter 说明（.md）

```yaml
title: '文章标题'
slug: my-post
status: publish
featured_image: ./hero.jpg
date: 2024-01-15
excerpt: '摘要'
tags: [教程, markdown]
categories: [开发]

# WooCommerce 产品可加
short_description: '一句话描述'
regular_price: "99.00"
sale_price: "79.00"
sku: SKU-001
```

- 不写 `featured_image` 时，会按「文件名-1」「文件名-feature」等规则在同目录找图。
- 分类/标签写名称即可，会按站点已有分类/标签解析为 ID。

更多字段说明见 [docs/FEATURES.md](docs/FEATURES.md) 与 [docs/REST_API.md](docs/REST_API.md)。

---

## 供自动化 / Agent 使用（如 OpenClaw）

需先完成上文「安装」与「配置」，并通过 `claw2wp config` 确认可用的 `site_id`。命令与示例见「使用」一节。

- **流程**：`init`（无配置时）→ `config`（取 site_id）→ 可选 `validate -f <文件>` → `publish` / `export`。
- **参数**：publish 必填 `-s <site_id>` 且 `-f` 与 `-d` 二选一；export 必填 `-d`、`-s`、`--csv`。详见各子命令 `--help`。
- **退出码**：0 成功，非 0 失败（错误信息在 stdout/stderr，可据此检查配置、site_id、文件与网络）。
- **配置路径**：见「配置」；Windows 下为 `%USERPROFILE%\.claw2wp\config.json`。

---

## 卸载

### 1. 卸载命令与包

```bash
pip uninstall claw2wp
```

按提示确认后，`claw2wp` 命令将不可用。

### 2. 删除配置（可选）

卸载包不会删除本机配置。若要彻底清理：

```bash
# Linux / macOS
rm -rf ~/.claw2wp
```

```powershell
# Windows PowerShell
Remove-Item -Recurse -Force $env:USERPROFILE\.claw2wp
```

之后若再安装，需重新执行 `claw2wp init` 并编辑 `~/.claw2wp/config.json`。

---

## 文档

- [功能一览与命令速查](docs/FEATURES.md)
- [REST API 与 Gutenberg 说明](docs/REST_API.md)
- [PRD / 开发说明](PRD.md)

---

## 许可证

与项目仓库一致。
