"""
cron: 40 6 * * *
new Env('和风天气推送');
# 说明：获取深圳光明区天气信息并推送
# 2025年5月19日更新
# @author: Alchemy

环境变量配置说明（适用于青龙面板）：
- QWEATHER_PRIVATE_KEY ：和风天气API私钥，换行用\\n转义
- QWEATHER_PROJECT_ID  ：项目ID，示例 "3A8X"
- QWEATHER_KEY_ID      ：Key ID，示例 "TW"
- QWEATHER_LOCATION    ：地理位置编码，示例 "101280610"（深圳光明区）

示例：
QWEATHER_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwRpe+Nr6LTkySuLtDhG/s1\n-----END PRIVATE KEY-----  #注意参照格式
QWEATHER_PROJECT_ID=3A8X
QWEATHER_KEY_ID=TW
QWEATHER_LOCATION=101280610
"""

import os
import time
import jwt
import requests
import notify  # 你已有的通知模块

class QWeatherClient:
    def __init__(self, private_key: str, project_id: str, key_id: str, location: str):
        self.private_key = private_key
        self.project_id = project_id
        self.key_id = key_id
        self.location = location
        self.base_url = "https://ne2mtdcmff.re.qweatherapi.com/v7/weather/now"

    def generate_jwt(self) -> str | None:
        now = int(time.time())
        payload = {
            "sub": self.project_id,
            "iat": now - 30,
            "exp": now + 900
        }
        headers = {
            "alg": "EdDSA",
            "kid": self.key_id
        }
        try:
            token = jwt.encode(payload, self.private_key, algorithm="EdDSA", headers=headers)
            return token
        except Exception as e:
            print(f"[ERROR] JWT 生成失败：{e}")
            return None

    def fetch_weather(self) -> dict | None:
        token = self.generate_jwt()
        if not token:
            return None

        headers = {
            "Authorization": f"Bearer {token}"
        }
        params = {
            "location": self.location
        }

        try:
            response = requests.get(self.base_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"[ERROR] 请求失败：{e}")
            return None

    def parse_weather(self, data: dict) -> str:
        now_data = data.get('now', {})
        if not now_data:
            return "未获取到天气信息。"

        weather = now_data.get('text', '未知')
        temperature = now_data.get('temp', '未知')
        humidity = now_data.get('humidity', '未知')
        wind_speed = now_data.get('windSpeed', '未知')
        wind_direction = now_data.get('windDir', '未知')

        message = (
            f"🌤️ 深圳光明区天气信息：\n\n"
            f"☁️ 天气：{weather}\n"
            f"🌡️ 温度：{temperature}°C\n"
            f"💧 湿度：{humidity}%\n"
            f"💨 风速：{wind_speed} km/h\n"
            f"🌀 风向：{wind_direction}\n\n"
            "📅 天气数据来源：和风天气\n"
            "🌐 官方网站：www.qweather.com\n"
        )
        return message


def main():
    private_key = os.getenv("QWEATHER_PRIVATE_KEY", "").replace("\\n", "\n")
    project_id = os.getenv("QWEATHER_PROJECT_ID", "3A8X")
    key_id = os.getenv("QWEATHER_KEY_ID", "TW")
    location = os.getenv("QWEATHER_LOCATION", "101280610")

    if not private_key:
        print("[ERROR] 请设置环境变量：QWEATHER_PRIVATE_KEY")
        return

    client = QWeatherClient(private_key, project_id, key_id, location)
    data = client.fetch_weather()
    if data:
        message = client.parse_weather(data)
        print(message)
        notify.send(title="深圳光明区天气", content=message)  # 传入标题和内容
    else:
        print("获取天气数据失败。")


if __name__ == "__main__":
    main()
