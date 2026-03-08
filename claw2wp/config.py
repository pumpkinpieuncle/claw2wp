import os
import json
from pathlib import Path

CONFIG_DIR = os.path.expanduser("~/.claw2wp")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def init_config():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "site_id_1": {
                "url": "https://example.com",
                "user": "admin",
                "pass": "xxxx xxxx xxxx xxxx"
            }
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"配置文件已初始化在 {CONFIG_FILE}")
        print("请编辑该文件以填入您的 WordPress 凭证 (推荐使用 Application Passwords)。")
    else:
        print(f"配置文件已经存在于 {CONFIG_FILE}，如需重置请手动删除或修改它。")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"配置文件未找到: {CONFIG_FILE}。请先运行 'claw2wp init'。")
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def get_site_config(site_id):
    config = load_config()
    if site_id not in config:
        raise ValueError(f"Site ID '{site_id}' 不在配置中找到。请检查您的 {CONFIG_FILE}。")
    return config[site_id]

def list_sites():
    """返回所有站点摘要（不含密码），用于 config 命令。"""
    try:
        config = load_config()
        return {sid: {"url": c.get("url", ""), "user": c.get("user", "")} for sid, c in config.items()}
    except FileNotFoundError:
        return {}
