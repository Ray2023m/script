'''
69机场签到脚本
添加环境变量：ACCOUNT=your.airport.com|you@example.com|yourpassword
'''
import requests
import os
import warnings
import notify  # 确保导入了 notify 模块
from urllib3.exceptions import InsecureRequestWarning

# 忽略所有 InsecureRequestWarning 警告
warnings.simplefilter('ignore', InsecureRequestWarning)

# ========= 简化配置读取 =========
account_str = os.getenv("ACCOUNT", "域名|邮箱|密码").strip()

try:
    domain, email, password = account_str.split("|")
except ValueError:
    raise Exception("❌ ACCOUNT 格式错误，应为: 域名|邮箱|密码")

def checkin():
    try:
        # 如果域名不包含 http 或 https，自动加上 https 前缀
        if not domain.startswith("http"):
            domain_full = f"https://{domain}"
        else:
            domain_full = domain

        session = requests.Session()
        
        # 登录请求
        login_resp = session.post(
            f"{domain_full}/auth/login",
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 Chrome/129.0.0.0',
                'Accept': 'application/json, text/plain, */*',
            },
            json={
                "email": email,
                "passwd": password,
                "remember_me": "on",
                "code": ""
            },
            verify=False  # 禁用 SSL 证书验证
        )

        # 检查登录请求是否成功
        login_resp.raise_for_status()
        login_result = login_resp.json()

        if login_result.get("ret") != 1:
            raise Exception(f"登录失败: {login_result.get('msg', '未知错误')}")

        print("✅ 登录成功")

        # 签到请求
        checkin_resp = session.post(
            f"{domain_full}/user/checkin",
            headers={
                'User-Agent': 'Mozilla/5.0 Chrome/129.0.0.0',
                'Accept': 'application/json, text/plain, */*',
                'X-Requested-With': 'XMLHttpRequest'
            }
        )

        # 检查签到请求是否成功
        checkin_resp.raise_for_status()
        result = checkin_resp.json()
        msg = result.get("msg", "无返回信息")
        status = "✅ 成功" if result.get("ret") == 1 else "⚠️ 可能失败"

        final_msg = f"🎉 签到结果: {status}\n{msg}"
        print(final_msg)

        # 调用 notify 模块的 send 函数发送通知，传递 title 和 content 参数
        title = "✈️69机场签到通知"  # 设置标题
        notify.send(title=title, content=final_msg)

    except requests.exceptions.RequestException as e:
        # 捕获网络请求相关异常
        error_msg = f"❌ 网络请求失败: {str(e)}"
        print(error_msg)
        notify.send(title="签到错误", content=error_msg)
    except Exception as e:
        # 捕获其他异常
        error_msg = f"❌ 签到异常: {str(e)}"
        print(error_msg)
        notify.send(title="签到异常", content=error_msg)

if __name__ == '__main__':
    checkin()
