# BiliRecorder


<div align=center>
  <img src="https://img.shields.io/badge/python-3.9-blue" alt="python">
  <img src="https://img.shields.io/badge/ffmpeg-4.41-green" alt="minecraft">
  <img src="https://img.shields.io/badge/bilibili-1.0-pink" alt="bilibili">
<a href="https://hub.docker.com/repository/docker/summerkirakira/bili-recorder">
  <img src="https://img.shields.io/badge/docker-1.0-yellow" alt="docker">
</a>
</div>

---

## 介绍
全自动监听、录制、投稿B站直播，并为录制文件添加ass弹幕。

## 实现功能
- [x] 监听直播间
- [x] 自动录制直播
- [x] 自动投稿
- [x] 自动添加ass弹幕
- [x] 自动添加直播间封面
- [x] 将弹幕渲染入视频

## 使用方法
### 1. docker安装
```bash
docker run -d --name bili-recorder \
  -v /path/to/config:/usr/src/app/config \
  -v /path/to/logs:/usr/src/app/logs \
  -v /path/to/output:/app/output 
  summerkirakira/bili-recorder
```

### 2. 源码安装
⚠️**弹幕转换等多项功能需要 [ffmpeg](https://ffmpeg.org) 的支持，请确保安装正确**⚠️
```bash
git clone https://github.com/summerkirakira/biliRecorder && cd biliRecorder # 下载源码
pip install -r requirements.txt # 安装依赖
python app.py # 运行
```

## 配置文件
配置文件在`config/config.json`中 (如要复制以下内容请**删除**注释！)
```yaml
{
    "mid": 0, // biliRecorder所使用账户的用户id 0为匿名
    "SESSDATA": null, // biliRecorder所使用账户的SESSDATA，为null时为匿名
    "bili_jct": null, // biliRecorder所使用账户的bili_jct，为null时为匿名
    "DedeUserID": null, // biliRecorder所使用账户的DedeUserID，为null时为匿名
    "DedeUserID__ckMd5": null, // biliRecorder所使用账户的DedeUserID__ckMd5，为null时为匿名
    "cookies": null,
    "refresh_token": null, // biliRecorder所使用账户的refresh_token，为null时为匿名
    "live_config": {
        "download_format": "%title-%Y年%m%月%d%日-%H点%M分场", // 直播录制文件名格式，支持strftime
        "download": {
            "download_type": 1,
            "custom_downloader": null
        }
    },
    "access_token": null, // biliRecorder所使用账户的access_token，为null时为匿名
    "monitor_live_rooms": [
        {
            "short_id": 83171, // 直播间号
            "auto_download": true,
            "auto_download_path": "/path/to/download", // 直播录制文件保存路径
            "auto_download_quality": 10000, // 直播录制画质
            "auto_upload": {
                "enabled": false, // 是否自动投稿
                "title": "【直播录制】%title-%Y年%m%月%d%日-%H点%M分场", // 直播投稿标题，支持strftime
                "desc": "直播录制", // 直播投稿简介
                "source": "https://live.bilibili.com/", //转载来源
                "tags": [
                    "直播录制" // 直播投稿标签
                ],
                "tid": 27, // 直播投稿分区，默认为生活区
                "cover_path": "AUTO" // 封面路径，AUTO为自动获取直播间封面
            }
        }
    ]
}
```
如果无需自动投稿录播，使用匿名账户即可，可以正常使用所有功能。账户信息可通过 [biliup-rs](https://github.com/ForgQi/biliup-rs) 获取。