'''
new Env('蓝光演唱会签到');
cron: 40 7 * * *
'''
import os
import requests
import re
import logging
import random
import time
import urllib3
import ssl
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import notify  # 导入通知模块

# 关闭 InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BluRayConcertSigner:
    def __init__(self):
        self.SIGN_IN_URL = "https://www.lgych.com/wp-content/themes/modown/action/user.php"
        self.USER_PAGE_URL = "https://www.lgych.com/user"
        self.SITE_URL = "https://www.lgych.com"
        # 添加首页URL用于触发访问奖励
        self.HOME_URL = "https://www.lgych.com"
        
        self.headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://www.lgych.com/user"
        }
        self.cookies = self._get_cookies_from_env()
        self.session = self._create_session()

    def _get_cookies_from_env(self):
        """从环境变量获取蓝光演唱会 Cookie"""
        cookie_str = os.getenv("LGYCH_COOKIE")
        if not cookie_str:
            logger.error("❌ 未找到环境变量 LGYCH_COOKIE，请配置后重试")
            raise ValueError("环境变量 LGYCH_COOKIE 未设置")

        cookie_dict = {}
        try:
            for item in cookie_str.split(';'):
                if '=' in item:
                    name, value = item.strip().split('=', 1)
                    cookie_dict[name] = value
            return cookie_dict
        except Exception as e:
            logger.error(f"❌ 解析 Cookie 失败: {e}")
            raise

    def _create_session(self):
        """创建带重试机制的 requests 会话并设置 SSL 配置"""
        session = requests.Session()

        # 创建 SSLContext
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT')

        # 配置 urllib3 连接池
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=5,
                backoff_factor=2,
                status_forcelist=[408, 429, 500, 502, 503, 504]
            )
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # 通过 urllib3 设置 SSL 配置
        session.verify = False  # 关闭证书验证

        return session

    def visit_page_for_points(self, url, page_name="页面"):
        """访问指定页面以获取积分奖励"""
        try:
            logger.info(f"🌐 正在访问{page_name}: {url}")
            
            # 使用GET请求访问页面，模拟正常浏览行为
            headers_copy = self.headers.copy()
            headers_copy.update({
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "accept-encoding": "gzip, deflate, br",
                "upgrade-insecure-requests": "1",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "same-origin"
            })
            
            response = self.session.get(
                url,
                headers=headers_copy,
                cookies=self.cookies,
                timeout=15,
                verify=False,
                allow_redirects=True
            )
            
            response.raise_for_status()
            logger.info(f"✅ 成功访问{page_name}，状态码: {response.status_code}")
            
            # 添加随机延迟，模拟真实用户行为
            time.sleep(random.uniform(2, 4))
            return True
            
        except Exception as e:
            logger.error(f"❌ 访问{page_name}失败: {e}")
            return False

    def get_user_info(self):
        """抓取用户当前积分和金币信息"""
        try:
            # 先访问用户页面获取积分奖励
            self.visit_page_for_points(self.USER_PAGE_URL, "用户页面")
            
            response = self.session.get(
                self.USER_PAGE_URL,
                headers=self.headers,
                cookies=self.cookies,
                timeout=15,
                verify=False
            )
            response.raise_for_status()
            
            # 打印HTML内容用于调试（可选，生产环境建议注释掉）
            # logger.debug(f"用户页面HTML片段: {response.text[:500]}...")
            
            soup = BeautifulSoup(response.text, 'html.parser')

            # 多种方法尝试提取积分信息
            points = "N/A"
            
            # 方法1: 使用正则表达式在整个文本中搜索
            points_match = re.search(r"可用积分[：:]\s*(\d+)", response.text)
            if points_match:
                points = points_match.group(1)
            else:
                # 方法2: 查找包含积分信息的元素
                points_elements = soup.find_all(string=re.compile(r"可用积分|积分"))
                for element in points_elements:
                    match = re.search(r"(\d+)", str(element))
                    if match:
                        points = match.group(1)
                        break
                
                # 方法3: 查找可能包含积分的数字元素
                if points == "N/A":
                    # 查找所有可能的积分显示位置
                    score_elements = soup.find_all(['span', 'div', 'p', 'strong', 'b'], 
                                                 text=re.compile(r'\d+'))
                    logger.info(f"找到的数字元素: {[elem.text.strip() for elem in score_elements[:5]]}")

            # 提取金币信息
            gold = "N/A"
            gold_element = soup.find('b', class_='color')
            if gold_element:
                gold = gold_element.text.strip()
            else:
                # 尝试其他方式查找金币
                gold_match = re.search(r'(\d+\.\d{2})\s*金币', response.text)
                if gold_match:
                    gold = gold_match.group(1)

            logger.info(f"📊 解析结果 - 积分: {points}, 金币: {gold}")
            return points, gold

        except Exception as e:
            logger.error(f"❌ 获取用户信息失败: {e}")
            return "N/A", "N/A"

    def trigger_daily_visit_reward(self):
        """触发每日访问奖励"""
        logger.info("🎯 开始触发每日访问奖励...")
        
        # 访问多个页面以确保触发积分奖励
        pages_to_visit = [
            (self.HOME_URL, "首页"),
            (self.USER_PAGE_URL, "用户页面"),
            (f"{self.SITE_URL}/about", "关于页面"),
        ]
        
        visited_count = 0
        for url, name in pages_to_visit:
            if self.visit_page_for_points(url, name):
                visited_count += 1
            time.sleep(random.uniform(1, 3))  # 随机延迟
        
        logger.info(f"✅ 完成页面访问，成功访问 {visited_count}/{len(pages_to_visit)} 个页面")
        return visited_count > 0

    def _format_output(self, title, status, details, is_success=True):
        """格式化输出内容"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        border = "⭐" * 15
        emoji = "✅" if is_success else "ℹ️" if status == "已签到" else "⚠️"
        
        content = (
            f"\n{border}\n"
            f"{emoji} {title}\n"
            f"📅 时间: {current_time}\n"
            f"🔖 状态: {status}\n"
            f"------------------------\n"
        )
        
        for detail in details:
            content += f"{detail}\n"
            
        content += (
            f"------------------------\n"
            f"🌐 官网: {self.SITE_URL}\n"
            f"{border}\n"
        )
        return content

    def sign_in(self):
        """执行蓝光演唱会签到流程"""
        try:
            # 添加随机延迟
            time.sleep(round(random.uniform(1, 3), 2))
            
            # 先触发每日访问奖励
            logger.info("🎯 步骤1: 触发每日访问奖励")
            self.trigger_daily_visit_reward()
            
            # 获取签到前的状态
            logger.info("📊 步骤2: 获取签到前状态")
            old_points, old_gold = self.get_user_info()
            logger.info(f"🔄 签到前状态 - 积分: {old_points}, 金币: {old_gold}")

            # 执行签到
            logger.info("✍️ 步骤3: 执行签到操作")
            data = {"action": "user.checkin"}
            response = self.session.post(
                self.SIGN_IN_URL,
                headers=self.headers,
                cookies=self.cookies,
                data=data,
                timeout=15,
                verify=False
            )

            response.raise_for_status()

            try:
                result_json = response.json()
                result_str = str(result_json)
                logger.info(f"📝 签到响应(JSON): {result_json}")
            except Exception:
                result_str = response.text.encode().decode('unicode_escape')
                logger.info(f"📝 签到响应(文本): {result_str}")

            # 签到后再次访问页面并获取状态
            logger.info("📊 步骤4: 获取签到后状态")
            time.sleep(2)  # 等待服务器处理
            self.visit_page_for_points(self.USER_PAGE_URL, "用户页面（签到后）")
            new_points, new_gold = self.get_user_info()
            
            # 计算积分变化
            point_diff = "N/A"
            if old_points.isdigit() and new_points.isdigit():
                point_diff = int(new_points) - int(old_points)
                if point_diff > 0:
                    point_diff = f"+{point_diff}"

            logger.info(f"📈 签到后状态 - 积分: {new_points}, 金币: {new_gold}, 变化: {point_diff}")

            # 判断签到结果
            if "金币" in result_str or "成功" in result_str:
                details = [
                    f"🪙 当前积分: {new_points}",
                    f"📈 积分变化: {point_diff}",
                    f"💰 当前金币: {new_gold}",
                    f"🎁 每日访问奖励已触发"
                ]
                content = self._format_output(
                    "蓝光演唱会签到成功", 
                    "签到成功", 
                    details
                )
                logger.info(content)
                notify.send("蓝光演唱会 签到成功 ✅", content)
                return True

            elif "已经" in result_str or "重复" in result_str:
                details = [
                    f"🪙 当前积分: {new_points}",
                    f"📈 积分变化: {point_diff}",
                    f"💰 当前金币: {new_gold}",
                    f"ℹ️ 今日已签到，但已触发访问奖励"
                ]
                content = self._format_output(
                    "蓝光演唱会签到状态", 
                    "已签到", 
                    details,
                    is_success=False
                )
                logger.info(content)
                notify.send("蓝光演唱会 今日已签到 ℹ️", content)
                return False

            else:
                details = [
                    f"❓ 返回结果: {result_str}",
                    f"🪙 当前积分: {new_points}",
                    f"📈 积分变化: {point_diff}",
                    f"💰 当前金币: {new_gold}"
                ]
                content = self._format_output(
                    "蓝光演唱会签到异常", 
                    "未知结果", 
                    details,
                    is_success=False
                )
                logger.warning(content)
                notify.send("蓝光演唱会 签到异常 ⚠️", content)
                return False

        except requests.exceptions.RequestException as e:
            details = [
                f"❌ 错误信息: {str(e)}",
                f"🌐 请检查网络连接或网站状态"
            ]
            content = self._format_output(
                "蓝光演唱会签到失败", 
                "网络请求失败", 
                details,
                is_success=False
            )
            logger.error(content)
            notify.send("蓝光演唱会 网络异常 ❌", content)
            return False

        except Exception as e:
            details = [
                f"❌ 错误信息: {str(e)}",
                f"🛠️ 请检查程序配置或联系开发者"
            ]
            content = self._format_output(
                "蓝光演唱会签到失败", 
                "程序错误", 
                details,
                is_success=False
            )
            logger.error(content)
            notify.send("蓝光演唱会 程序错误 ❌", content)
            return False

if __name__ == "__main__":
    try:
        signer = BluRayConcertSigner()
        signer.sign_in()
    except Exception as e:
        logger.error(f"❌ 程序初始化失败: {e}")
        notify.send("蓝光演唱会 启动失败 ❌", str(e))