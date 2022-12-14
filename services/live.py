import struct

from pydantic import BaseModel
from enum import IntEnum
from config import get_config, Config
from typing import Optional
import asyncio
import aiohttp
import json
from services.downloader import LiveDefaultDownloader, LiveFfmpegDownloader
import websockets
import zlib
from loguru import logger
import time
from services.util import Danmu
from services.exceptions import DownloadPathException
from services.live_service import RoomInfo, LiveService

config = get_config()


class MonitorRoom:
    class MessageStreamCommand(IntEnum):
        HEARTBEAT = 2
        HEARTBEAT_REPLY = 3
        COMMAND = 5
        AUTHENTICATION = 7
        AUTHENTICATION_REPLY = 8

    class DanmuMessage(BaseModel):
        cmd: str
        info: list[dict]

    def __init__(self, room_config: Config.MonitorLiveRoom):
        self.room_id = room_config.short_id
        self.live = False
        self.down_video = False
        self.room_config = room_config
        self.room_info: Optional[RoomInfo] = None
        self.download_status: Optional[LiveService.DownloadStatus] = None
        self.downloader: Optional[LiveFfmpegDownloader] = None
        self.message_stream_data = None
        self.session = None
        self.message_ws = None
        self.danmus: list[Danmu] = []
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',
            'Origin': 'https://live.bilibili.com',
            'Connection': 'Upgrade'
        }

    async def update_room_info(self):
        while True:
            try:
                self.room_info = await live_service.get_room_info(self.room_id)
                self.room_id = self.room_info.data.room_id
                self.live = self.room_info.data.live_status == RoomInfo.Data.LiveStatus.LIVE
                if self.live and self.download_status is None and self.room_config.auto_download:
                    if self.message_stream_data is None:
                        asyncio.get_running_loop().create_task(self.init_message_ws())
                    url = await live_service.get_video_stream_url(self.room_id)
                    asyncio.get_running_loop().create_task(self.download_live_video(url))
                    if self.room_config.auto_upload.enabled and self.room_config.auto_upload.cover_path == 'AUTO':
                        await self.download_live_image(self.room_info.data.user_cover)
                    self.download_status = LiveService.DownloadStatus(
                        status=LiveService.DownloadStatus.Status.DOWNLOADING)
                if self.room_info.data.live_status != RoomInfo.Data.LiveStatus.LIVE and self.download_status is not None:
                    self.live = False
                    await self.stop_download()
            except Exception as e:
                logger.debug(f'????????????????????????: {e}')
            await asyncio.sleep(10)

    async def download_live_image(self, url: str):
        # ??????????????????
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.default_headers)
        async with self.session.get(url) as response:
            with open(f'{self.room_config.short_id}.jpg', 'wb') as f:
                f.write(await response.read())

    async def download_live_video(self, url: str):
        """
            ??????????????????
            """
        self.download_status = LiveService.DownloadStatus(status=LiveService.DownloadStatus.Status.DOWNLOADING)
        try:
            self.downloader = LiveFfmpegDownloader(url, self.room_config, self.room_info)
        except DownloadPathException as e:
            logger.error(f'??????????????????????????????????????????: {e}')
            exit(1)
        self.downloader.download()
        while True:
            if self.download_status is None:
                self.download_status = None
                self.downloader = None
                return
            logger.info(
                f'?????????????????????: {self.room_info.data.title}({self.room_info.data.room_id if self.room_info.data.short_id == 0 else self.room_info.data.short_id})')
            await asyncio.sleep(10)

    async def get_live_message_stream_key(self, room_id: int) -> str:
        # ???????????????????????????
        url = 'https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo'
        params = {
            'id': room_id
        }
        async with self.session.get(url, params=params) as response:
            self.message_stream_data = LiveService.MessageKeyResponse.parse_obj(await response.json())
            return self.message_stream_data.data.token

    @logger.catch
    async def init_message_ws(self):
        # ????????????????????????
        self.session = aiohttp.ClientSession(cookies=live_service.cookies, headers=self.default_headers)
        key = await self.get_live_message_stream_key(self.room_id)
        logger.debug('?????????????????????')
        message: bytes = json.dumps({
            'uid': get_config().mid,
            'roomid': self.room_id,
            'protover': 2,
            'platform': 'web',
            'type': 2,
            'key': key
        },
            separators=(',', ':')
        ).encode('utf-8')
        self.message_ws = await websockets.connect('wss://{}:{}/sub'.format(
            self.message_stream_data.data.host_list[0].host,
            self.message_stream_data.data.host_list[0].wss_port
        ))
        await self.send_ws_message(MonitorRoom.MessageStreamCommand.AUTHENTICATION, message)
        await self.send_heartbeat()
        await self.receive_message()

    def generate_message_stream(self, command: MessageStreamCommand, payload: bytes) -> bytes:
        # ??????websocket??????
        header = bytearray()
        header.extend(struct.pack('>I', 16 + len(payload)))
        header.extend(struct.pack('>H', 16))
        if command == MonitorRoom.MessageStreamCommand.HEARTBEAT or command == MonitorRoom.MessageStreamCommand.AUTHENTICATION:
            header.extend(struct.pack('>H', 1))
        else:
            header.extend(struct.pack('>H', 0))
        header.extend(struct.pack('>I', command))
        header.extend(struct.pack('>I', self.message_stream_data.current_command_count))
        return bytes(header) + payload

    async def send_ws_message(self, command: 'MonitorRoom.MessageStreamCommand', message: bytes):
        message = self.generate_message_stream(command, message)
        logger.debug(f'????????????: {message}')
        try:
            await self.message_ws.send(message)
        except Exception as e:
            logger.error(f'??????????????????: {e}')
            await self.close_session()
            await self.init_message_ws()
        self.message_stream_data.current_command_count += 1

    async def send_heartbeat(self):
        # ????????????
        await self.send_ws_message(MonitorRoom.MessageStreamCommand.HEARTBEAT, b'')

    async def receive_message(self):
        # ????????????
        while self.download_status is not None and self.download_status.status == LiveService.DownloadStatus.Status.DOWNLOADING:
            try:
                message = await self.message_ws.recv()
                # logger.debug(f'????????????: {message}')
                try:
                    await self.handle_message(message)
                except Exception as e:
                    logger.debug(f'??????????????????: {e}')
            except Exception as e:
                logger.error(f'??????????????????: {e}')
                break
        await self.close_session()

    async def close_session(self):
        await self.session.close()
        self.session = None

    async def send_heartbeat_loop(self):
        while self.download_status is not None:
            await self.send_heartbeat()
            await asyncio.sleep(25)

    async def handle_message(self, message: bytes):
        # ????????????
        header = message[:16]
        payload = message[16:]
        length, header_length, version, operation, sequence_id = struct.unpack('>IHHII', header)
        if operation == MonitorRoom.MessageStreamCommand.HEARTBEAT_REPLY:
            logger.debug('??????????????????')
        elif operation == MonitorRoom.MessageStreamCommand.AUTHENTICATION_REPLY:
            logger.debug('??????????????????')
            asyncio.get_running_loop().create_task(self.send_heartbeat_loop())
        elif operation == MonitorRoom.MessageStreamCommand.COMMAND:
            # logger.debug('????????????')
            if version == 2:
                decompressed_message = zlib.decompress(payload)
                commands = await self.extract_commands(decompressed_message)
            else:
                commands = [json.loads(payload.decode('utf-8'))]
            for command in commands:
                if command['cmd'] == 'DANMU_MSG':
                    if len(self.danmus) % 20 == 0:
                        logger.info(f'????????????{self.room_id}??????{len(self.danmus)}?????????')
                    await self.process_danmu(command['info'])
                elif command['cmd'] == 'SEND_GIFT':
                    logger.debug(
                        f'????????????: {command["data"]["uname"]} ?????? {command["data"]["num"]} ??? {command["data"]["giftName"]}')
                elif command['cmd'] == 'WELCOME':
                    logger.debug(f'?????? {command["data"]["uname"]} ???????????????')
                elif command['cmd'] == 'WELCOME_GUARD':
                    logger.debug(f'?????? {command["data"]["username"]} ???????????????')
                elif command['cmd'] == 'SYS_MSG':
                    logger.debug(f'????????????: {command["msg"]}')
                elif command['cmd'] == 'PREPARING':
                    logger.debug('??????????????????')
                elif command['cmd'] == 'LIVE':
                    logger.debug('????????????')
                elif command['cmd'] == 'PREPARING':
                    logger.debug('????????????')
                elif command['cmd'] == 'ROOM_BLOCK_MSG':
                    logger.debug(f'??????????????????: {command["msg"]}')
                elif command['cmd'] == 'ROOM_SILENT_ON':
                    logger.debug(f'??????????????????????????????')
                elif command['cmd'] == 'ROOM_SILENT_OFF':
                    logger.debug(f'??????????????????????????????')
                elif command['cmd'] == 'ROOM_REAL_TIME_MESSAGE_UPDATE':
                    logger.debug(f'????????????????????????: {command["data"]["fans"]}')
                elif command['cmd'] == 'ROOM_RANK':
                    logger.debug(f'????????????????????????: {command["data"]}')
                elif command['cmd'] == 'ROOM_CHANGE':
                    logger.debug(f'?????????????????????: {command["data"]}')
                elif command['cmd'] == 'ROOM_ADMINS':
                    logger.debug(f'????????????????????????: {command["data"]}')
                elif command['cmd'] == 'ROOM_ADMINS_SET':
                    logger.debug(f'????????????????????????: {command["data"]}')
                elif command['cmd'] == 'ROOM_ADMINS_UNSET':
                    logger.debug(f'????????????????????????: {command["data"]}')
                elif command['cmd'] == 'ROOM_BLOCK_MSG':
                    logger.debug(f'??????????????????: {command["msg"]}')
                elif command['cmd'] == 'ROOM_LOCK':
                    logger.debug(f'????????????????????????')
                elif command['cmd'] == 'ROOM_UNLOCK':
                    logger.debug(f'????????????????????????')
                elif command['cmd'] == 'ROOM_ADMIN_ENTER':
                    logger.debug(f'????????? {command["data"]["username"]} ???????????????')
                elif command['cmd'] == 'NOTICE_MSG':
                    logger.debug(f'????????????: {command["msg"]}')
                elif command['cmd'] == 'ACTIVITY_BANNER_UPDATE_V2':
                    logger.debug(f'??????????????????: {command["data"]}')
                elif command['cmd'] == 'ANCHOR_LOT_CHECKSTATUS':
                    logger.debug(f'??????????????????: {command["data"]}')
                elif command['cmd'] == 'ANCHOR_LOT_START':
                    logger.debug(f'??????????????????: {command["data"]}')
                elif command['cmd'] == 'ANCHOR_LOT_END':
                    logger.debug(f'??????????????????: {command["data"]}')
                elif command['cmd'] == 'ANCHOR_LOT_AWARD':
                    logger.debug(f'??????????????????: {command["data"]}')

    @classmethod
    async def extract_commands(cls, message: bytes) -> list:
        # ????????????
        commands = []
        while len(message) > 0:
            header = message[:16]
            total_length, header_length, version, operation, sequence_id = struct.unpack('>IHHII', header)
            payload = message[16:total_length]
            message = message[total_length:]
            commands.append(json.loads(payload.decode('utf-8')))
        return commands

    async def process_danmu(self, danmu):
        # ????????????
        danmu_info = {
            'danmu_type': danmu[0][1],
            'font_size': danmu[0][2],
            'color': danmu[0][3],
            'send_time': danmu[0][4],
            'mid_hash': danmu[2][0],
            'd_mid': 123456789,
            'content': danmu[1],
        }
        if self.download_status is not None and self.download_status == LiveService.DownloadStatus.Status.DOWNLOADING:
            # ?????????
            danmu_info['appear_time'] = time.time() - self.downloader.get_download_status().start_time
        else:
            # ?????????
            danmu_info['appear_time'] = -1
        self.danmus.append(Danmu.parse_obj(danmu_info))

    async def stop_download(self):
        # ????????????
        logger.info(
            f'????????????: ???????????? {round(time.time() - self.downloader.get_download_status().start_time)} ???, ???????????? {len(self.danmus)} ???')
        self.download_status = LiveService.DownloadStatus(status=LiveService.DownloadStatus.Status.FINISHED)
        self.downloader.damu_list = self.danmus
        self.downloader.cancel()
        self.download_status = None
        self.message_stream_data = None
        self.danmus = []

    async def test_slice_video(self):
        self.downloader.download_process.kill()
        await asyncio.sleep(10)
        self.downloader.download_process.kill()
        await asyncio.sleep(10)
        self.downloader.download_process.kill()
        await asyncio.sleep(10)
        self.downloader.download_process.kill()
        await asyncio.sleep(10)
        self.downloader.download_process.kill()
        await asyncio.sleep(10)
        self.downloader.download_process.kill()
        await asyncio.sleep(10)
        self.downloader.download_process.kill()
        await asyncio.sleep(10)
        await self.stop_download()


async def test(monitor_room: MonitorRoom):
    # ??????
    await asyncio.sleep(20)
    print('????????????')
    await monitor_room.test_slice_video()


live_service = LiveService()


def start_monitor():
    # ????????????
    for room_config in config.monitor_live_rooms:
        if room_config.short_id == -1:
            continue
        monitor_room = MonitorRoom(room_config)
        try:
            asyncio.get_running_loop().create_task(monitor_room.update_room_info())
        except RuntimeError:
            asyncio.get_event_loop().create_task(monitor_room.update_room_info())
            # asyncio.get_event_loop().create_task(test(monitor_room))
    logger.info(
        f'?????????????????????: {", ".join([str(room_config.short_id) for room_config in config.monitor_live_rooms if room_config.short_id != -1])}')


start_monitor()
