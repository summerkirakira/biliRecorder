import struct

from pydantic import BaseModel, validator
from enum import IntEnum
import requests
from config import get_config, save_config, Config
from typing import Optional
import asyncio
import aiohttp
import json
import aiofiles
from services.downloader import LiveDefaultDownloader
from services.user_info import get_user_info_by_mid, UserInfo
from loguru import logger

config = get_config()


class RoomInfo(BaseModel):
    class Data(BaseModel):
        class LiveStatus(IntEnum):
            NOT_LIVE = 0
            LIVE = 1
            VIDEO = 2

        uid: int
        room_id: int
        short_id: int
        attention: int
        online: int
        is_portrait: bool
        description: str
        live_status: LiveStatus
        area_id: int
        area_name: str
        parent_area_id: int
        parent_area_name: str
        background: str
        title: str
        user_cover: str
        keyframe: str
        live_time: str
        tags: str
        is_strict_room: bool
    data: Data
    code: int
    message: str


class VideoStreamInfo(BaseModel):
    class Code(IntEnum):
        SUCCESS = 0
        INVALID_ARGUMENT = -400
        NO_ROOM = 19002003

    class Data(BaseModel):
        class QualityDescription(BaseModel):
            qn: int
            desc: str

        class Durl(BaseModel):
            order: int
            length: int
            url: str

            @validator('url')
            def format_url(cls, v):
                return v.replace("\\u0026", "&")

        current_quality: int
        accept_quality: list[str]
        current_qn: int
        quality_description: list[QualityDescription]
        durl: list[Durl]

    code: Code
    message: str
    ttl: int
    data: Data


