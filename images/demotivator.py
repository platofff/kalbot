import os
import sys
import tempfile
import textwrap
from io import BytesIO
from math import ceil
from random import randint

import requests
from PIL import Image, ImageDraw, ImageFont


class Demotivator:
    pattern: Image
    background: Image
    MAX_LEN_BIG = 25
    MAX_LEN_SM = 40

    def __init__(self):
        self.pattern = Image.open(os.path.join(sys.path[0], "images", "demotivator.jpg"))
        self.font1 = ImageFont.truetype(font=os.path.join(sys.path[0], "images", "fonts", "LiberationSerif-TWEmoji.ttf"),
                                        size=48, encoding="unic")
        self.font2 = ImageFont.truetype(font=os.path.join(sys.path[0], "images", "fonts", "LiberationSans-TWEmoji.ttf"),
                                        size=28, encoding="unic")

    def create(self, url, text1, text2, name=None):
        if not name:
            name = str(randint(-32767, 32767)) + '.png'
        r = requests.get(url, timeout=3)
        img = Image.open(BytesIO(r.content))
        img = img.resize((542, 358))
        result = self.pattern.copy()
        result.paste(img, (58, 58))

        def addBlack(num, img):
            self.background = Image.new('RGB', (img.size[0], img.size[1] + num * 50), (0, 0, 0))
            self.background.paste(img, (0, 0))
            return self.background.copy()

        text1 = textwrap.fill(text1, self.MAX_LEN_BIG)
        text2 = textwrap.fill(text2, self.MAX_LEN_SM)

        draw = ImageDraw.Draw(result)
        w1, h1 = draw.textsize(text1, font=self.font1)
        w2, h2 = draw.textsize(text2, font=self.font2)

        blackNum = 0
        if h1 + h2 > 140:
            blackNum += ceil((h1 + h2 - 140) / 50)
        result = addBlack(blackNum, result)
        del blackNum

        draw = ImageDraw.Draw(result)
        draw.multiline_text(((655 - w1) / 2, 450), text1, fill="white", font=self.font1, align="center")
        draw.multiline_text(((655 - w2) / 2, 470 + h1), text2, fill="white", font=self.font2, align="center")

        fPath = os.path.join(tempfile.gettempdir(), name)
        result.save(fPath)
        return fPath
