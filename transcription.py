import os
import requests
import json
import time
import hashlib
import base64
import hmac
from dotenv import load_dotenv

load_dotenv()

APPID = os.getenv('APPID')
APISecret = os.getenv('APISecret')
APIKey = os.getenv('APIKey')

# 讯飞录音文件转写标准版 API 地址（正式环境）
UPLOAD_URL = "https://raasr.xfyun.cn/v2/api/upload"
GET_RESULT_URL = "https://raasr.xfyun.cn/v2/api/getResult"

def build_headers():
    """构建请求头，包含签名"""
    current_time = str(int(time.time()))
    # 拼接签名原始字符串
    sign_str = APIKey + current_time
    signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "X-Appid": APPID,
        "X-CurTime": current_time,
        "X-Param": "",  # 本示例不传额外参数，如需设置语种、标点等可在此添加 base64 编码的字符串
        "X-CheckSum": signature
    }
    return headers

def upload_audio(file_path):
    """上传音频文件，返回 task_id"""
    headers = build_headers()
    # 读取文件并转成 base64
    with open(file_path, 'rb') as f:
        file_content = base64.b64encode(f.read()).decode('utf-8')
    
    data = {
        "file": file_content,
        "fileName": os.path.basename(file_path),
        "fileType": os.path.splitext(file_path)[1][1:],  # 扩展名不带点
        "language": "zh_cn",   # 中文
        "hasSeperate": 1,      # 开启标点符号
    }
    
    # 将参数转为 JSON 字符串，并 base64 编码放入 X-Param
    param_str = json.dumps(data)
    param_base64 = base64.b64encode(param_str.encode('utf-8')).decode('utf-8')
    headers["X-Param"] = param_base64
    
    # 重新计算签名（因为 X-Param 变了）
    current_time = headers["X-CurTime"]
    sign_str = APIKey + current_time + param_base64
    headers["X-CheckSum"] = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    # 发送上传请求
    response = requests.post(UPLOAD_URL, headers=headers, data={}, proxies={"http": None, "https": None})
    result = response.json()
    if result.get("code") == "0":
        return result.get("data")
    else:
        print(f"上传失败: {result}")
        return None

def get_transcription(task_id):
    """查询转写结果"""
    headers = build_headers()
    # 构建查询参数
    param = {"taskId": task_id}
    param_str = json.dumps(param)
    param_base64 = base64.b64encode(param_str.encode('utf-8')).decode('utf-8')
    headers["X-Param"] = param_base64
    
    # 重新计算签名
    current_time = headers["X-CurTime"]
    sign_str = APIKey + current_time + param_base64
    headers["X-CheckSum"] = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    response = requests.get(GET_RESULT_URL, headers=headers, proxies={"http": None, "https": None})
    result = response.json()
    if result.get("code") == "0":
        # 成功获取，返回包含文本的 data
        return result.get("data")
    else:
        print(f"查询失败: {result}")
        return None

def transcribe_audio(file_path):
    """主函数：上传音频并轮询结果，返回 (text, error)"""
    task_id = upload_audio(file_path)
    if not task_id:
        return None, "上传文件失败"
    
    # 轮询结果，最多等待 5 分钟（根据文件大小可调整）
    max_retries = 60   # 60次 * 5秒 = 300秒
    retry_interval = 5
    for _ in range(max_retries):
        data = get_transcription(task_id)
        if data:
            status = data.get("status")
            if status == "finished":
                # 转写完成，提取文本
                # 注意：返回的数据中可能有多个字段，如 'result' 是转写结果字符串
                text = data.get("result", "")
                return text, None
            elif status == "failed":
                return None, data.get("message", "转写失败")
        time.sleep(retry_interval)
    return None, "转写超时"

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
