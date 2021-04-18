FROM opensuse/tumbleweed:latest
ADD . /home/app
RUN zypper -n in --no-recommends ImageMagick\
 noto-coloremoji-fonts\
 dejavu-fonts\
 python3\
 curl\
 shadow
RUN curl -s https://bootstrap.pypa.io/get-pip.py | python3
RUN zypper -n rm --clean-deps curl && zypper -n clean
RUN python3 -m pip install -r /home/app/requirements.txt
RUN groupadd -g 2000 app &&\
 useradd -u 2000 -m app -g app
USER app
WORKDIR /home/app
ENTRYPOINT ["/home/app/main.py"]
