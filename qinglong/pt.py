import requests
import os
import datetime
from notify import send  # 青龙通知

# 获取当前日期
print("当前日期:", datetime.date.today())

# 加载环境变量（默认开启，除非手动关闭）
def parse_cookies(cookie_str):
    """解析 `key1=value1; key2=value2` 格式的 Cookies"""
    if not cookie_str:
        return {}
    return dict(pair.split("=", 1) for pair in cookie_str.split("; ") if "=" in pair)

config = {
    "青蛙": {
        "enabled": os.getenv("QWPT_ENABLED", "true").lower() == "true",  # 默认 true
        "url": "https://www.qingwapt.com/shoutbox.php",
        "cookies": parse_cookies(os.getenv("QWPT_COOKIES")),
        "headers": {
            "Host": "www.qingwapt.com",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.qingwapt.com/index.php",
        },
        "texts": ["蛙总，求上传"],
    },
    "zmpt": {
        "enabled": os.getenv("ZMPT_ENABLED", "true").lower() == "true",  # 默认 true
        "url": "https://zmpt.cc/shoutbox.php",
        "cookies": parse_cookies(os.getenv("ZMPT_COOKIES")),
        "headers": {
            "Host": "zmpt.cc",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://zmpt.cc/index.php",
        },
        "texts": ["皮总，求电力", "皮总，求上传"],
    },
}

# 喊话请求函数
def shoutbox_request(name, url, headers, cookies, texts):
    results = []
    for text in texts:
        params = {
            "shbox_text": text,
            "shout": "发送" if "zmpt" in url else "我喊",
            "sent": "yes",
            "type": "shoutbox",
        }
        try:
            response = requests.get(url, headers=headers, cookies=cookies, params=params)
            if response.status_code < 300:
                results.append(f"{name} 喊话成功：{text}")
            else:
                results.append(f"{name} 喊话失败（状态码 {response.status_code}）：{text}")
        except Exception as e:
            results.append(f"{name} 请求异常：{e}")
    return results

# 执行喊话
all_results = []
for site, info in config.items():
    if info["enabled"]:
        if not info["cookies"]:
            print(f"⚠️ {site} 未配置 Cookies，跳过")
            continue
        print(f"🔊 正在执行：{site}")
        result = shoutbox_request(site, info["url"], info["headers"], info["cookies"], info["texts"])
        all_results.extend(result)

# 输出结果
print("\n--- 执行结果 ---")
for res in all_results:
    print(res)

# 发送青龙通知
if all_results:
    send("喊话执行结果", "\n".join(all_results))
