from pydantic import BaseModel
from enum import IntEnum


class RoomInfo(BaseModel):
    class LiveStatus(IntEnum):
        NOT_LIVE = 0
        LIVE = 1
        VIDEO = 2
    uid: int
    room_id: int
    short_id: int
    attention: int
    online: int
    is_portrait: bool
    description: str
    liveStatus: LiveStatus
    area_id: int
    area_name: str
    parent_area_id: int
    parent_area_name: str
    background: str
    title: str
    user_cover: str
    keyframe: str
    live_time: str
    tags: str
    is_strict_room: bool


