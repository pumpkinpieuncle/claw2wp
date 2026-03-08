# -*- coding: utf-8 -*-
"""
将 HTML（BeautifulSoup）转为 WordPress Gutenberg 块格式。
文档：https://developer.wordpress.org/block-editor/getting-started/fundamentals/markup-representation-block/
"""
import json
from bs4 import BeautifulSoup, NavigableString, Tag

# 视为块级元素、需包一层 Gutenberg 注释的标签
BLOCK_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'pre', 'blockquote', 'figure', 'hr', 'table'}
# 块类型与标签对应（不含属性时）
BLOCK_NAMES = {
    'p': 'paragraph',
    'h1': 'heading', 'h2': 'heading', 'h3': 'heading', 'h4': 'heading', 'h5': 'heading', 'h6': 'heading',
    'ul': 'list', 'ol': 'list',
    'pre': 'code',
    'blockquote': 'quote',
    'figure': 'image',
    'hr': 'separator',
    'table': 'table',
}


def _wrap_block(block_name, attrs, html_content):
    """生成一块 Gutenberg 注释包裹的内容。"""
    attrs_str = json.dumps(attrs) if attrs else ""
    open_comment = f'<!-- wp:{block_name}' + (f' {attrs_str}' if attrs_str else '') + ' -->'
    close_comment = f'<!-- /wp:{block_name} -->'
    return f"{open_comment}\n{html_content}\n{close_comment}"


def _normalize_class_list(tag, extra_classes):
    """给 tag 的 class 追加 extra_classes，兼容 class 为 list 或 str。"""
    cls = tag.get('class')
    if cls is None:
        cls = []
    if isinstance(cls, str):
        cls = cls.split()
    tag['class'] = list(cls) + list(extra_classes)


def _block_for_heading(tag):
    level = int(tag.name[1])
    _normalize_class_list(tag, ['wp-block-heading'])
    return _wrap_block('heading', {'level': level}, str(tag))


def _block_for_image(tag, media_id=None):
    """单个 figure 或 单个 img 转 wp:image。"""
    if tag.name == 'img':
        media_id = media_id
        if media_id is None and tag.get('data-wp-media-id'):
            try:
                media_id = int(tag['data-wp-media-id'])
            except (ValueError, TypeError):
                pass
        attrs = {'sizeSlug': 'large'}
        if media_id:
            attrs['id'] = media_id
        extra = [f'wp-image-{media_id}'] if media_id else []
        _normalize_class_list(tag, extra)
        inner = f'<figure class="wp-block-image size-large">{str(tag)}</figure>'
        return _wrap_block('image', attrs, inner)
    # tag is figure
    img = tag.find('img')
    media_id = None
    if img and img.get('data-wp-media-id'):
        try:
            media_id = int(img['data-wp-media-id'])
        except (ValueError, TypeError):
            pass
    _normalize_class_list(tag, ['wp-block-image', 'size-large'])
    attrs = {'sizeSlug': 'large'}
    if media_id:
        attrs['id'] = media_id
    return _wrap_block('image', attrs, str(tag))


def _paragraph_get_image_blocks(p_tag):
    """
    若 <p> 内仅包含图片（img 或 figure），返回这些标签列表，用于转为多个 wp:image 块；
    否则返回 None，按普通段落处理。
    """
    tag_children = [c for c in p_tag.children if isinstance(c, Tag)]
    if not tag_children:
        return None
    images = []
    for t in tag_children:
        if t.name == 'img':
            images.append(t)
        elif t.name == 'figure' and t.find('img'):
            images.append(t)
        else:
            return None  # 含有非图片块级元素，当段落
    return images if images else None


def _block_for_paragraph(tag):
    return _wrap_block('paragraph', {}, str(tag))


def _block_for_list(tag):
    _normalize_class_list(tag, ['wp-block-list'])
    attrs = {'ordered': tag.name == 'ol'}
    return _wrap_block('list', attrs, str(tag))


def _block_for_code(tag):
    if tag.name == 'pre':
        _normalize_class_list(tag, ['wp-block-code'])
    return _wrap_block('code', {}, str(tag))


