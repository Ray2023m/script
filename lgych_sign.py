import os
import requests
import re
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# 配置日志
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
        self.cookies = self._get_cookies_from_env()  # 从环境变量获取cookies
        self.session = self._create_session()

    def _get_cookies_from_env(self):
        """从青龙面板环境变量获取cookies"""
        # 青龙面板的环境变量名，可以根据需要修改
        cookie_env_name = "LGYCH_COOKIE"
        
        cookie_str = os.getenv(cookie_env_name)
        if not cookie_str:
            logger.error(f"未找到环境变量 {cookie_env_name}，请先在青龙面板中配置")
            raise ValueError(f"环境变量 {cookie_env_name} 未设置")
        
        # 将cookie字符串转换为字典格式
        try:
            # 假设cookie格式为 "name1=value1; name2=value2"
            cookie_dict = {}
            for item in cookie_str.split(';'):
                if '=' in item:
                    name, value = item.strip().split('=', 1)
                    cookie_dict[name] = value
            return cookie_dict
        except Exception as e:
            logger.error(f"解析Cookie失败: {str(e)}")
            raise ValueError("Cookie格式不正确，请检查环境变量设置")

    def _create_session(self):
        """创建带有重试机制的会话"""
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
        """获取用户信息"""
        try:
            response = self.session.get(
                self.USER_PAGE_URL,
                headers=self.headers,
                cookies=self.cookies,
                timeout=10
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 获取积分
            points_element = soup.find(text=re.compile(r"可用积分：\d+"))
            points = re.search(r"可用积分：(\d+)", points_element).group(1) if points_element else "N/A"
            
            # 获取金币
            gold_element = soup.find('b', class_='color')
            gold = gold_element.text if gold_element else "N/A"
            
            return points, gold
            
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return "N/A", "N/A"

    def sign_in(self):
        """执行签到"""
        try:
            # 先获取当前积分状态
            old_points, old_gold = self.get_user_info()
            logger.info(f"签到前 - 积分: {old_points}, 金币: {old_gold}")
            
            # 执行签到
            data = {"action": "user.checkin"}
            response = self.session.post(
                self.SIGN_IN_URL,
                headers=self.headers,
                cookies=self.cookies,
                data=data,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.text.encode().decode('unicode_escape')
            logger.debug(f"签到响应: {result}")
            
            # 获取签到后的积分状态
            new_points, new_gold = self.get_user_info()
            
            if "金币" in result:
                logger.info(f"签到成功! 获得奖励. 当前积分: {new_points}, 金币: {new_gold}")
                return True
            elif "已经" in result:
                logger.info(f"今日已签到. 当前积分: {new_points}, 金币: {new_gold}")
                return False
            else:
                logger.warning(f"签到返回未知结果: {result}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"签到过程中发生错误: {str(e)}")
            return False

if __name__ == "__main__":
    try:
        signer = LGYCHSigner()
        signer.sign_in()
    except Exception as e:
        logger.error(f"程序初始化失败: {str(e)}")
