# -*- coding: utf-8 -*-
"""
从 Markdown AST 直接生成 Gutenberg 块 HTML（不经过 HTML 再解析）。
"""
import html
import json
import os
from mistletoe import Document
from mistletoe import block_token
from mistletoe import span_token


def _escape_html(text):
    """HTML 转义。"""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def _wrap_block(block_name, attrs, html_content):
    # 紧凑 JSON 无空格
    attrs_str = json.dumps(attrs, separators=(',', ':')) if attrs else ""
    open_c = f'<!-- wp:{block_name}' + (f' {attrs_str}' if attrs_str else '') + ' -->'
    close_c = f'<!-- /wp:{block_name} -->'
    return f"{open_c}\n{html_content}\n{close_c}"


def _render_inline(token):
    """将内联（span）节点转为 HTML。"""
    if token is None:
        return ""
    cls = type(token).__name__.lower()
    if cls == "rawtext":
        return _escape_html(token.content)
    if cls == "strong":
        inner = "".join(_render_inline(c) for c in token.children)
        return f"<strong>{inner}</strong>"
    if cls == "emphasis":
        inner = "".join(_render_inline(c) for c in token.children)
        return f"<em>{inner}</em>"
    if cls == "inlinecode":
        return f"<code>{_escape_html(token.children[0].content)}</code>"
    if cls == "link":
        href = _escape_html(token.target)
        title = f' title="{_escape_html(token.title)}"' if getattr(token, "title", None) else ""
        inner = "".join(_render_inline(c) for c in token.children)
        return f'<a href="{href}"{title}>{inner}</a>'
    if cls == "image":
        # 内联图片（与段落混排时）
        src = _escape_html(token.src)
        alt = "".join(_render_inline(c) for c in token.children) if token.children else ""
        alt = _escape_html(alt) if isinstance(alt, str) else alt
        return f'<img src="{src}" alt="{alt}" />'
    if cls == "linebreak":
        return "<br />" if not getattr(token, "soft", True) else " "
    if cls == "escapesequence":
        return _render_inline(token.children[0]) if token.children else ""
    if cls == "strikethrough":
        inner = "".join(_render_inline(c) for c in token.children)
        return f"<del>{inner}</del>"
    if hasattr(token, "children") and token.children is not None:
        return "".join(_render_inline(c) for c in token.children)
    if getattr(token, "content", None) is not None:
        return _escape_html(token.content)
    return ""


def _render_inner(token):
    """块级 token 的内联内容。"""
    if not getattr(token, "children", None):
        return _escape_html(getattr(token, "content", "") or "").strip()
    return "".join(_render_inline(c) for c in token.children).strip()


def _get_plain_text(token):
    """从 token 提取纯文本（无 HTML），用于与 document_title 比较。"""
    if not getattr(token, "children", None):
        return (getattr(token, "content", "") or "").strip()
    return "".join(_get_plain_text(c) for c in token.children).strip()


def _resolve_image_src(src, base_dir):
    """与 publisher 一致：解析为绝对路径，用于查 image_map。"""
    if not src or src.startswith(("http://", "https://", "data:")):
        return None
    if os.path.isabs(src):
        return os.path.normpath(src)
    return os.path.abspath(os.path.join(base_dir or ".", src))


def _block_heading(token):
    level = token.level
    content = _render_inner(token)
    tag = f"h{level}"
    inner = f'<{tag} class="wp-block-heading">{content}</{tag}>'
    return _wrap_block("heading", {"level": level}, inner)


def _block_paragraph(token, image_map, base_dir):
    # 段落内仅图片时，每张图一个 wp:image 块
    children = getattr(token, "children", None) or []
    if children and all(type(c).__name__.lower() == "image" for c in children):
        blocks = []
        for c in children:
            blocks.append(_block_image(c, image_map, base_dir))
        return "\n\n".join(blocks)
    content = _render_inner(token)
    return _wrap_block("paragraph", {}, f"<p>{content}</p>")


def _block_image(token, image_map, base_dir):
    """Image 块（独立或段落内仅图）。"""
    src = token.src
    alt = _render_inner(token).strip() if token.children else ""
    alt = alt.replace("&quot;", '"')  # _render_inner 会转义，alt 属性需要再还原引号或保持
    alt_escaped = _escape_html(alt) if alt else ""
    resolved = _resolve_image_src(src, base_dir)
    wp_media = image_map.get(resolved) if resolved else None
    if not wp_media and src:
        wp_media = image_map.get(src) or image_map.get(os.path.normpath(src))
    if wp_media:
        mid, url = wp_media[0], wp_media[1]
        attrs = {"sizeSlug": "large"}
        if mid:
            attrs["id"] = int(mid)
        img_class = f' class="wp-image-{mid}"' if mid else ""
        inner = (
            f'<figure class="wp-block-image size-large">\n'
            f'  <img src="{_escape_html(url)}" alt="{alt_escaped}"{img_class}/>\n'
            f'</figure>'
        )
        return _wrap_block("image", attrs, inner)
    inner = (
        f'<figure class="wp-block-image">\n'
        f'  <img src="{_escape_html(src)}" alt="{alt_escaped}"/>\n'
        f'</figure>'
    )
    return _wrap_block("image", {}, inner)


