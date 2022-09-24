FROM ubuntu
USER root
WORKDIR /usr/src/app
RUN apt-get update && apt-get install -y \
    python3.9 \
    python3-pip \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-setuptools \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt *.py /usr/src/app/
COPY ./services /usr/src/app/services
RUN pip install -U pip & pip install -r requirements.txt
CMD [ "python3", "app.py" ]

