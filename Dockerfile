FROM opensuse/leap:15.3
ADD . /home/app
RUN zypper -n in --no-recommends ImageMagick\
 noto-coloremoji-fonts\
 python39-base\
 curl
RUN curl -s https://bootstrap.pypa.io/get-pip.py -o - | python3.9
RUN groupadd -g 2000 app
RUN useradd -u 2000 -m app -g app
RUN python3.9 -m pip install vkwave requests wand pymysql PyYAML cachetools
RUN zypper -n rm --clean-deps curl
USER app
WORKDIR /home/app
ENTRYPOINT ["python3.9", "/home/app/main.py"]
