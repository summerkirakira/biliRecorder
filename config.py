from pydantic import BaseModel
import os
from typing import Optional
from enum import IntEnum


class Config(BaseModel):
    class LiveConfig(BaseModel):
        class DownloadConfig(BaseModel):
            class DownloadType(IntEnum):
                DEFAULT = 1
                CUSTOM = 2

            download_type: DownloadType = DownloadType.DEFAULT
            custom_downloader: Optional[str] = None
        download_format: str = '%title-%Y年%m月%d日-%H点%M分场'

        download: DownloadConfig = DownloadConfig()

    class MonitorLiveRoom(BaseModel):
        class Quality(IntEnum):
            FLUENT = 80
            STANDARD = 150
            HIGH = 400
            SUPER = 10000

        class AutoUpload(BaseModel):
            enabled: bool = False
            title: str = '【直播录制】%title-%Y年%m月%d日-%H点%M分场'
            desc: str = '直播录制'
            source: str = 'https://live.bilibili.com/'
            tags: list[str] = ['直播录制']
            tid: int = 27
            cover_path: str = 'AUTO'

        short_id: int = -1
        auto_download: bool = False
        auto_download_path: Optional[str]
        auto_download_quality: Quality = Quality.SUPER
        auto_upload: AutoUpload = AutoUpload()
        transcode: bool = False
    mid: int = 0
    SESSDATA: Optional[str]
    bili_jct: Optional[str]
    DedeUserID: Optional[str]
    DedeUserID__ckMd5: Optional[str]
    refresh_token: Optional[str]
    live_config: LiveConfig = LiveConfig()
    access_token: Optional[str]
    monitor_live_rooms: list[MonitorLiveRoom] = [
        MonitorLiveRoom(auto_download_path=None)
    ]


if not os.path.exists('config'):
    os.mkdir('config')


def get_config() -> Config:
    if not os.path.exists('config/config.json'):
        save_config(Config())
        return Config()
    config = Config.parse_file('config/config.json')
    return config


def save_config(config: Config):
    with open('config/config.json', 'w') as f:
        f.write(config.json(indent=4, ensure_ascii=False))
