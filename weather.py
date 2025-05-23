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

import time
import jwt
import requests
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# ====== 配置类 ======
@dataclass
class WeatherConfig:
    """天气配置类"""
    private_key: str
    project_id: str
    key_id: str
    location: str
    timeout: int = 10
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> 'WeatherConfig':
        """从环境变量加载配置"""
        return cls(
            private_key=os.getenv("QWEATHER_PRIVATE_KEY", "").replace("\\n", "\n"),
            project_id=os.getenv("QWEATHER_PROJECT_ID", "3A8X"),
            key_id=os.getenv("QWEATHER_KEY_ID", "TW"),
            location=os.getenv("QWEATHER_LOCATION", "101280610")
        )

# ====== 常量映射 ======
MOON_PHASE_MAP = {
    "800": "🌑 新月", "801": "🌒 蛾眉月", "802": "🌓 上弦月", "803": "🌔 盈凸月",
    "804": "🌕 满月", "805": "🌖 亏凸月", "806": "🌗 下弦月", "807": "🌘 残月",
}

# API 配置
API_BASE_URL = "https://ne2mtdcmff.re.qweatherapi.com"
API_ENDPOINTS = {
    "daily": "/v7/weather/3d",
    "city": "/geo/v2/city/lookup",
    "storm_list": "/v7/tropical/storm-list",
    "storm_forecast": "/v7/tropical/storm-forecast",
}

WEATHER_CODE_MAP = {
    # 晴空类
    "100": "☀️ 晴", "150": "☀️ 晴",
    "101": "🌤 多云", "151": "🌤 多云",
    "102": "⛅️ 少云", "152": "⛅️ 少云",
    "103": "🌥 晴间多云", "153": "🌥 晴间多云",
    "104": "☁️ 阴",

    # 降雨类
    "300": "🌦 阵雨", "301": "🌦 强阵雨", "350": "🌦 阵雨", "351": "🌦 强阵雨",
    "302": "⛈️ 雷阵雨", "303": "⛈️ 强雷阵雨", "304": "⛈️ 雷阵雨伴有冰雹",
    "305": "🌧 小雨", "306": "🌧 中雨", "307": "🌧 大雨", "308": "💦 极端降雨",
    "309": "🌧 毛毛雨", "310": "💦 暴雨", "311": "💦 大暴雨", "312": "💦 特大暴雨",
    "313": "🌧 冻雨", "314": "🌧 小到中雨", "315": "🌧 中到大雨",
    "316": "💦 大到暴雨", "317": "💦 暴雨到大暴雨", "318": "💦 大暴雨到特大暴雨",
    "399": "🌧 雨",

    # 降雪类
    "400": "🌨 小雪", "401": "🌨 中雪", "402": "❄️ 大雪", "403": "❄️ 暴雪",
    "404": "🌨 雨夹雪", "405": "🌨 雨雪天气", "406": "🌨 阵雨夹雪", "407": "🌨 阵雪",
    "408": "🌨 小到中雪", "409": "🌨 中到大雪", "410": "🌨 大到暴雪",
    "456": "🌨 阵雨夹雪", "457": "🌨 阵雪", "499": "❄️ 雪",

    # 雾霾类
    "500": "🌫 薄雾", "501": "🌫 雾", "502": "🌁 霾", "503": "🌪 扬沙",
    "504": "🌪 浮尘", "507": "🌪 沙尘暴", "508": "🌪 强沙尘暴",
    "509": "🌫 浓雾", "510": "🌫 强浓雾", "511": "🌁 中度霾",
    "512": "🌁 重度霾", "513": "🌁 严重霾", "514": "🌫 大雾",
    "515": "🌫 特强浓雾",

    # 其他
    "900": "🔥 热", "901": "❄️ 冷", "999": "❓ 未知",
}

TYPHOON_MAP = {
    "TS": "🌪️ 热带风暴", "TD": "🌬️ 热带低压", "HU": "🌀 飓风",
    "TY": "🌪️ 台风", "ST": "💨 强热带风暴", "SD": "🌪️ 热带风暴",
}

# ====== 通知类 ======
class NotificationManager:
    """通知管理器"""
    
    @staticmethod
    def center_title_wechat(text: str, width: int = 10) -> str:
        text_len = len(text)
        total_len = width * 2  # 估算总宽度（全角*2）
        padding = (total_len - text_len) // 2
        return "　" * padding + text
    @staticmethod
    def send(title: str, content: str) -> None:
        """
        发送通知
        
        Args:
            title: 通知标题
            content: 通知内容
        """
        try:
            # 使用全角空格使标题居中
            centered_title = NotificationManager.center_title_wechat(title, 8)
            
            # 打印发送内容
            print("\n" + "="*50)
            print("发送内容预览:")
            print("-"*50)
            print(f"标题: {centered_title}")
            print("-"*50)
            print("正文:")
            print(content)
            print("="*50 + "\n")
            
            # 尝试使用青龙面板的通知
            from notify import send as ql_send
            ql_send(centered_title, content)
        except ImportError:
            # 降级为控制台输出
            print(f"\n{centered_title}")
            print("=" * 30)
            print(content)
        except Exception as e:
            print(f"[ERROR] 发送通知失败: {e}")

