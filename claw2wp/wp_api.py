# -*- coding: utf-8 -*-
"""
WordPress REST API 客户端 (wp/v2 + WooCommerce wc/v3)。

认证：推荐使用 WordPress 5.6+ 的 Application Passwords + HTTPS，
参见 https://github.com/WordPress/agent-skills (wp-rest-api, authentication)。
"""
import os
import requests
import mimetypes
from urllib.parse import quote

# 默认请求超时（秒）
DEFAULT_TIMEOUT = 30


class WPApi:
    def __init__(self, site_config):
        self.url = site_config.get('url', '').rstrip('/')
        self.user = site_config.get('user', '')
        self.password = site_config.get('pass', '')
        self.auth = (self.user, self.password)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self._categories_cache = None  # list of {id, name, slug}
        self._tags_cache = None
        self._wc_categories_cache = None

    def _request(self, method, path, **kwargs):
        """统一请求：GET/POST 等，带认证与超时。"""
        url = f"{self.url}/wp-json{path}"
        headers = self.headers.copy()
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))
        
        kwargs.setdefault('auth', self.auth)
        kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
        kwargs.setdefault('headers', headers)
        return requests.request(method, url, **kwargs)

    # ------------------------- Media (wp/v2/media) -------------------------

    def _content_disposition_for_file(self, file_path):
        """生成 Content-Disposition，支持中文等非 ASCII 文件名（RFC 5987）。"""
        raw_name = os.path.basename(file_path)
        try:
            raw_name.encode('ascii')
            return f'attachment; filename="{raw_name}"'
        except UnicodeEncodeError:
            ext = os.path.splitext(raw_name)[1] or ''
            ascii_fallback = f"upload{ext}"
            encoded = quote(raw_name, safe='')
            return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"

    def upload_media(self, file_path):
        """上传媒体到 WP，返回 (media_id, cloud_url)。"""
        headers = {
            'Content-Disposition': self._content_disposition_for_file(file_path)
        }
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            headers['Content-Type'] = mime_type

        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            res = self._request('POST', '/wp/v2/media', headers=headers, data=data)
            if res.status_code in (200, 201):
                result = res.json()
                media_id = result.get('id')
                source_url = result.get('source_url') or (result.get('guid') or {}).get('rendered')
                return media_id, source_url
            print(f"上传媒体失败 {file_path}. HTTP {res.status_code}: {res.text}")
            return None, None
        except Exception as e:
            print(f"上传媒体发生异常 {file_path}: {e}")
            return None, None

    # ------------------------- Taxonomies: 分类/标签解析 -------------------------

    def get_wp_categories(self):
        """GET wp/v2/categories，缓存在内存。"""
        if self._categories_cache is not None:
            return self._categories_cache
        try:
            res = self._request('GET', '/wp/v2/categories', params={'per_page': 100})
            if res.status_code == 200:
                self._categories_cache = res.json()
                return self._categories_cache
        except Exception as e:
            print(f"获取分类列表异常: {e}")
        return []

    def get_wp_tags(self):
        """GET wp/v2/tags，缓存在内存。"""
        if self._tags_cache is not None:
            return self._tags_cache
        try:
            res = self._request('GET', '/wp/v2/tags', params={'per_page': 100})
            if res.status_code == 200:
                self._tags_cache = res.json()
                return self._tags_cache
        except Exception as e:
            print(f"获取标签列表异常: {e}")
        return []

    def resolve_wp_category_ids(self, names):
        """将分类名称（或 slug）解析为 wp/v2 的 category ID 列表。"""
        if not names:
            return []
        if isinstance(names, str):
            names = [n.strip() for n in names.split(',') if n.strip()]
        names = [n.strip() for n in names if n]
        categories = self.get_wp_categories()
        ids = []
        for name in names:
            name_lower = name.lower()
            for c in categories:
                if c.get('name') == name or c.get('slug', '').lower() == name_lower:
                    ids.append(c['id'])
                    break
        return ids

    def resolve_wp_tag_ids(self, names):
        """将标签名称（或 slug）解析为 wp/v2 的 tag ID 列表。"""
        if not names:
            return []
        if isinstance(names, str):
            names = [n.strip() for n in names.split(',') if n.strip()]
        names = [n.strip() for n in names if n]
        tags = self.get_wp_tags()
        ids = []
        for name in names:
            name_lower = name.lower()
            for t in tags:
                if t.get('name') == name or t.get('slug', '').lower() == name_lower:
                    ids.append(t['id'])
                    break
        return ids

    def get_wc_categories(self):
        """GET wc/v3/products/categories，用于 WooCommerce 产品分类。"""
        if self._wc_categories_cache is not None:
            return self._wc_categories_cache
        try:
            res = self._request('GET', '/wc/v3/products/categories', params={'per_page': 100})
            if res.status_code == 200:
                self._wc_categories_cache = res.json()
                return self._wc_categories_cache
        except Exception as e:
            print(f"获取 WooCommerce 分类列表异常: {e}")
        return []

    def resolve_wc_category_ids(self, names):
        """将名称解析为 WooCommerce 产品分类 ID 列表。"""
        if not names:
            return []
        if isinstance(names, str):
            names = [n.strip() for n in names.split(',') if n.strip()]
        names = [n.strip() for n in names if n]
        categories = self.get_wc_categories()
        ids = []
        for name in names:
            name_lower = name.lower()
            for c in categories:
                if c.get('name') == name or c.get('slug', '').lower() == name_lower:
                    ids.append(c['id'])
                    break
        return ids

    # ------------------------- Posts (wp/v2/posts) -------------------------

    def create_post(self, data):
        """
        创建标准 WordPress 文章。
        data 支持: name/title, description/content, status, excerpt, comment_status,
        ping_status, author, featured_media, categories (ID 列表), tags (ID 列表),
        images (用于取首图 ID)。
        """
        title_raw = data.get('title') or data.get('name', '')
        content_raw = data.get('content') or data.get('description', '')
        # 与 WP REST API schema 对齐：content 为对象时用 raw 存块格式，避免块注释被当纯文本导致格式变段落
        wp_data = {
            'title': title_raw,
            'content': {'raw': content_raw} if isinstance(content_raw, str) else content_raw,
            'status': data.get('status', 'publish'),
        }
        if data.get('date'):
            wp_data['date'] = data['date']
        if data.get('excerpt'):
            wp_data['excerpt'] = data['excerpt']
        if data.get('comment_status') in ('open', 'closed'):
            wp_data['comment_status'] = data['comment_status']
        if data.get('ping_status') in ('open', 'closed'):
            wp_data['ping_status'] = data['ping_status']
        if data.get('author') is not None:
            wp_data['author'] = int(data['author'])

        categories = data.get('categories', [])
        if categories:
            if isinstance(categories[0], dict) and 'id' in categories[0]:
                wp_data['categories'] = [c['id'] for c in categories]
            elif isinstance(categories[0], int):
                wp_data['categories'] = categories
        tags = data.get('tags', [])
        if tags and isinstance(tags[0], int):
            wp_data['tags'] = tags

        images = data.get('images', [])
        if images and isinstance(images[0], dict) and 'id' in images[0]:
            wp_data['featured_media'] = images[0]['id']
        elif data.get('featured_media') is not None:
            wp_data['featured_media'] = int(data['featured_media'])

        try:
            res = self._request('POST', '/wp/v2/posts', json=wp_data)
            if res.status_code in (200, 201):
                return res.json()
            print(f"创建标准文章失败. HTTP {res.status_code}: {res.text}")
            return None
        except Exception as e:
            print(f"请求创建标准文章发生异常: {e}")
            return None

    def get_post(self, post_id):
        """GET 单篇文章。返回 dict 或 None。"""
        try:
            res = self._request('GET', f'/wp/v2/posts/{int(post_id)}')
            if res.status_code == 200:
                return res.json()
            return None
        except Exception:
            return None

    def get_post_by_slug(self, slug):
        """按 slug 查找文章，返回第一篇匹配的 dict 或 None。"""
        if not slug:
            return None
        try:
            res = self._request('GET', '/wp/v2/posts', params={'slug': slug, 'per_page': 1})
            if res.status_code == 200:
                items = res.json()
                return items[0] if items else None
            return None
        except Exception:
            return None

    def update_post(self, post_id, data):
        """更新文章。content 以 schema 对象 { raw: ... } 发送，保证 Gutenberg 块格式被正确识别。"""
        title_raw = data.get('title') or data.get('name', '')
        content_raw = data.get('content') or data.get('description', '')
        wp_data = {
            'title': title_raw,
            'content': {'raw': content_raw} if isinstance(content_raw, str) else content_raw,
            'status': data.get('status', 'publish'),
        }
        if data.get('date'):
            wp_data['date'] = data['date']
        if data.get('excerpt') is not None:
            wp_data['excerpt'] = data['excerpt']
        if data.get('comment_status') in ('open', 'closed'):
            wp_data['comment_status'] = data['comment_status']
        if data.get('ping_status') in ('open', 'closed'):
            wp_data['ping_status'] = data['ping_status']
        if data.get('author') is not None:
            wp_data['author'] = int(data['author'])

        categories = data.get('categories', [])
        if categories:
            if isinstance(categories[0], dict) and 'id' in categories[0]:
                wp_data['categories'] = [c['id'] for c in categories]
            elif isinstance(categories[0], int):
                wp_data['categories'] = categories
        tags = data.get('tags', [])
        if tags and isinstance(tags[0], int):
            wp_data['tags'] = tags

        images = data.get('images', [])
        if images and isinstance(images[0], dict) and 'id' in images[0]:
            wp_data['featured_media'] = images[0]['id']
        elif data.get('featured_media') is not None:
            wp_data['featured_media'] = int(data['featured_media'])

        try:
            # 更新通常建议使用 PUT
            res = self._request('PUT', f'/wp/v2/posts/{int(post_id)}', json=wp_data)
            if res.status_code == 200:
                return res.json()
            print(f"更新文章失败. HTTP {res.status_code}: {res.text}")
            return None
        except Exception as e:
            print(f"请求更新文章发生异常: {e}")
            return None

    def delete_post(self, post_id, force=False):
        """删除文章。force=True 永久删除，否则移入回收站。"""
        try:
            res = self._request('DELETE', f'/wp/v2/posts/{int(post_id)}', params={'force': force})
            if res.status_code in (200, 204):
                return res.json() if res.content else {}
            print(f"删除文章失败. HTTP {res.status_code}: {res.text}")
            return None
        except Exception as e:
            print(f"请求删除文章发生异常: {e}")
            return None

    # ------------------------- WooCommerce Products (wc/v3/products) -------------------------

    def create_product(self, product_data):
        """创建 WooCommerce 产品。若无 WooCommerce 则 fallback 为 create_post。"""
        try:
            res = self._request('POST', '/wc/v3/products', json=product_data)
            if res.status_code in (200, 201):
                return res.json()

            if res.status_code == 404:
                print("未发现 WooCommerce，尝试创建标准文章...")
                return self.create_post(product_data)

            print(f"创建产品失败. HTTP {res.status_code}: {res.text}")
            return None
        except Exception as e:
            print(f"请求创建产品发生异常: {e}")
            return None

    def get_product(self, product_id):
        """GET 单个产品。返回 dict 或 None。"""
        try:
            res = self._request('GET', f'/wc/v3/products/{int(product_id)}')
            if res.status_code == 200:
                return res.json()
            return None
        except Exception:
            return None

    def get_product_by_slug(self, slug):
        """按 slug 查找产品，返回第一个匹配的 dict 或 None。"""
        if not slug:
            return None
        try:
            res = self._request('GET', '/wc/v3/products', params={'slug': slug, 'per_page': 1})
            if res.status_code == 200:
                items = res.json()
                return items[0] if items else None
            return None
        except Exception:
            return None

    def update_product(self, product_id, product_data):
        """更新 WooCommerce 产品。"""
        try:
            res = self._request('PUT', f'/wc/v3/products/{int(product_id)}', json=product_data)
            if res.status_code == 200:
                return res.json()
            print(f"更新产品失败. HTTP {res.status_code}: {res.text}")
            return None
        except Exception as e:
            print(f"请求更新产品发生异常: {e}")
            return None

    def delete_product(self, product_id, force=True):
        """删除产品。force=True 永久删除，否则移入回收站。"""
        try:
            res = self._request('DELETE', f'/wc/v3/products/{int(product_id)}', params={'force': force})
            if res.status_code in (200, 204):
                return res.json() if res.content else {}
            print(f"删除产品失败. HTTP {res.status_code}: {res.text}")
            return None
        except Exception as e:
            print(f"请求删除产品发生异常: {e}")
            return None
