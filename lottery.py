'''
new Env('彩票开奖信息')
cron: 20 22 * * *
'''

import requests
import datetime
import notify

# ==========================
# 彩票配置
# ==========================
LOTTERY_CONFIG = {
    'ssq': {
        'name': '双色球',
        'url': 'https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice',
        'draw_days': [1, 3, 6],  # 周二、四、日
        'official': 'https://www.cwl.gov.cn',
    },
    'dlt': {
        'name': '超级大乐透',
        'url': 'https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry',
        'draw_days': [0, 2, 5],  # 周一、三、六
        'official': 'https://www.lottery.gov.cn',
    }
}

# ==========================
# 判断今天是否开奖
# ==========================
def get_today_lottery():
    today = datetime.date.today().weekday()  # 0=周一
    weekday_map = ['一','二','三','四','五','六','日']
    print(f"🗓️ 今天是星期{weekday_map[today]}")
    for key, config in LOTTERY_CONFIG.items():
        if today in config['draw_days']:
            print(f"✅ 今天有{config['name']}开奖")
            return key, config
    print("❌ 今天没有彩票开奖")
    return None, None

# ==========================
# 自动重试请求
# ==========================
def get_with_retries(url, headers=None, params=None, retries=3, backoff=0.5):
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[500,502,503,504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    resp = session.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp

# ==========================
# 双色球
# ==========================
def get_latest_ssq():
    config = LOTTERY_CONFIG['ssq']
    headers = {"User-Agent":"Mozilla/5.0","Referer":config['official']}
    params = {"name":"ssq","issueCount":1}
    resp = get_with_retries(config['url'], headers=headers, params=params)
    data = resp.json()
    result = data["result"][0]

    red_numbers = result["red"].replace(',', ' ').split()
    blue_number = result["blue"]

    prizes = result.get("prizegrades", [])

    def safe_get(idx):
        if idx < len(prizes):
            return prizes[idx]
        return {}

    first = safe_get(0)
    second = safe_get(1)
    third = safe_get(2)

    def to_number(x):
        try:
            return float(x)
        except:
            return x

    return {
        "期号": result["code"],
        "开奖日期": result["date"],
        "红球": red_numbers,
        "蓝球": blue_number,
        "销售额": to_number(result["sales"]),
        "奖池金额": to_number(result["poolmoney"]),
        "一等奖注数": first.get("typenum","-"),
        "一等奖金额": to_number(first.get("typemoney","-")),
        "二等奖注数": second.get("typenum","-"),
        "二等奖金额": to_number(second.get("typemoney","-")),
        "三等奖注数": third.get("typenum","-"),
        "三等奖金额": to_number(third.get("typemoney","-"))
    }

# ==========================
# 大乐透
# ==========================
def get_latest_dlt():
    config = LOTTERY_CONFIG['dlt']
    headers = {"User-Agent":"Mozilla/5.0","Referer":config['official']}
    params = {"gameNo":"85","provinceId":"0","pageSize":"1","isVerify":"1"}
    resp = get_with_retries(config['url'], headers=headers, params=params)
    data = resp.json()
    latest = data.get("value",{}).get("list",[{}])[0]

    prize_list = latest.get("prizeLevelList", [])

    def safe_get(idx):
        if idx < len(prize_list):
            p = prize_list[idx]
            return p.get("stakeCount","-"), p.get("totalPrizeamount","-")
        return "-","-"

    # 体彩结构：0=一等奖,1=追加,2=二等奖,3=追加,4=三等奖
    first_count, first_amount = safe_get(0)
    second_count, second_amount = safe_get(2)
    third_count, third_amount = safe_get(4)

    numbers = latest.get("lotteryDrawResult","-").replace(',', ' ').split()

    def to_number(x):
        try:
            return float(x)
        except:
            return x

    return {
        "期号": latest.get("lotteryDrawNum","-"),
        "开奖日期": latest.get("lotteryDrawTime","-"),
        "开奖号码": numbers,
        "销售额": to_number(latest.get("totalSaleAmount","-")),
        "奖池金额": to_number(latest.get("poolBalanceAfterdraw","-")),
        "一等奖注数": first_count,
        "一等奖金额": to_number(first_amount),
        "二等奖注数": second_count,
        "二等奖金额": to_number(second_amount),
        "三等奖注数": third_count,
        "三等奖金额": to_number(third_amount)
    }

# ==========================
# 格式化输出
# ==========================
def format_message(lottery_type, data):

    def fmt_money(val):
        try:
            return f"{int(float(val)):,} 元"
        except:
            return f"{val} 元"

    if lottery_type == 'ssq':

        red = ' '.join([f"🔴{n}" for n in data["红球"]])
        blue = f"🔵{data['蓝球']}"

        msg = f"""✨【双色球第 {data['期号']}期】开奖结果✨
⏰ 开奖日期：{data['开奖日期']}
🎲 开奖号码：
══════════════
{red}  {blue}
══════════════
💰 销售额: {fmt_money(data['销售额'])}
🏦 奖池金额: {fmt_money(data['奖池金额'])}

🥇 一等奖：{data['一等奖注数']} 注，单注奖金 {fmt_money(data['一等奖金额'])}
🥈 二等奖：{data['二等奖注数']} 注，单注奖金 {fmt_money(data['二等奖金额'])}
🥉 三等奖：{data['三等奖注数']} 注，单注奖金 {fmt_money(data['三等奖金额'])}

🌐 官方网站：{LOTTERY_CONFIG['ssq']['official']}
"""
    else:

        nums = data["开奖号码"]
        front = ' '.join([f"🟡{n}" for n in nums[:5]])
        back = ' '.join([f"🔵{n}" for n in nums[5:]])

        msg = f"""✨【超级大乐透第 {data['期号']}期】开奖结果✨
⏰ 开奖日期：{data['开奖日期']}
🎲 开奖号码：
══════════════
{front}   {back}
══════════════
💰 销售额: {fmt_money(data['销售额'])}
🏦 奖池金额: {fmt_money(data['奖池金额'])}

🥇 一等奖：{data['一等奖注数']} 注，单注奖金 {fmt_money(data['一等奖金额'])}
🥈 二等奖：{data['二等奖注数']} 注，单注奖金 {fmt_money(data['二等奖金额'])}
🥉 三等奖：{data['三等奖注数']} 注，单注奖金 {fmt_money(data['三等奖金额'])}

🌐 官方网站：{LOTTERY_CONFIG['dlt']['official']}
"""

    return msg

# ==========================
# 主程序
# ==========================
if __name__=="__main__":
    print("🚀 启动彩票开奖程序...\n")
    lottery_type, config = get_today_lottery()
    if not config:
        exit(0)

    try:
        if lottery_type == 'ssq':
            data = get_latest_ssq()
        else:
            data = get_latest_dlt()

        message = format_message(lottery_type, data)
        print(message)
        notify.send(f"{LOTTERY_CONFIG[lottery_type]['name']}开奖信息", message)
        print("✅ 通知发送完成")

    except Exception as e:
        print(f"❌ 抓取或发送通知失败: {e}")