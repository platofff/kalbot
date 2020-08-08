import os
import tempfile
from io import BytesIO
from math import ceil

import requests
from PIL import Image, ImageDraw, ImageFont

os.chdir(os.path.dirname(os.path.realpath(__file__)))


class Demotivator:
    pattern: Image
    background: Image

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

        def addBlack(num, img):
            self.background = Image.new('RGB', (img.size[0], img.size[1] + num * 100), (0, 0, 0))
            self.background.paste(img, (0, 0))
            return self.background.copy()

        def formatLabel(label, big):
            if big:
                maxLen = 23
            else:
                maxLen = 34
            result = []
            r = 0
            label = label.split(" ")
            i = 0
            while i in range(len(label)):
                result.append([])
                while True:
                    result[r].append(label[i])
                    i += 1
                    if i == len(label):
                        break
                    elif len(''.join(result[r] + [label[i]])) >= maxLen:
                        break
                result[r] = ' '.join(result[r])
                r += 1
            return "\n".join(result)

        text1 = formatLabel(text1, True)
        text2 = formatLabel(text2, False)

        draw = ImageDraw.Draw(result)
        w1, h1 = draw.textsize(text1, font=self.font1)
        w2, h2 = draw.textsize(text2, font=self.font2)

        blackNum = 0
        if h1 > 143:
            blackNum += ceil((h1 - 143) / 100) + 1
        if h2 > 143:
            blackNum += ceil((h2 - 143) / 100)
        result = addBlack(blackNum, result)
        del blackNum

        draw = ImageDraw.Draw(result)
        draw.multiline_text(((655 - w1) / 2, 450), text1, fill="white", font=self.font1, align="center")
        draw.multiline_text(((655 - w2) / 2, 470 + h1), text2, fill="white", font=self.font2, align="center")

        fPath = os.path.join(tempfile.gettempdir(), "demotivator.png")
        result.save(fPath)
        return fPath
