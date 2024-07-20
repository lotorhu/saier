# -*- coding:utf-8 -*-
#
#   author: iflytek
#
#  本demo测试时运行的环境为：Windows + Python3.7
#  本demo测试成功运行时所安装的第三方库及其版本如下，您可自行逐一或者复制到一个新的txt文件利用pip一次性安装：
#   cffi==1.12.3
#   gevent==1.4.0
#   greenlet==0.4.15
#   pycparser==2.19
#   six==1.12.0
#   websocket==0.2.1
#   websocket-client==0.56.0
#
#  语音听写流式 WebAPI 接口调用示例 接口文档（必看）：https://doc.xfyun.cn/rest_api/语音听写（流式版）.html
#  webapi 听写服务参考帖子（必看）：http://bbs.xfyun.cn/forum.php?mod=viewthread&tid=38947&extra=
#  语音听写流式WebAPI 服务，热词使用方式：登陆开放平台https://www.xfyun.cn/后，找到控制台--我的应用---语音听写（流式）---服务管理--个性化热词，
#  设置热词
#  注意：热词只能在识别的时候会增加热词的识别权重，需要注意的是增加相应词条的识别率，但并不是绝对的，具体效果以您测试为准。
#  语音听写流式WebAPI 服务，方言试用方法：登陆开放平台https://www.xfyun.cn/后，找到控制台--我的应用---语音听写（流式）---服务管理--识别语种列表
#  可添加语种或方言，添加后会显示该方言的参数值
#  错误码链接：https://www.xfyun.cn/document/error-code （code返回错误码时必看）
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
import websocket
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
from sparkai.llm.llm import ChatSparkLLM, ChunkPrintHandler
from sparkai.core.messages import ChatMessage

STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

#星火认知大模型Spark Max的URL值，其他版本大模型URL值请前往文档（https://www.xfyun.cn/doc/spark/Web.html）查看
SPARKAI_URL = 'wss://spark-api.xf-yun.com/v3.5/chat'
#星火认知大模型调用秘钥信息，请前往讯飞开放平台控制台（https://console.xfyun.cn/services/bm35）查看
SPARKAI_APP_ID = 'f6282405'
SPARKAI_API_SECRET = 'MDgzM2MxOTE4MTg2OTJmYjk1ODI4Nzgx'
SPARKAI_API_KEY = '4e3ef72816c90cefb2e3772dff82052a'
#星火认知大模型Spark Max的domain值，其他版本大模型domain值请前往文档（https://www.xfyun.cn/doc/spark/Web.html）查看
SPARKAI_DOMAIN = 'generalv3.5'

finally_result = ""
AI_answer_pcm = './answer.pcm'

# This function is used to transfer .pcm to .wav
# param: channels 信道数 bits 采样位 sample_rate 采样率
def pcm2wav(pcm_file, wav_file, channels=1, bits=16, sample_rate=16000):
    pcmf = open(pcm_file, 'rb')
    pcmdata = pcmf.read()
    pcmf.close()
 
    if bits % 8 != 0:
        raise ValueError("bits % 8 must == 0. now bits:" + str(bits))
 
    wavfile = wave.open(wav_file, 'wb')
    wavfile.setnchannels(channels)
    wavfile.setsampwidth(bits // 8)
    wavfile.setframerate(sample_rate)
    wavfile.writeframes(pcmdata)
    wavfile.close()

# This class tries converting text to speech.
# The bits have to be 8k or 18k
# The file's format has to be pcm、mp3、speex（8k）、speex-wb（16k）
# The length of text should be less than 8000 bytes(About 2000 characters)
class text_to_speech(object):
    def __init__(self, APPID, APIKey, APISecret, Text):
        # Get the parameters: APPID, APIKey, APISecret are used to authorized, while the text will be converted to audio.
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.Text = Text

        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)，更多个性化参数可在官网查看
        self.BusinessArgs = {"aue": "raw", "auf": "audio/L16;rate=16000", "vcn": "xiaoyan", "tte": "utf8"}
        self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")}
        #使用小语种须使用以下方式，此处的unicode指的是 utf16小端的编码方式，即"UTF-16LE"”
        #self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-16')), "UTF8")}

    # 生成url
    def create_url(self):
        url = 'wss://tts-api.xfyun.cn/v2/tts'
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        # print("date: ",date)
        # print("v: ",v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        # print('websocket url :', url)
        return url

