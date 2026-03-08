import os
import re
import tempfile
import uuid
import markdown
import frontmatter
from bs4 import BeautifulSoup
from pathlib import Path
from claw2wp.utils import find_featured_image

def _docx_to_markdown_file(filepath):
    """
    将 docx 转为 Markdown（规范：源头为 docx 时一律先转 md，后续只从 md 解析并发布）。
    保留标题层级、正文结构，图片提取到临时目录。返回 (临时 .md 路径, 临时目录)，
    后续由 parse_md 统一解析，与直接使用 .md 文件走同一流程。
    """
    import mammoth
    import html2text

    output_dir = tempfile.mkdtemp(prefix="claw2wp_")

    def convert_image(image):
        with image.open() as image_stream:
            image_bytes = image_stream.read()
        ext = image.content_type.split('/')[-1] if '/' in image.content_type else 'jpeg'
        if ext == 'jpeg':
            ext = 'jpg'
        filename = f"{uuid.uuid4().hex}.{ext}"
        image_path = os.path.join(output_dir, filename)
        with open(image_path, "wb") as f:
            f.write(image_bytes)
        return {"src": image_path}

    with open(filepath, "rb") as docx_file:
        result = mammoth.convert_to_html(
            docx_file, convert_image=mammoth.images.img_element(convert_image)
        )
    html_content = result.value

    # 从 HTML 中取第一个 h1 作为标题，否则用文件名
    soup_title = BeautifulSoup(html_content, "html.parser")
    first_h1 = soup_title.find("h1")
    title = first_h1.get_text(strip=True) if first_h1 else Path(filepath).stem

    # HTML → Markdown，保留标题层级、列表、表格、图片等
    h2t = html2text.HTML2Text()
    h2t.ignore_links = False
    h2t.ignore_images = False
    h2t.body_width = 0
    md_body = h2t.handle(html_content).strip()

    # 用 frontmatter 安全写入标题与正文，与现有 .md 流程一致
    post = frontmatter.Post(md_body, **{"title": title})
    temp_md_path = os.path.join(output_dir, "content.md")
    with open(temp_md_path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))

    return temp_md_path, output_dir

def parse_md(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        post = frontmatter.load(f)
    meta = post.metadata

    # default title from filename if not in frontmatter
    title = meta.get('title', Path(filepath).stem)

    # 保留 HTML 用于图片发现与兼容；同时解析 AST 用于 Gutenberg 生成
    body = (post.content or "").replace("\r\n", "\n").replace("\r", "\n")
    if body.startswith("\ufeff"):
        body = body.lstrip("\ufeff")
    html_content = markdown.markdown(body, extensions=['tables', 'fenced_code'])
    ast = None
    md_content = body
    try:
        from mistletoe import Document
        ast = Document(body)
    except Exception as e:
        import warnings
        warnings.warn(
            f"mistletoe 解析失败，将尝试使用 MD 源码或 HTML 回退路径: {e}",
            UserWarning,
            stacklevel=2,
        )
        ast = None
        # 保留 md_content = body，供 publisher 优先尝试 md_to_gutenberg

    return {
        'title': title,
        'content': html_content,
        'meta': meta,
        'format': 'md',
        'ast': ast,
        'md_content': md_content,
        'type': meta.get('type', 'product'), # Default to product if not specified
    }

def process_file_images(filepath, html_content, meta=None):
    """
    从 HTML 提取本地图片引用并确定特色图。
    若 meta 中有 featured_image（相对路径），优先使用；否则按命名规则或正文第一张图。
    返回 (featured_image_path, [gallery_image_paths], soup)。
    """
    soup = BeautifulSoup(html_content, "html.parser")
    base_dir = Path(filepath).parent
    local_images = []

    for img in soup.find_all("img"):
        src = img.get("src")
        if not src or src.startswith("http://") or src.startswith("https://") or src.startswith("data:"):
            continue
        img_path = str((base_dir / src).resolve()) if not os.path.isabs(src) else src
        if os.path.exists(img_path):
            local_images.append(img_path)

    # 特色图：优先 frontmatter 的 featured_image
    featured_img = None
    if meta and meta.get("featured_image"):
        raw = meta["featured_image"]
        p = (base_dir / raw).resolve() if not os.path.isabs(raw) else Path(raw)
        if p.exists():
            featured_img = str(p)
    if not featured_img:
        featured_img = find_featured_image(filepath)
    gallery_imgs = []
    
    if featured_img:
        # All other local images will be gallery
        gallery_imgs = [img for img in local_images if Path(img).resolve() != Path(featured_img).resolve()]
    else:
        # If no explicit featured image, use the first image from content
        if local_images:
            featured_img = local_images[0]
            gallery_imgs = local_images[1:]
            
    # Removing duplicates in gallery using ordered dict approach
    gallery_imgs = list(dict.fromkeys(gallery_imgs))
    
    return featured_img, gallery_imgs, soup

def parse_file(filepath):
    """
    统一入口：仅支持 .md / .docx。
    设计原则：若源头为 docx，先转为 md，再只从 md 解析（ast/md_content），
    发布时与 .md 完全一致地走「Markdown → Gutenberg」路径，不绕经 HTML。
    """
    filepath = str(Path(filepath).resolve())
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")
        
    ext = filepath.lower().split('.')[-1]
    
    if ext == 'docx':
        # 先转 md，再只从 md 解析，与 .md 文件同一流程
        temp_md_path, temp_dir = _docx_to_markdown_file(filepath)
        data = parse_md(temp_md_path)
        # 图片在临时目录，用 temp_md_path 作为基准解析；供发布时用同一目录解析正文中的 img src
        featured_img, gallery_imgs, soup = process_file_images(
            temp_md_path, data['content'], meta=data.get('meta')
        )
        data['content_base_dir'] = temp_dir
    elif ext == 'md':
        data = parse_md(filepath)
        featured_img, gallery_imgs, soup = process_file_images(
            filepath, data['content'], meta=data.get('meta')
        )
        data['content_base_dir'] = str(Path(filepath).parent)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")
    
    data['featured_image'] = featured_img
    data['gallery_images'] = gallery_imgs
    data['soup'] = soup
    
    return data
