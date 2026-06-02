import os
import requests
import json
import time
import hashlib
import base64
from dotenv import load_dotenv

load_dotenv()

APPID = os.getenv('APPID')
APISecret = os.getenv('APISecret')
APIKey = os.getenv('APIKey')
BASE_URL = os.getenv('BASE_URL', 'https://office-api-ist-dx.iflyaisol.com')

def generate_signature(api_key, api_secret, timestamp):
    sign_str = f"{api_key}{timestamp}{api_secret}"
    signature = hashlib.sha256(sign_str.encode('utf-8')).hexdigest()
    return signature

def upload_audio(file_path):
    timestamp = str(int(time.time()))
    signature = generate_signature(APIKey, APISecret, timestamp)
    
    url = f"{BASE_URL}/api/audio/upload"
    
    headers = {
        'appId': APPID,
        'apiKey': APIKey,
        'timestamp': timestamp,
        'signature': signature
    }
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f)}
        response = requests.post(url, headers=headers, files=files)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('code') == 0:
            return result.get('data', {}).get('taskId')
    return None

def get_transcription(task_id):
    timestamp = str(int(time.time()))
    signature = generate_signature(APIKey, APISecret, timestamp)
    
    url = f"{BASE_URL}/api/audio/result"
    
    headers = {
        'appId': APPID,
        'apiKey': APIKey,
        'timestamp': timestamp,
        'signature': signature
    }
    
    params = {'taskId': task_id}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('code') == 0:
            return result.get('data', {})
    return None

def transcribe_audio(file_path):
    task_id = upload_audio(file_path)
    if not task_id:
        return None, "上传文件失败"
    
    max_retries = 60
    retry_interval = 5
    
    for _ in range(max_retries):
        result = get_transcription(task_id)
        if result:
            status = result.get('status')
            if status == 'completed':
                return result.get('text'), None
            elif status == 'failed':
                return None, result.get('message', '转写失败')
        
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
