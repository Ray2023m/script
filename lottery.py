'''
new Env('彩票开奖信息')
cron: 20 22 * * *
'''

import requests
import datetime
import notify

# ✅ 彩票配置
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

# ✅ 判断今天是否有开奖
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

# ✅ 自动重试请求
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

# ✅ 获取双色球最新一期
def get_latest_ssq():
    config = LOTTERY_CONFIG['ssq']
    headers = {"User-Agent":"Mozilla/5.0","Referer":config['official']}
    params = {"name":"ssq","issueCount":1}
    resp = get_with_retries(config['url'], headers=headers, params=params)
    data = resp.json()
    result = data["result"][0]
    numbers = result["red"] + " + " + result["blue"]
    first = result["prizegrades"][0]
    second = result["prizegrades"][1]
    third = result["prizegrades"][2] if len(result.get("prizegrades",[]))>2 else {}
    return {
        "期号": result["code"],
        "开奖日期": result["date"],
        "开奖号码": numbers,
        "销售额": result["sales"],
        "一等奖注数": first["typenum"],
        "一等奖金额": first["typemoney"],
        "二等奖注数": second["typenum"],
        "二等奖金额": second["typemoney"],
        "三等奖注数": third.get("typenum","-"),
        "三等奖金额": third.get("typemoney","-"),
        "奖池金额": result["poolmoney"]
    }

# ✅ 获取大乐透最新一期（一、二、三等奖）
def get_latest_dlt():
    config = LOTTERY_CONFIG['dlt']
    headers = {"User-Agent":"Mozilla/5.0","Referer":config['official']}
    params = {"gameNo":"85","provinceId":"0","pageSize":"1","isVerify":"1"}
    resp = get_with_retries(config['url'], headers=headers, params=params)
    data = resp.json()
    latest = data.get("value",{}).get("list",[{}])[0]
    prize_list = latest.get("prizeLevelList",[])

    def safe_get(idx):
        if idx < len(prize_list):
            p = prize_list[idx]
            return p.get("stakeCount","-"), p.get("totalPrizeamount","-")
        return "-","-"

    first_count, first_amount = safe_get(0)
    second_count, second_amount = safe_get(2)
    third_count, third_amount = safe_get(4)

    def fmt_money(x):
        try:
            return f"{int(float(x)):,} 元"
        except:
            return f"{x} 元"

    # 处理开奖号码
    numbers = latest.get("lotteryDrawResult","-").replace(',', ' ').split()
    front_nums = numbers[:5]
    back_nums = numbers[5:]
    front_str = ' '.join([f"🟡{n}" for n in front_nums])
    back_str = ' '.join([f"🔵{n}" for n in back_nums])

    return {
        "期号": latest.get("lotteryDrawNum","-"),
        "开奖日期": latest.get("lotteryDrawTime","-"),
        "开奖号码": f"{front_str}   {back_str}",
        "销售额": fmt_money(latest.get("totalSaleAmount","-")),
        "奖池金额": fmt_money(latest.get("poolBalanceAfterdraw","-")),
        "一等奖注数": first_count,
        "一等奖金额": fmt_money(first_amount),
        "二等奖注数": second_count,
        "二等奖金额": fmt_money(second_amount),
        "三等奖注数": third_count,
        "三等奖金额": fmt_money(third_amount)
    }

# ✅ 格式化消息
def format_message(lottery_type,data):
    def fmt_money(val):
        try:
            return f"{int(float(val)):,} 元"
        except:
            return f"{val} 元"

    if lottery_type=='ssq':
        red_nums = data['开奖号码'].split(' + ')[0].replace(',',' ').split()
        blue_num = data['开奖号码'].split(' + ')[1]
        red_balls = ' '.join([f"🔴{n}" for n in red_nums])
        blue_ball = f"🔵{blue_num}"
        msg = f"""✨【双色球第 {data['期号']}期】开奖结果✨
⏰ 开奖日期：{data['开奖日期']}
🎲 开奖号码：
══════════════
{red_balls}  {blue_ball}
══════════════
💰 销售额: {fmt_money(data['销售额'])}
🏦 奖池金额: {fmt_money(data['奖池金额'])}

🥇 一等奖：{data['一等奖注数']} 注，单注奖金 {fmt_money(data['一等奖金额'])}
🥈 二等奖：{data['二等奖注数']} 注，单注奖金 {fmt_money(data['二等奖金额'])}
🥉 三等奖：{data['三等奖注数']} 注，单注奖金 {fmt_money(data['三等奖金额'])}

🌐 官方网站：{LOTTERY_CONFIG['ssq']['official']}
"""
    else:
        nums = data['开奖号码'].replace(',','').split()
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

# ✅ 主程序
if __name__=="__main__":
    print("🚀 启动彩票开奖程序...\n")
    lottery_type,config = get_today_lottery()
    if not config:
        exit(0)
    try:
        if lottery_type=='ssq':
            data = get_latest_ssq()
        else:
            data = get_latest_dlt()
        message = format_message(lottery_type,data)
        print(message)
        notify.send(f"{LOTTERY_CONFIG[lottery_type]['name']}开奖信息", message)
        print("✅ 通知发送完成")
    except Exception as e:
        print(f"❌ 抓取或发送通知失败: {e}")