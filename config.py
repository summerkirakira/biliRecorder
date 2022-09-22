from pydantic import BaseModel
import os
from typing import Optional


class Config(BaseModel):
    class MonitorLiveRoom(BaseModel):
        short_id: int
        auto_download: bool
        auto_download_path: Optional[str]
        auto_download_format: Optional[str]
    SESSDATA: Optional[str]
    bili_jct: Optional[str]
    DedeUserID: Optional[str]
    DedeUserID__ckMd5: Optional[str]


def get_config() -> Config:
    if not os.path.exists('config.json'):
        return Config()
    config = Config.parse_file('config.json')
    return config


def save_config(config: Config):
    with open('config.json', 'w') as f:
        f.write(config.json())
