'''
new Env('阡陌居签到');
cron: 50 6 * * *
'''
'''
new Env('阡陌居签到');
cron: 40 6 * * *
'''

# 阡陌居自动签到 - 青龙面板日志增强版
# 环境变量：QMJ_COOKIE（从浏览器复制完整 cookie）
# 含经验/等级/连续签到天数输出
import os
import requests
from bs4 import BeautifulSoup
from notify import send
import random
import traceback

# ========== 配置 ==========
COOKIE = os.getenv("QMJ_COOKIE")
if not COOKIE:
    print("❌ [错误] 未检测到环境变量 QMJ_COOKIE，请配置后重试。")
    exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Cookie": COOKIE
}

BASE_URL = "http://www.1000qm.vip/"
MOODS = {
    "kx": "开心",
    "ng": "郁闷",
    "yl": "无聊",
    "wl": "微笑",
    "nu": "愤怒",
    "ch": "擦汗"
}
MOOD_CODE, MOOD_NAME = random.choice(list(MOODS.items()))

session = requests.Session()
session.headers.update(HEADERS)

# ========== 核心流程 ==========
def get_signin_link():
    print("🔍 正在访问首页，准备提取签到链接...")
    try:
        response = session.get(BASE_URL)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        link = soup.find('a', onclick=lambda x: x and 'dsu_paulsign:sign' in x)
        if link:
            full_url = BASE_URL + link['href']
            print(f"✅ 成功获取签到链接: {full_url}")
            return full_url
        else:
            print("⚠️ 未找到签到链接，可能已签到或页面结构变化。")
            return None
    except Exception as e:
        print("❌ 获取签到链接失败：", e)
        return None


def extract_reward_info(html):
    """从返回页面中提取签到结果信息（只保留你关心的字段）"""
    soup = BeautifulSoup(html, "html.parser")
    info = soup.find("div", class_="c")
    if not info:
        info = soup.find("div", class_="msgbox")  # 兼容其他结构

    if info:
        keywords = ["累计已签到", "本月已累计签到", "签到时间", "铜币", "等级"]
        reward_lines = []
        for p in info.find_all("p"):
            text = p.get_text(strip=True)
            if any(k in text for k in keywords):
                reward_lines.append(text)
        return "\n".join(reward_lines)
    return ""


def perform_signin(signin_url):
    print(f"📥 访问签到页面：{signin_url}")
    try:
        res = session.get(signin_url)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        form = soup.find("form", id="qiandao")
        if not form:
            return "❌ 未找到签到表单，签到失败"

        formhash = form.find("input", {"name": "formhash"})["value"]
        data = {
            "formhash": formhash,
            "qdxq": MOOD_CODE,
            "qdmode": "1",
            "todaysay": f"来自青龙的自动签到~ 心情：{MOOD_NAME}"
        }

        post_url = BASE_URL + form["action"]
        print("📤 正在提交签到表单...")
        res = session.post(post_url, data=data)
        res.encoding = 'utf-8'

        reward = extract_reward_info(res.text)

        if "已经签到" in res.text:
            return f"✔️ 今日已签到，无需重复（心情：{MOOD_NAME}）\n{reward if reward else '✅ 无奖励信息显示'}"
        elif "签到成功" in res.text or "成功" in reward:
            return f"🎉 签到成功！（心情：{MOOD_NAME}）\n{reward if reward else '✅ 无奖励信息显示'}"
        else:
            print("⚠️ 未检测到成功提示，返回页面内容截断如下：")
            print(res.text[:300])
            return "⚠️ 签到已提交，但未检测到成功提示"

    except Exception as e:
        print("❌ 签到流程发生异常：")
        traceback.print_exc()
        return f"❌ 签到异常：{e}"


# ========== 主流程 ==========
print("🚀 阡陌居自动签到任务开始")
print(f"🧠 今日心情随机选择为：{MOOD_NAME} ({MOOD_CODE})")

signin_url = get_signin_link()
if signin_url:
    result = perform_signin(signin_url)
else:
    result = "⚠️ 未获取到签到链接，可能已签到或页面出错"

print(f"\n📌 最终结果：\n{result}")
try:
    send("阡陌居签到通知", result)
except Exception as e:
    print(f"⚠️ 通知发送失败：{e}")
