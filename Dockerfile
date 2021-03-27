FROM opensuse/leap:15.2
ADD . /home/app
RUN zypper ar -f https://download.opensuse.org/repositories/home:/wicked:/qubes-build/openSUSE_Leap_15.2/ python &&\
 zypper ar -f https://download.opensuse.org/repositories/home:/regataos/openSUSE_Leap_15.2/ imagemagick &&\
 zypper -n --gpg-auto-import-keys ref &&\
 zypper -n in --no-recommends ImageMagick\
 noto-coloremoji-fonts\
 dejavu-fonts\
 python3\
 curl
RUN curl -s https://bootstrap.pypa.io/get-pip.py | python3
RUN zypper -n rm --clean-deps curl && zypper -n clean
RUN python3 -m pip install pipenv
RUN groupadd -g 2000 app &&\
 useradd -u 2000 -m app -g app &&\
 mkdir -p /home/app/.local &&\
 chown -R app /home/app/.local

USER app
WORKDIR /home/app
RUN pipenv install
ENTRYPOINT ["pipenv", "run", "python", "main.py"]
