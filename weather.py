"""
cron: 0 9,15,21 * * *
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
try:
    import notify
except ImportError:
    print("[WARN] 未找到notify模块，将使用标准输出")

def print_success(text: str) -> None:
    """打印成功信息"""
    print(f"✅ {text}")

def print_info(text: str) -> None:
    """打印信息"""
    print(f"ℹ️ {text}")

def print_warning(text: str) -> None:
    """打印警告信息"""
    print(f"⚠️ {text}")

def print_error(text: str) -> None:
    """打印错误信息"""
    print(f"❌ {text}")

def print_header(text: str) -> None:
    """打印标题"""
    print(f"\n🌟 {text} 🌟")

def print_progress(text: str) -> None:
    """打印进度信息"""
    print(f"🔄 {text}")

def print_section(text: str) -> None:
    """打印分区信息"""
    print(f"\n📌 {text}")

def print_subsection(text: str) -> None:
    """打印子分区信息"""
    print(f"\n➡️ {text}")

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
    "now": "/v7/weather/now",
    "city": "/geo/v2/city/lookup",
    "air_quality": "/airquality/v1/daily/{latitude}/{longitude}",
    "warning": "/v7/warning/now",  # 新增灾害预警API
}

# 预警类型映射
WARNING_TYPE_MAP = {
    # 1000系列 - 气象预警
    "1002": "🌪️ 龙卷风预警","1003": "🌧️ 暴雨预警","1004": "❄️ 暴雪预警","1005": "❄️ 寒潮预警",
    "1006": "💨 大风预警","1007": "🌪️ 沙尘暴预警","1008": "❄️ 低温冻害预警","1009": "🔥 高温预警","1010": "🔥 热浪预警",
    "1011": "🌡️ 干热风预警","1012": "🌪️ 下击暴流预警","1013": "🏔️ 雪崩预警","1014": "⚡️ 雷电预警","1015": "🧊 冰雹预警",
    "1016": "❄️ 霜冻预警","1017": "🌫️ 大雾预警","1018": "💨 低空风切变预警","1019": "🌫️ 霾预警","1020": "⛈️ 雷雨大风预警",
    "1021": "❄️ 道路结冰预警","1022": "🌵 干旱预警","1023": "🌊 海上大风预警","1024": "🥵 高温中暑预警","1025": "🔥 森林火险预警",
    "1026": "🔥 草原火险预警","1027": "❄️ 冰冻预警","1028": "🌌 空间天气预警","1029": "🌫️ 重污染预警","1030": "❄️ 低温雨雪冰冻预警",
    "1031": "⛈️ 强对流预警","1032": "🌫️ 臭氧预警","1033": "❄️ 大雪预警","1034": "❄️ 寒冷预警","1035": "🌧️ 连阴雨预警",
    "1036": "💧 渍涝风险预警","1037": "🏔️ 地质灾害气象风险预警","1038": "🌧️ 强降雨预警","1039": "❄️ 强降温预警","1040": "❄️ 雪灾预警",
    "1041": "🔥 森林（草原）火险预警","1042": "🏥 医疗气象预警","1043": "⚡️ 雷暴预警","1044": "🏫 停课信号","1045": "🏢 停工信号",
    "1046": "🌊 海上风险预警","1047": "🌪️ 春季沙尘天气预警","1048": "❄️ 降温预警","1050": "❄️ 严寒预警",
    "1051": "🌪️ 沙尘预警","1052": "🌊 海上雷雨大风预警","1053": "🌊 海上大雾预警","1054": "🌊 海上雷电预警",

    # 1200系列 - 水文预警
    "1201": "💧 洪水预警","1202": "💧 内涝预警","1203": "💧 水库重大险情预警","1204": "💧 堤防重大险情预警",
    "1205": "💧 凌汛灾害预警","1206": "💧 渍涝预警","1207": "💧 洪涝预警","1208": "💧 枯水预警","1209": "💧 中小河流洪水和山洪气象风险预警",
    "1210": "💧 农村人畜饮水困难预警","1211": "💧 中小河流洪水气象风险预警","1212": "💧 防汛抗旱风险提示","1213": "💧 城市内涝风险预警",
    "1214": "💧 山洪灾害事件预警","1215": "🌵 农业干旱预警","1216": "💧 城镇缺水预警","1217": "🌵 生态干旱预警",
    "1218": "⚠️ 灾害风险预警","1219": "💧 山洪灾害气象风险预警","1221": "💧 水利旱情预警",

    # 1240系列 - 地质灾害预警
    "1241": "🏔️ 滑坡事件预警","1242": "🏔️ 泥石流事件预警","1243": "🏔️ 山体崩塌事件预警","1244": "🏔️ 地面塌陷事件预警",
    "1245": "🏔️ 地裂缝事件预警","1246": "🏔️ 地面沉降事件预警","1247": "🌋 火山喷发事件预警","1248": "🏔️ 地质灾害气象风险预警",
    "1249": "🏔️ 地质灾害气象预警","1250": "🏔️ 地质灾害预警","1251": "🏔️ 地质灾害风险预警",

    # 1270系列 - 环境预警
    "1271": "🌫️ 空气污染事件预警","1272": "🌫️ 空气重污染预警","1273": "🌫️ 大气污染预警","1274": "🌫️ 重污染天气预警",

    # 1600系列 - 香港预警
    "1601": "🔥 炎热预警", "1602": "💨 强烈季风信号","1603": "🏔️ 山泥倾泻预警","1604": "🌀 热带气旋预警",
    "1605": "🔥 火灾危险预警","1606": "💧 新界北部水浸特别报告","1607": "❄️ 寒冷天气预警","1608": "⚡️ 雷暴预警",
    "1609": "🌧️ 暴雨预警","1610": "❄️ 霜冻预警",

    # 1700系列 - 台湾预警
    "1701": "❄️ 低温特报","1702": "💨 陆上强风预警","1703": "🌧️ 降雨特报",

    # 1800系列 - 澳门预警
    "1801": "💨 强烈季风信号（黑球）","1802": "🌊 风暴潮预警","1803": "🌀 热带气旋预警","1804": "🌧️ 暴雨预警","1805": "⚡️ 雷暴预警",

    # 2000系列 - 国际预警
    "2001": "💨 大风预警","2002": "❄️ 强降雪和结冰预警","2003": "🌫️ 大雾预警","2004": "🌊 海岸风险预警",
    "2005": "🔥 森林火险预警","2006": "🌧️ 雨预警","2007": "💧 大雨洪水预警","2029": "⚡️ 雷暴预警",
    "2030": "🔥 高温预警","2031": "❄️ 低温预警","2032": "🏔️ 雪崩预警","2033": "💧 洪水预警",
    "2050": "🌧️ 大雨预警","2051": "💨 大风预警","2052": "❄️ 大雪预警","2053": "💨 Zonda wind预警",
    "2054": "💨 暴风预警","2070": "🌪️ 扬尘风预警","2071": "💨 强地面风预警","2072": "🔥 炎热预警",
    "2073": "🔥 夜间炎热预警","2074": "❄️ 寒冷预警","2075": "⚡️ 雷暴和闪电预警","2076": "🧊 冰雹风暴预警",
    "2077": "🌊 海况风险预警","2078": "🐟 渔业风险预警","2079": "❄️ 大雪预警","2080": "🌪️ 沙尘暴预警",
    "2081": "🔥 热浪预警","2082": "❄️ 寒潮预警","2083": "🌫️ 大雾预警","2084": "🌧️ 强降雨预警","2085": "❄️ 地面霜预警",

    # 2100系列 - 其他国际预警
    "2100": "🌫️ 大雾预警","2101": "🌧️ 雷雨预警","2102": "⚡️ 雷暴预警","2103": "🌧️ 小雨预警","2104": "🌧️ 大雨预警",
    "2105": "💨 风预警","2106": "⚡️ 雷暴和沙尘预警","2107": "🌪️ 沙尘预警","2108": "🌊 高海浪预警","2109": "❄️ 霜预警",
    "2111": "🌫️ 能见度降低预警","2120": "🌵 低湿度预警","2121": "🌧️ 累计降水风险预警","2122": "❄️ 寒潮预警",
    "2123": "🌪️ 龙卷风预警","2124": "⚡️ 雷暴预警","2125": "🧊 冰雹预警","2126": "🌧️ 强降雨预警","2127": "💨 大风预警",
    "2128": "🔥 热浪预警","2129": "❄️ 寒冷预警","2130": "❄️ 霜冻预警","2131": "🌵 干旱预警","2132": "🔥 森林火险预警",
    "2133": "❄️ 大雪预警","2134": "❄️ 强降温预警","2135": "🌧️ 暴雨预警",

    # 9999 - 其他预警
    "9999": "⚠️ 其他预警"
}

# 预警等级映射
WARNING_LEVEL_MAP = {
    "Minor": "🔵 蓝色预警",
    "Moderate": "🟡 黄色预警",
    "Severe": "🟠 橙色预警",
    "Extreme": "🔴 红色预警",
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
        self._city_info_cache = None  # 添加城市信息缓存
        print_success("和风天气客户端初始化完成")

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
            print_error(f"JWT生成失败: {e}")
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
                print_progress(f"正在请求: {url}")
                response = requests.get(url, headers=headers, params=params, timeout=self.config.timeout)
                response.raise_for_status()
                
                try:
                    data = response.json()
                except ValueError as e:
                    print_error(f"JSON解析失败: {e}")
                    return None
                
                return data
                    
            except requests.exceptions.RequestException as e:
                print_warning(f"请求失败 ({retry + 1}/{self.config.max_retries}): {e}")
                if retry == self.config.max_retries - 1:
                    raise RuntimeError(f"请求失败 ({retry + 1}/{self.config.max_retries}): {e}")
                time.sleep(1)  # 重试前等待1秒
            except Exception as e:
                print_error(f"请求异常: {e}")
                return None
        return None

    def fetch_city_name(self) -> Optional[Dict[str, Any]]:
        """获取城市名称和坐标"""
        # 如果缓存中有城市信息，直接返回
        if self._city_info_cache is not None:
            return self._city_info_cache

        print_progress("正在获取城市信息...")
        params = {"location": self.config.location, "lang": "zh"}
        data = self._request(self.urls["city"], params)
        if not data:
            print_warning("未获取到城市信息")
            return None
        locations = data.get("location", [])
        if not locations:
            print_warning("未找到位置信息")
            return None
        location = locations[0]
        print_success(f"已获取城市信息: {location.get('name')}")
        
        # 缓存城市信息
        self._city_info_cache = location
        return location

    def fetch_daily(self) -> Optional[Dict[str, Any]]:
        """获取每日天气数据"""
        print_progress("正在获取每日天气数据...")
        params = {"location": self.config.location, "lang": "zh", "unit": "m"}
        data = self._request(self.urls["daily"], params)
        if data:
            print_success("成功获取每日天气数据")
        else:
            print_warning("未获取到每日天气数据")
        return data

    def fetch_air_quality(self, latitude: str, longitude: str) -> Optional[Dict[str, Any]]:
        """获取空气质量数据"""
        print_progress("正在获取空气质量数据...")
        url = self.urls["air_quality"].format(latitude=latitude, longitude=longitude)
        try:
            data = self._request(url)
            if data:
                print_success("成功获取空气质量数据")
                return data
            else:
                print_warning("未获取到空气质量数据")
                return None
        except Exception as e:
            print_error(f"获取空气质量数据失败: {e}")
            return None

    def parse_air_quality(self, data: Optional[Dict[str, Any]]) -> str:
        """
        解析空气质量数据
        
        Args:
            data: 空气质量数据
            
        Returns:
            格式化的空气质量信息
        """
        if not data or "days" not in data or not data["days"]:
            print_warning("空气质量数据格式无效")
            return "暂无空气质量数据"

        today = data["days"][0]
        
        # 获取中国标准AQI指数
        aqi = next((idx for idx in today["indexes"] if idx["code"] == "cn-mee"), None)
        if not aqi:
            print_warning("未找到AQI指数数据")
            return "暂无空气质量数据"

        # 获取空气质量指数和等级
        aqi_value = aqi.get("aqiDisplay", "未知")
        level = aqi.get("level", "未知")
        category = aqi.get("category", "未知")

        # 获取健康建议
        health = aqi.get("health", {})
        effect = health.get("effect", "暂无影响说明")

        return f"💨 AQI指数: {aqi_value} 等级: {level} 类别: {category}\n💡 健康影响: {effect}"

    def parse_daily(self, data: Optional[Dict[str, Any]]) -> str:
        """
        解析每日天气数据
        
        Args:
            data: 天气数据
            
        Returns:
            格式化的天气信息
        """
        if not data or "daily" not in data or not data["daily"]:
            print_warning("天气数据格式无效")
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
        temp_range = f" 最高温度 {temp_max}°C, 最低温度 {temp_min}°C." if temp_min != "未知" and temp_max != "未知" else "未知"

        # 获取紫外线建议和每日提示
        uv_index = daily.get("uvIndex", "未知")
        uv_level = classify_uv_index(uv_index)
        uv_advice = get_uv_advice(uv_index)
        daily_tip = get_daily_tip(temp_max, text_day)

        # 获取空气质量信息
        city_info = self.fetch_city_name()
        air_quality_text = ""
        if city_info:
            latitude = city_info.get("lat", "")
            longitude = city_info.get("lon", "")
            if latitude and longitude:
                air_quality_data = self.fetch_air_quality(latitude, longitude)
                if air_quality_data:
                    today = air_quality_data.get("days", [{}])[0]
                    aqi = next((idx for idx in today.get("indexes", []) if idx.get("code") == "cn-mee"), None)
                    if aqi:
                        aqi_value = aqi.get("aqiDisplay", "未知")
                        level = aqi.get("level", "未知")
                        category = aqi.get("category", "未知")
                        air_quality_text = f"💨 空气AQI指数: {aqi_value} 等级: {level} 类别: {category}"

        # 获取预警信息
        warning_text = ""
        warning_data = self.fetch_warning()
        if warning_data and warning_data.get("warning"):
            warning_text = self.parse_warning(warning_data)

        # 构建输出信息
        lines = [
            "──────── 今日概览 ────────",
            f"☀️ 日出日落: ({daily.get('sunrise', '未知')} - {daily.get('sunset', '未知')})",
            f"🌙 月升月落: ({daily.get('moonrise', '未知')} - {daily.get('moonset', '未知')})  {moon_phase}"
        ]

        # 添加空气质量信息（如果存在）
        if air_quality_text:
            lines.append(air_quality_text)

        # 继续添加其他信息
        lines.extend([
            f"🌡️ 温差范围: {temp_range}",
            "──────── 天气趋势 ────────",
            f"☀️ 白天: {text_day} {daily.get('windDirDay', '未知')} {daily.get('windScaleDay', '未知')} 级 ({daily.get('windSpeedDay', '未知')} km/h)",
            f"🌙 夜间: {text_night} {daily.get('windDirNight', '未知')} {daily.get('windScaleNight', '未知')} 级 ({daily.get('windSpeedNight', '未知')} km/h)",
            "──────── 环境指标 ────────",
            f"🔆 紫外线: {uv_index} 级({uv_level})",
            f"💧 相对湿度: {daily.get('humidity', '未知')}%  🌧️ 累计:{daily.get('precip', '未知')}mm",
            "──────── 生活指南 ────────",
            f"🧴 防晒建议: {uv_advice.split('：')[1] if '：' in uv_advice else uv_advice}",
            f"🌂 出行提示: {daily_tip}"
        ])

        # 添加预警信息（仅当有预警时）
        if warning_text:
            lines.extend(warning_text.split("\n"))

        return "\n".join(lines)

    def fetch_warning(self) -> Optional[Dict[str, Any]]:
        """获取灾害预警数据"""
        print_progress("正在获取灾害预警数据...")
        params = {"location": self.config.location, "lang": "zh"}
        data = self._request(self.urls["warning"], params)
        if data:
            print_success("成功获取灾害预警数据")
            return data
        else:
            print_warning("未获取到灾害预警数据")
            return None

    def parse_warning(self, data: Optional[Dict[str, Any]]) -> str:
        """
        解析灾害预警数据
        
        Args:
            data: 灾害预警数据
            
        Returns:
            格式化的灾害预警信息
        """
        if not data or "warning" not in data or not data["warning"]:
            return ""

        warnings = data["warning"]
        lines = []

        for warning in warnings:
            # 获取预警类型和等级
            warning_type = WARNING_TYPE_MAP.get(warning.get("type", ""), f"未知预警类型({warning.get('typeName', '')})")
            warning_level = WARNING_LEVEL_MAP.get(warning.get("severity", ""), f"未知预警等级({warning.get('severity', '')})")
            
            # 格式化时间
            def format_warning_time(time_str: str) -> str:
                try:
                    if not time_str:
                        return "未知"
                    dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M%z")
                    return dt.strftime("%m/%d %H:%M")
                except ValueError:
                    return "未知"

            # 处理预警内容，去除括号内容
            warning_text = warning.get('text', '暂无详细说明')
            if '【' in warning_text and '】' in warning_text:
                warning_text = warning_text.split('】', 1)[1].strip()

            # 提取区域信息
            areas = []
            if "南山区" in warning_text:
                areas.append("南山")
            if "福田区" in warning_text:
                areas.append("福田")
            if "宝安区" in warning_text:
                areas.append("宝安")
            if "光明区" in warning_text:
                areas.append("光明")
            if "龙华区" in warning_text:
                areas.append("龙华")
            area_text = "/".join(areas) if areas else "未知区域"

            # 提取影响信息
            impact = []
            if "降水" in warning_text:
                impact.append("降水")
            if "阵风" in warning_text:
                impact.append("阵风")
            if "雷电" in warning_text:
                impact.append("雷电")
            impact_text = "+".join(impact) if impact else "未知影响"

            # 构建预警信息
            warning_info = [
                "──────── 灾害预警 ────────",
                f"🚨 等级: {warning_level}",
                f"🏷️ 类型: {warning_type}",
                f"📢 来源: {warning.get('sender', '未知单位')}",
                f"🕒 生效: {format_warning_time(warning.get('startTime', ''))}-{format_warning_time(warning.get('endTime', ''))}",
                f"🏙️ 区域: {area_text}",
                f"💥 影响: {impact_text}",
            ]
            lines.extend(warning_info)

        return "\n".join(lines)

    def fetch_now(self) -> Optional[Dict[str, Any]]:
        """获取实时天气数据"""
        print_progress("正在获取实时天气数据...")
        params = {"location": self.config.location, "lang": "zh", "unit": "m"}
        data = self._request(self.urls["now"], params)
        if data:
            print_success("成功获取实时天气数据")
        else:
            print_warning("未获取到实时天气数据")
        return data

    def parse_now(self, data: Optional[Dict[str, Any]]) -> str:
        """
        解析实时天气数据
        
        Args:
            data: 实时天气数据
            
        Returns:
            格式化的实时天气信息
        """
        if not data or "now" not in data:
            print_warning("实时天气数据格式无效")
            return "无有效实时天气数据"

        now = data["now"]

        # 处理天气现象
        text = WEATHER_CODE_MAP.get(now.get("icon", ""), now.get("text", "未知"))
        
        # 处理体感温度
        feels_like = now.get("feelsLike", "")
        temp_display = f"{now.get('temp', '未知')}°C"
        if feels_like:
            temp_display += f"(体感{feels_like}°C)"
        
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
                return dt.strftime("%H:%M")
            except ValueError:
                return "未知"

        # 获取城市信息
        city_info = self.fetch_city_name()
        city_name = city_info.get("name", "未知位置") if city_info else "未知位置"

        # 构建输出信息
        lines = [
            f"📍 深圳市·{city_name}区",
            f"🌦️ 实时天气: {text} [{format_time(now.get('obsTime', ''))}更新]",
            f"🌡️ {temp_display}  💧 湿度: {now.get('humidity', '未知')}%",
            f"🌬️ {now.get('windDir', '未知')}{now.get('windScale', '未知')}级({now.get('windSpeed', '未知')}km/h) ☁️ 云量: {now.get('cloud', '未知')}%",
            f"🏙️ 能见度: {now.get('vis', '未知')}km 🌀 气压: {now.get('pressure', '未知')}hPa"
        ]
        return "\n".join(lines)

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
        return "🟠 紫外线较强，请涂抹SPF30+防晒霜。"
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

def main():
    """主函数"""
    try:
        config = WeatherConfig.from_env()
        client = QWeatherClient(config)

        # 获取城市信息
        city_info = client.fetch_city_name()
        if not city_info:
            raise RuntimeError("无法获取城市信息")

        # 收集所有天气信息
        weather_info = []
        weather_info.append("===== 今天又是新的一天 =====")

        # 获取实时天气数据
        now_data = client.fetch_now()
        if now_data:
            now_text = client.parse_now(now_data)
            weather_info.append(now_text)

        # 获取天气数据
        daily_data = client.fetch_daily()
        if not daily_data:
            raise RuntimeError("无法获取天气数据")
        daily_text = client.parse_daily(daily_data)
        weather_info.append(daily_text)

        # 整合所有信息
        final_message = "\n".join(weather_info)

        # 发送通知
        try:
            notify.send("天气信息", final_message)
        except Exception as e:
            print(f"通知发送失败: {e}")

    except Exception as e:
        error_msg = f"程序运行出错: {str(e)}"
        try:
            notify.send("天气信息获取失败", error_msg)
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()