def text_to_speech_on_message(ws, message):
    try:
        message =json.loads(message)
        code = message["code"]
        sid = message["sid"]
        audio = message["data"]["audio"]
        audio = base64.b64decode(audio)
        status = message["data"]["status"]
        #print(message)
        if status == 2:
            print("ws is closed")
            ws.close()
        if code != 0:
            errMsg = message["message"]
            print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
        else:

            with open(AI_answer_pcm, 'ab') as f:
                f.write(audio)

    except Exception as e:
        print("receive msg,but parse exception:", e)



# 收到websocket错误的处理
def text_to_speech_on_error(ws, error):
    print("### error:", error)


# 收到websocket关闭的处理
def text_to_speech_on_close(ws,a,b):
    print("### closed ###")


# 收到websocket连接建立的处理
def text_to_speech_on_open(ws):
    def run(*args):
        d = {"common": text_to_speech.CommonArgs,
             "business": text_to_speech.BusinessArgs,
             "data": text_to_speech.Data,
             }
       # print("text_to_speech.Data", text_to_speech.Data)
        d = json.dumps(d)
        print("------>开始发送文本数据")
        ws.send(d)
        if os.path.exists(AI_answer_pcm):
            os.remove(AI_answer_pcm)

    thread.start_new_thread(run, ())

class speech_to_text(object):
    # 初始化
    def __init__(self, APPID, APIKey, APISecret, AudioFile):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.AudioFile = AudioFile

        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)，更多个性化参数可在官网查看
        self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo":1,"vad_eos":10000}

    # 生成url
    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        # print("date: ",date)
        # print("v: ",v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        # print('websocket url :', url)
        return url


# 收到websocket消息的处理
def speech_to_text_on_message(ws, message):
    global finally_result
    try:
        code = json.loads(message)["code"]
        sid = json.loads(message)["sid"]
        if code != 0:
            errMsg = json.loads(message)["message"]
            print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))

        else:
            data = json.loads(message)["data"]["result"]["ws"]
            # print(json.loads(message))
            result = ""
            for i in data:
                for w in i["cw"]:
                    result += w["w"]
            # data是网站接收到声音后，传回来的包括翻译文本的json文件，其中result则是文本
            # 这里由于使用流式传输，所以需要把所有的result叠加在一起放在finally_result
            finally_result += str(result)
            print("sid:%s call success!,data is:%s" % (sid, json.dumps(data, ensure_ascii=False)))
    except Exception as e:
        print("receive msg,but parse exception:", e)

# 收到websocket错误的处理
def speech_to_text_on_error(ws, error):
    print("### error:", error)

# 收到websocket关闭的处理
def speech_to_text_on_close(ws,a,b):
    print("### closed ###")

# 收到websocket连接建立的处理
def speech_to_text_on_open(ws):
    def run(*args):
        frameSize = 8000  # 每一帧的音频大小
        intervel = 0.04  # 发送音频间隔(单位:s)
        status = STATUS_FIRST_FRAME  # 音频的状态信息，标识音频是第一帧，还是中间帧、最后一帧

        with open(speech_to_text.AudioFile, "rb") as fp:
            while True:
                buf = fp.read(frameSize)
                # 文件结束
                if not buf:
                    status = STATUS_LAST_FRAME
                # 第一帧处理
                # 发送第一帧音频，带business 参数
                # appid 必须带上，只需第一帧发送
                if status == STATUS_FIRST_FRAME:

                    d = {"common": speech_to_text.CommonArgs,
                         "business": speech_to_text.BusinessArgs,
                         "data": {"status": 0, "format": "audio/L16;rate=16000",
                                  "audio": str(base64.b64encode(buf), 'utf-8'),
                                  "encoding": "raw"}}
                    d = json.dumps(d)
                    ws.send(d)
                    status = STATUS_CONTINUE_FRAME
                # 中间帧处理
                elif status == STATUS_CONTINUE_FRAME:
                    d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                  "audio": str(base64.b64encode(buf), 'utf-8'),
                                  "encoding": "raw"}}
                    ws.send(json.dumps(d))
                # 最后一帧处理
                elif status == STATUS_LAST_FRAME:
                    d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                  "audio": str(base64.b64encode(buf), 'utf-8'),
                                  "encoding": "raw"}}
                    ws.send(json.dumps(d))
                    time.sleep(1)
                    break
                # 模拟音频采样间隔
                time.sleep(intervel)
        ws.close()

    thread.start_new_thread(run, ())

