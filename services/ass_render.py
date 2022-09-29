import os
import subprocess
from pathlib import Path
import shutil
from loguru import logger
import ffmpeg


@logger.catch
async def render_ass(video_path: Path):
    if not video_path.exists():
        raise FileNotFoundError(f'视频文件不存在：{video_path}')
    ass_path = video_path.with_suffix('.zh-CN.ass')
    if not ass_path.exists():
        raise FileNotFoundError(f'弹幕文件不存在：{ass_path}')
    await fix_video(video_path)
    p = subprocess.Popen(f'ffmpeg -i "{video_path.absolute()}" -vf ass="{ass_path.absolute()}" -vcodec libx264 -acodec copy "{video_path.with_suffix(".danmaku.flv").absolute()}"',
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        raise RuntimeError(f'渲染弹幕出错：{stderr.decode("utf-8")}')
    return stdout, stderr


@logger.catch
async def fix_video(video_path: Path, transcode=False):
    if not video_path.exists():
        raise FileNotFoundError(f'视频文件不存在：{video_path}')
    # p = subprocess.Popen(f'ffmpeg -y -i "{video_path.absolute()}" -codec copy "{video_path.with_suffix(".temp.flv").absolute()}"',
    #                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    # stdout, stderr = p.communicate()
    # if p.returncode != 0:
    #     raise RuntimeError(f'修复视频文件出错：{stderr.decode("utf-8")}')
    # else:
    #     os.remove(video_path)
    #     shutil.copy(video_path.with_suffix('.temp.flv').absolute(), video_path.absolute())
    #     os.remove(video_path.with_suffix('.temp.flv').absolute())
    #
    # return stdout, stderr
    input_video = ffmpeg.input(video_path.absolute())
    out = ffmpeg.output(input_video, filename=video_path.with_suffix('.temp.flv').absolute(), vcodec='copy',
                        acodec='copy')
    try:
        out.run()
    except ffmpeg.Error as e:
        raise RuntimeError(f'修复视频文件出错：{e.stderr.decode("utf-8")}')
    os.remove(video_path)
    shutil.copy(video_path.with_suffix('.temp.flv').absolute(), video_path.absolute())
    os.remove(video_path.with_suffix('.temp.flv').absolute())
    if transcode:
        out = ffmpeg.output(input_video, filename=video_path.with_suffix('.temp.flv').absolute(), vcodec='h264', acodec='aac')
        try:
            out.run()
            os.remove(video_path)
            shutil.copy(video_path.with_suffix('.temp.flv').absolute(), video_path.absolute())
            os.remove(video_path.with_suffix('.temp.flv').absolute())
        except ffmpeg.Error as e:
            raise RuntimeError(f'修复视频文件出错：{e.stderr.decode("utf-8")}')


if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop().run_until_complete(fix_video(Path(input('请输入视频文件路径：')), transcode=True))

