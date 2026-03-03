import requests
import datetime
import time
import notify
import xml.etree.ElementTree as ET

# 彩票配置
LOTTERY_CONFIG = {
    'ssq': {
        'name': '双色球',
        'url': 'https://kaijiang.500.com/static/info/kaijiang/xml/ssq/list.xml',
        'draw_days': [1, 3, 6],  # 星期二、四、日
        'time': (21, 15),
        'official': 'https://www.cwl.gov.cn',
    },
    'dlt': {
        'name': '超级大乐透',
        'url': 'https://kaijiang.500.com/static/info/kaijiang/xml/dlt/list.xml',
        'draw_days': [0, 2, 5],  # 星期一、三、六
        'time': (21, 25),
        'official': 'https://www.lottery.gov.cn',
    }
}

# 自动识别今天开奖的彩票类型
def get_today_lottery():
    today = datetime.date.today().weekday()
    weekday_map = ['一','二','三','四','五','六','日']
    print(f"🗓️ 今天是星期{weekday_map[today]}")
    for key, config in LOTTERY_CONFIG.items():
        if today in config['draw_days']:
            print(f"✅ 今天有{config['name']}开奖")
            return key, config
    print("❌ 今天没有彩票开奖")
    return None, None

# 自动重试请求
def get_with_retries(url, headers, retries=3, backoff=0.5):
    session = requests.Session()
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    retry = Retry(total=retries, backoff_factor=backoff, status_forcelist=[500,502,503,504], allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session.get(url, headers=headers, timeout=10)

# 抓取最新开奖数据
def fetch_latest_lottery(config):
    url = f"{config['url']}?_A={int(time.time())}"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = get_with_retries(url, headers)
    resp.encoding = 'utf-8'
    root = ET.fromstring(resp.text)
    rows = root.findall("row")
    if not rows:
        print("❌ 未获取到开奖数据")
        return None
    latest = rows[0]
    issue = latest.get("expect")
    opencode = latest.get("opencode")
    opentime = latest.get("opentime")

    # 拆分红球/蓝球
    red, blue = [], []
    if opencode:
        if "|" in opencode:
            red_str, blue_str = opencode.split("|")
            red = [x.strip() for x in red_str.split(",")]
            blue = [x.strip() for x in blue_str.split(",")]
        elif "+" in opencode:
            red_str, blue_str = opencode.split("+")
            red = [x.strip() for x in red_str.split(",")]
            blue = [x.strip() for x in blue_str.split(",")]

    # 优化文本显示
    red_text = " ".join(red)
    blue_text = " ".join(blue)

    # 格式化开奖时间
    try:
        draw_date = datetime.datetime.strptime(opentime, "%Y-%m-%d %H:%M:%S")
        draw_date = draw_date.replace(hour=config['time'][0], minute=config['time'][1])
        weekday = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][draw_date.weekday()]
    except:
        draw_date = opentime
        weekday = ""

    # 构建消息
    message = f"""✨【{config['name']}第 {issue} 期】开奖结果✨
⏰ 开奖时间：{draw_date} {weekday}
🎲 开奖号码：
═══════════════════
🔴{red_text}  🔵{blue_text}
🌐 官方网站：{config['official']}
"""
    return message

# ===== 主程序入口 =====
if __name__ == "__main__":
    print("🚀 启动彩票开奖程序...\n")
    key, config = get_today_lottery()
    if not config:
        exit(0)
    message = fetch_latest_lottery(config)
    if message:
        print("✅ 抓取成功，准备发送通知...")
        notify.send(f"{config['name']}最新开奖", message)
        print("✅ 通知发送完成")
    else:
        print("❌ 抓取失败")