from pydantic import BaseModel

import asyncio

from pathlib import Path
import random


class Danmu(BaseModel):
    appear_time: float
    danmu_type: int
    font_size: int
    color: int
    send_time: int
    pool: int = 0
    mid_hash: str
    d_mid: int
    content: str
    level: int = 11

    def __str__(self):
        if '<' in self.content or '>' in self.content or '&' in self.content:
            return f'<d p="{round(self.appear_time, 5)},{self.danmu_type},{self.font_size},{self.color},{int(self.send_time / 1000)},{self.pool},{self.mid_hash},{self.d_mid},{self.level}"><![CDATA[{self.content}]]></d>'
        else:
            return f'<d p="{round(self.appear_time, 5)},{self.danmu_type},{self.font_size},{self.color},{int(self.send_time / 1000)},{self.pool},{self.mid_hash},{self.d_mid},{self.level}">{self.content}</d>'

    @classmethod
    def generate_danmu_xml(self, danmus: list['Danmu']):
        danmu_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<i>
    <chatserver>chat.bilibili.com</chatserver>
    <chatid>404122228</chatid>
    <mission>0</mission>
    <maxlimit>100</maxlimit>
    <state>0</state>
    <real_name>0</real_name>
    <source>k-v</source>'''
        for danmu in danmus:
            danmu_xml += str(danmu)
        danmu_xml += '</i>'
        return danmu_xml


async def concat_videos(input_files: list[Path], output_file: Path):
    # 首先，我们使用 ffmpeg 的 `concat` 功能来生成一个临时文件，该文件包含了需要拼接的视频文件的列表
    temp_file_name = f'temp{str(random.randint(0, 10000))}.txt'
    with open(temp_file_name, "w") as f:
        for file in input_files:
            f.write(f"file '{file.absolute()}'\n")

    # 然后，我们调用 ffmpeg 命令行工具，使用该临时文件来拼接视频文件
    await asyncio.create_subprocess_exec(
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", Path(temp_file_name).absolute(), "-c", "copy", output_file.absolute(),
    )



