import os
import re
import sys
from pathlib import Path
from datetime import datetime


def normalize_path_for_cli(path_str):
    """
    规范化来自命令行或环境的路径，解决 Windows 下非 ASCII（如中文）路径乱码问题。
    PowerShell 等可能用 GBK/CP936 传参，而 Python 可能按错误编码解析，此处尝试纠正。
    返回可用于 pathlib/os 的路径字符串（已 resolve 为绝对路径若可能）。
    """
    if not path_str or not isinstance(path_str, str):
        return path_str
    path_str = path_str.strip()
    if not path_str:
        return path_str
    # 先尝试原样解析
    try:
        p = Path(path_str)
        if p.exists():
            return str(p.resolve())
    except (OSError, ValueError):
        pass
    # 仅 Windows 做编码纠正尝试
    if sys.platform != "win32":
        return str(Path(path_str).resolve())
    # 常见情况：控制台用 GBK 传参，但被当成 Latin-1/cp1252 解析，导致乱码
    # 用“错误解码”反推原始字节，再按控制台编码重解码
    for console_encoding in ("gbk", "cp936", "utf-8"):
        try:
            raw = path_str.encode("cp1252", errors="replace")
            fixed = raw.decode(console_encoding, errors="replace")
            if fixed and fixed != path_str:
                q = Path(fixed)
                if q.exists():
                    return str(q.resolve())
        except (UnicodeEncodeError, UnicodeDecodeError, OSError, ValueError):
            continue
    try:
        raw = path_str.encode("latin1")
        fixed = raw.decode("utf-8", errors="replace")
        if fixed and fixed != path_str:
            q = Path(fixed)
            if q.exists():
                return str(q.resolve())
    except (UnicodeEncodeError, UnicodeDecodeError, OSError, ValueError):
        pass
    # 无法纠正则返回解析后的原串
    try:
        return str(Path(path_str).resolve())
    except (OSError, ValueError):
        return path_str


def slugify(text):
    """将标题等转为 URL 友好 slug（与 WP 自动生成规则近似）。"""
    if not text:
        return ""
    text = re.sub(r'[^\w\s\-]', '', str(text))
    text = re.sub(r'[-\s]+', '-', text).strip('-').lower()
    return text or ""

def date_to_iso8601(value):
    """将 frontmatter 的 date（字符串或 date 对象）转为 WP 所需的 ISO8601 字符串。"""
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    s = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None

def find_featured_image(filepath):
    """
    寻找目录下遵循特定命名规则的特色图片:
    1. {文件同名}-1.* 
    2. {文件同名}-feature.*
    """
    filepath = Path(filepath)
    base_name = filepath.stem
    dir_name = filepath.parent
    
    # 优先匹配特定后缀
    patterns = [
        f"{base_name}-1.*",
        f"{base_name}-feature.*",
    ]
    
    for pattern in patterns:
        for file in dir_name.glob(pattern):
            if file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
                return str(file.resolve())
            
    return None
