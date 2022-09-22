import asyncio
import aiohttp
from config import get_config, save_config, Config
from pydantic import BaseModel, validator

default_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36',
    'Referer': 'https://live.bilibili.com/'
}


class UserInfo(BaseModel):
    class Data(BaseModel):
        class Card(BaseModel):
            class LevelInfo(BaseModel):
                current_level: int
                current_min: int
                current_exp: int
                next_exp: int

            mid: int
            name: str
            sex: str
            face: str
            fans: int
            attention: int
            level_info: LevelInfo

        archive_count: int
        card: Card

    code: int
    message: str
    ttl: int
    data: Data


async def get_user_info_by_mid(mid: int) -> UserInfo:
    config = get_config()
    cookies = {
        'SESSDATA': config.SESSDATA,
        'bili_jct': config.bili_jct,
        'DedeUserID': config.DedeUserID,
        'DedeUserID__ckMd5': config.DedeUserID__ckMd5,
    }
    session = aiohttp.ClientSession(cookies=cookies, headers=default_headers)
    params = {
        'mid': mid
    }
    async with session.get('https://api.bilibili.com/x/web-interface/card', params=params) as response:
        user_info = UserInfo.parse_obj(await response.json())
    await session.close()
    return user_info

