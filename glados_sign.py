#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: Gladoscheckin.py(GLaDOS签到)
Author: Hennessey
cron: 40 6 * * *
new Env('GLaDOS签到');
Update: 2023/7/27
使用方法：青龙面板 添加环境变量：GR_COOKIE
"""

import requests
import json
import os
import sys
import time

# 导入通知模块
try:
    import notify
except ImportError:
    notify = None

# 获取GlaDOS账号Cookie
def get_cookies():
    if os.environ.get("GR_COOKIE"):
        print("已获取并使用Env环境 Cookie")
        if '&' in os.environ["GR_COOKIE"]:
            cookies = os.environ["GR_COOKIE"].split('&')
        elif '\n' in os.environ["GR_COOKIE"]:
            cookies = os.environ["GR_COOKIE"].split('\n')
        else:
            cookies = [os.environ["GR_COOKIE"]]
    else:
        from config import Cookies
        cookies = Cookies
        if len(cookies) == 0:
            print("未获取到正确的GlaDOS账号Cookie")
            return
    print(f"共获取到{len(cookies)}个GlaDOS账号Cookie\n")
    print(f"脚本执行时间(北京时区): {time.strftime('%Y/%m/%d %H:%M:%S', time.localtime())}\n")
    return cookies

# GlaDOS签到
def checkin(cookie):
    checkin_url = "https://glados.rocks/api/user/checkin"
    state_url = "https://glados.rocks/api/user/status"
    referer = 'https://glados.rocks/console/checkin'
    origin = "https://glados.rocks"
    useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36"
    payload = {
        'token': 'glados.one'
    }

    try:
        checkin_resp = requests.post(checkin_url, headers={
            'cookie': cookie,
            'referer': referer,
            'origin': origin,
            'user-agent': useragent,
            'content-type': 'application/json;charset=UTF-8'
        }, data=json.dumps(payload))

        state_resp = requests.get(state_url, headers={
            'cookie': cookie,
            'referer': referer,
            'origin': origin,
            'user-agent': useragent
        })

    except Exception as e:
        print(f"签到失败，请检查网络：{e}")
        return None, None, None

    try:
        mess = checkin_resp.json().get('message', '无返回信息')
        mail = state_resp.json()['data']['email']
        left_days = state_resp.json()['data']['leftDays']
        time_left = int(float(left_days))  # 防止 split 报错
    except Exception as e:
        print(f"解析登录结果失败：{e}")
        return None, None, None

    return mess, time_left, mail

# 执行签到任务
def run_checkin():
    contents = []
    cookies = get_cookies()
    if not cookies:
        return ""

    for cookie in cookies:
        ret, remain, email = checkin(cookie)
        if not ret:
            continue

        content = f"账号：{email}\n签到结果：{ret}\n剩余天数：{remain}\n"
        print(content)
        contents.append(content)

    contents_str = "".join(contents)
    return contents_str

if __name__ == '__main__':
    title = "GlaDOS签到通知"
    contents = run_checkin()

    if notify:
        if contents == '':
            contents = '签到失败，请检查账户信息以及网络环境'
            print(contents)
        notify.send(title, contents)
