'''
new Env('蓝光演唱会签到');
cron: 40 6 * * *
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
from requests.packages.urllib3.util.retry import Retry
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
        self.headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
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
                total=5,  # 增加重试次数
                backoff_factor=2,  # 增加退避因子，使得每次重试的等待时间逐渐增加
                status_forcelist=[408, 429, 500, 502, 503, 504]  # 重试的 HTTP 状态码
            )
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # 通过 urllib3 设置 SSL 配置
        session.verify = False  # 关闭证书验证

        return session

    def get_user_info(self):
        """抓取用户当前积分和金币信息"""
        try:
            response = self.session.get(
                self.USER_PAGE_URL,
                headers=self.headers,
                cookies=self.cookies,
                timeout=10,
                verify=False  # 关闭证书验证
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 使用 string 代替 text
            points_element = soup.find(string=re.compile(r"可用积分：\d+"))
            points = re.search(r"可用积分：(\d+)", points_element).group(1) if points_element else "N/A"

            gold_element = soup.find('b', class_='color')
            gold = gold_element.text.strip() if gold_element else "N/A"

            return points, gold

        except Exception as e:
            logger.error(f"❌ 获取用户信息失败: {e}")
            return "N/A", "N/A"

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
            time.sleep(round(random.uniform(1, 3), 2))
            old_points, old_gold = self.get_user_info()
            logger.info(f"🔄 签到前状态 - 积分: {old_points}, 金币: {old_gold}")

            data = {"action": "user.checkin"}
            response = self.session.post(
                self.SIGN_IN_URL,
                headers=self.headers,
                cookies=self.cookies,
                data=data,
                timeout=10,
                verify=False  # 关闭证书验证
            )

            try:
                result_json = response.json()
                result_str = str(result_json)
            except Exception:
                result_str = response.text.encode().decode('unicode_escape')

            new_points, new_gold = self.get_user_info()
            point_diff = (
                int(new_points) - int(old_points)
                if old_points.isdigit() and new_points.isdigit()
                else "N/A"
            )

            if "金币" in result_str:
                details = [
                    f"🪙 当前积分: {new_points}",
                    f"📈 积分变化: +{point_diff}",
                    f"💰 当前金币: {new_gold}"
                ]
                content = self._format_output(
                    "蓝光演唱会签到成功", 
                    "签到成功", 
                    details
                )
                logger.info(content)
                notify.send("蓝光演唱会 签到成功 ✅", content)
                return True

            elif "已经" in result_str:
                details = [
                    f"🪙 当前积分: {new_points}",
                    f"💰 当前金币: {new_gold}",
                    f"ℹ️ 今日已签到，无需重复操作"
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