class QWeatherClient:
    """和风天气API客户端"""
    
    def __init__(self, config: WeatherConfig):
        """
        初始化客户端
        
        Args:
            config: 天气配置对象
        """
        self.config = config
        self.urls = {
            endpoint: f"{API_BASE_URL}{path}"
            for endpoint, path in API_ENDPOINTS.items()
        }
        print("[INFO] 和风天气客户端初始化完成")

    def _generate_jwt(self) -> str:
        """生成JWT令牌"""
        now = int(time.time())
        payload = {
            "sub": self.config.project_id,
            "iat": now - 30,
            "exp": now + 900,
        }
        headers = {
            "alg": "EdDSA",
            "kid": self.config.key_id,
        }
        try:
            token = jwt.encode(payload, self.config.private_key, algorithm="EdDSA", headers=headers)
            return token if isinstance(token, str) else token.decode("utf-8")
        except Exception as e:
            print(f"[ERROR] JWT生成失败: {e}")
            raise RuntimeError(f"JWT生成失败: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        token = self._generate_jwt()
        if not token:
            raise RuntimeError("JWT生成失败")
        return {"Authorization": f"Bearer {token}"}

    def _request(self, url: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """
        发送HTTP请求
        
        Args:
            url: 请求URL
            params: 请求参数
            
        Returns:
            响应数据或None（如果请求失败）
        """
        headers = self._get_headers()
        
        for retry in range(self.config.max_retries):
            try:
                print(f"[INFO] 正在请求: {url}")
                response = requests.get(url, headers=headers, params=params, timeout=self.config.timeout)
                response.raise_for_status()
                data = response.json()
                print(f"[INFO] 请求成功: {url}")
                return data
            except requests.exceptions.RequestException as e:
                print(f"[WARN] 请求失败 ({retry + 1}/{self.config.max_retries}): {e}")
                if retry == self.config.max_retries - 1:
                    raise RuntimeError(f"请求失败 ({retry + 1}/{self.config.max_retries}): {e}")
                time.sleep(1)  # 重试前等待1秒
        return None

    def fetch_city_name(self) -> Optional[str]:
        """获取城市名称"""
        print("[INFO] 正在获取城市信息...")
        params = {"location": self.config.location, "lang": "zh"}
        data = self._request(self.urls["city"], params)
        if not data:
            print("[WARN] 未获取到城市信息")
            return None
        locations = data.get("location", [])
        city_name = locations[0].get("name") if locations else None
        print(f"[INFO] 获取到城市信息: {city_name}")
        return city_name

    def fetch_daily(self) -> Optional[Dict[str, Any]]:
        """获取每日天气数据"""
        print("[INFO] 正在获取每日天气数据...")
        params = {"location": self.config.location, "lang": "zh", "unit": "m"}
        data = self._request(self.urls["daily"], params)
        if data:
            print("[INFO] 成功获取每日天气数据")
        else:
            print("[WARN] 未获取到每日天气数据")
        return data

    def parse_daily(self, data: Optional[Dict[str, Any]]) -> str:
        """
        解析每日天气数据
        
        Args:
            data: 天气数据
            
        Returns:
            格式化的天气信息
        """
        if not data or "daily" not in data or not data["daily"]:
            return "无有效天气数据"

        daily = data["daily"][0]
        
        # 处理月相
        moon_phase = MOON_PHASE_MAP.get(str(daily.get("moonPhaseIcon", "")), daily.get("moonPhase", "未知"))

        # 处理天气现象
        text_day = WEATHER_CODE_MAP.get(daily.get("iconDay", ""), daily.get("textDay", "未知"))
        text_night = WEATHER_CODE_MAP.get(daily.get("iconNight", ""), daily.get("textNight", "未知"))

        # 处理温度
        temp_min = daily.get("tempMin", "未知")
        temp_max = daily.get("tempMax", "未知")
        temp_range = f"{temp_min} ~ {temp_max} °C" if temp_min != "未知" and temp_max != "未知" else "未知"

        # 构建输出信息
        lines = [
            f"📅 日期: {daily.get('fxDate', '未知')}",
            f"🌅 日出: {daily.get('sunrise', '未知')}  🌇 日落: {daily.get('sunset', '未知')}",
            f"🌙 月升: {daily.get('moonrise', '未知')}  月落: {daily.get('moonset', '未知')}  🌔 月相: {moon_phase}",
            f"🌡 温度范围: {temp_range}",
            f"🌞 白天: {text_day}  💨 {daily.get('windDirDay', '未知')} {daily.get('windScaleDay', '未知')}级",
            f"🌜 夜间: {text_night}  💨 {daily.get('windDirNight', '未知')} {daily.get('windScaleNight', '未知')}级",
            f"💧 湿度: {daily.get('humidity', '未知')}%  ☁️ 云量: {daily.get('cloud', '未知')}%",
            f"🌂 降水量: {daily.get('precip', '未知')}mm  🌡️ 气压: {daily.get('pressure', '未知')}hPa",
            f"🔆 紫外线指数: {daily.get('uvIndex', '未知')}  👁️ 能见度: {daily.get('vis', '未知')}km",
        ]
        return "\n".join(lines)

    def fetch_storm_list(self, basin: str = "NP", year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        获取台风列表
        
        Args:
            basin: 台风区域
            year: 年份
            
        Returns:
            台风列表数据
        """
        if year is None:
            year = datetime.now().year
        print(f"[INFO] 正在获取{year}年台风列表...")
        params = {"basin": basin, "year": str(year)}
        data = self._request(self.urls["storm_list"], params)
        if data and data.get("storms"):
            print(f"[INFO] 获取到{len(data['storms'])}个台风信息")
        else:
            print("[INFO] 当前没有台风信息")
        return data

    def fetch_storm_forecast(self, storm_id: str) -> Optional[Dict[str, Any]]:
        """获取单个台风预报"""
        print(f"[INFO] 正在获取台风预报信息 (ID: {storm_id})...")
        params = {"stormId": storm_id}
        data = self._request(self.urls["storm_forecast"], params)
        if data:
            print("[INFO] 成功获取台风预报信息")
        else:
            print("[WARN] 未获取到台风预报信息")
        return data


def format_storm_forecast(data: Optional[Dict[str, Any]]) -> str:
    """格式化台风预报"""
    if not data or "forecasts" not in data or not data["forecasts"]:
        return "无台风预报数据"

    storm_info = data.get("storm", {})
    storm_name = storm_info.get("nameCn", "未知台风")
    storm_code = storm_info.get("stormType", "")
    storm_type = TYPHOON_MAP.get(storm_code, storm_code)

    forecasts = data["forecasts"]
    lines = [f"===== 台风预报: {storm_name} {storm_type} ====="]

    for fc in forecasts:
        fc_time = fc.get("fcstTime", "")
        time_str = fc_time[-5:] if fc_time else ""
        wind_scale = fc.get("windScale", "")
        wind_speed = fc.get("windSpeed", "")
        pressure = fc.get("pressure", "")
        lat = fc.get("lat", "")
        lon = fc.get("lon", "")
        status = fc.get("status", "")

        lines.append(
            f"时间: {time_str}，风力等级: {wind_scale}级，风速: {wind_speed}km/h，气压: {pressure}hPa，位置: {lat},{lon}，状态: {status}"
        )
    return "\n".join(lines)


def main():
    """主函数"""
    try:
        print("\n[INFO] 开始获取天气信息...")
        
        # 加载配置
        config = WeatherConfig.from_env()
        print("[INFO] 配置加载完成")
        
        client = QWeatherClient(config)

        # 获取城市名称
        city_name = client.fetch_city_name() or "未知位置"
        header = f"===== 深圳市{city_name}区 今日天气预报 ====="

        # 获取天气数据
        daily_data = client.fetch_daily()
        daily_text = client.parse_daily(daily_data)
        notify_text = f"{header}\n{daily_text}"

        # 获取台风信息
        print("\n[INFO] 开始获取台风信息...")
        storm_list = client.fetch_storm_list()
        if storm_list and storm_list.get("storms"):
            first_storm_id = storm_list["storms"][0].get("stormId")
            if first_storm_id:
                forecast = client.fetch_storm_forecast(first_storm_id)
                storm_text = format_storm_forecast(forecast)
                notify_text += "\n" + storm_text

        # 发送通知
        print("\n[INFO] 正在发送通知...")
        NotificationManager.send("天气预报", notify_text)
        print("[INFO] 通知发送完成")

    except Exception as e:
        error_msg = f"程序运行出错: {str(e)}"
        print(f"\n[ERROR] {error_msg}")
        NotificationManager.send("错误通知", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()