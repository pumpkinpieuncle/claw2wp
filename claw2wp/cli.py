import argparse
import sys
from claw2wp.config import init_config, get_site_config, list_sites
from claw2wp.wp_api import WPApi
from claw2wp.publisher import Publisher
from claw2wp.exporter import Exporter
from claw2wp.parser import parse_file
from claw2wp.utils import slugify, normalize_path_for_cli
from pathlib import Path


def _ensure_console_utf8():
    """Windows 下尽量让控制台输出使用 UTF-8，避免打印非 ASCII 路径时报错。"""
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8")
        except (OSError, AttributeError):
            pass


def main():
    _ensure_console_utf8()
    parser = argparse.ArgumentParser(
        prog="claw2wp",
        description="将 Markdown (.md) 或 Word (.docx) 发布到 WordPress 文章或 WooCommerce 产品，支持 Gutenberg 块、更新/删除、批量发布与 CSV 导出。",
        epilog="""
示例:
  claw2wp init
  claw2wp config
  claw2wp validate -f post.md -s mysite
  claw2wp publish -f post.md -s mysite --post
  claw2wp publish -d ./posts -s mysite --update
  claw2wp export -d ./products -s mysite --csv

详细文档: 见项目 README 与 docs/FEATURES.md
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令（用 <子命令> -h 查看详情）")

    # init
    subparsers.add_parser(
        "init",
        help="初始化配置：在 ~/.claw2wp/config.json 生成示例，需编辑填入 url/user/pass",
        description="首次使用前执行一次。会在用户目录创建 ~/.claw2wp/config.json，需手动编辑填入站点 URL、用户名与 Application Password。",
    )

    subparsers.add_parser(
        "config",
        help="列出已配置站点：显示 site_id、url、user（不显示密码）",
        description="显示 config.json 中所有 site_id 及其 url 和 user，用于确认 -s/--site 可用值。",
    )

    # validate
    parser_val = subparsers.add_parser(
        "validate",
        help="校验文件：解析 frontmatter 与正文，不发布",
        description="校验单个 .md 或 .docx 的 frontmatter 与解析结果；可选 -s 检查 site_id 是否已配置。不访问 WordPress API。",
    )
    parser_val.add_argument("-f", "--file", required=True, metavar="FILE", help="要校验的 .md 或 .docx 文件路径")
    parser_val.add_argument("-s", "--site", metavar="SITE_ID", help="若指定，校验该 site_id 是否存在于 config.json")

    # publish
    parser_pub = subparsers.add_parser(
        "publish",
        help="发布/更新/删除：单文件(-f)或目录(-d)，需指定 -s site_id",
        description="将内容发布到 WordPress。新建时不写 --update/--delete；更新用 --update（按 slug/标题匹配）；删除用 --delete（可配合 --id）。发布类型用 --post（文章）或 --product（产品），不指定时由 frontmatter 或内容推断。",
        epilog="必须且仅能指定 -f/--file 或 -d/--dir 之一。--delete 与 -d 同时使用时不可用 --id。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser_pub.add_argument("-f", "--file", metavar="FILE", help="单个要发布的 .md 或 .docx 文件")
    parser_pub.add_argument("-d", "--dir", metavar="DIR", help="要批量发布的目录（递归处理其中 .md/.docx）")
    parser_pub.add_argument("-s", "--site", required=True, metavar="SITE_ID", help="config.json 中的站点 ID（如 mysite）")
    parser_pub.add_argument("--update", action="store_true", help="更新模式：按 slug 或标题匹配已有文章/产品，找到则更新，否则新建")
    parser_pub.add_argument("--delete", action="store_true", help="删除模式：按 slug 或 --id 删除对应文章/产品")
    parser_pub.add_argument("--id", type=int, metavar="ID", help="与 --update/--delete 配合，直接指定 WordPress 文章/产品 ID")
    parser_pub.add_argument("--draft", action="store_true", help="强制以草稿发布，覆盖 frontmatter 中的 status")
    parser_pub.add_argument("--dry-run", action="store_true", help="仅解析并打印将要发布的内容，不请求 API、不实际上传")
    parser_pub.add_argument("--post", action="store_true", dest="as_post", help="明确按「文章」(post) 发布")
    parser_pub.add_argument("--product", action="store_true", help="明确按「产品」(WooCommerce product) 发布")

    # export
    parser_exp = subparsers.add_parser(
        "export",
        help="导出目录内产品为 WooCommerce 可导入的 CSV",
        description="扫描目录下 .md/.docx，解析为产品数据，上传图片到站点后生成 WooCommerce 标准 CSV，供 WP 后台「产品→导入」使用。",
    )
    parser_exp.add_argument("-d", "--dir", required=True, metavar="DIR", help="包含产品 .md/.docx 的目录路径")
    parser_exp.add_argument("-s", "--site", required=True, metavar="SITE_ID", help="config.json 中的站点 ID，用于上传图片与 API")
    parser_exp.add_argument("--csv", action="store_true", help="启用 CSV 导出（当前 export 仅支持此模式，必须带上）")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_config()
        sys.exit(0)
    
    elif args.command == "config":
        sites = list_sites()
        if not sites:
            print("未找到配置。请先运行: claw2wp init")
            sys.exit(1)
        print("已配置站点:")
        for sid, info in sites.items():
            print(f"  {sid}: {info.get('url', '')} (user: {info.get('user', '')})")
        sys.exit(0)
    
    elif args.command == "validate":
        try:
            file_path = normalize_path_for_cli(args.file)
            data = parse_file(file_path)
            slug = data.get("meta", {}).get("slug") or slugify(data.get("title") or Path(file_path).stem)
            print(f"✓ 解析成功: {file_path}")
            print(f"  标题: {data.get('title')}")
            print(f"  slug: {slug}")
            print(f"  特色图: {data.get('featured_image') or '(无)'}")
            if args.site:
                get_site_config(args.site)
                print(f"  站点 '{args.site}': 存在")
        except Exception as e:
            print(f"✗ 校验失败: {e}")
            sys.exit(1)
        sys.exit(0)
        
    elif args.command == "publish":
        if not args.file and not args.dir:
            print("必须指定 -f/--file <文件> 或 -d/--dir <目录>")
            sys.exit(1)
        if args.delete and args.dir and args.id:
            print("--delete 与 -d/--dir 同时使用时不能指定 --id")
            sys.exit(1)

        site_config = get_site_config(args.site)
        api = WPApi(site_config)
        publisher = Publisher(api)

        mode = 'delete' if args.delete else ('update' if args.update else 'create')
        status_override = 'draft' if args.draft else None
        dry_run = getattr(args, 'dry_run', False)
        target_id = getattr(args, 'id', None)
        as_post = getattr(args, 'as_post', False)

        if args.file:
            file_path = normalize_path_for_cli(args.file)
            print(f"模式: 单文件 {mode} -> {file_path}")
            publisher.publish_file(file_path, mode=mode, target_id=target_id, status_override=status_override, dry_run=dry_run, as_post=as_post)
        elif args.dir:
            dir_path = normalize_path_for_cli(args.dir)
            print(f"模式: 目录级批量 {mode} -> {dir_path}")
            publisher.publish_directory(dir_path, mode=mode, status_override=status_override, dry_run=dry_run, as_post=as_post)
            
    elif args.command == "export":
        if not args.csv:
            print("export 命令当前只支持 --csv 标志，比如: claw2wp export -d . -s site_id --csv")
            sys.exit(1)
            
        site_config = get_site_config(args.site)
        api = WPApi(site_config)
        exporter = Exporter(api)
        
        dir_path = normalize_path_for_cli(args.dir)
        print(f"模式: CSV 极速上新预处理 -> {dir_path}")
        exporter.export_directory_to_csv(dir_path)
        
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
