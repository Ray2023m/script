#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阡陌居签到脚本
版本: 1.0.0
作者: madrays
功能:
- 自动完成阡陌居每日签到
- 支持签到失败重试
- 保存签到历史记录
- 提供详细的签到信息显示
"""

import os
import re
import time
import json
import random
import requests
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urljoin
from lxml import etree

# 通知模块，适配青龙面板
try:
    from notify import send
except ImportError:
    def send(title, content):
        print(f"{title}\n{content}")

# 默认环境变量
os.environ.setdefault('QMJ_MAX_RETRIES', '3')
os.environ.setdefault('QMJ_RETRY_INTERVAL', '30')

# 青龙面板环境变量
COOKIE = os.getenv('QMJ_COOKIE', '')  # 阡陌居Cookie
MAX_RETRIES = int(os.getenv('QMJ_MAX_RETRIES', '3'))  # 最大重试次数
RETRY_INTERVAL = int(os.getenv('QMJ_RETRY_INTERVAL', '30'))  # 重试间隔(秒)

class QMJSign:
    def __init__(self):
        self.cookie = COOKIE
        self.max_retries = MAX_RETRIES
        self.retry_interval = RETRY_INTERVAL
        self.history_file = 'qmj_sign_history.json'
        self.base_url = "https://www.1000qm.vip/"
        self.session = requests.Session()
        self.log_msgs = []  # 存储日志消息
        
        # 设置请求头
        self.session.headers.update({
            "Host": "www.1000qm.vip",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.160 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9"
        })

        # 配置参数
        self.config = {
            'sign_delay': 2,        # 签到延迟
            'confirm_delay': 1,     # 确认延迟
            'sign_text': '每天签到一下，希望论坛越来越好！',  # 签到感言
            'moods': {  # 签到心情选项
                'kx': '开心', 'ng': '难过', 'ym': '郁闷', 'wl': '无聊',
                'nu': '怒', 'ch': '擦汗', 'fd': '奋斗', 'zm': '睡觉'
            }
        }

    def _log(self, message):
        """记录日志"""
        print(message)
        self.log_msgs.append(message)

    def _get_random_mood(self):
        """随机选择签到心情"""
        return random.choice(list(self.config['moods'].keys()))

    def sign(self, retry_count=0):
        """执行签到"""
        self._log("🚀 阡陌居签到开始")
        
        # 检查Cookie
        if not self.cookie:
            self._log("❌ 未配置Cookie，请在环境变量中设置QMJ_COOKIE")
            return
        
        # 解析Cookie
        cookies = {}
        try:
            for cookie_item in self.cookie.split(';'):
                if '=' in cookie_item:
                    name, value = cookie_item.strip().split('=', 1)
                    cookies[name] = value
            self.session.cookies.update(cookies)
        except Exception as e:
            self._log(f"❌ Cookie解析错误: {str(e)}")
            return

        # 检查Cookie是否有效
        if not self._check_cookie_valid():
            self._log("❌ Cookie无效或已过期，请更新Cookie")
            return

        # 检查今日是否已签到
        if self._is_already_signed_today():
            self._log("✔️ 今日已签到")
            self._fetch_sign_info()
            return

        try:
            # 访问首页获取formhash
            self._log("正在访问阡陌居首页...")
            response = self.session.get(self.base_url, timeout=10)
            formhash_match = re.search(r'name="formhash" value="(.+)"', response.text)
            
            if not formhash_match:
                if retry_count < self.max_retries:
                    self._log(f"未找到formhash参数，{self.retry_interval}秒后进行第{retry_count+1}次重试...")
                    time.sleep(self.retry_interval)
                    return self.sign(retry_count + 1)
                else:
                    self._log("❌ 未找到formhash参数，请检查站点是否变更")
                    return

            formhash = formhash_match.group(1)
            self._log(f"成功获取formhash: {formhash[:10]}...")

            # 随机选择心情
            mood = self._get_random_mood()
            time.sleep(self.config['sign_delay'])

            # 执行签到
            self._log("正在执行签到...")
            sign_url = urljoin(self.base_url, "plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1")
            post_data = {
                "formhash": formhash,
                "qdxq": mood,
                "qdmode": "1",
                "todaysay": self.config['sign_text'],
                "fastreply": "0"
            }

            response = self.session.post(sign_url, data=post_data, timeout=15)
            log_match = re.search(r'<div class="c">([^>]+)<', response.text)

            if log_match:
                log_message = log_match.group(1).strip()
                self._log(f"签到响应消息: {log_message}")

                # 处理签到结果
                if "成功" in log_message or "签到" in log_message:
                    self._handle_success(log_message)
                elif "已经签到" in log_message or "已签到" in log_message:
                    self._handle_already_signed(log_message)
                else:
                    self._handle_failure(log_message)
            else:
                if retry_count < self.max_retries:
                    self._log(f"未找到响应消息，{self.retry_interval}秒后进行第{retry_count+1}次重试...")
                    time.sleep(self.retry_interval)
                    return self.sign(retry_count + 1)
                else:
                    self._log("❌ 未找到响应消息，请检查站点是否变更")

        except requests.Timeout:
            if retry_count < self.max_retries:
                self._log(f"请求超时，{self.retry_interval}秒后进行第{retry_count+1}次重试...")
                time.sleep(self.retry_interval)
                return self.sign(retry_count + 1)
            else:
                self._log("❌ 请求多次超时，请检查网络连接")
        except Exception as e:
            self._log(f"❌ 发生错误: {str(e)}")

        # 申请威望红包任务
        self._check_task()
        
        # 发送通知
        send("阡陌居自动签到", "\n".join(self.log_msgs))

    def _check_cookie_valid(self) -> bool:
        """检查Cookie是否有效"""
        try:
            response = self.session.get(self.base_url, timeout=10)
            return "退出" in response.text or "个人资料" in response.text or "用户名" in response.text
        except:
            return False

    def _is_already_signed_today(self) -> bool:
        """检查今天是否已经成功签到"""
        try:
            if not os.path.exists(self.history_file):
                return False

            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

            today = datetime.now().strftime('%Y-%m-%d')
            today_records = [
                record for record in history
                if record.get("date", "").startswith(today)
                and record.get("status") in ["签到成功", "已签到"]
            ]

            return len(today_records) > 0
        except:
            return False

    def _save_sign_history(self, sign_data: Dict):
        """保存签到历史记录"""
        try:
            history = []
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)

            history.append(sign_data)
            
            # 只保留最近30天的记录
            retention_days = 30
            now = datetime.now()
            valid_history = []
            
            for record in history:
                try:
                    record_date = datetime.strptime(record["date"], '%Y-%m-%d %H:%M:%S')
                    if (now - record_date).days < retention_days:
                        valid_history.append(record)
                except:
                    continue

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(valid_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"保存签到历史记录失败: {str(e)}")

    def _handle_success(self, message: str):
        """处理签到成功"""
        sign_dict = {
            "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "status": "签到成功",
            "message": message
        }
        
        # 尝试提取积分信息
        points_match = re.search(r'(\d+)', message)
        if points_match:
            sign_dict["points"] = points_match.group(1)
        
        self._save_sign_history(sign_dict)
        self._fetch_sign_info()

    def _handle_already_signed(self, message: str):
        """处理已签到情况"""
        sign_dict = {
            "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "status": "已签到",
            "message": message
        }
        self._save_sign_history(sign_dict)
        self._fetch_sign_info()

    def _handle_failure(self, message: str):
        """处理签到失败"""
        sign_dict = {
            "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "status": f"签到失败: {message}",
            "message": message
        }
        self._save_sign_history(sign_dict)
        self._log(f"❌ 签到失败: {message}")

    def _fetch_sign_info(self):
        """获取并显示签到信息"""
        try:
            url = urljoin(self.base_url, "plugin.php?id=dsu_paulsign:sign")
            response = self.session.get(url)
            html = etree.HTML(response.text)
            
            # 使用XPath提取签到信息
            p_list = html.xpath("//div[@class='mn']//p")

            if not p_list or len(p_list) < 5:
                self._log("⚠️ 未能提取到完整签到信息")
                return

            def parse_sign_info(p_elements):
                """解析签到信息"""
                data = {}
                
                # 解析用户名
                p1 = p_elements[0]
                username = p1.xpath("./font/b/text()")
                data["用户名"] = username[0] if username else ""
                
                # 累计签到天数
                sign_days = html.xpath("//p[contains(., '累计已签到')]/b[1]/text()")[0]
                data["累计签到天数"] = sign_days

                # 本月签到天数
                p2 = p_elements[1]
                month_days = p2.xpath("./b/text()")
                data["本月签到天数"] = month_days[0] if month_days else ""

                # 上次签到时间
                p3 = p_elements[2]
                last_sign_time = p3.xpath("./font/text()")
                data["上次签到时间"] = last_sign_time[0] if last_sign_time else ""

                # 铜币奖励信息
                p4 = p_elements[3]
                coins = p4.xpath("./font/b/text()")
                data["总奖励铜币"] = coins[0] if len(coins) > 0 else ""
                data["上次奖励铜币"] = coins[1] if len(coins) > 1 else ""

                # 等级信息
                p5 = p_elements[4]
                levels = p5.xpath("./font/b/text()")
                data["当前等级"] = levels[0] if len(levels) > 0 else ""
                data["升级所需天数"] = levels[1] if len(levels) > 1 else ""
                data["下一等级"] = levels[2] if len(levels) > 2 else ""

                return data

            # 解析并显示信息
            info = parse_sign_info(p_list)
            
            # 格式化输出签到信息
            self._log(f"👤 用户名: {info.get('用户名', '')}")
            self._log(f"📆 本月签到: {info.get('本月签到天数', '')} 天")
            self._log(f"📅 累计签到: {info.get('累计签到天数', '')} 天")
            self._log(f"⏰ 今天签到: {info.get('上次签到时间', '')}")
            self._log(f"💰 今天奖励: 获得 {info.get('上次奖励铜币', '')} 铜币,累计获得 {info.get('总奖励铜币', '')} 铜币")
            self._log(f"🏅 当前等级: {info.get('当前等级', '')}")
            self._log(f"🔜 下一等级: {info.get('下一等级', '')}, 还需要 {info.get('升级所需天数', '')} 天")
                
        except Exception as e:
            self._log(f"⚠️ 签到信息提取失败：{str(e)}")

    def _check_task(self):
        """检查并申请威望红包任务"""
        try:
            task_url = urljoin(self.base_url, "home.php?mod=task&do=apply&id=1")
            time.sleep(self.config['confirm_delay'])
            response = self.session.get(task_url)

            if "任务已成功申请" in response.text:
                self._log("🎉 威望红包任务申请成功")
            elif "已经申请过此任务" in response.text:
                # 不显示已申请过的消息，减少输出
                pass
            else:
                # 不显示任务申请失败的消息，减少输出
                pass
                
        except Exception as e:
            # 不显示任务申请异常，减少输出
            pass

if __name__ == "__main__":
    signer = QMJSign()
    signer.sign()