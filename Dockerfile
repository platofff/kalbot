FROM alpine:3.13
RUN adduser -D -u 1000 app
ADD . /home/app
RUN apk add py3-pip\
 py3-pillow\
 py3-cachetools\
 py3-yaml\
 py3-multidict\
 py3-aiohttp\
 py3-typing-extensions\
 libffi\
 libffi-dev\
 build-base\
 python3-dev\
 openssl-dev
RUN pip3 install pymysql vkwave
RUN apk del libffi-dev\
 build-base\
 python3-dev\
 openssl-dev
USER app
WORKDIR /home/app
ENTRYPOINT ["python3", "/home/app/main.py"]
