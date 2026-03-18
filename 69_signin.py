'''
69机场签到脚本
cron: 40 6 * * *
new Env('69机场签到');
添加环境变量：ACCOUNT=your.airport.com|you@example.com|yourpassword
脚本由网上收集,ai修改完善,仅供学习交流使用,请勿用于商业用途,如有侵权请联系删除
'''

import os
import requests
import re
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from notify import send

# ========== 读取配置 ==========
account_str = os.getenv("ACCOUNT", "").strip()

if not account_str:
    raise Exception("❌ 请设置 ACCOUNT=域名|邮箱|密码")

try:
    domain, email, password = account_str.split("|")
except ValueError:
    raise Exception("❌ ACCOUNT 格式错误，应为: 域名|邮箱|密码")

# 自动补 https
if not domain.startswith("http"):
    domain = f"https://{domain}"

# ========== Session ==========
session = requests.Session()
retries = Retry(total=3, backoff_factor=1)
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))


# ========== 获取用户信息 ==========
def fetch_and_extract_info(headers):
    try:
        res = session.get(f"{domain}/user", headers=headers, timeout=10)

        if res.status_code != 200:
            return "用户信息获取失败\n"

        soup = BeautifulSoup(res.text, 'html.parser')

        script_tags = soup.find_all('script')
        chatra_script = None

        for script in script_tags:
            if 'window.ChatraIntegration' in str(script):
                chatra_script = script.string
                break

        if not chatra_script:
            return "未获取到用户信息\n"

        expire = re.search(r"'Class_Expire': '(.*?)'", chatra_script)
        traffic = re.search(r"'Unused_Traffic': '(.*?)'", chatra_script)

        info = ""
        info += f"到期时间: {expire.group(1) if expire else '未知'}\n"
        info += f"剩余流量: {traffic.group(1) if traffic else '未知'}\n"

        link_match = re.search(r"https://.*?/link/.*?\?sub=\d+", res.text)
        if link_match:
            base = link_match.group(0).split("?")[0]
            info += f"订阅: {base}?sub=3\n"

        return info + "\n"

    except Exception as e:
        return f"用户信息异常: {e}\n"


# ========== 核心签到 ==========
def checkin():
    try:
        print(f"开始签到: {email}")

        # 登录
        res = session.post(
            f"{domain}/auth/login",
            json={
                "email": email,
                "passwd": password,
                "remember_me": "on"
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json"
            },
            timeout=10
        )

        if res.status_code != 200:
            return "❌ 登录请求失败"

        data = res.json()

        if data.get("ret") != 1:
            return f"❌ 登录失败: {data.get('msg')}"

        cookies = session.cookies.get_dict()

        headers = {
            "Cookie": "; ".join([f"{k}={v}" for k, v in cookies.items()]),
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest"
        }

        # 签到
        res = session.post(f"{domain}/user/checkin", headers=headers, timeout=10)
        result = res.json()

        msg = result.get("msg", "未知结果")

        user_info = fetch_and_extract_info(headers)

        return (
            f"👤 {email}\n"
            f"📌 {msg}\n"
            f"{user_info}"
        )

    except Exception as e:
        return f"❌ 异常: {e}"


# ========== 主程序 ==========
if __name__ == "__main__":
    print("========== 开始签到 ==========")

    result = checkin()
    print(result)

    print("========== 结束 ==========")

    send("🎉 机场签到结果", result)