'''
new Env('阡陌居签到');
cron: 50 6 * * *
'''

import requests
import notify
from lxml import etree

url = "https://www.1000qm.vip/plugin.php?id=dsu_paulsign:sign"
headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36",
    "cookie": "_dx_captcha_cid=25423253; _dx_uzZo5y=0246037c1bcd9a38415608d532429ad8d1564192f42c74026ee890676ee54206763327cb; flo1_2132_widthauto=-1; _dx_FMrPY6=6825837eMltQy4VHYqXbD2rMPNstVYY6eyEfmgu1; _dx_app_captchadiscuzpluginbydingxiang2017=6825837eMltQy4VHYqXbD2rMPNstVYY6eyEfmgu1; flo1_2132_saltkey=RYFRJqJf; flo1_2132_lastvisit=1747443540; _dx_captcha_vid=605720B52C2F4670CD878791D72179A6C3960742F7B051E1A32F3731566A673522AE1A4C1ADA85BEC8D6C6BDA651031EB9A44893432C8C7D7824BDEC07FD8F64220D0AAC8DD5C68C9B02D6CC9CB5E1C4; flo1_2132_auth=a835etNLCGo1t0GqYLDJ5CUOdUTMYMdK9WkyMkkVlYSogfeQgSnJlOOds8I6mrI1nwy1v4SXuOry02MY3cv6vGSqyg; flo1_2132_nofavfid=1; flo1_2132_pc_size_c=0; flo1_2132_myrepeat_rr=R0; flo1_2132_ulastactivity=7288Y0AeSkCYPQkWI0gtP10jnk5cg%2BhPv%2Bt%2B0BilNdC3tdSOfY2D; flo1_2132_smile=1D1; flo1_2132_forum_lastvisit=D_57_1747610616D_91_1747610860D_30_1747610868D_35_1747610871D_38_1747610891D_95_1747610924D_90_1747610929D_37_1747610942; flo1_2132_visitedfid=25D37D90D95D38D35D30D91D57; flo1_2132_sid=Djl7lA; flo1_2132_lip=163.125.183.104%2C1747610457; flo1_2132_sendmail=1; flo1_2132_lastcheckfeed=11618%7C1747618249; flo1_2132_lastact=1747618251%09misc.php%09patch"
}
response = requests.get(url, headers=headers,)
response.raise_for_status()
html = etree.HTML(response.text)

# 用户名
username = html.xpath("//p/font[@color='#FF0000']/b/text()")[0]

# 累计签到天数
total_days = html.xpath("//p[contains(., '累计已签到')]/b[1]/text()")[0]

# 本月签到天数
month_days = html.xpath("//p[contains(., '本月已累计签到')]/b[1]/text()")[0]

# 上次签到时间
last_signin_time = html.xpath("//p[contains(., '上次签到时间')]/font/text()")[0]

# 当前总奖励铜币
total_reward = html.xpath("//p[contains(., '总奖励为')]/font[1]/b/text()")[0]

# 上次奖励铜币
last_reward = html.xpath("//font[@color='#ff00cc'][2]/b/text()")[0]
# 当前等级
current_level = html.xpath("//font[@color='green'][1]/b/text()")[0]


# # 距离升级还需天数
#days_to_next = html.xpath('//p[contains(., "Tips")]//font[contains(@color, "#FF0000")]/b[1]/text()')[0]
days_to_next = html.xpath('//p[contains(., "Tips")]/font[2]/b[1]/text()')[0]
# # 下一级等级
next_level = html.xpath("//font[@color='#FF0000'][2]/b/text()")[0]

message = f"""
👤  用户名: {username}
📆 本月签到: {month_days} 天
📅 累计签到: {total_days} 天
⏰ 今天签到: {last_signin_time}
💰 今天奖励: 获得 {last_reward} 铜币,累计获得 {total_reward} 铜币
🏅 当前等级: {current_level}
🔜 下一等级: {next_level}, 还需要 {days_to_next} 天
"""
notify.send(title="阡陌居签到信息", content=message)