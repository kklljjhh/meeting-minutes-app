import os
import streamlit as st
import requests
import json
import time
import hashlib
import base64
import hmac
import urllib.parse
import random
import string
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 配置读取：优先从 Streamlit secrets 读取，其次从环境变量读取
# ============================================================
def _get_secret(key, default=None):
    """先从 Streamlit secrets 读取，失败则从环境变量读取"""
    try:
        # 支持两种 secrets 结构：
        # 1. [iflytek] 分组: st.secrets["iflytek"]["appid"]
        # 2. 顶层键: st.secrets["appid"]
        if "iflytek" in st.secrets and key in st.secrets["iflytek"]:
            return st.secrets["iflytek"][key]
        elif key in st.secrets:
            return st.secrets[key]
    except (KeyError, FileNotFoundError, TypeError):
        pass

    val = os.environ.get(key, default)
    if val is None and default is None:
        raise ValueError(
            f"缺少必要配置：{key}。请在 .streamlit/secrets.toml 或环境变量中设置。"
        )
    return val


def get_config():
    """获取讯飞星火大模型录音文件转写配置"""
    return {
        "appid": _get_secret("appid"),
        "api_key": _get_secret("api_key"),      # 对应 accessKeyId
        "api_secret": _get_secret("api_secret"),  # 对应 access_key_secret，用于签名
    }


# ============================================================
# 讯飞星火大模型录音文件转写 API 配置
# ============================================================
BASE_URL = "https://office-api-ist-dx.iflyaisol.com"
UPLOAD_URL = f"{BASE_URL}/v2/upload"
GET_RESULT_URL = f"{BASE_URL}/v2/getResult"


# ============================================================
# 签名生成（HMAC-SHA1）
# ============================================================
def generate_signature(params, api_secret):
    """
    生成签名（HMAC-SHA1）
    1. 排除 signature 字段和空值
    2. 按参数名自然排序（ASCII升序）
    3. 对每个键和值进行标准URL编码（不保留任何特殊字符，safe=""）
    4. 用 & 连接成 baseString
    5. HMAC-SHA1(baseString, api_secret) -> Base64
    """
    # 排除 signature 字段和空值/空字符串
    filtered = {
        k: v for k, v in params.items()
        if k != "signature" and v is not None and str(v) != ""
    }

    # 按参数名自然排序
    sorted_items = sorted(filtered.items(), key=lambda x: x[0])

    # URL编码（不保留任何特殊字符）并构建 baseString
    encoded_pairs = []
    for k, v in sorted_items:
        k_enc = urllib.parse.quote(str(k), safe="")
        v_enc = urllib.parse.quote(str(v), safe="")
        encoded_pairs.append(f"{k_enc}={v_enc}")

    base_string = "&".join(encoded_pairs)

    # HMAC-SHA1 签名
    signature = hmac.new(
        api_secret.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1
    ).digest()

    return base64.b64encode(signature).decode("utf-8")


