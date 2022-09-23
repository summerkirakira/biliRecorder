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
from services.util import Danmu
from services.danmu_converter import get_video_width_height, generate_ass


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
        start_time: int = 0

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
        self.download_status.start_time = time.time()

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
        self.download_status.target_path = str(self.path / self.user_info.data.card.name / file_name)
        async with aiofiles.open(self.path / self.user_info.data.card.name / file_name, 'wb') as f:
            while self.download_status.status != self.DownloadStatus.Status.CANCELED:
                try:
                    async with self.session.get(self.url) as response:
                        async for chunk in response.content.iter_chunked(1024):
                            if self.download_status.status == self.DownloadStatus.Status.CANCELED:
                                break
                            self.download_status.current_downloaded_size += len(chunk)
                            self.download_status.total_size = self.download_status.current_downloaded_size
                            self.download_status.status = self.DownloadStatus.Status.DOWNLOADING
                            await f.write(chunk)
                except Exception as e:
                    if self.download_status.status == self.DownloadStatus.Status.CANCELED:
                        self.download_status.status = self.DownloadStatus.Status.UNDEFINED
                        return
                    logger.error(f"下载失败，正在重试，错误信息：{e}")

    async def save_danmus(self, damus: list[Danmu]):
        current_time = time.time() * 1000
        valid_danmus = [damu for damu in damus if (current_time >= damu.send_time >= self.download_status.start_time)]
        for damu in valid_danmus:
            damu.appear_time = (damu.send_time - self.download_status.start_time * 1000) / 1000
        video_file = Path(self.download_status.target_path)
        video_width, video_height = get_video_width_height(video_file)
        ass_file = video_file.with_suffix('.zh-CN.ass')
        generate_ass(Danmu.generate_danmu_xml(valid_danmus), str(ass_file), video_width, video_height)

