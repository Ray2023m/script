import urllib.request
import datetime
from lxml import etree
import notify
import re

def get_xinfo(url, headers, is_ssq=True):
    try:
        print(f"🌐 正在请求数据：{url}")
        req = urllib.request.Request(url=url, headers=headers)
        res = urllib.request.urlopen(req).read().decode('gb2312')
        print("✅ 成功获取网页内容")

        html = etree.HTML(res)

        title = html.xpath('//div[@class="kjxq_box02_title_left"]/img/@alt')[0]
        period = html.xpath('//font[@class="cfont2"]/strong/text()')[0]
        numbers = html.xpath('//div[@class="ball_box01"]/ul/li/text()')
        # 提取开奖时间和兑奖截止日期
        draw_time_text = html.xpath('//span[@class="span_right"]/text()')[0].strip()
        
        print(f"📌 彩种：{title}")
        print(f"📌 期号：{period}")
        print(f"📌 号码：{' '.join(numbers)}")
        print(f"📌 原始时间文本：{draw_time_text}")

        # 使用正则表达式提取开奖日期和兑奖截止日期
        draw_match = re.search(r'开奖日期：(\d{4}年\d{1,2}月\d{1,2}日)', draw_time_text)
        deadline_match = re.search(r'兑奖截止日期：(\d{4}年\d{1,2}月\d{1,2}日)', draw_time_text)
        
        if not draw_match or not deadline_match:
            raise ValueError("无法从文本中提取日期信息")
        
        draw_date_str = draw_match.group(1)
        deadline_date_str = deadline_match.group(1)
        
        draw_date = datetime.datetime.strptime(draw_date_str, '%Y年%m月%d日')
        deadline_date = datetime.datetime.strptime(deadline_date_str, '%Y年%m月%d日')
        
        # 假设开奖时间是晚上20:30
        draw_date = draw_date.replace(hour=20, minute=30)
        
        weekday_map = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        weekday = weekday_map[draw_date.weekday()]
        formatted_draw_time = draw_date.strftime('%Y年%m月%d日 %H:%M')
        formatted_deadline = deadline_date.strftime('%Y年%m月%d日')
        
        update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        if is_ssq:
            msg = f"""✨【{title}第 {period} 期开奖结果】✨

⏰ 开奖时间：{formatted_draw_time}（{weekday}）
⏳ 兑奖截止日期：{formatted_deadline}

🏆 开奖号码：
════════════════
🔴{numbers[0]}  🔴{numbers[1]}  🔴{numbers[2]}  🔴{numbers[3]}  🔴{numbers[4]}  🔴{numbers[5]}  🔵{numbers[6]}
════════════════

📅 下期开奖：每周二、四、日 20:30
🌐 官方网站：https://www.zhcw.com/kjxx/ssq/
📞 客服电话：95086

🔄 数据更新时间：{update_time}
"""
        else:
            msg = f"""💫【超级大乐透第 {period} 期开奖结果】💫
⏰ 开奖时间：{formatted_draw_time}（{weekday}）
⏳ 兑奖截止日期：{formatted_deadline}

🏆 开奖号码（前区 + 后区）：
══════════════════════
🟡{numbers[0]}  🟡{numbers[1]}  🟡{numbers[2]}  🟡{numbers[3]}  🟡{numbers[4]}   🔵{numbers[5]}  🔵{numbers[6]}
══════════════════════

📅 大乐透开奖日：每周一、三、六 晚上20:30
🌐 官方网站：https://www.lottery.gov.cn/

🔄 数据更新时间：{update_time}

"""
        print("✅ 格式化内容生成完毕")
        return title, msg
    except Exception as e:
        print(f"❌ 出错了: {e}")
        return None, None


if __name__ == '__main__':
    print("🚀 启动彩票开奖查询程序...\n")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
        'Connection': 'keep-alive'
    }

    week = datetime.date.today().strftime('%w')
    is_ssq = week in ['0', '2', '4']  # 判断今天是否是双色球开奖日（0代表星期日）
    url = 'http://kaijiang.500.com/ssq.shtml' if is_ssq else 'http://kaijiang.500.com/dlt.shtml'

    print(f"📅 今天是星期 {week}，正在抓取 {'双色球' if is_ssq else '大乐透'} 开奖信息...\n")

    title, message = get_xinfo(url, headers, is_ssq)

    if title and message:
        print("\n📨 准备发送通知...\n")
        notify.send(title, message)
        print("🏁 程序执行完毕")
    else:
        print("❌ 抓取数据失败，请检查网络连接或网页结构。")
