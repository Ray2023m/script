#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
cron: 40 6 * * *
new Env('GLaDOS签到');
使用方法：青龙面板 添加环境变量：GLADOS_COOKIE
'''

import os
import time
import requests
import json
import logging
from datetime import date, timedelta
import notify  

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def get_cookies():
    raw = os.environ.get("GLADOS_COOKIE")
    if not raw:
        logging.error("未获取到环境变量 GLADOS_COOKIE")
        return []
    if '&' in raw:
        return raw.split('&')
    elif '\n' in raw:
        return raw.split('\n')
    else:
        return [raw]

def checkin(cookie):
    checkin_url = "https://glados.rocks/api/user/checkin"
    status_url = "https://glados.rocks/api/user/status"
    headers = {
        'cookie': cookie,
        'referer': 'https://glados.rocks/console/checkin',
        'origin': 'https://glados.rocks',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36',
        'content-type': 'application/json;charset=UTF-8',
    }
    payload = {'token': 'glados.one'}

    try:
        start_time = time.time()
        checkin_resp = requests.post(checkin_url, headers=headers, data=json.dumps(payload))
        status_resp = requests.get(status_url, headers=headers)
        time_used = time.time() - start_time

        checkin_json = checkin_resp.json()
        status_json = status_resp.json()

        message = checkin_json.get('message', '无返回信息')
        email = status_json['data'].get('email', '未知账号')
        left_days = int(float(status_json['data'].get('leftDays', 0)))

        points_balance = int(float(checkin_json['list'][0]['balance']))
        change = int(float(checkin_json['list'][0]['change']))
        change_str = f"+{change}" if change >= 0 else str(change)

        exp_date = (date.today() + timedelta(days=left_days)).strftime('%Y-%m-%d')

        result = (
            f"账号：{email}\n"
            
            f"📬 GLaDOS机场 签到结果\n"
            
            f"✅ 状态：{message}\n"
            
            f"🕐 用时：{time_used:.2f}s\n"
            
            f"🧧 积分余额：{points_balance} ({change_str})\n"
            
            f"⏳ 剩余会员：{left_days} 天（到期时间：{exp_date}）\n"
        )

        return result

    except Exception as e:
        logging.error(f"签到异常：{e}")
        return None

def main():
    cookies = get_cookies()
    if not cookies:
        print("未获取到有效Cookie")
        return

    all_results = []
    for i, cookie in enumerate(cookies, 1):
        print(f"---- 第 {i} 个账号开始签到 ----")
        result = checkin(cookie)
        if result:
            print(result)
            all_results.append(result)
        else:
            print("签到失败，请检查Cookie或网络")

    if all_results:
        notify.send("GLaDOS 签到通知", "\n".join(all_results))
    else:
        notify.send("GLaDOS 签到通知", "所有账号签到失败，请检查Cookie或网络")

if __name__ == "__main__":
    main()
