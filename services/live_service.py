import struct

from pydantic import BaseModel, validator
from enum import IntEnum
from config import get_config
import aiohttp

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
        self.cookies = {
            'bili_jct': config.bili_jct,
            'DedeUserID': config.DedeUserID,
            'DedeUserID__ckMd5': config.DedeUserID__ckMd5,
            'SESSDATA': config.SESSDATA,
        }
        self.session = None

    async def create_session(self):
        # 创建会话
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.default_headers)

    async def get_room_info(self, room_id: int) -> RoomInfo:
        # 获取房间信息
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.default_headers)
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
        await self.create_session()
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
        current_command_count: int = 1