# recording audio
def Monitor_MIC(th, filename, stopBit, rate=16000):
    CHUNK = 512
    FORMAT = pyaudio.paInt16 # 音频格式
    CHANNELS = 1 # 声道数
    RATE = rate  # 使用传入的采样率
    PCM_OUTPUT_FILENAME = filename + ".pcm" # 输出文件名
    p = pyaudio.PyAudio()
    
    # 初始化 PyAudio 对象并打开音频流
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    frames = []
    frames2 = []
    # 循环读取麦克风输入，并将数据存储在 frames 列表中。 将读取的数据转换为 numpy 数组，并找到最大值 temp。
    # 如果 temp 超过阈值 th，则进入录音模式。 在录音模式中，继续读取音频数据并存储到 frames2 列表中。
    # 如果连续 less 个循环检测到的音频信号低于阈值，则认为录音结束。
    while True:
        for _ in range(5):
            data = stream.read(CHUNK)
            frames.append(data)
        
        audio_data = np.frombuffer(data, dtype=np.int16)
        temp = np.max(audio_data)
        
        if temp > th:
            print("detected a signal")
            print('current threshold:', temp)
            less = []
            
            while True:
                print("recording")
                for _ in range(30):
                    data2 = stream.read(CHUNK)
                    frames2.append(data2)
                
                audio_data2 = np.frombuffer(data2, dtype=np.int16)
                temp2 = np.max(audio_data2)
                
                if temp2 < th:
                    less.append(-1)
                    print("below threshold, counting:", less)
                    
                    if len(less) == stopBit:#修改th以及less可控制等待时间
                        break
                else:
                    less = []
            break
    
    # 停止并关闭音频流，终止 PyAudio 对象，将录音数据保存为 pcm 文件
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    if frames2:
        with open(PCM_OUTPUT_FILENAME, 'wb') as f:
            f.write(b''.join(frames2))

def AI_responder():
    spark = ChatSparkLLM(
        spark_api_url=SPARKAI_URL,
        spark_app_id=SPARKAI_APP_ID,
        spark_api_key=SPARKAI_API_KEY,
        spark_api_secret=SPARKAI_API_SECRET,
        spark_llm_domain=SPARKAI_DOMAIN,
        streaming=False,
    )
    messages = [ChatMessage(
        role="user",
        content=finally_result
    )]
    handler = ChunkPrintHandler()
    a = spark.generate([messages], callbacks=[handler])
    # print("Raw Data", a)
    text = a.generations[0][0].text
    return text

if __name__ == "__main__":
    # 测试时候在此处正确填写相关信息即可运行
    while 1:
        print("######### Say Someting! #########")
        time1 = datetime.now()
        Monitor_MIC(th=1000, filename="output", stopBit=3, rate=16000)
        speech_to_text = speech_to_text(APPID=SPARKAI_APP_ID, APISecret=SPARKAI_API_SECRET,
                            APIKey=SPARKAI_API_KEY,
                            AudioFile=r'output.pcm')
        websocket.enableTrace(False)
        wsUrl = speech_to_text.create_url()
        ws = websocket.WebSocketApp(wsUrl, on_message = speech_to_text_on_message, on_error = speech_to_text_on_error, on_close = speech_to_text_on_close)
        ws.on_open = speech_to_text_on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        time2 = datetime.now()
        print("audio to text(s):", time2-time1)
        print("finally_result",finally_result)

        answer = AI_responder()
        time1 = datetime.now()
        print("AI respond(s):", time1-time2)
        print("answer",answer)

        text_to_speech = text_to_speech(APPID=SPARKAI_APP_ID, APISecret=SPARKAI_API_SECRET,
                       APIKey=SPARKAI_API_KEY,
                       Text=answer)
        websocket.enableTrace(False)
        WSUrl = text_to_speech.create_url()
        WS = websocket.WebSocketApp(WSUrl, on_message=text_to_speech_on_message, on_error=text_to_speech_on_error, on_close=text_to_speech_on_close)
        WS.on_open = text_to_speech_on_open
        WS.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

        time2 = datetime.now()
        print("text to audio(s):", time2-time1)
        
        pcm2wav("answer.pcm", "answer.wav")
        os.remove("answer.pcm")
        os.remove("output.pcm")

        finally_result = ""
