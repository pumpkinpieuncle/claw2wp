import os
import csv
from pathlib import Path
from claw2wp.parser import parse_file
from claw2wp.wp_api import WPApi

class Exporter:
    def __init__(self, api_client: WPApi):
        self.api = api_client
        self.uploaded_cache = {}

    def _upload_image_cached(self, filepath):
        if filepath in self.uploaded_cache:
            return self.uploaded_cache[filepath]
        if not os.path.exists(filepath):
            return None, None
            
        print(f"为 CSV 预上传图片: {filepath} ...")
        media_id, cloud_url = self.api.upload_media(filepath)
        if cloud_url:
            self.uploaded_cache[filepath] = cloud_url
            return media_id, cloud_url
        return None, None

    def export_directory_to_csv(self, dirpath):
        dirpath = Path(dirpath)
        if not dirpath.is_dir():
            print(f"错误: {dirpath} 不是一个有效的目录")
            return
            
        print(f"[CSV 模式] 开始扫描并预上传图片: {dirpath}")
        
        csv_file_path = dirpath / "wc_products_import.csv"
        
        headers = [
            "Type", "SKU", "Name", "Published", "Is featured?", "Visibility in catalog",
            "Short description", "Description", "Date sale price starts", "Date sale price ends",
            "Tax status", "Tax class", "In stock?", "Stock", "Low stock amount",
            "Backorders allowed?", "Sold individually?", "Weight (kg)", "Length (cm)",
            "Width (cm)", "Height (cm)", "Allow customer reviews?", "Purchase note",
            "Sale price", "Regular price", "Categories", "Tags", "Shipping class",
            "Images"
        ]
        
        rows = []
        
        for file in dirpath.rglob("*"):
            if file.is_file() and file.suffix.lower() in ['.md', '.docx']:
                print(f"正在处理导出: {file.name}")
                try:
                    data = parse_file(str(file))
                    
                    # 1. Upload Featured
                    featured_url = ""
                    if data['featured_image']:
                        _, featured_url = self._upload_image_cached(data['featured_image'])
                        
                    # 2. Upload Gallery
                    gallery_urls = []
                    for img in data['gallery_images']:
                        _, g_url = self._upload_image_cached(img)
                        if g_url: gallery_urls.append(g_url)
                        
                    # All cloud URLs for this product
                    all_image_urls = []
                    if featured_url:
                        all_image_urls.append(featured_url)
                    all_image_urls.extend(gallery_urls)
                    
                    images_str = ", ".join(all_image_urls)
                    
                    meta = data.get('meta', {})
                    
                    row = {
                        "Type": "simple",
                        "SKU": meta.get('sku', ''),
                        "Name": data.get('title', ''),
                        "Published": 1,
                        "Is featured?": 0,
                        "Visibility in catalog": "visible",
                        "Short description": meta.get('short_description', ''),
                        "Description": str(data.get('soup', '')),
                        "Date sale price starts": "",
                        "Date sale price ends": "",
                        "Tax status": "taxable",
                        "Tax class": "",
                        "In stock?": 1,
                        "Stock": "",
                        "Low stock amount": "",
                        "Backorders allowed?": 0,
                        "Sold individually?": 0,
                        "Weight (kg)": meta.get('weight', ''),
                        "Length (cm)": meta.get('length', ''),
                        "Width (cm)": meta.get('width', ''),
                        "Height (cm)": meta.get('height', ''),
                        "Allow customer reviews?": 1,
                        "Purchase note": "",
                        "Sale price": meta.get('sale_price', ''),
                        "Regular price": meta.get('regular_price', ''),
                        "Categories": meta.get('categories', ''),
                        "Tags": meta.get('tags', ''),
                        "Shipping class": "",
                        "Images": images_str
                    }
                    
                    # If categories is a list, join it
                    if isinstance(row["Categories"], list):
                        row["Categories"] = ", ".join(row["Categories"])
                    if isinstance(row["Tags"], list):
                        row["Tags"] = ", ".join(row["Tags"])
                        
                    rows.append(row)
                    
                except Exception as e:
                    print(f"处理文件 {file} 发生异常: {e}")
                    
        if rows:
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            print(f"🎉 成功导出 CSV 到 {csv_file_path}")
        else:
            print("❗ 没有任何可导出的数据。")