class LiveService:
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',
        'Referer': 'https://live.bilibili.com/',
        'Origin': 'https://live.bilibili.com',
        'Sec-Fetch-Site': 'same-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept': 'application/json, text/plain, */*',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }

    def __init__(self):
        self.cookies = config.cookies
        self.session = None

    async def get_room_info(self, room_id: int) -> RoomInfo:
        # 获取房间信息
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.default_headers, cookies=self.cookies)
        url = 'https://api.live.bilibili.com/room/v1/Room/get_info'
        params = {
            'room_id': room_id
        }
        async with self.session.get(url, params=params) as response:
            return RoomInfo.parse_obj(await response.json())

    async def get_video_stream_info(self, room_id: int, qn: int) -> VideoStreamInfo:
        # 获取视频流信息
        url = 'https://api.live.bilibili.com/room/v1/Room/playUrl'
        params = {
            'cid': room_id,
            'qn': qn,
            'platform': 'web'
        }
        async with self.session.get(url, params=params) as response:
            return VideoStreamInfo.parse_obj(await response.json())

    async def get_video_stream_url(self, room_id: int) -> str:
        # 获取视频流链接
        video_stream_info = await self.get_video_stream_info(room_id, 10000)
        if video_stream_info.code != VideoStreamInfo.Code.SUCCESS:
            raise ValueError(f'获取视频流信息失败: {video_stream_info.message}')
        return video_stream_info.data.durl[0].url

    class DownloadStatus(BaseModel):
        class Status(IntEnum):
            DOWNLOADING = 0
            FINISHED = 1
            FAILED = 2

        status: Status
        progress: int = 0
        start_time: int = 0

    class MonitorRoom:
        class MessageStreamCommand(IntEnum):
            HEARTBEAT = 2
            HEARTBEAT_REPLY = 3
            COMMAND = 5
            AUTHENTICATION = 7
            AUTHENTICATION_REPLY = 8

        class DanmuMessage(BaseModel):
            cmd: str
            info: list[dict]

        def __init__(self, room_config: Config.MonitorLiveRoom):
            self.room_id = room_config.short_id
            self.live = False
            self.down_video = False
            self.room_config = room_config
            self.room_info: Optional[RoomInfo] = None
            self.download_status: Optional[LiveService.DownloadStatus] = None
            self.downloader: Optional[LiveDefaultDownloader] = None
            self.message_stream_data = None
            self.session = None
            self.message_ws = None

        async def update_room_info(self):
            while True:
                try:
                    self.room_info = await live_service.get_room_info(self.room_id)
                    self.live = self.room_info.data.live_status == RoomInfo.Data.LiveStatus.LIVE
                    if self.live and self.download_status is None and self.room_config.auto_download:
                        url = await live_service.get_video_stream_url(self.room_id)
                        asyncio.get_running_loop().create_task(self.download_live_video(url))
                        self.download_status = LiveService.DownloadStatus(status=LiveService.DownloadStatus.Status.DOWNLOADING)
                except Exception as e:
                    logger.error(f'更新房间信息失败: {e}')
                await asyncio.sleep(10)

        async def download_live_video(self, url: str):
            """
            下载直播视频
            """
            self.download_status = LiveService.DownloadStatus(status=LiveService.DownloadStatus.Status.DOWNLOADING)
            self.downloader = LiveDefaultDownloader(url, '/Users/forever/PycharmProjects/biliRecorder', self.room_info)
            self.download_status = LiveService.DownloadStatus(status=LiveService.DownloadStatus.Status.FINISHED)
            self.downloader.download()
            while True:
                await asyncio.sleep(5)
                print(self.downloader.get_download_status())

        async def get_live_message_stream_key(self, room_id: int) -> str:
            # 获取直播弹幕流密钥
            url = 'https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo'
            params = {
                'room_id': room_id
            }
            async with self.session.get(url, params=params) as response:
                self.message_stream_data = LiveService.MessageKeyResponse.parse_obj(await response.json())
                return self.message_stream_data.data.token

        async def init_message_ws(self):
            # 初始化弹幕流连接
            self.session = aiohttp.ClientSession(headers=LiveService.default_headers, cookies=get_config().cookies)
            key = await self.get_live_message_stream_key(self.room_id)
            self.message_ws = await self.session.ws_connect('wss://{}:{}/sub'.format(
                self.message_stream_data.data.host_server_list[0].host,
                self.message_stream_data.data.host_server_list[0].wss_port
            ))
            message: bytes = json.dumps({
                'uid': 0,
                'roomid': self.room_id,
                'protover': 2,
                'platform': 'web',
                'type': 2,
                'key': key
            }).encode('utf-8')
            await self.send_ws_message(LiveService.MonitorRoom.MessageStreamCommand.AUTHENTICATION, message)

            await self.send_heartbeat()

        def generate_message_stream(self, command: MessageStreamCommand, payload: bytes) -> bytes:
            # 生成websocket消息
            header = bytearray()
            header.extend(struct.pack('>I', 16 + len(payload)))
            header.extend(struct.pack('>IH', 16))
            if command == LiveService.MonitorRoom.MessageStreamCommand.HEARTBEAT:
                header.extend(struct.pack('>IH', 1))
            else:
                header.extend(struct.pack('>IH', 0))
            header.extend(struct.pack('>I', command))
            header.extend(struct.pack('>I', self.message_stream_data.current_command_count))
            return bytes(header) + payload

        async def send_ws_message(self, command: 'LiveService.MonitorRoom.MessageStreamCommand', message: bytes):
            await self.message_ws.send_bytes(self.generate_message_stream(command, message))

        async def send_heartbeat(self):
            # 发送心跳
            await self.send_ws_message(LiveService.MonitorRoom.MessageStreamCommand.HEARTBEAT, b'')

        async def receive_message(self):
            # 接收消息
            while True:
                try:
                    message: aiohttp.WSMessage = await self.message_ws.receive()
                    if message.type == aiohttp.WSMsgType.TEXT:
                        logger.debug(f'接收到文本消息: {message.data}')
                    elif message.type == aiohttp.WSMsgType.BINARY:
                        logger.debug(f'接收到二进制消息: {message.data}')
                        await self.handle_message(message.data)
                    elif message.type == aiohttp.WSMsgType.CLOSED:
                        logger.debug('连接已关闭')
                        break
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        logger.debug('连接出错')
                        break
                except Exception as e:
                    logger.error(f'接收消息出错: {e}')
                    break

        async def handle_message(self, message: bytes):
            # 处理消息
            header = message[:16]
            payload = message[16:]
            length, header_length, version, operation, sequence_id = struct.unpack('>IHHII', header)
            if operation == LiveService.MonitorRoom.MessageStreamCommand.HEARTBEAT_REPLY:
                logger.debug('收到心跳回复')
            elif operation == LiveService.MonitorRoom.MessageStreamCommand.AUTHENTICATION_REPLY:
                logger.debug('收到认证回复')
                asyncio.get_running_loop().create_task(self.receive_message())
            elif operation == LiveService.MonitorRoom.MessageStreamCommand.COMMAND:
                logger.debug('收到命令')
                command = json.loads(payload.decode('utf-8'))
                if command['cmd'] == 'DANMU_MSG':
                    logger.debug(f'收到弹幕: {command["info"][1]}')

                # elif command['cmd'] == 'SEND_GIFT':
                #     logger.debug(f'收到礼物: {command["data"]["uname"]} 赠送 {command["data"]["num"]} 个 {command["data"]["giftName"]}')
                # elif command['cmd'] == 'WELCOME':
                #     logger.debug(f'欢迎 {command["data"]["uname"]} 进入直播间')
                # elif command['cmd'] == 'WELCOME_GUARD':
                #     logger.debug(f'欢迎 {command["data"]["username"]} 进入直播间')
                # elif command['cmd'] == 'SYS_MSG':
                #     logger.debug(f'系统消息: {command["msg"]}')
                # elif command['cmd'] == 'PREPARING':
                #     logger.debug('直播间准备中')
                # elif command['cmd'] == 'LIVE':
                #     logger.debug('直播开始')
                # elif command['cmd'] == 'PREPARING':
                #     logger.debug('直播结束')
                # elif command['cmd'] == 'ROOM_BLOCK_MSG':
                #     logger.debug(f'直播间被封禁: {command["msg"]}')
                # elif command['cmd'] == 'ROOM_SILENT_ON':
                #     logger.debug(f'直播间已开启全员禁言')
                # elif command['cmd'] == 'ROOM_SILENT_OFF':
                #     logger.debug(f'直播间已关闭全员禁言')
                # elif command['cmd'] == 'ROOM_REAL_TIME_MESSAGE_UPDATE':
                #     logger.debug(f'直播间人气值更新: {command["data"]["fans"]}')
        async def process_danmu(self, danmu):
            # 处理弹幕
            pass

    class MessageKeyResponse(BaseModel):

        class Data(BaseModel):
            class Host(BaseModel):
                host: str
                port: int
                wss_port: int
                ws_port: int
            token: str
            host_list: list[Host]
        code: int
        message: str
        data: Data
        current_command_count: int = 0


live_service = LiveService()


def start_monitor():
    for room_config in config.monitor_live_rooms:
        monitor_room = LiveService.MonitorRoom(room_config)
        try:
            asyncio.get_running_loop().create_task(monitor_room.update_room_info())
        except RuntimeError:
            asyncio.get_event_loop().create_task(monitor_room.update_room_info())


start_monitor()
