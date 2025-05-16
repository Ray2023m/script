'''
new Env('阡陌居签到');
cron: 50 6 * * *
'''

import re
import random
import requests
import time
import os
from urllib.parse import urljoin
from datetime import datetime

# 通知模块，适配青龙
try:
    from notify import send
except ImportError:
    def send(title, content):
        print(f"{title}\n{content}")

class QMAutoSigner:
    def __init__(self, cookie):
        self.base_url = "https://www.1000qm.vip/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': self.base_url
        })
        self._set_cookies(cookie)

        self.log_msgs = []

        self.config = {
            'sign_delay': 2,
            'confirm_delay': 1,
            'sign_text': '每天签到一下，希望论坛越来越好！',
            'moods': {
                'kx': '开心',
                'ng': '难过',
                'ym': '郁闷',
                'wl': '无聊',
                'nu': '怒',
                'ch': '擦汗',
                'fd': '奋斗',
                'zm': '睡觉'
            }
        }

    def _set_cookies(self, cookie_str):
        cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key] = value
        self.session.cookies.update(cookies)

    def _log(self, message):
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        print(msg)
        self.log_msgs.append(msg)

    def _get_random_mood(self):
        return random.choice(list(self.config['moods'].keys()))

    def _check_signed(self):
        url = urljoin(self.base_url, "plugin.php?id=dsu_paulsign:sign")
        response = self.session.get(url)
        if "您今天已经签到过了" in response.text:
            return True
        if 'id="mnqian"' in response.text:
            return False
        return True

    def _do_sign(self):
        try:
            url = urljoin(self.base_url, "plugin.php?id=dsu_paulsign:sign")
            response = self.session.get(url)

            formhash_match = re.search(r'formhash=([a-f0-9]+)', response.text)
            if not formhash_match:
                raise Exception("无法获取formhash")
            formhash = formhash_match.group(1)
            self._log(f"获取 formhash 成功: {formhash}")

            mood = self._get_random_mood()
            self._log(f"选择心情: {self.config['moods'][mood]}")

            time.sleep(self.config['sign_delay'])

            sign_url = urljoin(self.base_url, "plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1")
            data = {
                'formhash': formhash,
                'qdxq': mood,
                'qdmode': '1',
                'todaysay': self.config['sign_text'],
                'fastreply': '0'
            }

            response = self.session.post(sign_url, data=data)

            if "签到成功" in response.text:
                msg_match = re.search(r'<div class="c">(.+?)</div>', response.text)
                msg = msg_match.group(1) if msg_match else "签到成功"
                self._log(f"✅ 签到成功: {msg}")
                return True
            elif "已经签到" in response.text:
                self._log("ℹ️ 今日已签到")
                return True
            else:
                raise Exception("签到失败")
        except Exception as e:
            self._log(f"❌ 签到异常: {str(e)}")
            return False

    def _check_task(self):
        try:
            task_url = urljoin(self.base_url, "home.php?mod=task&do=apply&id=1")
            time.sleep(self.config['confirm_delay'])

            response = self.session.get(task_url)
            if "任务已成功申请" in response.text:
                self._log("🎉 威望红包任务申请成功")
            elif "已经申请过此任务" in response.text:
                self._log("ℹ️ 已申请过任务")
            else:
                self._log(f"⚠️ 任务申请失败，响应: {response.text[:80]}")
        except Exception as e:
            self._log(f"❌ 任务申请异常: {str(e)}")

    def auto_sign(self):
        self._log("🚀 开始执行签到任务")
        if self._check_signed():
            self._log("✔️ 今日已签到")
        else:
            if self._do_sign():
                self._log("✅ 签到流程完成")
            else:
                self._log("❌ 签到流程失败")
        self._check_task()
        self._log("🏁 签到任务执行结束")
        send("阡陌居自动签到", "\n".join(self.log_msgs))

# 主程序入口
if __name__ == "__main__":
    cookie = os.environ.get("QMJ_COOKIE")
    if not cookie:
        print("❌ 环境变量 QMJ_COOKIE 未设置")
        send("阡陌居自动签到", "❌ 环境变量 QMJ_COOKIE 未设置，脚本终止")
    else:
        signer = QMAutoSigner(cookie)
        signer.auto_sign()
