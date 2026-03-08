# Claw2WP 功能一览

用命令行把 Markdown / Word 发布到 WordPress，支持 Gutenberg 块、WooCommerce 产品、更新/删除、批量发布与 CSV 导出。

## 命令行一览

```bash
# 初始化配置
claw2wp init

# 显示已配置站点（不含密码）
claw2wp config

# 校验文件与可选站点
claw2wp validate -f post.md
claw2wp validate -f post.md -s mysite

# 发布（新建）
claw2wp publish -f post.md -s mysite

# 强制草稿、仅预览
claw2wp publish -f post.md -s mysite --draft
claw2wp publish -f post.md -s mysite --dry-run

# 更新 / 删除
claw2wp publish -f post.md -s mysite --update
claw2wp publish -f post.md -s mysite --delete
claw2wp publish -f post.md -s mysite --delete --id 42

# 目录批量
claw2wp publish -d ./posts -s mysite
claw2wp publish -d ./posts -s mysite --update

# 导出 WooCommerce CSV
claw2wp export -d ./products -s mysite --csv
```

## Frontmatter 选项

```yaml
title: '文章标题'          # 必填（或使用文件名）
slug: custom-url-slug      # 可选，用于更新/删除匹配
status: draft              # draft | publish，默认 publish
featured_image: ./hero.jpg # 可选，显式特色图路径
date: 2024-01-15           # 可选，支持 2024-01-15 或 2024-01-15 12:00
excerpt: '摘要'            # 可选
tags: [tag1, tag2]         # 可选
categories: [cat1, cat2]   # 可选（文章分类或 WooCommerce 产品分类）
comment_status: open       # open | closed

# WooCommerce 专用
short_description: '...'
regular_price: "99.00"
sale_price: "79.00"
sku: SKU-001
```

未在 frontmatter 中写 `featured_image` 时，会按「同名文件-1 / 同名文件-feature」等命名规则自动寻找特色图。

## 配置

- 全局配置：`~/.claw2wp/config.json`
- 支持多站点（多个 site_id），每项含 `url`、`user`、`pass`（Application Password）。

详见 [REST_API.md](REST_API.md)。
