'''
cron: 40 6 * * *
new Env('69机场签到');

使用方法：
青龙面板添加环境变量：ACCOUNT= 69机场地址|注册邮箱|yourpassword
此脚本来源于https://github.com/cmliussss2024/CF-Workers-checkin，感谢原作者付出！
通过 AI修改，以适用于青龙面板。
'''
import os
import requests
import time
import re
from bs4 import BeautifulSoup
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from notify import send  # ✅ 青龙通知

# ========== 全局 ==========
session = requests.Session()
retries = Retry(total=3, backoff_factor=1)
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))


# ========== 获取用户信息 ==========
def fetch_and_extract_info(domain, headers):
    try:
        url = f"{domain}/user"
        res = session.get(url, headers=headers, timeout=10)

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


# ========== 读取青龙变量 ==========
def load_config():
    domain = os.getenv("DOMAIN", "").strip()

    accounts = []
    i = 1

    while True:
        user = os.getenv(f"USER{i}")
        pwd = os.getenv(f"PASS{i}")

        if not user or not pwd:
            break

        accounts.append({"user": user, "pass": pwd})
        i += 1

    return domain, accounts


# ========== 核心签到 ==========
def checkin(account, domain):
    user = account["user"]
    pwd = account["pass"]

    print(f"开始处理账号: {user}")

    try:
        login_url = f"{domain}/auth/login"

        res = session.post(
            login_url,
            json={
                "email": user,
                "passwd": pwd,
                "remember_me": "on"
            },
            timeout=10
        )

        if res.status_code != 200:
            return f"{user} ❌ 登录请求失败"

        data = res.json()

        if data.get("ret") != 1:
            return f"{user} ❌ 登录失败: {data.get('msg')}"

        cookies = res.cookies.get_dict()

        headers = {
            "Cookie": "; ".join([f"{k}={v}" for k, v in cookies.items()]),
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest"
        }

        # 签到
        res = session.post(f"{domain}/user/checkin", headers=headers, timeout=10)

        result = res.json()
        msg = result.get("msg", "未知结果")

        user_info = fetch_and_extract_info(domain, headers)

        return (
            f"👤 {user}\n"
            f"📌 {msg}\n"
            f"{user_info}"
        )

    except Exception as e:
        return f"{user} ❌ 异常: {e}"


# ========== 主程序 ==========
if __name__ == "__main__":
    domain, accounts = load_config()

    if not domain:
        print("❌ 请设置 DOMAIN")
        exit()

    if not accounts:
        print("❌ 未配置账号")
        exit()

    print("========== 开始签到 ==========")

    all_msg = ""

    for acc in accounts:
        result = checkin(acc, domain)
        print(result)
        print("----------------------------------")
        all_msg += result + "\n"

    print("========== 结束 ==========")

    # ✅ 青龙通知
    title = "🎉 机场签到结果"
    send(title, all_msg)