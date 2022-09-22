from pydantic import BaseModel, validator
from enum import IntEnum
import requests
from config import get_config, save_config

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
        self.session = requests.Session()
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
        self.session.headers.update(self.default_headers)
        self.session.cookies.update({
            'SESSDATA': config.SESSDATA,
            'bili_jct': config.bili_jct,
            'DedeUserID': config.DedeUserID,
            'DedeUserID__ckMd5': config.DedeUserID__ckMd5,
        })

    def get_room_info(self, room_id: int) -> RoomInfo:
        # 获取房间信息
        url = 'https://api.live.bilibili.com/room/v1/Room/get_info'
        params = {
            'room_id': room_id
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return RoomInfo.parse_obj(response.json())

    def get_video_stream_info(self, room_id: int) -> VideoStreamInfo:
        # 获取视频流信息
        url = 'https://api.live.bilibili.com/room/v1/Room/playUrl'
        params = {
            'cid': room_id,
            'qn': 10000,
            'platform': 'web'
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return VideoStreamInfo.parse_obj(response.json())

    def get_video_stream_url(self, room_id: int) -> str:
        # 获取视频流链接
        video_stream_info = self.get_video_stream_info(room_id)
        if video_stream_info.code != VideoStreamInfo.Code.SUCCESS:
            raise ValueError(f'获取视频流信息失败: {video_stream_info.message}')
        return video_stream_info.data.durl[0].url

    def download_video_stream(self, room_id: int, path: str):
        # 下载视频流
        url = self.get_video_stream_url(room_id)
        with open(path, 'wb') as f:
            with self.session.get(url, stream=True) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)


if __name__ == '__main__':
    live_service = LiveService()
    # room_info = live_service.get_room_info(22301377)
    # print(room_info)
    # video_stream_url = live_service.get_video_stream_url(1)
    # print(video_stream_url)
    live_service.download_video_stream(545240, 'test.flv')
