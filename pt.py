'''
new Env('PT网站喊话')
cron: 12 7 * * *

使用方法：
青龙面板环境变量中添加：QWPT_COOKIES,ZMPT_COOKIES
原脚本来源于：https://github.com/huoyart/PT-shouting,感谢原作者。AI修改删减适应个人使用。
'''
import requests
import os
import datetime
import time
from lxml import etree
from urllib.parse import urljoin
from notify import send

class BasePTSite:
    def __init__(self, site_info: dict):
        self.site_info = site_info
        self.site_url = site_info["url"]
        self.site_name = site_info["name"]
        self.cookies = site_info["cookies"]
        self.headers = site_info["headers"]
        self._last_message_result = None
        
    def send_message(self, text: str) -> tuple[bool, str]:
        """发送喊话消息"""
        try:
            params = {
                "shbox_text": text,
                "shout": "发送" if "zmpt" in self.site_url else "我喊",
                "sent": "yes",
                "type": "shoutbox",
            }
            
            response = requests.get(
                self.site_url, 
                headers=self.headers,
                cookies=self.cookies,
                params=params
            )
            
            if response.status_code >= 300:
                return False, f"请求失败: {response.status_code}"
                
            # 解析响应
            feedback = self.parse_response(response)
            return True, feedback
            
        except Exception as e:
            return False, f"发送异常: {str(e)}"
            
    def parse_response(self, response) -> str:
        """解析响应内容"""
        try:
            html = etree.HTML(response.text)
            messages = html.xpath("//ul[1]/li/text()")
            return " ".join(messages) if messages else response.text
        except:
            return response.text

class QingwaPT(BasePTSite):
    def parse_response(self, response) -> str:
        feedback = super().parse_response(response)
        # 青蛙特殊处理
        if feedback == "发了！":
            feedback = "发了！一般为10G！"
        return feedback

class ZmPT(BasePTSite):
    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self._feedback_timeout = site_info.get("feedback_timeout", 5)
        
    def send_message(self, text: str) -> tuple[bool, str]:
        result = super().send_message(text)
        if not result[0]:
            return result
            
        # 等待反馈
        time.sleep(self._feedback_timeout)
        
        # 获取用户数据
        stats = self.get_user_stats()
        if stats:
            return True, f"消息已发送，当前数据：上传={stats.get('upload', '未知')}, " \
                        f"下载={stats.get('download', '未知')}, 电力值={stats.get('bonus', '未知')}"
        return result
        
    def get_user_stats(self) -> dict:
        """获取用户数据统计"""
        try:
            response = requests.get(
                urljoin(self.site_url, "/index.php"),
                headers=self.headers,
                cookies=self.cookies
            )
            
            if response.status_code >= 300:
                return {}
                
            html = etree.HTML(response.text)
            stats = {}
            
            # 提取数据
            upload = html.xpath("//font[contains(text(), '上传量')]/following-sibling::text()[1]")
            download = html.xpath("//font[contains(text(), '下载量')]/following-sibling::text()[1]")
            bonus = html.xpath("//a[@id='self_bonus']/text()[last()]")
            
            stats["upload"] = upload[0].strip() if upload else "未知"
            stats["download"] = download[0].strip() if download else "未知"
            stats["bonus"] = bonus[0].strip() if bonus else "未知"
            
            return stats
        except:
            return {}

def parse_cookies(cookie_str):
    if not cookie_str:
        return {}
    return dict(pair.split("=", 1) for pair in cookie_str.split("; ") if "=" in pair)

# 站点配置
config = {
    "青蛙": {
        "name": "青蛙",
        "enabled": os.getenv("QWPT_ENABLED", "true").lower() == "true",
        "url": "https://www.qingwapt.com/shoutbox.php",
        "cookies": parse_cookies(os.getenv("QWPT_COOKIES")),
        "headers": {
            "Host": "www.qingwapt.com",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.qingwapt.com/index.php",
        },
        "texts": ["蛙总，求上传"],
        "site_class": QingwaPT
    },
    "zmpt": {
        "name": "织梦",
        "enabled": os.getenv("ZMPT_ENABLED", "true").lower() == "true",
        "url": "https://zmpt.cc/shoutbox.php",
        "cookies": parse_cookies(os.getenv("ZMPT_COOKIES")),
        "headers": {
            "Host": "zmpt.cc",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://zmpt.cc/index.php",
        },
        "texts": ["皮总，求电力", "皮总，求上传"],
        "site_class": ZmPT
    }
}

def main():
    print(f"开始执行PT喊话任务 - {datetime.date.today()}")
    
    all_results = []
    for site_name, info in config.items():
        if not info["enabled"]:
            continue
            
        if not info["cookies"]:
            print(f"⚠️ {site_name} 未配置 Cookies，跳过")
            continue
            
        print(f"🔊 正在执行：{site_name}")
        site = info["site_class"](info)
        
        for text in info["texts"]:
            success, feedback = site.send_message(text)
            result = f"{site_name} {'✅' if success else '❌'} {text}"
            if feedback:
                result += f"\n反馈: {feedback}"
            all_results.append(result)
            print(result)
                
    # 发送青龙通知
    if all_results:
        send("PT喊话执行结果", "\n\n".join(all_results))

if __name__ == "__main__":
    main()