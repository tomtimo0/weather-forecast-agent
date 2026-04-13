"""气象数据检索工具"""

from datetime import datetime
import requests
from langchain.tools import tool

from src.config.settings import QWEATHER_API_KEY, QWEATHER_API_HOST


@tool
def get_current_time() -> str:
    """获取当前的日期和时间，格式为 YYYY-MM-DD HH:MM:SS。
    当用户提到"今天"、"现在"、"明天"等相对时间时，应先调用此工具确定当前时间。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def search_city(location: str, adm: str = "") -> dict:
    """根据城市名称搜索城市信息，返回城市的LocationID、经纬度等。
    用户提到任何地名时，应先调用此工具获取LocationID，再用于天气查询。

    Args:
        location: 城市名称、经纬度坐标或LocationID。支持模糊搜索，如"北京"或"beij"
        adm: 上级行政区划，用于过滤重名城市。如 location="朝阳" adm="北京" 只返回北京朝阳区
    """
    url = f"https://{QWEATHER_API_HOST}/geo/v2/city/lookup"
    params = {"location": location, "key": QWEATHER_API_KEY, "range": "cn"}
    if adm:
        params["adm"] = adm

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("code") != "200":
        return {"error": f"城市搜索失败，状态码：{data.get('code')}"}

    results = []
    for city in data.get("location", []):
        results.append({
            "name": city["name"],
            "id": city["id"],
            "lat": city["lat"],
            "lon": city["lon"],
            "adm2": city["adm2"],
            "adm1": city["adm1"],
            "country": city["country"]
        })
    return {"cities": results}


@tool
def get_forcast_weather(location: str, hours: str) -> dict:
    """获取指定地点的逐小时天气预报数据，包括温度、天气状况、风力风向、湿度、降水概率等。

    Args:
        location: 城市的LocationID（如"101010100"）或经纬度坐标（如"116.41,39.92"）。
                  LocationID可通过search_city工具获取。
        hours: 预报小时数，支持最多168小时预报，可选值：
               24h 24小时预报。
               72h 72小时预报。
               168h 168小时预报。
    """
    url = f"https://{QWEATHER_API_HOST}/v7/weather/{hours}"
    params = {"location": location, "key": QWEATHER_API_KEY}

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("code") != "200":
        return {"error": f"天气查询失败，状态码: {data.get('code')}"}

    hourly_list = []
    for hour in data.get("hourly", []):
        hourly_list.append({
            "fxTime": hour["fxTime"],
            "temp": f"{hour['temp']}°C",
            "text": hour["text"],
            "windDir": hour["windDir"],
            "windScale": f"{hour['windScale']}级",
            "humidity": f"{hour['humidity']}%",
            "pop": f"{hour['pop']}%",
            "precip": f"{hour['precip']}mm",
        })
    return {"hourly": hourly_list}
