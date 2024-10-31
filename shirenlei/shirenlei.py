import datetime
import hashlib
import base64
import os
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import pyaudio
import numpy as np
import wave
import pandas as pd
import subprocess
import random


STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识



# recording audio
def Monitor_MIC(th, filename, stopBit, rate=16000, max_duration=10):
    CHUNK = 512
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = rate
    PCM_OUTPUT_FILENAME = filename + ".pcm"
    p = pyaudio.PyAudio()
    
    # 打开音频流
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    frames = []  # 存储初始音频数据
    frames2 = []  # 存储录音数据

    start_time = time.time()  # 记录开始时间

    while True:
        # 读取麦克风输入，检测是否有信号超过阈值
        for _ in range(5):
            data = stream.read(CHUNK)
            frames.append(data)
        
        audio_data = np.frombuffer(data, dtype=np.int16)
        temp = np.max(audio_data)  # 获取音频数据的最大值
        
        # 检测到信号超过阈值，进入录音模式
        if temp > th:
            print("detected a signal")
            print('current threshold:', temp)
            less = []  # 记录低于阈值的次数
            
            while True:
                print("recording")
                for _ in range(30):
                    data2 = stream.read(CHUNK)
                    frames2.append(data2)
                
                audio_data2 = np.frombuffer(data2, dtype=np.int16)
                temp2 = np.max(audio_data2)  # 获取录音数据的最大值
                
                # 检查信号是否低于阈值
                if temp2 < th:
                    less.append(-1)
                    print("below threshold, counting:", less)
                    
                    if len(less) == stopBit:  # 如果低于阈值次数达到 stopBit，停止录音
                        break
                else:
                    less = []  # 重置计数

                # 检查录音时间是否超过最大时长
                if time.time() - start_time >= max_duration:
                    print("Maximum recording duration reached.")
                    break

            break

        # 如果没有检测到信号且达到最大监听时长，则停止
        if time.time() - start_time >= max_duration:
            print("Maximum listening duration reached without detecting signal.")
            break
    
    # 停止并关闭音频流
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # 如果录音数据不为空，则保存到文件
    if frames2:
        print(f"Saving recording to {PCM_OUTPUT_FILENAME}")
        with open(PCM_OUTPUT_FILENAME, 'wb') as f:
            f.write(b''.join(frames2))
    else:
        print("No valid recording detected, not saving.")

def monitor():
    result = subprocess.run(['python', '.\streaming_server\\test_client.py'])
    
    # 检查被调用程序的返回码
    if result.returncode == 0:
        print("Called program executed successfully.")
    else:
        print("Called program failed with return code:", result.returncode)
    
    print("Main program continues.")


def copy_random_wav():
    # 随机选择一个文件
    file_number = random.randint(1, 12)
    source_file = f"{file_number}.wav"
    destination_file = "answer.wav"

    try:
        # 打开源文件和目标文件
        with wave.open(source_file, 'rb') as src_wav:
            params = src_wav.getparams()
            frames = src_wav.readframes(src_wav.getnframes())

            with wave.open(destination_file, 'wb') as dest_wav:
                dest_wav.setparams(params)
                dest_wav.writeframes(frames)

        print(f"Copied {source_file} to {destination_file}")

    except FileNotFoundError:
        print(f"File {source_file} not found.")


def copy_to_streaming_server():
    destination_folder = "./streaming_server/"
    os.makedirs(destination_folder, exist_ok=True)
    destination_file = os.path.join(destination_folder, "answer.wav")
    
    try:
        # 打开源文件
        with wave.open("answer.wav", 'rb') as src_wav:
            params = src_wav.getparams()
            frames = src_wav.readframes(src_wav.getnframes())

            # 打开目标文件
            with wave.open(destination_file, 'wb') as dest_wav:
                dest_wav.setparams(params)
                dest_wav.writeframes(frames)

        print(f"Copied answer.wav to {destination_file}")
    except FileNotFoundError:
        print("answer.wav not found.")
        
if __name__ == "__main__":
    # 测试时候在此处正确填写相关信息即可运行
    while 1:
        #检测输入
        print("######### Say Someting! #########")
        Monitor_MIC(th=1600, filename="output", stopBit=3, rate=16000)
        if not os.path.exists("output.pcm"):
            continue

        #随机选择一个wav文件，把它复制到streamingserver文件夹中
        copy_random_wav()
        copy_to_streaming_server()
        print("#########  Over ##########")

        #调用streaming_server中的test_client,将数据传输到a2f
        monitor()
        os.remove("output.pcm")
