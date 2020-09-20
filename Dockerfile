FROM ubuntu:20.04
RUN adduser -q --gecos "" --disabled-password --uid 1000 app
ADD . /home/app
RUN apt-get update && apt-get install --install-recommends=false -y \
python3-pip \
python3-pil \
python3-pymysql \
python3-requests \
python3-cachetools \
python3-yaml \
python3-multidict \
python3-aiohttp \
python3-typing-extensions
USER app
WORKDIR /home/app
RUN pip3 install --user vkwave
ENTRYPOINT ["python3", "/home/app/main.py"]
