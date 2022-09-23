import requests
import time
from abc import abstractmethod
from enum import IntEnum, Enum
from pydantic import BaseModel
from loguru import logger
from requests import Response
from typing import Optional, Union
from config import get_config, save_config
import json
import qrcode
import sys

config = get_config()


class BLogin:
    def __init__(self):
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 BiliDroid/5.15.0 (bbcallen@gmail.com)",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br"
        }
        self.session = requests.Session()
        self.session.headers.update(self.default_headers)
        self.SESSDATA: Optional[str] = None
        self.bili_jct: Optional[str] = None
        self.DedeUserID: Optional[str] = None
        self.DedeUserID__ckMd5: Optional[str] = None
        self.sid: Optional[str] = None
        self.cookies: Optional[dict] = None

    class LoginType(Enum):
        QR = 1
        PASSWORD = 2

    class LoginStatus(Enum):
        SUCCESS = 1
        FAILED = 2
        UNDEFINED = 3

    @abstractmethod
    def login(self):
        # Login to Bilibili
        pass

    def update_login_config(self):
        config = get_config()
        config.SESSDATA = self.SESSDATA
        config.bili_jct = self.bili_jct
        config.DedeUserID = self.DedeUserID
        config.DedeUserID__ckMd5 = self.DedeUserID__ckMd5
        config.cookies = self.cookies
        save_config(config)


class QRLogin(BLogin):

    class QRRequestResponse(BaseModel):
        # 向服务器请求登录二维码的响应
        class Data(BaseModel):
            url: str
            qrcode_key: str

        code: int
        message: str
        ttl: int
        data: Data

    class QRRequestStatusResponse(BaseModel):
        # 二维码请求状态
        class Code(IntEnum):
            SUCCESS = 0
            QR_EXPIRED = 86038
            QR_NOT_SCANNED = 86101
            QR_SCANNED = 86090
            UNDEFINED = 2

        class Data(BaseModel):
            code: 'QRLogin.QRRequestStatusResponse.Code'
            message: str

        data: Data

    def __init__(self):
        super().__init__()
        self.login_status = self.LoginStatus.UNDEFINED
        self.login_type = self.LoginType.QR
        self.qr_request_url = "http://passport.bilibili.com/x/passport-login/web/qrcode/generate"
        self.qr_check_url = "http://passport.bilibili.com/x/passport-login/web/qrcode/poll"
        self.QRRequestStatusResponse.Data.update_forward_refs()

    @logger.catch
    def login(self):
        # 向服务器请求登录二维码
        try:
            qr_request_response: QRLogin.QRRequestResponse = self.QRRequestResponse(
                **self.session.get(self.qr_request_url).json()
            )
            logger.success(f"请在bili客户端中点击链接登录或使用二维码登录：{qr_request_response.data.url}")
            qrcode.make(qr_request_response.data.url).show()
        except Exception as e:
            logger.error(f"获取验证码失败: {e}")
            self.login_status = self.LoginStatus.FAILED
            return
        max_retry = 180
        while True:
            # 检查二维码状态
            login_status: Response = self.session.get(self.qr_check_url, headers=self.default_headers, params={
                    "qrcode_key": qr_request_response.data.qrcode_key
                })
            login_status_response: QRLogin.QRRequestStatusResponse = self.QRRequestStatusResponse(
                **login_status.json()
            )
            if login_status_response.data.code == self.QRRequestStatusResponse.Code.SUCCESS:
                self.cookies = login_status.cookies.get_dict()
                for key, value in self.session.cookies.get_dict().items():
                    if key == "SESSDATA":
                        self.SESSDATA = value
                    elif key == "bili_jct":
                        self.bili_jct = value
                    elif key == "DedeUserID":
                        self.DedeUserID = value
                    elif key == "DedeUserID__ckMd5":
                        self.DedeUserID__ckMd5 = value
                    elif key == "sid":
                        self.sid = value
                self.login_status = self.LoginStatus.SUCCESS
                break
            elif login_status_response.data.code == self.QRRequestStatusResponse.Code.QR_EXPIRED:
                logger.error("二维码已过期")
                self.login_status = self.LoginStatus.FAILED
                break
            elif login_status_response.data.code == self.QRRequestStatusResponse.Code.QR_NOT_SCANNED:
                logger.info("二维码未扫描")
            elif login_status_response.data.code == self.QRRequestStatusResponse.Code.QR_SCANNED:
                logger.info("二维码已扫描")
            max_retry -= 1
            if max_retry == 0:
                logger.error("超过最大重试次数")
                self.login_status = self.LoginStatus.FAILED
                break

            time.sleep(1)

        if self.login_status == self.LoginStatus.SUCCESS:
            logger.success("登录成功")
            self.update_login_config()


def login():
    qr_login = QRLogin()
    qr_login.login()