def _block_for_quote(tag):
    _normalize_class_list(tag, ['wp-block-quote'])
    return _wrap_block('quote', {}, str(tag))


def _block_for_separator(tag):
    """hr 使用 wp-block-separator has-alpha-channel-opacity。"""
    _normalize_class_list(tag, ['wp-block-separator', 'has-alpha-channel-opacity'])
    return _wrap_block('separator', {}, str(tag))


def _block_for_table(tag):
    """表格包成 core/table 结构：<figure class="wp-block-table"><table>...</table></figure>。"""
    inner = f'<figure class="wp-block-table">{str(tag)}</figure>'
    return _wrap_block('table', {}, inner)


def _render_block(tag):
    """将单个 Tag 转为 Gutenberg 块 HTML 字符串。与 WP 古腾堡 core 块一一对应。"""
    name = tag.name
    if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
        return _block_for_heading(tag)
    if name == 'p':
        # 段落内仅图片时，每张图一个 wp:image 块
        image_blocks = _paragraph_get_image_blocks(tag)
        if image_blocks:
            return '\n\n'.join(_block_for_image(t) for t in image_blocks)
        return _block_for_paragraph(tag)
    if name in ('ul', 'ol'):
        return _block_for_list(tag)
    if name == 'pre':
        return _block_for_code(tag)
    if name == 'blockquote':
        return _block_for_quote(tag)
    if name == 'hr':
        return _block_for_separator(tag)
    if name == 'table':
        return _block_for_table(tag)
    if name == 'figure':
        return _block_for_image(tag)
    if name == 'img':
        return _block_for_image(tag)
    # 其他块级或未知：用 wp:html 包一层，保证可编辑
    return _wrap_block('html', {}, str(tag))


def _get_block_children(container):
    """获取容器的直接子节点（用于逐块处理）。"""
    children = []
    for c in container.children:
        if isinstance(c, NavigableString):
            s = c.strip()
            if s:
                # 裸文本包成段落
                children.append(('text', s))
        elif isinstance(c, Tag):
            children.append(('tag', c))
    return children


def _get_container(soup):
    """
    确定要逐块遍历的容器（body，或 html 的 body，或根）。
    若根容器只有一个直接子节点且是 div，则用该 div 作为容器，避免整篇被包成一块导致格式丢失。
    """
    body = soup.find('body')
    if body:
        container = body
    else:
        html = soup.find('html')
        if html and html.find('body'):
            container = html.find('body')
        else:
            container = soup
    # 根容器仅有一层 div 包裹时，展开该 div，直接处理其子节点
    tag_children = [c for c in container.children if isinstance(c, Tag)]
    if len(tag_children) == 1 and tag_children[0].name == 'div':
        container = tag_children[0]
    return container


def _process_container(container):
    """
    将容器的直接子节点逐块转为 Gutenberg 块字符串列表。
    对 div 递归展开其子节点，避免整段被当成一个 wp:html 块导致格式丢失。
    """
    parts = []
    for kind, item in _get_block_children(container):
        if kind == 'text':
            parts.append(_wrap_block('paragraph', {}, f'<p>{item}</p>'))
        else:
            tag = item
            if tag.name in BLOCK_TAGS or tag.name == 'img':
                parts.append(_render_block(tag))
            elif tag.name == 'div':
                # 递归处理 div 内子节点，保证段落/标题/列表等各自成块
                parts.extend(_process_container(tag))
            else:
                parts.append(_wrap_block('html', {}, str(tag)))
    return parts


def soup_to_gutenberg(soup):
    """
    将 BeautifulSoup 解析后的 HTML 转为 Gutenberg 块格式的 HTML 字符串。
    若 soup 含 body 则对 body 的直接子节点处理，否则对根直接子节点处理；
    对 div 会递归展开子节点，避免 MD 或扩展产生的包裹层导致格式丢失。
    """
    container = _get_container(soup)
    if not container:
        return ""
    parts = _process_container(container)
    return '\n\n'.join(parts)


def html_to_gutenberg(html_string):
    """将 HTML 字符串转为 Gutenberg 块格式。"""
    soup = BeautifulSoup(html_string, 'html.parser')
    return soup_to_gutenberg(soup)
