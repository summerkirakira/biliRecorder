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
from services.ass_render import fix_video
from services.exceptions import DownloadPathException
from services.uploader import BiliBiliLiveUploader
from services.live_service import LiveService


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

    def __init__(self, url, room_config: Config.MonitorLiveRoom, mid):
        if room_config.auto_download_path is None:
            raise DownloadPathException('path 不能为空')
        self.url = url
        self.room_config = room_config
        self.path = Path(room_config.auto_download_path)
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

    def __init__(self, url: str, room_config: Config.MonitorLiveRoom, room_info):
        super().__init__(url, room_config, room_info.data.room_id)
        self.download_status.target_path = room_config.auto_download_path
        self.room_info = room_info
        self.live_service = LiveService()
        self.start_time = time.localtime()

    @logger.catch
    async def _download(self):
        await super()._download()
        self.user_info = await get_user_info_by_mid(self.room_info.data.uid)
        config = get_config()
        if not (self.path / self.user_info.data.card.name).exists():
            (self.path / self.user_info.data.card.name).mkdir()
        file_name = (config.live_config.download_format
                     .replace('%title', self.room_info.data.title)
                     .replace('/', '_')
                     .replace('\\', '_')
                     .replace(':', '_')
                     .replace('*', '_')
                     .replace('?', '_')
                     )
        self.start_time = time.localtime()
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
                    logger.error(f'下载出错，正在重试')
                    logger.exception(e)
                    logger.error(f'重新获取推流地址中...')
                    self.url = await self.live_service.get_video_stream_url(self.room_info.data.room_id)
        logger.opt(colors=True).info(f'<yellow>下载完成</yellow> 直播间：{self.room_info.data.title}已关闭')
        logger.info('正在保存视频...')
        await fix_video(Path(self.download_status.target_path))
        logger.info('保存成功')
        if self.room_config.auto_upload.enabled:
            await self.upload()

    async def upload(self):
        if self.room_config.auto_upload.title is None:
            logger.error('上传失败，标题不能为空')
            return
        if self.room_config.auto_upload.desc is None:
            logger.error('上传失败，描述不能为空')
            return
        if self.room_config.auto_upload.tags is None:
            logger.error('上传失败，标签不能为空')
            return
        if self.room_config.auto_upload.tid is None:
            logger.error('上传失败，分区不能为空')
            return
        if self.room_config.auto_upload.source is None:
            logger.error('上传失败，来源不能为空')
            return

        bill_uploader = BiliBiliLiveUploader()

        bill_uploader.set_title(
            time.strftime(
                self.room_config.auto_upload.title.replace('%title', self.room_info.data.title),
                self.start_time
            )
        )
        ass_name = Path(self.download_status.target_path).with_suffix('.zh-CN.ass').name
        file_name = Path(self.download_status.target_path).name
        bill_uploader.set_desc(
            time.strftime(
                self.room_config.auto_upload.desc
                    .replace('%title', self.room_info.data.title)
                    .replace('%ass_name', ass_name)
                    .replace('%file_name', file_name)
                    .replace('%room_id', str(self.room_info.data.room_id))
                    .replace('%uid', str(self.room_info.data.uid))
                    .replace('%uname', self.user_info.data.card.name),
                time.localtime()
            )
        )
        bill_uploader.set_tags(self.room_config.auto_upload.tags)
        bill_uploader.set_tid(self.room_config.auto_upload.tid)
        bill_uploader.set_source(self.room_config.auto_upload.source)
        if self.room_config.auto_upload.cover_path == 'AUTO':
            bill_uploader.set_cover(f'{self.room_config.short_id}.jpg')
        else:
            bill_uploader.set_cover(self.room_config.auto_upload.cover)
        bill_uploader.set_files([
            {
                'path': self.download_status.target_path,
                'title': self.room_config.auto_upload.title,
            }
        ])
        bill_uploader.start()

        logger.info('正在上传视频...')

    async def save_danmus(self, damus: list[Danmu]):
        current_time = time.time() * 1000
        valid_danmus = [damu for damu in damus if (current_time >= damu.send_time >= self.download_status.start_time)]
        for damu in valid_danmus:
            damu.appear_time = (damu.send_time - self.download_status.start_time * 1000) / 1000
        video_file = Path(self.download_status.target_path)
        video_width, video_height = get_video_width_height(video_file)
        ass_file = video_file.with_suffix('.zh-CN.ass')
        generate_ass(Danmu.generate_danmu_xml(valid_danmus), str(ass_file), video_width, video_height)

