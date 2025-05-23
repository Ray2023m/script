"""
cron: 30 7 * * *
new Env('灾害预警推送');
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


import notify  # 添加青龙面板通知功能
import time
import jwt
import requests
import os
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

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

# ====== 常量映射 ======
# 预警类型映射
WARNING_TYPE_MAP = {
    # 1000系列 - 气象预警
    "1001": "🌀 台风预警","1002": "🌪️ 龙卷风预警","1003": "🌧️ 暴雨预警","1004": "❄️ 暴雪预警","1005": "❄️ 寒潮预警",
    "1006": "💨 大风预警","1007": "🌪️ 沙尘暴预警","1008": "❄️ 低温冻害预警","1009": "🔥 高温预警","1010": "🔥 热浪预警",
    "1011": "🌡️ 干热风预警","1012": "🌪️ 下击暴流预警","1013": "🏔️ 雪崩预警","1014": "⚡️ 雷电预警","1015": "🧊 冰雹预警",
    "1016": "❄️ 霜冻预警","1017": "🌫️ 大雾预警","1018": "💨 低空风切变预警","1019": "🌫️ 霾预警","1020": "⛈️ 雷雨大风预警",
    "1021": "❄️ 道路结冰预警","1022": "🌵 干旱预警","1023": "🌊 海上大风预警","1024": "🥵 高温中暑预警","1025": "🔥 森林火险预警",
    "1026": "🔥 草原火险预警","1027": "❄️ 冰冻预警","1028": "🌌 空间天气预警","1029": "🌫️ 重污染预警","1030": "❄️ 低温雨雪冰冻预警",
    "1031": "⛈️ 强对流预警","1032": "🌫️ 臭氧预警","1033": "❄️ 大雪预警","1034": "❄️ 寒冷预警","1035": "🌧️ 连阴雨预警",
    "1036": "💧 渍涝风险预警","1037": "🏔️ 地质灾害气象风险预警","1038": "🌧️ 强降雨预警","1039": "❄️ 强降温预警","1040": "❄️ 雪灾预警",
    "1041": "🔥 森林（草原）火险预警","1042": "🏥 医疗气象预警","1043": "⚡️ 雷暴预警","1044": "🏫 停课信号","1045": "🏢 停工信号",
    "1046": "🌊 海上风险预警","1047": "🌪️ 春季沙尘天气预警","1048": "❄️ 降温预警","1049": "🌀 台风暴雨预警","1050": "❄️ 严寒预警",
    "1051": "🌪️ 沙尘预警","1052": "🌊 海上雷雨大风预警","1053": "🌊 海上大雾预警","1054": "🌊 海上雷电预警","1055": "🌊 海上台风预警",
    "1056": "❄️ 低温预警","1057": "❄️ 道路冰雪预警","1058": "⛈️ 雷暴大风预警","1059": "❄️ 持续低温预警","1060": "🌫️ 能见度不良预警",
    "1061": "🌫️ 浓浮沉预警","1062": "🌊 海区大风预警","1063": "🌧️ 短历时强降水预警","1064": "🌧️ 短时强降雨预警","1065": "🌊 海区大雾预警",
    "1066": "🥵 中暑气象条件预警","1067": "🌫️ 重污染天气预警","1068": "⚠️ 一氧化碳中毒气象条件预警","1069": "🤧 感冒等呼吸道疾病气象条件预警",
    "1071": "🤢 腹泻等肠道疾病气象条件预警","1072": "❤️ 心脑血管疾病气象条件预警","1073": "💧 洪涝灾害气象风险预警","1074": "🌫️ 重污染气象条件预警",
    "1075": "💧 城市内涝气象风险预警","1076": "💧 洪水灾害气象风险预警","1077": "🔥 森林火险气象风险预警","1078": "🌵 气象干旱预警","1079": "🌾 农业气象风险预警",
    "1080": "💨 强季风预警","1081": "⚡️ 电线积冰预警","1082": "🏥 脑卒中气象风险预警","1084": "🔥 森林（草原）火灾气象风险预警","1085": "⛈️ 雷雨强风预警",
    "1086": "❄️ 低温凝冻预警","1087": "❄️ 低温冷害预警","1088": "🌾 全国农业气象灾害风险预警","1089": "🌾 冬小麦干热风灾害风险预警",

    # 1200系列 - 水文预警
    "1201": "💧 洪水预警","1202": "💧 内涝预警","1203": "💧 水库重大险情预警","1204": "💧 堤防重大险情预警","1205": "💧 凌汛灾害预警",
    "1206": "💧 渍涝预警","1207": "💧 洪涝预警","1208": "💧 枯水预警","1209": "💧 中小河流洪水和山洪气象风险预警","1210": "💧 农村人畜饮水困难预警",
    "1211": "💧 中小河流洪水气象风险预警","1212": "💧 防汛抗旱风险提示","1213": "💧 城市内涝风险预警","1214": "💧 山洪灾害事件预警","1215": "🌵 农业干旱预警",
    "1216": "💧 城镇缺水预警","1217": "🌵 生态干旱预警","1218": "⚠️ 灾害风险预警","1219": "💧 山洪灾害气象风险预警","1221": "💧 水利旱情预警",

    # 1240系列 - 地质灾害预警
    "1241": "🏔️ 滑坡事件预警","1242": "🏔️ 泥石流事件预警","1243": "🏔️ 山体崩塌事件预警","1244": "🏔️ 地面塌陷事件预警","1245": "🏔️ 地裂缝事件预警",
    "1246": "🏔️ 地面沉降事件预警","1247": "🌋 火山喷发事件预警","1248": "🏔️ 地质灾害气象风险预警","1249": "🏔️ 地质灾害气象预警","1250": "🏔️ 地质灾害预警",
    "1251": "🏔️ 地质灾害风险预警",

    # 1270系列 - 环境预警
    "1271": "🌫️ 空气污染事件预警","1272": "🌫️ 空气重污染预警","1273": "🌫️ 大气污染预警","1274": "🌫️ 重污染天气预警",

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

# API 配置
API_BASE_URL = "https://ne2mtdcmff.re.qweatherapi.com"
API_ENDPOINTS = {
    "warning": "/v7/warning/now",  # 灾害预警API
}

# ====== 预警记录管理 ======
class WarningTracker:
    """预警记录管理类"""
    def __init__(self, cache_file: str = "warning_cache.json"):
        self.cache_file = Path(cache_file)
        self.sent_warnings: Set[str] = self._load_cache()

    def _load_cache(self) -> Set[str]:
        """加载已发送的预警ID"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            logger.error(f"加载预警记录失败: {e}")
            return set()

    def _save_cache(self):
        """保存已发送的预警ID"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.sent_warnings), f)
        except Exception as e:
            logger.error(f"保存预警记录失败: {e}")

    def is_warning_sent(self, warning_id: str) -> bool:
        """检查预警是否已发送"""
        return warning_id in self.sent_warnings

    def add_warning(self, warning_id: str):
        """添加预警记录"""
        self.sent_warnings.add(warning_id)
        self._save_cache()

    def get_new_warnings(self, warnings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """获取新的预警信息"""
        return [
            warning for warning in warnings
            if not self.is_warning_sent(warning.get('id', ''))
        ]

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
        self._session = requests.Session()
        self.warning_tracker = WarningTracker()
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

    def fetch_warning(self) -> Optional[Dict[str, Any]]:
        """获取灾害预警数据"""
        logger.info("正在获取灾害预警数据...")
        params = {"location": self.config.location, "lang": "zh"}
        data = self._request(self.urls["warning"], params)
        if data:
            logger.info("成功获取灾害预警数据")
            return data
        else:
            logger.warning("未获取到灾害预警数据")
            return None

    def parse_warning(self, data: Optional[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
        """
        解析灾害预警数据
        
        Returns:
            tuple: (格式化的预警信息, 新的预警列表)
        """
        if not data or "warning" not in data or not data["warning"]:
            return "\n⚠️〚 生效中的灾害预警 〛⚠️\n暂无灾害预警信息", []

        warnings = data["warning"]
        new_warnings = self.warning_tracker.get_new_warnings(warnings)
        lines = ["\n⚠️〚 生效中的灾害预警 〛⚠️"]

        for warning in warnings:
            # 获取预警类型和等级
            warning_type = WARNING_TYPE_MAP.get(
                warning.get("type", ""),
                f"未知预警类型({warning.get('typeName', '')})"
            )
            warning_level = WARNING_LEVEL_MAP.get(
                warning.get("severity", ""),
                f"未知预警等级({warning.get('severity', '')})"
            )
            
            # 格式化时间
            def format_warning_time(time_str: str) -> str:
                try:
                    if not time_str:
                        return "未知"
                    dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M%z")
                    return dt.strftime("%m/%d %H:%M")
                except ValueError:
                    return "未知"

            # 处理预警文本
            warning_text = warning.get('text', '暂无详细说明')
            if '【' in warning_text and '】' in warning_text:
                warning_text = warning_text.split('】', 1)[1].strip()

            # 构建预警信息
            warning_info = [
                f"\n▌{warning.get('title', '未知预警')}",
                "━" * 20,
                f"│ 🏷️ 预警类型 │ {warning_type}",
                f"│ 🚨 预警等级 │ {warning_level}",
                f"│ 🕒 发布时间 │ {format_warning_time(warning.get('pubTime', ''))}",
                f"│ ⏳ 生效时段 │ {format_warning_time(warning.get('startTime', ''))} → {format_warning_time(warning.get('endTime', ''))}",
                f"│ 📌 发布单位 │ {warning.get('sender', '未知')}",
                "━" * 20,
                "📢 预警详情：",
                f"{warning_text}",
                "━" * 20,
            ]
            lines.extend(warning_info)

        return "\n".join(lines), new_warnings

def main():
    """主函数"""
    try:
        logger.info("开始获取灾害预警信息...")
        
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

        # 获取灾害预警信息
        warning_data = client.fetch_warning()
        if warning_data:
            warning_text, new_warnings = client.parse_warning(warning_data)
            logger.info(f"\n{warning_text}")
            
            # 只发送新的预警信息
            if new_warnings:
                logger.info(f"发现 {len(new_warnings)} 条新的预警信息")
                notify.send("灾害预警通知", warning_text)
                
                # 记录已发送的预警
                for warning in new_warnings:
                    client.warning_tracker.add_warning(warning.get('id', ''))
            else:
                logger.info("没有新的预警信息")

        logger.info("灾害预警信息获取完成")

    except Exception as e:
        error_msg = f"程序运行出错: {str(e)}"
        logger.error(error_msg)
        # 发送错误通知到青龙面板
        notify.send("灾害预警脚本错误", error_msg)
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()