def generate_random_string(length=16):
    """生成16位随机字符串（大小写字母+数字）"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def get_datetime():
    """获取当前时间，格式：yyyy-MM-dd'T'HH:mm:ss±HHmm（东八区）"""
    return time.strftime("%Y-%m-%dT%H:%M:%S+0800", time.localtime())


# ============================================================
# 音频上传接口（/v2/upload）
# ============================================================
def upload_audio(file_path):
    """上传音频文件，返回 order_id"""
    config = get_config()
    appid = config["appid"]
    api_key = config["api_key"]
    api_secret = config["api_secret"]

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    # 构建查询参数（参与签名的参数）
    params = {
        "appId": appid,
        "accessKeyId": api_key,
        "dateTime": get_datetime(),
        "signatureRandom": generate_random_string(),
        "fileSize": str(file_size),
        "fileName": file_name,
        "language": "autodialect",       # 中英 + 202种方言免切识别
        "durationCheckDisable": "true",  # 关闭音频时长校验，简化流程
        "eng_smoothproc": "true",        # 开启顺滑
    }

    # 生成签名
    signature = generate_signature(params, api_secret)
    params["signature"] = signature

    # 构建完整URL（同样使用 quote safe="" 确保编码一致）
    query_parts = []
    for k, v in params.items():
        k_enc = urllib.parse.quote(str(k), safe="")
        v_enc = urllib.parse.quote(str(v), safe="")
        query_parts.append(f"{k_enc}={v_enc}")
    query_string = "&".join(query_parts)

    url = f"{UPLOAD_URL}?{query_string}"

    # 读取文件二进制内容
    with open(file_path, 'rb') as f:
        file_data = f.read()

    headers = {
        "Content-Type": "application/octet-stream",
    }

    # 发送请求（直接传二进制文件流）
    response = requests.post(url, headers=headers, data=file_data, timeout=60)
    result = response.json()

    if result.get("code") == "000000":
        content = result.get("content", {})
        order_id = content.get("orderId")
        if not order_id:
            raise Exception(f"上传成功但未返回订单ID：{result}")
        return order_id
    else:
        error_msg = result.get("descInfo", "未知错误")
        raise Exception(f"上传失败 [{result.get('code')}]: {error_msg}")


# ============================================================
# 结果查询接口（/v2/getResult）
# ============================================================
def get_transcription_result(order_id):
    """查询转写结果，返回 content 对象"""
    config = get_config()
    appid = config["appid"]
    api_key = config["api_key"]
    api_secret = config["api_secret"]

    # 构建查询参数
    params = {
        "accessKeyId": api_key,
        "dateTime": get_datetime(),
        "signatureRandom": generate_random_string(),
        "orderId": order_id,
        "resultType": "transfer",  # 查询转写结果
    }

    # 生成签名
    signature = generate_signature(params, api_secret)
    params["signature"] = signature

    # 构建URL
    query_parts = []
    for k, v in params.items():
        k_enc = urllib.parse.quote(str(k), safe="")
        v_enc = urllib.parse.quote(str(v), safe="")
        query_parts.append(f"{k_enc}={v_enc}")
    query_string = "&".join(query_parts)

    url = f"{GET_RESULT_URL}?{query_string}"

    headers = {
        "Content-Type": "application/json",
    }

    # 发送POST请求，请求体为空JSON对象 {}
    response = requests.post(url, headers=headers, json={}, timeout=30)
    result = response.json()

    if result.get("code") == "000000":
        return result.get("content", {})
    else:
        error_msg = result.get("descInfo", "未知错误")
        raise Exception(f"查询失败 [{result.get('code')}]: {error_msg}")


# ============================================================
# 从转写结果中提取纯文本
# ============================================================
def extract_text_from_result(content):
    """从转写结果 content 中提取纯文本"""
    order_result = content.get("orderResult", "")
    if not order_result:
        return ""

    try:
        result_obj = json.loads(order_result)
    except json.JSONDecodeError:
        return order_result

    # 优先使用 lattice（顺滑后结果），其次 lattice2（原始结果）
    lattice = result_obj.get("lattice", []) or result_obj.get("lattice2", [])
    if not lattice:
        return ""

    text_parts = []

    for item in lattice:
        json_1best = item.get("json_1best", "")
        if not json_1best:
            continue
        try:
            best_obj = json.loads(json_1best)
            st = best_obj.get("st", {})
            rt_list = st.get("rt", [])
            for rt in rt_list:
                ws_list = rt.get("ws", [])
                for ws in ws_list:
                    cw_list = ws.get("cw", [])
                    for cw in cw_list:
                        w = cw.get("w", "")
                        # wp: n=正常词, s=顺滑, p=标点, g=分段
                        if w:
                            text_parts.append(w)
        except json.JSONDecodeError:
            continue

    return "".join(text_parts)


# ============================================================
# 主函数：上传音频并轮询结果
# ============================================================
def transcribe_audio(file_path):
    """上传音频并轮询结果，返回 (text, error)"""
    try:
        order_id = upload_audio(file_path)
        if not order_id:
            return None, "上传文件失败：未获取到订单ID"

        # 轮询结果
        max_retries = 120      # 120次 × 3秒 = 6分钟
        retry_interval = 3     # 每3秒查询一次

        for i in range(max_retries):
            content = get_transcription_result(order_id)
            order_info = content.get("orderInfo", {})
            status = order_info.get("status")

            if status == 4:      # 订单已完成
                text = extract_text_from_result(content)
                return text, None
            elif status == -1:   # 订单失败
                fail_type = order_info.get("failType", 99)
                fail_messages = {
                    1: "音频上传失败",
                    2: "音频转码失败",
                    3: "音频识别失败",
                    4: "音频时长超限（最大5小时）",
                    5: "音频校验失败（时长不匹配）",
                    6: "静音文件",
                    7: "翻译失败",
                    8: "账号无翻译权限",
                    9: "转写质检失败",
                    10: "转写质检未匹配出关键词",
                    11: "未开启对应能力",
                    12: "音频语种分析失败",
                    99: "其他错误",
                }
                return None, f"转写失败：{fail_messages.get(fail_type, f'未知错误（类型{fail_type}）')}"
            elif status in [0, 3]:  # 0=已创建, 3=处理中
                time.sleep(retry_interval)
                continue
            else:
                time.sleep(retry_interval)

        return None, "转写超时，请稍后通过订单ID查询结果"

    except Exception as e:
        return None, str(e)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        text, error = transcribe_audio(file_path)
        if text:
            print("转写成功：")
            print(text)
        else:
            print(f"转写失败：{error}")
