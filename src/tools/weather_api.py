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
    用户提到任何地名时，应先调用此工具获取LocationID或者经纬度，再用于天气查询。

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


@tool
def get_current_weather(location: str) -> dict:
    """获取指定地点的实时天气数据（近实时，有5-20分钟延迟）。

    Args:
        location: 城市的LocationID（如"101010100"）或经纬度坐标（如"116.41,39.92"）。
                  LocationID可通过search_city工具获取。
    """
    url = f"https://{QWEATHER_API_HOST}/v7/weather/now"
    params = {"location": location, "key": QWEATHER_API_KEY}

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("code") != "200":
        return {"error": f"实时天气查询失败，状态码: {data.get('code')}"}

    now = data["now"]
    return {
        "obsTime": now["obsTime"],
        "temp": f"{now['temp']}°C",
        "feelsLike": f"{now['feelsLike']}°C",
        "text": now["text"],
        "windDir": now["windDir"],
        "windScale": f"{now['windScale']}级",
        "windSpeed": f"{now['windSpeed']}km/h",
        "humidity": f"{now['humidity']}%",
        "precip": f"{now['precip']}mm",
        "pressure": f"{now['pressure']}hPa",
        "vis": f"{now['vis']}km",
    }


@tool
def get_daily_forecast(location: str, days: str) -> dict:
    """获取指定地点的逐日天气预报，包括每天的最高最低温度、白天夜间天气、日出日落等。

    Args:
        location: 城市的LocationID（如"101010100"）或经纬度坐标（如"116.41,39.92"）。
                  LocationID可通过search_city工具获取。
        days: 预报天数，可选值：
              3d 3天预报。
              7d 7天预报。
              10d 10天预报。
              15d 15天预报。
              30d 30天预报。
    """
    url = f"https://{QWEATHER_API_HOST}/v7/weather/{days}"
    params = {"location": location, "key": QWEATHER_API_KEY}

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("code") != "200":
        return {"error": f"每日预报查询失败，状态码: {data.get('code')}"}

    daily_list = []
    for day in data.get("daily", []):
        daily_list.append({
            "fxDate": day["fxDate"],
            "tempMax": f"{day['tempMax']}°C",
            "tempMin": f"{day['tempMin']}°C",
            "textDay": day["textDay"],
            "textNight": day["textNight"],
            "windDirDay": day["windDirDay"],
            "windScaleDay": f"{day['windScaleDay']}级",
            "windDirNight": day["windDirNight"],
            "windScaleNight": f"{day['windScaleNight']}级",
            "humidity": f"{day['humidity']}%",
            "precip": f"{day['precip']}mm",
            "uvIndex": day["uvIndex"],
            "sunrise": day["sunrise"],
            "sunset": day["sunset"],
        })
    return {"daily": daily_list}


@tool
def get_weather_warning(latitude: str, longitude: str) -> dict:
    """获取指定经纬度位置当前生效的天气预警信息，如暴雨、大风、高温等预警。
    经纬度可通过search_city工具获取。

    Args:
        latitude: 纬度，十进制，最多小数点后两位，如"39.90"
        longitude: 经度，十进制，最多小数点后两位，如"116.40"
    """
    url = f"https://{QWEATHER_API_HOST}/weatheralert/v1/current/{latitude}/{longitude}"
    params = {"key": QWEATHER_API_KEY, "localTime": "true"}

    response = requests.get(url, params=params)
    data = response.json()

    metadata = data.get("metadata", {})
    if metadata.get("zeroResult", False):
        return {"alerts": [], "message": "当前该地区无预警信息"}

    alerts_list = []
    for alert in data.get("alerts", []):
        alerts_list.append({
            "headline": alert.get("headline", ""),
            "severity": alert.get("severity", ""),
            "eventType": alert.get("eventType", {}).get("name", ""),
            "colorCode": alert.get("color", {}).get("code", ""),
            "senderName": alert.get("senderName", ""),
            "issuedTime": alert.get("issuedTime", ""),
            "expireTime": alert.get("expireTime", ""),
            "description": alert.get("description", ""),
            "instruction": alert.get("instruction", ""),
        })
    return {"alerts": alerts_list}


@tool
def get_weather_indices(location: str, days: str, types: str = "0") -> dict:
    """获取天气生活指数预报，如穿衣指数、洗车指数、运动指数、紫外线指数等。

    Args:
        location: 城市的LocationID（如"101010100"）或经纬度坐标（如"116.41,39.92"）。
                  LocationID可通过search_city工具获取。
        days: 预报天数，可选值：
              1d 1天预报。
              3d 3天预报。
        types: 生活指数类型ID，多个用英文逗号分隔。传"0"表示查询所有类型。完整类型列表：
               1-运动指数 2-洗车指数 3-穿衣指数 4-感冒指数 5-紫外线指数
               6-旅游指数 7-空气污染扩散条件指数 8-舒适度指数 9-交通指数
               10-空调开启指数 11-太阳镜指数 12-化妆指数 13-晾晒指数
               14-过敏指数 15-钓鱼指数 16-防晒指数
    """
    url = f"https://{QWEATHER_API_HOST}/v7/indices/{days}"
    params = {"location": location, "key": QWEATHER_API_KEY, "type": types}

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("code") != "200":
        return {"error": f"天气指数查询失败，状态码: {data.get('code')}"}

    indices_list = []
    for item in data.get("daily", []):
        indices_list.append({
            "date": item["date"],
            "name": item["name"],
            "level": item["level"],
            "category": item["category"],
            "text": item.get("text", ""),
        })
    return {"indices": indices_list}
