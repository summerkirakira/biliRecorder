from services.bili_uploader import BiliBili, Data
from config import get_config, save_config, Config
from services.exceptions import NotAuthorizedException
from abc import abstractmethod

from threading import Thread
from typing import Optional


class Uploader(Thread):

    def __init__(self):
        super().__init__()
        self.config = get_config()
        if self.config is None:
            raise NotAuthorizedException('未登录')
        self.video = Data()
        self.file_list: list[str] = []

    @abstractmethod
    def run(self):
        pass


class BiliBiliVtbLiveUploader(Uploader):

    def __init__(self):
        super().__init__()
        self.cover_path = None

    def run(self):
        lines = 'bda2'
        tasks = 3
        with BiliBili(self.video) as bili:
            if self.cover_path is None:
                raise Exception('未设置封面')
            bili.login("bili.cookies", {
                'cookies': self.config.cookies,
                'access_token': self.config.refresh_token,
            })
            self.video.cover = bili.cover_up(self.cover_path).replace('http:', '')
            for file in self.file_list:
                video_part = bili.upload_file(file['path'], lines=lines, tasks=tasks, title=file['title'])  # 上传视频，默认线路AUTO自动选择，线程数量3。
                self.video.append(video_part)  # 添加已经上传的视频

            bili.submit()  # 提交视频

    def set_title(self, title: str):
        self.video.title = title

    def set_desc(self, desc: str):
        self.video.desc = desc

    def set_cover(self, cover: str):
        self.cover_path = cover

    def set_tags(self, tags: list[str]):
        self.video.set_tag(tags)

    def set_files(self, files: list[dict]):
        self.file_list = files

    def set_tid(self, tid: int):
        self.video.tid = tid

    def set_source(self, resource: str):
        self.video.source = resource


# bilibili_uploader = BiliBiliVtbLiveUploader()
#
# bilibili_uploader.set_title('【录播】VirtualReal夏日合唱Super')
#
# bilibili_uploader.set_desc('')
#
# bilibili_uploader.set_tid(27)

# bilibili_uploader.set_desc('七海Nana7mi的个人空间: https://space.bilibili.com/434334701/')

# bilibili_uploader.set_tags(['虚拟UP主', 'VirtualReal'])
#
# bilibili_uploader.set_source("https://live.bilibili.com/21470454")
#
# bilibili_uploader.set_cover('/Users/forever/Downloads/111.jpeg')
#
# # bilibili_uploader.set_files(['/Users/forever/PycharmProjects/biliRecorder/七海Nana7mi/就！半小时-2022年09月23日-19点45分场.有弹幕.flv', '/Users/forever/PycharmProjects/biliRecorder/七海Nana7mi/就！半小时-2022年09月23日-19点45分场.flv'][:-1])
# bilibili_uploader.set_files(
#     [
#         {
#             'path': '/Users/forever/PycharmProjects/biliRecorder/VirtuaReal/【夏日合唱Super】- Day1-2022年09月24日-13点00分场.danmaku.flv',
#             'title': '带弹幕',
#         },
#         {
#             'path': '/Users/forever/PycharmProjects/biliRecorder/VirtuaReal/【夏日合唱Super】- Day1-2022年09月24日-13点00分场.flv',
#             'title': '无弹幕',
#         }
#     ]
# )
# bilibili_uploader.run()
