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
import datetime
import notify


class QWeatherForecastClient:
    def __init__(self, private_key, project_id, key_id, location, forecast_days='3d'):
        self.private_key = private_key
        self.project_id = project_id
        self.key_id = key_id
        self.location = location
        self.forecast_days = forecast_days
        self.base_url = f"https://ne2mtdcmff.re.qweatherapi.com/v7/weather/{forecast_days}"

    def generate_jwt(self):
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
            if isinstance(token, bytes):
                token = token.decode('utf-8')
            return token
        except Exception as e:
            print(f"[ERROR] JWT生成失败: {e}")
            return None

    def fetch_forecast(self):
        token = self.generate_jwt()
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}
        params = {"location": self.location, "lang": "zh", "unit": "m"}
        try:
            response = requests.get(self.base_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] 请求天气预报失败: {e}")
            return None

    def parse_forecast(self, data):
        daily_list = data.get('daily', [])
        if not daily_list:
            return "未获取到天气预报数据。"

        MOON_PHASE_MAP = {
            "800": "🌑 新月",
            "801": "🌒 娥眉月",
            "802": "🌓 上弦月",
            "803": "🌖 盈凸月",
            "804": "🌕 满月",
            "805": "🌔 娥眉残月",
            "806": "🌘 下弦月",
        }

        lines = []
        for day in daily_list:
            moon_icon_code = day.get('moonPhaseIcon', '')
            moon_emoji = MOON_PHASE_MAP.get(moon_icon_code, day.get('moonPhase', '未知月相'))

            day_line = (
                f"📅 {day.get('fxDate', '')}  白天: {day.get('textDay', '')}  夜晚: {day.get('textNight', '')}\n"
                f"🌡️ 温度: {day.get('tempMin', '')}°C ~ {day.get('tempMax', '')}°C  "
                f"💨 风: {day.get('windDirDay', '')} {day.get('windScaleDay', '')}级  "
                f"💧 降水: {day.get('precip', '')}mm  湿度: {day.get('humidity', '')}%\n"
                f"🌅 日出: {day.get('sunrise', '')}  日落: {day.get('sunset', '')}  "
                f"🌙 月相: {moon_emoji}  ☀️ 紫外线指数: {day.get('uvIndex', '')}\n"
                "-------------------------------------"
            )
            lines.append(day_line)
        return "\n".join(lines)

    def fetch_indices(self):
        token = self.generate_jwt()
        if not token:
            return None

        url = "https://ne2mtdcmff.re.qweatherapi.com/v7/indices/3d"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"location": self.location, "type": "0", "lang": "zh"}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] 请求天气指数失败: {e}")
            return None

    def parse_indices(self, data):
        daily = data.get("daily", [])
        if not daily:
            return "⚠️ 无生活指数数据。"

        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        today_items = [item for item in daily if item["date"] == today_str]

        needed = {
            "运动指数": "🏃‍♀️ 运动指数",
            "洗车指数": "🚗 洗车指数",
            "穿衣指数": "👕 穿衣指数",
            "空气污染扩散条件指数": "🌫 空气污染扩散条件指数",
            "防晒指数": "🌞 防晒指数"
        }

        lines = [f"📅 {today_str}（周{'一二三四五六日'[datetime.datetime.now().weekday()]}）"]
        for item in today_items:
            name = item.get("name", "")
            if name in needed:
                icon_name = needed[name]
                category = item.get("category", "")
                text = item.get("text", "")
                lines.append(f"{icon_name}：{category}\n{text}")
        lines.append("-------------------------------------")
        return "\n".join(lines)

    def fetch_typhoon(self):
        token = self.generate_jwt()
        if not token:
            return None

        year = datetime.datetime.now().year
        url = f"https://ne2mtdcmff.re.qweatherapi.com/v7/tropical/storm-list?basin=NP&year={year}"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] 请求台风数据失败: {e}")
            return None

    def parse_typhoon(self, data):
        typhoons = data.get('tropicalCyclone', [])
        if not typhoons:
            return "🌪️ 当前无台风信息。"

        lines = ["🌪️ 当前台风信息："]
        for ty in typhoons:
            lines.append(
                f"名称：{ty.get('name', '未知')} ({ty.get('enName', '')})\n"
                f"状态：{ty.get('status', '未知状态')}\n"
                f"位置：{ty.get('lat', '未知纬度')}°N, {ty.get('lon', '未知经度')}°E\n"
                f"最大风速：{ty.get('maxWind', '未知风速')} km/h  气压：{ty.get('pressure', '未知气压')} hPa\n"
                f"移动方向：{ty.get('moveDirection', '未知方向')}  速度：{ty.get('moveSpeed', '未知速度')} km/h\n"
                f"7级风圈半径：{ty.get('radius7', '未知')} km\n"
                "-------------------------------------"
            )
        return "\n".join(lines)

    def fetch_city_name(self):
        token = self.generate_jwt()
        if not token:
            return None

        url = "https://ne2mtdcmff.re.qweatherapi.com/geo/v2/city/lookup"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"location": self.location, "lang": "zh"}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            locations = data.get('location', [])
            return locations[0].get('name') if locations else None
        except Exception as e:
            print(f"[ERROR] 请求城市名称失败: {e}")
            return None


def main():
    private_key = os.getenv("QWEATHER_PRIVATE_KEY", "").replace("\\n", "\n")
    project_id = os.getenv("QWEATHER_PROJECT_ID", "3A8X")
    key_id = os.getenv("QWEATHER_KEY_ID", "TW")
    location = os.getenv("QWEATHER_LOCATION", "101280610")
    forecast_days = os.getenv("QWEATHER_FORECAST_DAYS", "3d")
    fallback_city_name = os.getenv("QWEATHER_CITY_NAME", location)

    if not private_key:
        print("[ERROR] 请设置环境变量 QWEATHER_PRIVATE_KEY")
        return

    days_map = {"3d": "3 天", "7d": "7 天", "10d": "10 天", "15d": "15 天", "30d": "30 天"}
    forecast_days_text = days_map.get(forecast_days, forecast_days)

    client = QWeatherForecastClient(private_key, project_id, key_id, location, forecast_days)
    city_name = client.fetch_city_name() or fallback_city_name

    weather_data = client.fetch_forecast()
    weather_message = client.parse_forecast(weather_data) if weather_data else "获取天气预报失败。"

    indices_data = client.fetch_indices()
    indices_message = client.parse_indices(indices_data) if indices_data else "获取生活指数失败。"

    typhoon_data = client.fetch_typhoon()
    typhoon_message = client.parse_typhoon(typhoon_data) if typhoon_data else "获取台风信息失败。"

    full_message = (
        f"{weather_message}\n\n"
        f"{indices_message}\n\n"
        f"{typhoon_message}\n\n"
        "数据来源：和风天气 | https://www.qweather.com/"
    )

    notify.send(title=f"{city_name}未来{forecast_days_text}天气预报及生活指数/台风信息", content=full_message)
    print(full_message)


if __name__ == "__main__":
    main()
