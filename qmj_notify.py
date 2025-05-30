#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阡陌居论坛自动签到脚本
功能：自动完成每日签到并申请威望红包任务
适配：青龙面板等自动化工具
作者：原代码来源未知
"""

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
from lxml import etree

# 通知模块，适配青龙面板
try:
    from notify import send
except ImportError:
    def send(title, content):
        print(f"{title}\n{content}")

class QMAutoSigner:
    """阡陌居自动签到类"""
    
    def __init__(self, cookie):
        """初始化签到器
        
        Args:
            cookie (str): 论坛登录cookie字符串
        """
        self.base_url = "https://www.1000qm.vip/"
        self.session = requests.Session()
        
        # 设置请求头，模拟浏览器访问
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': self.base_url
        })
        
        self._set_cookies(cookie)
        self.log_msgs = []  # 存储日志消息
        
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

    def _set_cookies(self, cookie_str):
        """解析并设置cookie"""
        cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key] = value
        self.session.cookies.update(cookies)

    def _log(self, message):
        """记录日志"""
        print(message)
        self.log_msgs.append(message)

    def _get_random_mood(self):
        """随机选择签到心情"""
        return random.choice(list(self.config['moods'].keys()))

    def _check_signed(self):
        """检查今日是否已签到"""
        url = urljoin(self.base_url, "plugin.php?id=dsu_paulsign:sign")
        try:
            response = self.session.get(url)
            
            # 检查是否需要登录
            if "需要先登录" in response.text or "您需要先登录" in response.text:
                self._log("❌ 未登录或cookie已失效")
                return None
            
            # 检查插件是否存在
            if "插件不存在" in response.text or "已关闭" in response.text:
                self._log("❌ 签到插件不存在或已关闭")
                return None
            
            # 检查是否已签到
            if "您今天已经签到过了" in response.text or "今日已签到" in response.text:
                return True
                
            # 检查签到按钮是否存在
            if 'id="mnqian"' in response.text or "签到按钮" in response.text:
                return False
            
            return True  # 默认已签到，避免重复尝试
            
        except Exception as e:
            self._log(f"❌ 检查签到状态异常: {str(e)}")
            return None

    def _do_sign(self):
        """执行签到操作"""
        try:
            # 1. 获取签到页面和formhash
            url = urljoin(self.base_url, "plugin.php?id=dsu_paulsign:sign")
            response = self.session.get(url)
            
            # 检查页面是否正常加载
            if response.status_code != 200:
                raise Exception(f"页面加载失败，状态码: {response.status_code}")
            
            # 多种方式尝试获取formhash
            formhash_patterns = [
                r'formhash=([a-f0-9]+)',
                r'name="formhash"[^>]*value="([a-f0-9]+)"',
                r'<input[^>]*name="formhash"[^>]*value="([a-f0-9]+)"'
            ]
            
            formhash = None
            for pattern in formhash_patterns:
                match = re.search(pattern, response.text)
                if match:
                    formhash = match.group(1)
                    break
            
            if not formhash:
                raise Exception("无法获取formhash")

            # 2. 随机选择心情
            mood = self._get_random_mood()
            time.sleep(self.config['sign_delay'])

            # 3. 提交签到请求
            sign_url = urljoin(self.base_url, "plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1")
            
            # 构建签到数据
            data = {
                'formhash': formhash,
                'qdxq': mood,           # 签到心情
                'qdmode': '1',          # 签到模式
                'todaysay': self.config['sign_text'],  # 签到感言
                'fastreply': '0'
            }

            # 设置请求头
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': url
            }
            
            response = self.session.post(sign_url, data=data, headers=headers)
            response_text = response.text.strip()

            # 4. 检查签到结果
            if "签到成功" in response.text:
                # 尝试提取成功消息
                success_patterns = [
                    r'<div class="c">(.+?)</div>',
                    r'签到成功[^<]*([^<]+)',
                    r'恭喜[^<]*([^<]+)'
                ]
                
                msg = "签到成功"
                for pattern in success_patterns:
                    match = re.search(pattern, response.text)
                    if match:
                        msg = match.group(1).strip()
                        break
                
                self._log(f"✅ {msg}")
                self._fetch_sign_info()
                return True
                
            elif "已经签到" in response.text or "今天已经签到" in response.text:
                self._log("ℹ️ 今日已签到")
                self._fetch_sign_info()
                return True
                
            else:
                raise Exception(f"签到失败: {response_text[:100]}")
                
        except Exception as e:
            self._log(f"❌ 签到失败: {str(e)}")
            return False

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

    def auto_sign(self):
        """执行自动签到主流程"""
        self._log("🚀 阡陌居签到开始")
        
        # 检查cookie是否有效
        try:
            test_response = self.session.get(self.base_url)
            if test_response.status_code != 200:
                self._log(f"❌ 网站访问异常，状态码: {test_response.status_code}")
                return
        except Exception as e:
            self._log(f"❌ 网站连接失败: {str(e)}")
            return
        
        # 检查是否已签到
        sign_status = self._check_signed()
        
        if sign_status is None:
            self._log("❌ 无法检查签到状态，可能是cookie失效或网站异常")
        elif sign_status:
            self._log("✔️ 今日已签到")
            self._fetch_sign_info()
        else:
            # 执行签到
            if self._do_sign():
                pass  # 签到成功的消息在_do_sign中已显示
            else:
                self._log("❌ 签到失败")
        
        # 申请威望红包任务
        self._check_task()
        
        # 发送通知
        send("阡陌居自动签到", "\n".join(self.log_msgs))

# 主程序入口
if __name__ == "__main__":
    # 从环境变量获取cookie
    cookie = os.environ.get("QMJ_COOKIE")
    
    if not cookie:
        print("❌ 环境变量 QMJ_COOKIE 未设置")
        send("阡陌居自动签到", "❌ 环境变量 QMJ_COOKIE 未设置，脚本终止")
    else:
        # 创建签到器并执行签到
        signer = QMAutoSigner(cookie)
        signer.auto_sign()