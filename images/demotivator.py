import os
import tempfile
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

os.chdir(os.path.dirname(os.path.realpath(__file__)))


class Demotivator:
    pattern: Image

    def __init__(self):
        self.pattern = Image.open('demotivator.jpg')
        self.font1 = ImageFont.truetype(font="DejaVuSerifCondensed.ttf", size=48, encoding="unic")
        self.font2 = ImageFont.truetype(font="DejaVuSans.ttf", size=28, encoding="unic")

    def create(self, url, text1, text2):
        r = requests.get(url)
        img = Image.open(BytesIO(r.content))
        img = img.resize((542, 358))
        result = self.pattern.copy()
        result.paste(img, (58, 58))
        draw = ImageDraw.Draw(result)
        w1, h1 = draw.textsize(text1, font=self.font1)
        draw.text(((655 - w1) / 2, 450), text1, fill="white", font=self.font1)
        w2, h2 = draw.textsize(text2, font=self.font2)
        draw.text(((655 - w2) / 2, 525), text2, fill="white", font=self.font2)
        fPath = os.path.join(tempfile.gettempdir(), "demotivator.png")
        result.save(fPath)
        return fPath