def _block_list(token):
    # List: token.children 是 ListItem，ListItem 有 children（块级）
    ordered = getattr(token, "start", None) is not None
    tag = "ol" if ordered else "ul"
    attrs = {"ordered": ordered}
    items = []
    for item in token.children:
        part = []
        for ch in getattr(item, "children", []) or []:
            ch_name = type(ch).__name__.lower()
            if ch_name == "paragraph":
                # 只提取段落内的内联内容
                part.append(_render_inner(ch))
        items.append("<li>{}</li>".format(" ".join(part).strip()))
    inner = "\n".join(items)
    return _wrap_block("list", attrs, f"<{tag} class=\"wp-block-list\">\n{inner}\n</{tag}>")


def _block_code(token):
    raw = ""
    if hasattr(token, "content"):
        raw = token.content
    elif getattr(token, "children", None) and len(token.children) == 1:
        raw = getattr(token.children[0], "content", "") or ""
    code_escaped = _escape_html(raw)
    inner = f"<pre class=\"wp-block-code\"><code>{code_escaped}</code></pre>"
    return _wrap_block("code", {}, inner)


def _block_quote(token):
    parts = []
    for ch in getattr(token, "children", []) or []:
        name = type(ch).__name__.lower()
        if name == "paragraph":
            # 引用内只放 p 标签包裹的内联内容
            parts.append(f"<p>{_render_inner(ch)}</p>")
    inner = "\n".join(parts).strip()
    return _wrap_block("quote", {}, f'<blockquote class="wp-block-quote">\n{inner}\n</blockquote>')


def _block_separator():
    return _wrap_block("separator", {}, '<hr class="wp-block-separator has-alpha-channel-opacity"/>')


def _block_table(token):
    rows = []
    # Table: token.header + token.children (body rows)
    header = getattr(token, "header", None)
    if header:
        cells = []
        for cell in getattr(header, "children", []) or []:
            cells.append(f"<th>{_render_inner(cell)}</th>")
        rows.append("<tr>\n" + "\n".join(cells) + "\n</tr>")
    for row in getattr(token, "children", []) or []:
        cells = []
        tag = "td"
        for cell in getattr(row, "children", []) or []:
            cells.append(f"<{tag}>{_render_inner(cell)}</{tag}>")
        rows.append("<tr>\n" + "\n".join(cells) + "\n</tr>")
    table_inner = "\n".join(rows)
    inner = f'<figure class="wp-block-table"><table>\n{table_inner}\n</table></figure>'
    return _wrap_block("table", {}, inner)


def _render_block(token, image_map, base_dir):
    """将单个块级 token 转为 Gutenberg 块字符串。"""
    cls = type(token).__name__.lower()
    if cls in ("heading", "setextheading"):
        return _block_heading(token)
    if cls == "paragraph":
        return _block_paragraph(token, image_map, base_dir)
    if cls == "list":
        return _block_list(token)
    if cls == "image":
        return _block_image(token, image_map, base_dir)
    if cls in ("codefence", "blockcode"):
        return _block_code(token)
    if cls == "quote":
        return _block_quote(token)
    if cls == "thematicbreak":
        return _block_separator()
    if cls == "table":
        return _block_table(token)
    # 未识别的块：用 wp:html 包一层（可选：用默认 HTML 渲染）
    try:
        from mistletoe import HTMLRenderer
        with HTMLRenderer() as r:
            raw = r.render(token)
        return _wrap_block("html", {}, raw)
    except Exception:
        return _wrap_block("html", {}, "")


def transform_ast_to_gutenberg(doc, image_map=None, base_dir="", document_title=None):
    """
    遍历 AST 根的子节点，逐个转为 Gutenberg 块。
    image_map: 本地路径（绝对或解析后） -> (media_id, url)
    base_dir: 解析相对图片路径的基准目录。
    document_title: 文章标题；若首块为段落且其纯文本与标题一致，则输出为 wp:heading level 1（避免首行无 # 时全成段落）。
    """
    image_map = image_map or {}
    blocks = []
    for i, node in enumerate(doc.children):
        if (
            i == 0
            and document_title
            and type(node).__name__.lower() == "paragraph"
        ):
            plain = _get_plain_text(node).strip()
            title_norm = (document_title or "").strip()
            if plain and title_norm and plain == title_norm:
                # 首段与标题一致：作为 H1 输出
                class _FakeHeading:
                    level = 1
                    children = getattr(node, "children", None) or []
                block = _block_heading(_FakeHeading())
                blocks.append(block)
                continue
        block = _render_block(node, image_map, base_dir)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def md_to_gutenberg(content, image_map=None, base_dir="", document_title=None):
    """
    先解析 Markdown 为 AST，再转为 Gutenberg HTML。
    content: 纯 Markdown 正文（不含 frontmatter）。
    document_title: 可选，与 transform_ast_to_gutenberg 一致，用于首段当标题时输出为 H1。
    """
    doc = Document(content)
    return transform_ast_to_gutenberg(
        doc,
        image_map=image_map,
        base_dir=base_dir,
        document_title=document_title,
    )
