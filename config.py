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
        download_format: str = '%title-%Y年%m%月%d%日-%H点%M分场'

        download: DownloadConfig = DownloadConfig()

    class MonitorLiveRoom(BaseModel):
        class Quality(IntEnum):
            FLUENT = 80
            STANDARD = 150
            HIGH = 400
            SUPER = 10000
        short_id: int
        auto_download: bool
        auto_download_path: Optional[str]
        auto_download_quality: Quality = Quality.SUPER
    mid: int = 0
    SESSDATA: Optional[str]
    bili_jct: Optional[str]
    DedeUserID: Optional[str]
    DedeUserID__ckMd5: Optional[str]
    cookies: Optional[dict]
    refresh_token: Optional[str]
    live_config: LiveConfig = LiveConfig()

    monitor_live_rooms: list[MonitorLiveRoom] = []


def get_config() -> Config:
    if not os.path.exists('config.json'):
        return Config()
    config = Config.parse_file('config.json')
    return config


def save_config(config: Config):
    with open('config.json', 'w') as f:
        f.write(config.json())
