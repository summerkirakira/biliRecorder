from biliup.plugins.bili_webup import BiliBili, Data
from config import get_config, save_config, Config
from services.exceptions import NotAuthorizedException
from abc import abstractmethod

from threading import Thread


class Uploader(Thread):

    def __init__(self, data: Data, bili: BiliBili):
        super().__init__()
        self.data = data
        self.bili = bili
        self.config = get_config()
        if self.config is None:
            raise NotAuthorizedException('未登录')
        self.video = Data()

    @abstractmethod
    def run(self):
        pass
