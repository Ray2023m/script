'''
new Env('蓝光演唱会签到');
cron: 40 0 * * *
'''
import os
import requests
import re
import logging
import time
import random
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib3

# ✅ 新增：引入 notify 模块（需确保 notify.py 存在且含 send 函数）
try:
    from notify import send
except ImportError:
    def send(title, content):
        print(f"[通知] {title}\n{content}")

# 可选：屏蔽 SSL 警告（仅调试用）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LGYCHSigner:
    def __init__(self):
        self.SIGN_IN_URL = "https://www.lgych.com/wp-content/themes/modown/action/user.php"
        self.USER_PAGE_URL = "https://www.lgych.com/user"
        self.headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.cookies = self._get_cookies_from_env()
        self.session = self._create_session()

    def _get_cookies_from_env(self):
        cookie_env_name = "LGYCH_COOKIE"
        cookie_str = os.getenv(cookie_env_name)
        if not cookie_str:
            msg = f"未找到环境变量 {cookie_env_name}"
            logger.error(msg)
            send("LGYCH 签到失败", msg)
            raise ValueError(msg)

        try:
            cookie_dict = {}
            for item in cookie_str.split(';'):
                if '=' in item:
                    name, value = item.strip().split('=', 1)
                    cookie_dict[name] = value
            return cookie_dict
        except Exception as e:
            msg = f"Cookie解析失败: {str(e)}"
            logger.error(msg)
            send("LGYCH 签到失败", msg)
            raise ValueError(msg)

    def _create_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[408, 429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get_user_info(self):
        try:
            response = self.session.get(
                self.USER_PAGE_URL,
                headers=self.headers,
                cookies=self.cookies,
                timeout=10,
                verify=False
            )
            logger.debug(f"用户页面响应状态码: {response.status_code}")
            if response.status_code != 200:
                return "N/A", "N/A"

            soup = BeautifulSoup(response.text, 'html.parser')

            if soup.title and "登录" in soup.title.string:
                logger.error("Cookie 可能已失效")
                return "N/A", "N/A"

            points_element = soup.find(string=re.compile(r"可用积分：\d+"))
            points = re.search(r"可用积分：(\d+)", points_element).group(1) if points_element else "N/A"

            gold_element = soup.find('b', class_='color')
            gold = gold_element.text.strip() if gold_element else "N/A"

            return points, gold

        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return "N/A", "N/A"

    def sign_in(self):
        try:
            time.sleep(round(random.uniform(1, 3), 2))

            old_points, old_gold = self.get_user_info()
            logger.info(f"签到前 - 积分: {old_points}, 金币: {old_gold}")

            data = {"action": "user.checkin"}
            response = self.session.post(
                self.SIGN_IN_URL,
                headers=self.headers,
                cookies=self.cookies,
                data=data,
                timeout=10,
                verify=False
            )

            logger.debug(f"签到响应状态码: {response.status_code}")
            logger.debug(f"签到响应内容: {response.text}")

            try:
                result_json = response.json()
                result_str = str(result_json)
            except Exception:
                result_str = response.text.encode().decode('unicode_escape')

            new_points, new_gold = self.get_user_info()

            if "金币" in result_str:
                msg = f"✅ 签到成功!\n积分: {new_points}（+？）\n金币: {new_gold}"
                logger.info(msg)
                send("LGYCH 签到成功", msg)
                return True
            elif "已经" in result_str:
                msg = f"ℹ️ 今日已签到.\n积分: {new_points}\n金币: {new_gold}"
                logger.info(msg)
                send("LGYCH 已签到", msg)
                return False
            else:
                msg = f"⚠️ 签到返回未知结果: {result_str}"
                logger.warning(msg)
                send("LGYCH 签到异常", msg)
                return False

        except requests.exceptions.RequestException as e:
            msg = f"网络请求失败: {str(e)}"
            logger.error(msg)
            send("LGYCH 网络请求失败", msg)
            return False
        except Exception as e:
            msg = f"签到过程中发生错误: {str(e)}"
            logger.error(msg)
            send("LGYCH 签到出错", msg)
            return False

if __name__ == "__main__":
    try:
        signer = LGYCHSigner()
        signer.sign_in()
    except Exception as e:
        msg = f"程序初始化失败: {str(e)}"
        logger.error(msg)
        send("LGYCH 程序启动失败", msg)
