# Claw2WP 与 WordPress REST API

本文说明 Claw2WP 使用的 WordPress REST API 端点、认证方式，以及如何与官方实践对齐。

## 参考资源

- **WordPress REST API 手册**: https://developer.wordpress.org/rest-api/
- **WordPress agent-skills**（服务端扩展 REST API 时的最佳实践）: https://github.com/WordPress/agent-skills  
  - 其中 `wp-rest-api` skill 面向在 WordPress 端注册/扩展路由与认证；Claw2WP 作为**客户端**遵循其认证建议（Application Passwords + HTTPS）。

## 认证

- 推荐使用 **WordPress 5.6+ Application Passwords**，配合 **HTTPS**。
- 在 `~/.claw2wp/config.json` 中配置 `user` 与 `pass`（Application Password），请求时使用 HTTP Basic Auth。
- 参见 [agent-skills - authentication](https://github.com/WordPress/agent-skills/blob/trunk/skills/wp-rest-api/references/authentication.md)。

## 内容格式：Gutenberg 块

发布到 WordPress 时，正文会转换为 **Gutenberg 块格式**（与块编辑器一致），而不是纯 HTML：

- 段落 → `<!-- wp:paragraph -->` … `<!-- /wp:paragraph -->`
- 标题 h1–h6 → `<!-- wp:heading {"level":n} -->`，并加上 `wp-block-heading` 类
- 图片 → `<!-- wp:image {"id":媒体ID,"sizeSlug":"large"} -->`，使用上传后的媒体 ID
- 列表 ul/ol、代码块、引用、分隔线、表格等也会包成对应块注释

这样在 WP 后台编辑器中会显示为可编辑的块，而不是单一 HTML 块。

## 已使用的端点

| 用途           | 方法 | 路径 | 说明 |
|----------------|------|------|------|
| 上传媒体       | POST | `/wp/v2/media` | 上传图片，返回 `id`、`source_url` |
| 创建文章       | POST | `/wp/v2/posts` | 无 WooCommerce 时的 fallback；支持 title, content, excerpt, featured_media, categories, tags, comment_status 等 |
| 获取文章       | GET  | `/wp/v2/posts/{id}`、`/wp/v2/posts?slug=` | 按 ID 或 slug 查找，用于更新/删除 |
| 更新文章       | POST | `/wp/v2/posts/{id}` | 更新已有文章 |
| 删除文章       | DELETE | `/wp/v2/posts/{id}` | 删除文章（可选移入回收站） |
| 分类列表       | GET  | `/wp/v2/categories` | 按名称解析为 ID，用于文章分类 |
| 标签列表       | GET  | `/wp/v2/tags` | 按名称解析为 ID，用于文章标签 |
| 创建产品       | POST | `/wc/v3/products` | WooCommerce 插件；支持 name, description, images, categories 等 |
| 获取产品       | GET  | `/wc/v3/products/{id}`、`/wc/v3/products?slug=` | 按 ID 或 slug 查找 |
| 更新产品       | PUT  | `/wc/v3/products/{id}` | 更新已有产品 |
| 删除产品       | DELETE | `/wc/v3/products/{id}` | 删除产品（可选永久删除） |
| 产品分类列表   | GET  | `/wc/v3/products/categories` | 按名称解析为 ID，用于产品分类 |

## Frontmatter / Meta 与 API 字段对应

在 `.md` 的 frontmatter 或解析结果 `meta` 中可配置：

- `categories`：分类名称（字符串或列表），会解析为站点已有分类 ID 后传入。
- `tags`：标签名称，同上。
- `short_description` / `excerpt`：摘要。
- `comment_status`：`open` 或 `closed`。
- `status`：`publish` / `draft` / `pending` 等。
- `regular_price` / `sale_price` / `sku`：WooCommerce 产品字段。
- `slug`：用于更新/删除时匹配已有文章或产品（不填则用标题生成的 slug）。
- `featured_image`：显式特色图路径（如 `./images/hero.jpg`）。
- `date`：发布日期，支持 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM`，会转为 ISO8601 传给 WP。

## 更新与删除（命令行）

- **更新**：`claw2wp publish -f <文件> -s <site_id> --update`  
  按 frontmatter 的 `slug`（或标题生成的 slug）查找已有产品或文章并更新；找不到则新建。  
  也可指定 `--id <ID>` 直接按 ID 更新。
- **删除**：`claw2wp publish -f <文件> -s <site_id> --delete`  
  按 `slug` 或 `--id` 查找并删除对应产品或文章。  
  批量删除：`claw2wp publish -d <目录> -s <site_id> --delete`（按各文件 slug 逐个删除）。

## 未覆盖的 WordPress 自带能力

以下为 WordPress 自带 REST API 能力，当前 Claw2WP **未实现**，可按需扩展：

- **Pages**: `POST/GET/PUT/DELETE /wp/v2/pages`
- **Media**: GET/PUT/DELETE 单条媒体、列表
- **Users / Comments / Settings / Search** 等

扩展时可继续参考 [WordPress REST API Reference](https://developer.wordpress.org/rest-api/reference/)。
