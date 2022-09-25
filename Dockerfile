FROM python:3.9
USER root
WORKDIR /usr/src/app
COPY requirements.txt *.py /usr/src/app/
COPY services /usr/src/app/services
RUN pip install -U pip & pip install -r requirements.txt
RUN wget https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.4.1-amd64-static.tar.xz \
    && tar xvf ffmpeg-4.4.1-amd64-static.tar.xz \
    && mv ffmpeg-4.4.1-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && mv ffmpeg-4.4.1-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-4.4.1-amd64-static ffmpeg-4.4.1-amd64-static.tar.xz
RUN apt-get update && apt-get install -y nano
CMD ["python", "app.py"]

