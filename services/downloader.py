import aiohttp
import asyncio
from config import get_config, save_config, Config
from typing import Optional
from abc import abstractmethod
import time
from loguru import logger
from pydantic import BaseModel
from enum import IntEnum
from pathlib import Path
import aiofiles
from services.user_info import get_user_info_by_mid, UserInfo


class Downloader:

    class DownloadStatus(BaseModel):

        class Status(IntEnum):
            # 下载状态
            SUCCESS = 1
            FAILED = 2
            UNDEFINED = 3
            CANCELED = 4
            DOWNLOADING = 5
        current_downloaded_size: int = 0
        total_size: int = 0
        target_path: str = ''
        file_name: str = ''
        status: Status = Status.UNDEFINED

    def __init__(self, url, path, mid):
        self.url = url
        self.path = Path(path)
        self.session = None
        self.mid = mid
        config = get_config()
        self.cookies = {
            'SESSDATA': config.SESSDATA,
            'bili_jct': config.bili_jct,
            'DedeUserID': config.DedeUserID,
            'DedeUserID__ckMd5': config.DedeUserID__ckMd5,
        }
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
        self.download_status = self.DownloadStatus()
        self.user_info: Optional[UserInfo] = None

    @abstractmethod
    async def _download(self):
        if not self.session:
            await self.create_session()

    def download(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self._download())

    async def create_session(self):
        self.session = aiohttp.ClientSession(cookies=self.cookies, headers=self.default_headers)
        return self.session

    def get_download_status(self) -> DownloadStatus:
        return self.download_status


class LiveDefaultDownloader(Downloader):

    def __init__(self, url: str, path: str, room_info):
        super().__init__(url, path, room_info.data.room_id)
        self.download_status.target_path = path
        self.room_info = room_info

    async def _download(self):
        await super()._download()
        self.user_info = await get_user_info_by_mid(self.room_info.data.uid)
        config = get_config()
        if not (self.path / self.user_info.data.card.name).exists():
            (self.path / self.user_info.data.card.name).mkdir()
        file_name = (config.live_config.download_format
                     .replace('%title', self.room_info.data.title)
                     )
        file_name = time.strftime(file_name, time.localtime()) + '.flv'
        async with aiofiles.open(self.path / self.user_info.data.card.name / file_name, 'wb') as f:
            async with self.session.get(self.url) as response:
                async for chunk in response.content.iter_chunked(1024):
                    self.download_status.current_downloaded_size += len(chunk)
                    self.download_status.total_size = self.download_status.current_downloaded_size
                    self.download_status.status = self.DownloadStatus.Status.DOWNLOADING
                    await f.write(chunk)

