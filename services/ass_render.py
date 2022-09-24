import os
import subprocess
from pathlib import Path
import shutil


async def render_ass(video_path: Path):
    if not video_path.exists():
        raise FileNotFoundError(f'视频文件不存在：{video_path}')
    ass_path = video_path.with_suffix('.zh-CN.ass')
    if not ass_path.exists():
        raise FileNotFoundError(f'弹幕文件不存在：{ass_path}')
    await fix_video(video_path)
    p = subprocess.Popen(f'ffmpeg -i {video_path.absolute()} -vf ass={ass_path.absolute()} -vcodec libx264 -acodec copy {video_path.with_suffix(".danmaku.flv").absolute()}',
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = p.communicate()
    return stdout, stderr


async def fix_video(video_path: Path):
    if not video_path.exists():
        raise FileNotFoundError(f'视频文件不存在：{video_path}')
    p = subprocess.Popen(f'ffmpeg -y -i {video_path.absolute()} -codec copy {video_path.with_suffix(".temp.flv").absolute()}',
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        raise RuntimeError(f'修复视频文件出错：{stderr}')
    else:
        os.remove(video_path)
        shutil.copy(video_path.with_suffix('.temp.flv').absolute(), video_path.absolute())
        os.remove(video_path.with_suffix('.temp.flv').absolute())
    return stdout, stderr


if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()

