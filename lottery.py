'''
new Env('彩票开奖信息')
cron: 20 22 * * *
'''
import requests
import datetime
import re
import notify
from lxml import etree
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ✅ 正确的彩票配置
LOTTERY_CONFIG = {
    'ssq': {
        'name': '双色球',
        'url': 'https://kaijiang.500.com/ssq.shtml',
        'draw_days': [1, 3, 6],  # 每周二、四、日
        'time': (21, 15),
        'official': 'https://www.cwl.gov.cn',
    },
    'dlt': {
        'name': '大乐透',
        'url': 'https://kaijiang.500.com/dlt.shtml',
        'draw_days': [0, 2, 5],  # 每周一、三、六
        'time': (21, 25),
        'official': 'https://www.lottery.gov.cn',
    }
}

# ✅ 自动识别今天的彩票类型
def get_today_lottery():
    today = datetime.date.today().weekday()  # 返回 0-6（0=星期一）
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    print(f"🗓️ 今天是星期{weekday_map[today]}")
    for key, config in LOTTERY_CONFIG.items():
        if today in config['draw_days']:
            print(f"✅ 今天有{config['name']}开奖")
            return key, config
    print("❌ 今天没有彩票开奖")
    return None, None

# ✅ 自动重试请求函数
def get_with_retries(url, headers, retries=3, backoff=0.5):
    print(f"\n🌐 开始请求URL: {url}")
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    try:
        response = session.get(url, headers=headers, timeout=10)
        print(f"✅ 请求成功，状态码: {response.status_code}")
        return response
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")
        raise

# ✅ 主抓取与格式化函数
def get_lottery_info(config, headers):
    is_ssq = config['name'] == '双色球'
    url = config['url']
    print(f"\n🔍 开始抓取{config['name']}开奖信息")
    print(f"📡 目标URL: {url}")
    
    try:
        print("\n1️⃣ 发送网络请求...")
        resp = get_with_retries(url, headers)
        resp.raise_for_status()
        resp.encoding = 'gb2312'
        print("✅ 响应编码设置完成")

        print("\n2️⃣ 解析HTML内容...")
        html = etree.HTML(resp.text)
        print("✅ HTML解析完成")

        print("\n3️⃣ 提取基础数据...")
        title = html.xpath('//div[contains(@class,"kjxq_box02_title_left")]/img/@alt')[0]
        time_draw = html.xpath('//span[contains(@class,"span_right")]/text()')[0].strip()
        period = html.xpath('//font[contains(@class,"cfont2")]/strong/text()')[0]
        numbers = html.xpath('//div[contains(@class,"ball_box01")]/ul/li/text()')
        sales_amount = html.xpath('//span[contains(@class, "cfont1")]/text()')[0].strip() 
        prize_pool_rollover = html.xpath('//span[contains(@class, "cfont1")]/text()')[1].strip()

        print("\n4️⃣ 提取中奖金额信息...")
        if is_ssq:
            first = html.xpath('//tr[@align="center"][2]/td/text()')
            second = html.xpath('//tr[@align="center"][3]/td/text()')
            third = html.xpath('//tr[@align="center"][4]/td/text()')
        else:
            first = html.xpath('//tr[@align="center"][2]/td/text()')
            second = html.xpath('//tr[@align="center"][6]/td/text()')
            third = html.xpath('//tr[@align="center"][10]/td/text()')

        # 清洗中奖金额数据
        first = [s.strip() for s in first]
        second = [s.strip() for s in second]
        third = [s.strip() for s in third]

        print("\n5️⃣ 处理时间信息...")
        time_draw = time_draw.replace(' ', '')
        open_time = re.search(r'开奖日期[:：]\s*(\d{4}年\d{1,2}月\d{1,2}日)', time_draw)
        close_time = re.search(r'兑奖截止日期[:：]\s*(\d{4}年\d{1,2}月\d{1,2}日)', time_draw)

        if not open_time or not close_time:
            print("❌ 无法解析开奖时间或兑奖截止时间")
            return None, None

        draw_date = datetime.datetime.strptime(open_time.group(1), '%Y年%m月%d日')
        deadline = datetime.datetime.strptime(close_time.group(1), '%Y年%m月%d日')
        draw_date = draw_date.replace(hour=config['time'][0], minute=config['time'][1])
        weekday = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][draw_date.weekday()]

        update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        print(f"🔄 数据更新时间: {update_time}")

        print("\n6️⃣ 生成消息内容...")
        if is_ssq:
            message = f"""✨【{title}第 {period}期】开奖结果✨\n
⏰ 开奖时间：{draw_date.strftime('%Y年%m月%d日 %H:%M')}（{weekday}）
⏳ 兑奖截止：{deadline.strftime('%Y年%m月%d日')}
🎲 开奖号码：
═══════════════════
🔴{'  🔴'.join(numbers[:6])}  🔵{numbers[6]}
═══════════════════
💰 销售金额: {sales_amount}
🏦 奖池滚存: {prize_pool_rollover}\n
🥇 一等奖: {first[1]}注，单注奖金:{first[2]} 元
🥈 二等奖: {second[1]}注，单注奖金:{second[2]} 元
🥉 三等奖: {third[1]}注，单注奖金:{third[2]} 元\n
📅 双色球开奖日：每周二、四、日 21:15
🌐 官方网站：{config['official']}
🔄 数据更新时间：{update_time}
"""
        else:
            message = f"""✨【{title}第 {period}期】开奖结果✨\n
⏰ 开奖时间：{draw_date.strftime('%Y年%m月%d日 %H:%M')}（{weekday}）
⏳ 兑奖截止：{deadline.strftime('%Y年%m月%d日')}
🎲 开奖号码（前区 + 后区）：
═══════════════════
🟡{'  🟡'.join(numbers[:5])}   🔵{numbers[5]}  🔵{numbers[6]}
═══════════════════
💰 销售金额: {sales_amount}
🏦 奖池滚存: {prize_pool_rollover}\n
🥇 一等奖: {first[2]}注，单注奖金 {first[3]} 元
🥈 二等奖: {second[2]}注，单注奖金 {second[3]} 元
🥉 三等奖: {third[2]}注，单注奖金 {third[3]} 元\n
📅 大乐透开奖日：每周一、三、六 21:25
🌐 官方网站：{config['official']}
🔄 数据更新时间：{update_time}
"""
        print("✅ 消息内容生成完成")
        return title, message

    except requests.RequestException as e:
        print(f"❌ 网络请求错误: {str(e)}")
        print(f"🔍 错误类型: {type(e).__name__}")
        return None, None
    except Exception as e:
        print(f"❌ 处理数据时出错: {str(e)}")
        print(f"🔍 错误类型: {type(e).__name__}")
        print(f"📋 错误位置: {e.__traceback__.tb_lineno}")
        return None, None

# ✅ 程序入口
if __name__ == '__main__':
    print("🚀 启动彩票开奖程序...\n")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    print("1️⃣ 检查今日开奖信息...")
    key, config = get_today_lottery()
    if not config:
        print("❌ 今天不是开奖日，程序退出")
        exit(0)

    print("\n2️⃣ 开始抓取开奖数据...")
    title, message = get_lottery_info(config, headers)

    if title and message:
        print("\n3️⃣ 准备发送通知...")
        notify.send(title, message)
        print("✅ 通知发送完成")
    else:
        print("❌ 抓取或格式化失败，未发送通知")
        print("🔍 建议检查:")
        print("  1. 网络连接是否正常")
        print("  2. 目标网站是否可以访问")
        print("  3. 网页结构是否发生变化")
        print("  4. 请求头是否需要更新")
