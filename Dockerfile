FROM alpine:3.12
RUN adduser -D -u 1000 app
ADD . /home/app
RUN apk add py3-pip\
 py3-pillow\
 py3-cachetools\
 py3-yaml\
 py3-multidict\
 py3-aiohttp\
 py3-typing-extensions
USER app
WORKDIR /home/app
RUN pip3 install --user pymysql vkwave
ENTRYPOINT ["python3", "/home/app/main.py"]
