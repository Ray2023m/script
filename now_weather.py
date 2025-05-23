"""
cron: 0 9,15,21 * * *
new Env('实时天气推送');
# 说明：获取深圳光明区实时天气信息并推送
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

import notify  # 添加青龙面板通知功能
import time
import jwt
import requests
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from functools import lru_cache

# ====== 日志配置 ======
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
        try:
            private_key = os.getenv("QWEATHER_PRIVATE_KEY", "").replace("\\n", "\n")
            if not private_key:
                raise ValueError("未设置 QWEATHER_PRIVATE_KEY 环境变量")
            
            return cls(
                private_key=private_key,
                project_id=os.getenv("QWEATHER_PROJECT_ID", "3A8X"),
                key_id=os.getenv("QWEATHER_KEY_ID", "TW"),
                location=os.getenv("QWEATHER_LOCATION", "101280610")
            )
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            raise

# ====== 天气代码映射 ======
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

# ====== API 配置 ======
API_BASE_URL = "https://ne2mtdcmff.re.qweatherapi.com"
API_ENDPOINTS = {
    "now": "/v7/weather/now",
    "city": "/geo/v2/city/lookup",
    "daily": "/v7/weather/3d",  # 添加3天预报API，用于获取紫外线指数
}

def classify_uv_index(uv_index: str) -> str:
    """
    对紫外线指数进行分类
    
    Args:
        uv_index: 紫外线指数
        
    Returns:
        紫外线强度等级
    """
    try:
        uv = int(uv_index)
    except ValueError:
        return "未知"

    if uv <= 2:
        return "弱"
    elif 3 <= uv <= 5:
        return "中等"
    elif 6 <= uv <= 7:
        return "较强"
    elif 8 <= uv <= 10:
        return "强"
    else:
        return "极强"

def get_uv_advice(uv_index: str) -> str:
    """
    根据紫外线指数给出建议
    
    Args:
        uv_index: 紫外线指数
        
    Returns:
        紫外线防护建议
    """
    try:
        uv = int(uv_index)
    except ValueError:
        return "⚠️ 紫外线强度未知，建议注意防晒措施。"

    if uv <= 2:
        return "🟢 紫外线弱，无需特殊防护。"
    elif 3 <= uv <= 5:
        return "🟡 紫外线中等，建议适当涂抹防晒霜。"
    elif 6 <= uv <= 7:
        return "🟠 紫外线较强，请涂抹SPF30+防晒霜并戴帽子。"
    elif 8 <= uv <= 10:
        return "🔴 紫外线强，避免长时间户外暴晒。"
    else:
        return "🟣 紫外线极强，避免外出，做好全面防护。"

def get_daily_tip(temp_max: str, weather_day: str) -> str:
    """
    根据温度和天气给出每日提示
    
    Args:
        temp_max: 最高温度
        weather_day: 白天天气状况
        
    Returns:
        每日生活提示
    """
    try:
        temp = int(temp_max)
    except ValueError:
        temp = 25  # 默认温度

    if "雨" in weather_day or "雪" in weather_day:
        return "🌂 今日有降水，请带伞出门。"
    elif temp >= 32:
        return "🔥 高温天气注意防暑，多喝水。"
    elif temp <= 10:
        return "❄️ 天气寒冷，请注意保暖。"
    else:
        return "😊 适宜出行，祝您心情愉快！"

def get_visibility_level(vis: str) -> str:
    """
    根据能见度值判断能见度等级
    
    Args:
        vis: 能见度值（千米）
        
    Returns:
        能见度等级描述
    """
    try:
        visibility = float(vis)
    except ValueError:
        return "未知"

    if visibility >= 10:
        return "极好"
    elif visibility >= 5:
        return "良好"
    elif visibility >= 2:
        return "一般"
    elif visibility >= 1:
        return "较差"
    else:
        return "很差"

class QWeatherClient:
    """和风天气API客户端"""
    
    def __init__(self, config: WeatherConfig):
        """初始化客户端"""
        self.config = config
        self.urls = {
            endpoint: f"{API_BASE_URL}{path}"
            for endpoint, path in API_ENDPOINTS.items()
        }
        self._session = requests.Session()
        logger.info("和风天气客户端初始化完成")

    @lru_cache(maxsize=1)
    def _generate_jwt(self) -> str:
        """生成JWT令牌（使用缓存优化）"""
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
            logger.error(f"JWT生成失败: {e}")
            raise RuntimeError(f"JWT生成失败: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        token = self._generate_jwt()
        if not token:
            raise RuntimeError("JWT生成失败")
        return {"Authorization": f"Bearer {token}"}

    def _request(self, url: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """发送HTTP请求"""
        headers = self._get_headers()
        
        for retry in range(self.config.max_retries):
            try:
                logger.info(f"正在请求: {url}")
                response = self._session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                try:
                    data = response.json()
                    if data.get("code") != "200":
                        logger.warning(f"API返回错误: {data.get('code')} - {data.get('message')}")
                        return None
                    return data
                except ValueError as e:
                    logger.error(f"JSON解析失败: {e}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"请求失败 ({retry + 1}/{self.config.max_retries}): {e}")
                if retry == self.config.max_retries - 1:
                    raise RuntimeError(f"请求失败 ({retry + 1}/{self.config.max_retries}): {e}")
                time.sleep(1)  # 重试前等待1秒
            except Exception as e:
                logger.error(f"请求异常: {e}")
                return None
        return None

    def fetch_city_name(self) -> Optional[Dict[str, Any]]:
        """获取城市名称和坐标"""
        logger.info("正在获取城市信息...")
        params = {"location": self.config.location, "lang": "zh"}
        data = self._request(self.urls["city"], params)
        if not data:
            logger.warning("未获取到城市信息")
            return None
        locations = data.get("location", [])
        if not locations:
            logger.warning("未找到位置信息")
            return None
        location = locations[0]
        logger.info(f"获取到城市信息: {location.get('name')}")
        return location

    def fetch_now(self) -> Optional[Dict[str, Any]]:
        """获取实时天气数据"""
        logger.info("正在获取实时天气数据...")
        params = {"location": self.config.location, "lang": "zh", "unit": "m"}
        data = self._request(self.urls["now"], params)
        if data:
            logger.info("成功获取实时天气数据")
        else:
            logger.warning("未获取到实时天气数据")
        return data

    def fetch_daily(self) -> Optional[Dict[str, Any]]:
        """获取每日天气数据"""
        logger.info("正在获取每日天气数据...")
        params = {"location": self.config.location, "lang": "zh", "unit": "m"}
        data = self._request(self.urls["daily"], params)
        if data:
            logger.info("成功获取每日天气数据")
        else:
            logger.warning("未获取到每日天气数据")
        return data

    def parse_now(self, data: Optional[Dict[str, Any]]) -> str:
        """解析实时天气数据"""
        if not data or "now" not in data:
            logger.warning("实时天气数据格式无效")
            return "无有效实时天气数据"

        now = data["now"]

        # 处理天气现象
        text = WEATHER_CODE_MAP.get(now.get("icon", ""), now.get("text", "未知"))
        
        # 处理体感温度
        feels_like = now.get("feelsLike", "")
        temp_display = f"{now.get('temp', '未知')}°C"
        if feels_like:
            temp_display += f" (体感温度: {feels_like}°C)"
        
        # 处理露点温度
        dew = now.get("dew", "")
        dew_display = f"  🧊 露点温度: {dew}°C" if dew else ""

        # 处理能见度
        vis = now.get("vis", "未知")
        vis_level = get_visibility_level(vis)
        vis_display = f"{vis}km ({vis_level})"

        # 获取紫外线指数和建议
        daily_data = self.fetch_daily()
        uv_index = "未知"
        uv_level = "未知"
        uv_advice = ""
        daily_tip = ""
        if daily_data and "daily" in daily_data and daily_data["daily"]:
            today = daily_data["daily"][0]
            uv_index = today.get("uvIndex", "未知")
            uv_level = classify_uv_index(uv_index)
            uv_advice = get_uv_advice(uv_index)
            daily_tip = get_daily_tip(today.get("tempMax", "25"), text)

        # 格式化时间
        def format_time(time_str: str) -> str:
            try:
                if not time_str:
                    return "未知"
                # 处理带时区的时间格式
                if "+" in time_str:
                    dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M%z")
                else:
                    dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%MZ")
                    # 转换为北京时间（UTC+8）
                    dt = dt.replace(hour=(dt.hour + 8) % 24)
                    if dt.hour < 8:  # 如果加8小时后小于8点，说明跨天了
                        dt = dt.replace(day=dt.day + 1)
                return dt.strftime("%Y年%m月%d日 %H:%M")
            except ValueError:
                return "未知"
        
        # 构建输出信息
        lines = [
            "─" * 20,
            f"🕒 更新时间: {format_time(now.get('obsTime', ''))}",
            f"🔄 API更新: {format_time(data.get('updateTime', ''))}",
            "─" * 20,
            f"🌤 天气: {text}",
            f"💨 {now.get('windDir', '未知')} {now.get('windScale', '未知')}级 风速: {now.get('windSpeed', '未知')}km/h",
            f"🔆 紫外线指数: {uv_index} ({uv_level})",
            f"🌡 温度: {temp_display}",
            "─" * 20,
            f"🌡️ 气压: {now.get('pressure', '未知')}hPa 云量: {now.get('cloud', '未知')}%",
            f"👁️ 能见度: {vis_display} 相对湿度: {now.get('humidity', '未知')}%",
            f"🌧️ 降水量: {now.get('precip', '未知')}mm{dew_display}",
            "─" * 20,
            f"💡 生活提示: {daily_tip}",
            f"🧢 防护建议: {uv_advice}"
            
        ]
        
        return "\n".join(lines)

def main():
    """主函数"""
    try:
        logger.info("开始获取天气信息...")
        
        # 加载配置
        config = WeatherConfig.from_env()
        logger.info("配置加载完成")
        
        # 打印配置信息（不包含私钥）
        logger.info("当前配置:")
        logger.info("-" * 50)
        logger.info(f"Project ID: {config.project_id}")
        logger.info(f"Key ID: {config.key_id}")
        logger.info(f"Location: {config.location}")
        logger.info(f"Timeout: {config.timeout}s")
        logger.info(f"Max Retries: {config.max_retries}")
        logger.info("-" * 50)
        
        client = QWeatherClient(config)

        # 获取城市信息
        city_info = client.fetch_city_name()
        if not city_info:
            raise RuntimeError("无法获取城市信息")
            
        city_name = city_info.get("name", "未知位置")
        header = f"===== 深圳市{city_name}区 实时天气 ====="

        # 获取实时天气数据
        now_data = client.fetch_now()
        if now_data:
            now_text = client.parse_now(now_data)
            logger.info(f"\n{header}\n{now_text}")
            # 发送青龙面板通知
            notify.send("实时天气通知", f"{header}\n{now_text}")
        else:
            logger.warning(f"\n{header}")

        logger.info("天气信息获取完成")

    except Exception as e:
        error_msg = f"程序运行出错: {str(e)}"
        logger.error(error_msg)
        # 发送错误通知到青龙面板
        notify.send("实时天气脚本错误", error_msg)
        raise

if __name__ == "__main__":
    main() 