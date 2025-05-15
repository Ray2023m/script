#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
new Env('FnOS论坛签到');
cron: 10 7 * * *
使用方法：
青龙面板添加环境变量：FNOS_CONFIG="myuser,mypass,baidu_api_key,baidu_secret_key"
原脚本来自https://github.com/kggzs/FN_AQ;感谢付出！
此脚本仅修改适配青龙通知，和增加环境变量方便输入
'''
import os
import re
import json
import time
import logging
import requests
import base64
import urllib.parse
from bs4 import BeautifulSoup
from datetime import datetime
import notify  # 新增通知模块

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'sign_{datetime.now().strftime("%Y%m%d")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 配置信息
class Config:
    """
    使用 FNOS_CONFIG 环境变量，格式如下（用英文逗号分隔）：
      用户名,密码,百度API_KEY,百度SECRET_KEY
    例如：
      myuser,mypass,xxxxxxx,yyyyyyy
    """
    config_env = os.environ.get('FNOS_CONFIG', '')
    t = [i.strip() for i in config_env.split(',')] if config_env else []
    USERNAME = t[0] if len(t) > 0 else ''
    PASSWORD = t[1] if len(t) > 1 else ''
    API_KEY = t[2] if len(t) > 2 else ''
    SECRET_KEY = t[3] if len(t) > 3 else ''
    
    BASE_URL = 'https://club.fnnas.com/'
    LOGIN_URL = BASE_URL + 'member.php?mod=logging&action=login'
    SIGN_URL = BASE_URL + 'plugin.php?id=zqlj_sign'
    COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.json')
    CAPTCHA_API_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    TOKEN_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'token_cache.json')

class FNSignIn:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        })
        self.load_cookies()
    
    def load_cookies(self):
        """从文件加载Cookie"""
        if os.path.exists(Config.COOKIE_FILE):
            try:
                with open(Config.COOKIE_FILE, 'r') as f:
                    cookies_list = json.load(f)
                    if isinstance(cookies_list, list) and len(cookies_list) > 0 and 'name' in cookies_list[0]:
                        for cookie_dict in cookies_list:
                            self.session.cookies.set(
                                cookie_dict['name'],
                                cookie_dict['value'],
                                domain=cookie_dict.get('domain'),
                                path=cookie_dict.get('path')
                            )
                    else:
                        self.session.cookies.update(cookies_list)
                logger.info("已从文件加载Cookie")
                return True
            except Exception as e:
                logger.error(f"加载Cookie失败: {e}")
        return False
    
    def save_cookies(self):
        """保存Cookie到文件"""
        try:
            cookies_list = []
            for cookie in self.session.cookies:
                cookie_dict = {
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'expires': cookie.expires,
                    'secure': cookie.secure
                }
                cookies_list.append(cookie_dict)
            with open(Config.COOKIE_FILE, 'w') as f:
                json.dump(cookies_list, f)
            logger.info("Cookie已保存到文件")
            return True
        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
            return False
    
    def check_login_status(self):
        """检查登录状态"""
        try:
            response = self.session.get(Config.BASE_URL)
            soup = BeautifulSoup(response.text, 'html.parser')
            login_links = soup.select('a[href*="member.php?mod=logging&action=login"]')
            username_in_page = Config.USERNAME in response.text
            user_center_links = soup.select('a[href*="home.php?mod=space"]')
            logger.debug(f"登录状态检测: 登录链接数量={len(login_links)}, 用户名在页面中={username_in_page}, 个人中心链接数量={len(user_center_links)}")
            if (len(login_links) == 0 or username_in_page) and len(user_center_links) > 0:
                logger.info("Cookie有效，已登录状态")
                return True
            else:
                logger.info("Cookie无效或已过期，需要重新登录")
                return False
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def get_access_token(self):
        """获取百度API的access_token，带缓存功能"""
        try:
            if os.path.exists(Config.TOKEN_CACHE_FILE):
                try:
                    with open(Config.TOKEN_CACHE_FILE, 'r') as f:
                        token_data = json.load(f)
                        if token_data.get('expires_time', 0) > time.time():
                            logger.info("使用缓存的access_token")
                            return token_data.get('access_token')
                        else:
                            logger.info("缓存的access_token已过期，重新获取")
                except Exception as e:
                    logger.warning(f"读取token缓存文件失败: {e}")
            url = "https://aip.baidubce.com/oauth/2.0/token"
            params = {
                "grant_type": "client_credentials", 
                "client_id": Config.API_KEY, 
                "client_secret": Config.SECRET_KEY
            }
            for retry in range(Config.MAX_RETRIES):
                try:
                    response = requests.post(url, params=params)
                    if response.status_code == 200:
                        result = response.json()
                        access_token = str(result.get("access_token"))
                        expires_in = result.get("expires_in", 2592000)
                        token_cache = {
                            'access_token': access_token,
                            'expires_time': time.time() + expires_in - 86400
                        }
                        try:
                            with open(Config.TOKEN_CACHE_FILE, 'w') as f:
                                json.dump(token_cache, f)
                            logger.info("access_token已缓存")
                        except Exception as e:
                            logger.warning(f"缓存access_token失败: {e}")
                        return access_token
                    else:
                        logger.error(f"获取access_token失败，状态码: {response.status_code}，重试({retry+1}/{Config.MAX_RETRIES})")
                        if retry < Config.MAX_RETRIES - 1:
                            time.sleep(Config.RETRY_DELAY)
                except Exception as e:
                    logger.error(f"获取access_token请求异常: {e}，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
            logger.error(f"获取access_token失败，已达到最大重试次数({Config.MAX_RETRIES})")
            return None
        except Exception as e:
            logger.error(f"获取access_token过程发生错误: {e}")
            return None
    
    def recognize_captcha(self, captcha_url):
        """识别验证码，带重试机制"""
        for retry in range(Config.MAX_RETRIES):
            try:
                captcha_response = self.session.get(captcha_url)
                if captcha_response.status_code != 200:
                    logger.error(f"下载验证码图片失败，状态码: {captcha_response.status_code}，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return None
                captcha_base64 = base64.b64encode(captcha_response.content).decode('utf-8')
                access_token = self.get_access_token()
                if not access_token:
                    logger.error(f"获取百度API access_token失败，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return None
                url = f"{Config.CAPTCHA_API_URL}?access_token={access_token}"
                payload = f'image={urllib.parse.quote_plus(captcha_base64)}&detect_direction=false&paragraph=false&probability=false'
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json'
                }
                api_response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
                if api_response.status_code != 200:
                    logger.error(f"验证码识别API请求失败，状态码: {api_response.status_code}，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return None
                result = api_response.json()
                if 'words_result' in result and len(result['words_result']) > 0:
                    captcha_text = result['words_result'][0]['words']
                    captcha_text = re.sub(r'[\s\W]+', '', captcha_text)
                    logger.info(f"验证码识别成功: {captcha_text}")
                    return captcha_text
                elif 'error_code' in result:
                    logger.error(f"验证码识别API返回错误: {result.get('error_code')}, {result.get('error_msg')}，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return None
                else:
                    logger.error(f"验证码识别API返回格式异常: {result}，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return None
            except Exception as e:
                logger.error(f"验证码识别过程发生错误: {e}，重试({retry+1}/{Config.MAX_RETRIES})")
                if retry < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                return None
        logger.error(f"验证码识别失败，已达到最大重试次数({Config.MAX_RETRIES})")
        return None
    
    def login(self):
        """使用账号密码登录，带重试机制"""
        for retry in range(Config.MAX_RETRIES):
            try:
                response = self.session.get(Config.LOGIN_URL)
                soup = BeautifulSoup(response.text, 'html.parser')
                login_form = None
                for form in soup.find_all('form'):
                    form_id = form.get('id', '')
                    if form_id and ('loginform' in form_id or 'lsform' in form_id):
                        login_form = form
                        break
                    elif form.get('name') == 'login':
                        login_form = form
                        break
                    elif form.get('action') and 'logging' in form.get('action'):
                        login_form = form
                        break
                if not login_form:
                    all_forms = soup.find_all('form')
                    if all_forms:
                        login_form = all_forms[0]
                        logger.info(f"使用备选表单: ID={login_form.get('id')}, Action={login_form.get('action')}")
                if not login_form:
                    logger.error(f"未找到登录表单，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return False
                form_id = login_form.get('id', '')
                login_hash = form_id.split('_')[-1] if '_' in form_id else ''
                form_action = login_form.get('action', '')
                logger.info(f"找到登录表单: ID={form_id}, Action={form_action}")
                formhash = soup.find('input', {'name': 'formhash'})
                if not formhash:
                    logger.error(f"未找到登录表单的formhash字段，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return False
                formhash = formhash['value']
                username_input = soup.find('input', {'name': 'username'})
                username_id = username_input.get('id', '') if username_input else ''
                password_input = soup.find('input', {'name': 'password'})
                password_id = password_input.get('id', '') if password_input else ''
                logger.info(f"找到用户名输入框ID: {username_id}")
                logger.info(f"找到密码输入框ID: {password_id}")
                login_data = {
                    'formhash': formhash,
                    'referer': Config.BASE_URL,
                    'loginfield': 'username',
                    'username': Config.USERNAME,
                    'password': Config.PASSWORD,
                    'questionid': '0',
                    'answer': '',
                    'cookietime': '2592000',
                    'loginsubmit': 'true'
                }
                if username_id:
                    login_data[username_id] = Config.USERNAME
                if password_id:
                    login_data[password_id] = Config.PASSWORD
                seccodeverify = soup.find('input', {'name': 'seccodeverify'})
                if seccodeverify:
                    logger.info("检测到需要验证码，尝试自动识别验证码")
                    seccode_id = seccodeverify.get('id', '').replace('seccodeverify_', '')
                    captcha_img = soup.find('img', {'src': re.compile(r'misc\.php\?mod=seccode')})
                    if not captcha_img:
                        logger.error(f"未找到验证码图片，重试({retry+1}/{Config.MAX_RETRIES})")
                        if retry < Config.MAX_RETRIES - 1:
                            time.sleep(Config.RETRY_DELAY)
                            continue
                        return False
                    captcha_url = Config.BASE_URL + captcha_img['src']
                    logger.info(f"验证码图片URL: {captcha_url}")
                    captcha_text = self.recognize_captcha(captcha_url)
                    if not captcha_text:
                        logger.error(f"验证码识别失败，重试({retry+1}/{Config.MAX_RETRIES})")
                        if retry < Config.MAX_RETRIES - 1:
                            time.sleep(Config.RETRY_DELAY)
                            continue
                        return False
                    login_data['seccodeverify'] = captcha_text
                    login_data['seccodehash'] = seccode_id
                self.session.headers.update({
                    'Origin': Config.BASE_URL.rstrip('/'),
                    'Referer': Config.LOGIN_URL,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Upgrade-Insecure-Requests': '1'
                })
                login_url = f"{Config.LOGIN_URL}&loginsubmit=yes&inajax=1"
                login_response = self.session.post(login_url, data=login_data, allow_redirects=True)
                logger.debug(f"登录请求URL: {login_url}")
                logger.debug(f"登录请求数据: {login_data}")
                logger.debug(f"登录响应状态码: {login_response.status_code}")
                logger.debug(f"登录响应内容: {login_response.text[:500]}...")
                if '验证码' in login_response.text and '验证码错误' in login_response.text:
                    logger.error(f"验证码错误，登录失败，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return False
                if 'succeedhandle_' in login_response.text or self.check_login_status():
                    logger.info(f"账号 {Config.USERNAME} 登录成功")
                    self.save_cookies()
                    return True
                else:
                    logger.error(f"登录失败，请检查账号密码，重试({retry+1}/{Config.MAX_RETRIES})")
                    logger.debug(f"登录响应: {login_response.text[:200]}...")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return False
            except Exception as e:
                logger.error(f"登录过程发生错误: {e}，重试({retry+1}/{Config.MAX_RETRIES})")
                if retry < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                return False
        logger.error(f"登录失败，已达到最大重试次数({Config.MAX_RETRIES})")
        return False
    
    def check_sign_status(self):
        """检查签到状态，带重试机制"""
        for retry in range(Config.MAX_RETRIES):
            try:
                response = self.session.get(Config.SIGN_URL)
                soup = BeautifulSoup(response.text, 'html.parser')
                sign_btn = soup.select_one('.signbtn .btna')
                if not sign_btn:
                    logger.error(f"未找到签到按钮，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return None, None
                sign_text = sign_btn.text.strip()
                sign_link = sign_btn.get('href')
                sign_param = None
                if sign_link:
                    match = re.search(r'sign=([^&]+)', sign_link)
                    if match:
                        sign_param = match.group(1)
                return sign_text, sign_param
            except Exception as e:
                logger.error(f"检查签到状态失败: {e}，重试({retry+1}/{Config.MAX_RETRIES})")
                if retry < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                return None, None
    
    def do_sign(self, sign_param):
        """执行签到，带重试机制"""
        for retry in range(Config.MAX_RETRIES):
            try:
                sign_url = f"{Config.SIGN_URL}&sign={sign_param}"
                response = self.session.get(sign_url)
                if response.status_code == 200:
                    sign_text, _ = self.check_sign_status()
                    if sign_text == "今日已打卡":
                        logger.info("签到成功")
                        return True
                    else:
                        logger.error(f"签到请求已发送，但状态未更新，重试({retry+1}/{Config.MAX_RETRIES})")
                        if retry < Config.MAX_RETRIES - 1:
                            time.sleep(Config.RETRY_DELAY)
                            continue
                        return False
                else:
                    logger.error(f"签到请求失败，状态码: {response.status_code}，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return False
            except Exception as e:
                logger.error(f"签到过程发生错误: {e}，重试({retry+1}/{Config.MAX_RETRIES})")
                if retry < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                return False
    
    def get_sign_info(self):
        """获取签到信息，带重试机制"""
        for retry in range(Config.MAX_RETRIES):
            try:
                response = self.session.get(Config.SIGN_URL)
                soup = BeautifulSoup(response.text, 'html.parser')
                sign_info_divs = soup.find_all('div', class_='bm')
                sign_info_div = None
                for div in sign_info_divs:
                    header = div.find('div', class_='bm_h')
                    if header and '我的打卡动态' in header.get_text():
                        sign_info_div = div
                        break
                if not sign_info_div:
                    logger.error(f"未找到签到信息区域，重试({retry+1}/{Config.MAX_RETRIES})")
                    if retry < Config.MAX_RETRIES - 1:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                    return {}
                info_list = sign_info_div.find('div', class_='bm_c').find_all('li')
                sign_info = {}
                for item in info_list:
                    text = item.get_text(strip=True)
                    if '：' in text:
                        key, value = text.split('：', 1)
                        sign_info[key] = value
                return sign_info
            except Exception as e:
                logger.error(f"获取签到信息失败: {e}，重试({retry+1}/{Config.MAX_RETRIES})")
                if retry < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                return {}
        logger.error(f"获取签到信息失败，已达到最大重试次数({Config.MAX_RETRIES})")
        return {}
    
    def run(self):
        """运行签到流程，带重试机制"""
        logger.info("===== 开始运行签到脚本 =====")
        notify_content = ""
        result_title = ""
        if not self.check_login_status():
            if not self.login():
                logger.error("登录失败，签到流程终止")
                result_title = "FnOS论坛 签到失败"
                notify_content = "登录失败，流程终止"
                notify.send(result_title, notify_content)
                return False
        sign_text, sign_param = self.check_sign_status()
        if sign_text is None or sign_param is None:
            logger.error("获取签到状态失败，签到流程终止")
            result_title = "FnOS论坛 签到失败"
            notify_content = "获取签到状态失败"
            notify.send(result_title, notify_content)
            return False
        logger.info(f"当前签到状态: {sign_text}")
        if sign_text == "点击打卡":
            logger.info("开始执行签到...")
            if self.do_sign(sign_param):
                sign_info = self.get_sign_info()
                if sign_info:
                    logger.info("===== 签到信息 =====")
                    for key, value in sign_info.items():
                        logger.info(f"{key}: {value}")
                    result_title = "FnOS论坛 签到成功"
                    notify_content = "\n".join([f"{key}: {value}" for key, value in sign_info.items()])
                    notify.send(result_title, notify_content)
                return True
            else:
                logger.error("签到失败")
                result_title = "FnOS论坛 签到失败"
                notify_content = "签到失败"
                notify.send(result_title, notify_content)
                return False
        elif sign_text == "今日已打卡":
            logger.info("今日已签到，无需重复签到")
            sign_info = self.get_sign_info()
            if sign_info:
                logger.info("===== 签到信息 =====")
                for key, value in sign_info.items():
                    logger.info(f"{key}: {value}")
                result_title = "FnOS论坛 今日已打卡"
                notify_content = "\n".join([f"{key}: {value}" for key, value in sign_info.items()])
                notify.send(result_title, notify_content)
            return True
        else:
            logger.warning(f"未知的签到状态: {sign_text}，签到流程终止")
            result_title = "FnOS论坛 签到失败"
            notify_content = f"未知状态: {sign_text}"
            notify.send(result_title, notify_content)
            return False

if __name__ == "__main__":
    try:
        if os.environ.get('DEBUG') == '1':
            logger.setLevel(logging.DEBUG)
            logger.debug("调试模式已启用")
        # 检查环境变量
        if not (Config.USERNAME and Config.PASSWORD and Config.API_KEY and Config.SECRET_KEY):
            logger.error("环境变量未配置完整，FNOS_CONFIG 必须设置为“用户名,密码,百度API_KEY,百度SECRET_KEY”（英文逗号分隔）！")
            notify.send("FnOS论坛 签到失败", "环境变量未配置完整，FNOS_CONFIG 必须设置为“用户名,密码,百度API_KEY,百度SECRET_KEY”（英文逗号分隔）！")
            exit(1)
        sign = FNSignIn()
        result = sign.run()
        if result:
            logger.info("===== 签到脚本执行成功 =====")
        else:
            logger.error("===== 签到脚本执行失败 =====")
    except KeyboardInterrupt:
        logger.info("脚本被用户中断")
    except Exception as e:
        logger.error(f"脚本运行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
