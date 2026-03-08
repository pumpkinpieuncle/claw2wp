import os
from pathlib import Path
from claw2wp.parser import parse_file
from claw2wp.wp_api import WPApi
from claw2wp.utils import slugify, date_to_iso8601
from claw2wp.gutenberg import soup_to_gutenberg
from claw2wp.gutenberg_ast import md_to_gutenberg, transform_ast_to_gutenberg
from bs4 import BeautifulSoup

class Publisher:
    def __init__(self, api_client: WPApi):
        self.api = api_client
        self.uploaded_cache = {} # local_path -> (media_id, cloud_url)

    def _upload_image_cached(self, filepath):
        if filepath in self.uploaded_cache:
            return self.uploaded_cache[filepath]
        if not os.path.exists(filepath):
            return None, None
            
        print(f"正在上传图片: {filepath} ...")
        media_id, cloud_url = self.api.upload_media(filepath)
        if media_id:
            self.uploaded_cache[filepath] = (media_id, cloud_url)
            return media_id, cloud_url
        return None, None

    def _replace_img_src(self, soup, old_src, new_src, media_id=None):
        for img in soup.find_all("img", src=old_src):
            img["src"] = new_src
            if media_id is not None:
                img["data-wp-media-id"] = str(media_id)

    def _resolve_slug(self, data, filepath):
        """从 meta.slug 或标题生成用于查找的 slug。"""
        meta = data.get('meta', {})
        if meta.get('slug'):
            return meta['slug'].strip()
        return slugify(data.get('title') or Path(filepath).stem)

    def publish_file(self, filepath, mode='create', target_id=None, status_override=None, dry_run=False, as_post=False):
        """
        发布单文件。mode: create | update | delete。
        target_id: 可选，指定已有文章/产品 ID。
        status_override: 可选，如 'draft' 覆盖 frontmatter 的 status。
        dry_run: True 时只解析并打印将要发布的内容，不实际上传或请求 API。
        as_post: True 时强制发布为 WordPress 文章（不走 WooCommerce 产品），在「文章」列表可见。
        """
        try:
            if mode == 'delete' and target_id is not None:
                return self._delete_by_id(filepath, target_id)

            print(f"解析文件: {filepath}")
            data = parse_file(filepath)
            slug = self._resolve_slug(data, filepath)

            if mode == 'delete':
                return self._delete_by_slug(filepath, data, slug)

            meta = data.get('meta', {})

            if dry_run:
                self._print_dry_run(data, filepath, slug, meta)
                return

            # 1. 上传特色图片
            featured_media_id = None
            featured_url = None
            if data['featured_image']:
                featured_media_id, featured_url = self._upload_image_cached(data['featured_image'])

            # 2. 上传画廊图片
            gallery_media_ids = []
            for img_path in data['gallery_images']:
                mid, murl = self._upload_image_cached(img_path)
                if mid:
                    gallery_media_ids.append(mid)

            # 3. 解析为 Gutenberg 块正文
            soup = data['soup']
            base_dir = data.get("content_base_dir") or os.path.dirname(os.path.abspath(filepath))
            for img in soup.find_all("img"):
                old_src = img.get("src")
                if not old_src or old_src.startswith("http") or old_src.startswith("data:"):
                    continue
                local_path = old_src if os.path.isabs(old_src) else os.path.abspath(os.path.join(base_dir, old_src))
                if local_path in self.uploaded_cache:
                    media_id, cloud_url = self.uploaded_cache[local_path]
                    self._replace_img_src(soup, old_src, cloud_url, media_id=media_id)
            # MD 用 AST 直接生成 Gutenberg，避免 HTML 再解析导致格式错乱
            document_title = data.get("title")
            if data.get("ast") is not None:
                print(f"DEBUG: 使用 AST 生成 Gutenberg 块...")
                html_content = transform_ast_to_gutenberg(
                    data["ast"],
                    image_map=self.uploaded_cache,
                    base_dir=base_dir,
                    document_title=document_title,
                )
            elif data.get("md_content") is not None:
                print(f"DEBUG: 使用 MD 源码生成 Gutenberg 块...")
                try:
                    html_content = md_to_gutenberg(
                        data["md_content"],
                        image_map=self.uploaded_cache,
                        base_dir=base_dir,
                        document_title=document_title,
                    )
                except Exception as e:
                    print(f"DEBUG: md_to_gutenberg 失败，回退到 BeautifulSoup: {e}")
                    html_content = soup_to_gutenberg(soup)
            else:
                print(f"DEBUG: 回退到 BeautifulSoup 生成 Gutenberg 块...")
                html_content = soup_to_gutenberg(soup)

            print(f"DEBUG: 正文块生成完毕，长度: {len(html_content)} 字符")
            if len(html_content) > 100:
                print(f"DEBUG: 正文样例 (前200字): \n{html_content[:200]}...")

            if dry_run:
                self._print_dry_run(data, filepath, slug, meta, html_snippet=html_content[:500])
                return

            # 4. 准备 payload。如果 meta 中有 type='post'，则强制 as_post=True
            final_as_post = as_post or (data.get('type') == 'post')
            status = status_override if status_override else meta.get('status', 'publish')
            
            if final_as_post:
                # 标准文章 Payload
                payload = {
                    "title": data['title'],
                    "content": html_content,
                    "status": status,
                }
                if slug:
                    payload['slug'] = slug
                if meta.get('excerpt'):
                    payload['excerpt'] = meta['excerpt']
                if meta.get('author'):
                    payload['author'] = meta['author']
            else:
                # WooCommerce 产品 Payload
                payload = {
                    "name": data['title'],
                    "type": "simple",
                    "description": html_content,
                    "short_description": meta.get('short_description', ''),
                    "status": status,
                    "sku": str(meta.get('sku', '')),
                    "regular_price": str(meta.get('regular_price', '')),
                }

            date_iso = date_to_iso8601(meta.get('date'))
            if date_iso:
                payload['date'] = date_iso

            images = []
            if featured_media_id:
                images.append({"id": featured_media_id})
            for gid in gallery_media_ids:
                images.append({"id": gid})
            if images:
                payload["images"] = images

            wp_cat_ids = self.api.resolve_wp_category_ids(meta.get('categories') or [])
            wp_tag_ids = self.api.resolve_wp_tag_ids(meta.get('tags') or [])
            wc_cat_ids = self.api.resolve_wc_category_ids(meta.get('categories') or [])
            if wc_cat_ids:
                payload['categories'] = [{"id": i} for i in wc_cat_ids]
            elif wp_cat_ids:
                payload['categories'] = wp_cat_ids
            if wp_tag_ids:
                payload['tags'] = wp_tag_ids

            if meta.get('regular_price') is not None:
                payload['regular_price'] = str(meta['regular_price'])
            if meta.get('sale_price') is not None:
                payload['sale_price'] = str(meta['sale_price'])
            if meta.get('sku') is not None:
                payload['sku'] = str(meta['sku'])

            if mode == 'update':
                result = self._update_or_create(filepath, data, payload, slug, target_id, as_post=final_as_post)
            else:
                if final_as_post:
                    print(f"正在发布文章: {data['title']} ...")
                    result = self.api.create_post(payload)
                else:
                    print(f"正在发布商品/文章: {data['title']} ...")
                    result = self.api.create_product(payload)
            if result:
                url = result.get('permalink') or result.get('link', 'Unknown URL')
                kind = "文章" if (as_post or result.get('type') == 'post') else "产品"
                print(f"✅ 发布成功（{kind}）! {url}")
            else:
                print("❌ 发布失败.")
                return

        except Exception as e:
            print(f"处理文件 {filepath} 发生异常: {e}")

    def _print_dry_run(self, data, filepath, slug, meta, html_snippet=None):
        """Dry-run：打印将要发布的内容摘要，不请求 API。"""
        n_featured = 1 if data.get('featured_image') else 0
        n_gallery = len(data.get('gallery_images') or [])
        print("--- [dry-run] 预览，不会实际上传或发布 ---")
        print(f"  标题: {data.get('title')}")
        print(f"  slug: {slug}")
        print(f"  状态: {meta.get('status', 'publish')}")
        if meta.get('date'):
            print(f"  日期: {meta.get('date')}")
        print(f"  特色图: {data.get('featured_image') or '(无)'}")
        print(f"  画廊图数量: {n_gallery}")
        if meta.get('categories'):
            print(f"  分类: {meta.get('categories')}")
        if meta.get('tags'):
            print(f"  标签: {meta.get('tags')}")
        if meta.get('excerpt'):
            print(f"  摘要: {meta.get('excerpt', '')[:60]}...")
        if html_snippet:
            print(f"  正文预览 (前500字):\n{html_snippet}...")
        print("---")

    def _update_or_create(self, filepath, data, payload, slug, target_id=None, as_post=False):
        """按 slug 或 target_id 查找已有产品/文章并更新，找不到则新建。as_post=True 时只操作文章。"""
        existing_id = target_id
        is_product = None
        if as_post:
            if existing_id is not None:
                post = self.api.get_post(existing_id)
                if post:
                    is_product = False
            else:
                post = self.api.get_post_by_slug(slug) if slug else None
                if post:
                    existing_id = post['id']
                    is_product = False
        else:
            if existing_id is not None:
                prod = self.api.get_product(existing_id)
                if prod:
                    is_product = True
                else:
                    post = self.api.get_post(existing_id)
                    if post:
                        is_product = False
            else:
                prod = self.api.get_product_by_slug(slug) if slug else None
                if prod:
                    existing_id = prod['id']
                    is_product = True
                else:
                    post = self.api.get_post_by_slug(slug) if slug else None
                    if post:
                        existing_id = post['id']
                        is_product = False
        if existing_id is None:
            print(f"未找到 slug=\"{slug}\" 的已有内容，将新建...")
            return self.api.create_post(payload) if as_post else self.api.create_product(payload)
        if is_product:
            print(f"正在更新产品 id={existing_id} ...")
            return self.api.update_product(existing_id, payload)
        else:
            print(f"正在更新文章 id={existing_id} ...")
            return self.api.update_post(existing_id, payload)

    def _delete_by_slug(self, filepath, data, slug):
        """按 slug 查找并删除产品或文章。"""
        prod = self.api.get_product_by_slug(slug) if slug else None
        if prod:
            print(f"正在删除产品 id={prod['id']} ({prod.get('name', slug)}) ...")
            result = self.api.delete_product(prod['id'])
        else:
            post = self.api.get_post_by_slug(slug) if slug else None
            if post:
                print(f"正在删除文章 id={post['id']} ({post.get('title', {}).get('rendered', slug)}) ...")
                result = self.api.delete_post(post['id'])
            else:
                print(f"未找到 slug=\"{slug}\" 的产品或文章，无法删除。")
                return
        if result is not None:
            print("✅ 已删除。")
        else:
            print("❌ 删除失败。")

    def _delete_by_id(self, filepath, target_id):
        """按 ID 删除（先尝试产品，再尝试文章）。"""
        prod = self.api.get_product(target_id)
        if prod:
            print(f"正在删除产品 id={target_id} ...")
            result = self.api.delete_product(target_id)
        else:
            post = self.api.get_post(target_id)
            if post:
                print(f"正在删除文章 id={target_id} ...")
                result = self.api.delete_post(post['id'])
            else:
                print(f"未找到 id={target_id} 的产品或文章。")
                return
        if result is not None:
            print("✅ 已删除。")
        else:
            print("❌ 删除失败。")

    def publish_directory(self, dirpath, mode='create', status_override=None, dry_run=False, as_post=False):
        dirpath = Path(dirpath)
        if not dirpath.is_dir():
            print(f"错误: {dirpath} 不是一个有效的目录")
            return
        print(f"开始批量处理目录: {dirpath} (mode={mode}, 发布为={'文章' if as_post else '产品/文章'})")
        for file in dirpath.rglob("*"):
            if file.is_file() and file.suffix.lower() in ['.md', '.docx']:
                self.publish_file(str(file), mode=mode, status_override=status_override, dry_run=dry_run, as_post=as_post)
        print("🎉 目录处理结束。")
