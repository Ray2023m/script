# 需要提前执行：
# pip install requests bs4

import requests
from bs4 import BeautifulSoup
import re

# 配置部分 ============================================
url = 'https://www.1000qm.vip/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1'
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Cookie": "flo1_2132_saltkey=Zr5c594c; flo1_2132_auth=803f2h3%2FU08Pv%2F0KgqVh604Vt%2Bg3bL4Y3IxuddE2BxNQtXgBmi4Jabm5ZvHXOJUZ4L58JP7IWT102F%2F0vEhWQcV2qQ",  # 替换成你的真实Cookie
    "Referer": "https://www.1000qm.vip/plugin.php?id=dsu_paulsign:sign"
}
# ====================================================

def get_formhash():
    """获取最新的formhash值"""
    formhash_url = "https://www.1000qm.vip/plugin.php?id=dsu_paulsign:sign"
    r = requests.get(formhash_url, headers=headers)
    match = re.search(r'formhash" value="([a-f0-9]+)"', r.text)
    return match.group(1) if match else None

def qiandao():
    # 获取formhash
    formhash = get_formhash()
    if not formhash:
        return "获取formhash失败，请检查Cookie是否有效"
    
    # 签到数据
    form_data = {
        "formhash": formhash,
        "qdxq": "kx",  # 心情：开心
        "todaysay": "每日签到，支持论坛发展！",  # 固定签到话语
        "fastreply": "1"
    }
    
    # 发送签到请求
    r = requests.post(url, data=form_data, headers=headers)
    
    # 解析响应
    if "签到成功" in r.text:
        # 尝试提取详细信息
        match = re.search(r'<div class="c">([\s\S]+?)</div>', r.text)
        return match.group(1).strip() if match else "签到成功(未获取到详细信息)"
    else:
        return f"签到失败，服务器返回: {r.text}"

# 执行签到
result = qiandao()
print("签到结果:", result)