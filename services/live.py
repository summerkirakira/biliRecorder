from pydantic import BaseModel, validator
from enum import IntEnum
import requests
from config import get_config, save_config, Config
from typing import Optional
import asyncio
import aiohttp
import aiofiles
from services.downloader import LiveDefaultDownloader
from services.user_info import get_user_info_by_mid, UserInfo

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
    def __init__(self):
        self.default_headers = {
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
        self.cookies = {
            'SESSDATA': config.SESSDATA,
            'bili_jct': config.bili_jct,
            'DedeUserID': config.DedeUserID,
            'DedeUserID__ckMd5': config.DedeUserID__ckMd5,
        }
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
        def __init__(self, room_config: Config.MonitorLiveRoom):
            self.room_id = room_config.short_id
            self.live = False
            self.down_video = False
            self.room_config = room_config
            self.room_info: Optional[RoomInfo] = None
            self.download_status: Optional[LiveService.DownloadStatus] = None
            self.downloader: Optional[LiveDefaultDownloader] = None

        async def update_room_info(self):
            while True:
                self.room_info = await live_service.get_room_info(self.room_id)
                self.live = self.room_info.data.live_status == RoomInfo.Data.LiveStatus.LIVE
                if self.live and self.download_status is None and self.room_config.auto_download:
                    url = await live_service.get_video_stream_url(self.room_id)
                    asyncio.get_running_loop().create_task(self.download_live_video(url))
                    self.download_status = LiveService.DownloadStatus(status=LiveService.DownloadStatus.Status.DOWNLOADING)
                await asyncio.sleep(5)

        async def download_live_video(self, url: str):
            """
            下载直播视频
            """
            self.download_status = LiveService.DownloadStatus(status=LiveService.DownloadStatus.Status.DOWNLOADING)
            self.downloader = LiveDefaultDownloader(url, '/Users/forever/PycharmProjects/biliRecorder', self.room_info)
            self.download_status = LiveService.DownloadStatus(status=LiveService.DownloadStatus.Status.FINISHED)
            self.downloader.download()
            while True:
                await asyncio.sleep(1)
                print(self.downloader.get_download_status())


live_service = LiveService()

room1 = live_service.MonitorRoom(Config.MonitorLiveRoom(short_id=213, auto_download=True))

asyncio.get_event_loop().run_until_complete(room1.update_room_info())


