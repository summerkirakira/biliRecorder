from pydantic import BaseModel, validator


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

