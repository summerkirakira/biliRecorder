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

    running_downloaders: list['Downloader'] = []

    def __str__(self):
        return f'{self.__class__.__name__}({self.url}, {self.path})'

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
        self.cookies = config.cookies
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',
            'Referer': 'https://live.bilibili.com/'
        }
        self.download_status = self.DownloadStatus()
        self.user_info: Optional[UserInfo] = None
        self.running_downloaders.append(self)

    @abstractmethod
    async def _download(self):
        if not self.session:
            await self.create_session()

    def download(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self._download())

    def cancel(self):
        self.download_status.status = self.DownloadStatus.Status.CANCELED

    async def create_session(self):
        self.session = aiohttp.ClientSession(cookies=self.cookies, headers=self.default_headers)
        return self.session

    def get_download_status(self) -> DownloadStatus:
        return self.download_status


class LiveDefaultDownloader(Downloader):

    def __str__(self):
        return f'[{self.__class__.__name__}] {self.path}, 房间号：{self.room_info.data.room_id})'

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
            while True:
                try:
                    async with self.session.get(self.url) as response:
                        async for chunk in response.content.iter_chunked(1024):
                            self.download_status.current_downloaded_size += len(chunk)
                            self.download_status.total_size = self.download_status.current_downloaded_size
                            self.download_status.status = self.DownloadStatus.Status.DOWNLOADING
                            await f.write(chunk)
                except Exception as e:
                    if self.download_status.status == self.DownloadStatus.Status.CANCELED:
                        self.download_status.status = self.DownloadStatus.Status.UNDEFINED
                        return
                    logger.error(f"下载失败，正在重试，错误信息：{e}")


