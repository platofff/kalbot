import os
import sys
import tempfile

from math import ceil
from random import randint

from urllib import request
from PIL import Image, ImageDraw, ImageFont


class Demotivator:
    pattern: Image
    background: Image
    BIG_FONT_DIV = 14
    SM_FONT_DIV = 24

    def create(self, url, text1, text2, name=None):
        if not name:
            name = str(randint(-32767, 32767)) + '.png'
        r = request.urlopen(url)
        img = Image.open(r)

        font1 = ImageFont.truetype(font=os.path.join(sys.path[0], "images", "fonts", "LiberationSerif-TWEmoji.ttf"),
                                   size=ceil((img.size[1] + img.size[0]) / self.BIG_FONT_DIV), encoding="unic")
        font2 = ImageFont.truetype(font=os.path.join(sys.path[0], "images", "fonts", "LiberationSans-TWEmoji.ttf"),
                                   size=ceil((img.size[1] + img.size[0]) / self.SM_FONT_DIV), encoding="unic")

        result = Image.new('RGB', (ceil(img.size[0] * 1.2), ceil(img.size[1] * 1.4)))
        draw = ImageDraw.Draw(result)
        offset = ceil(img.size[0] * 0.1)
        result.paste(img, (offset, offset))
        draw.rectangle([offset - 6, offset - 6, result.size[0] - offset + 6, img.size[1] + offset + 6], fill=None,
                       outline=(255, 255, 255), width=3)

        def addBlack(px, img):
            self.background = Image.new('RGB', (img.size[0], img.size[1] + px), (0, 0, 0))
            self.background.paste(img, (0, 0))
            return self.background.copy()

        max_w = ceil(result.size[0] * 0.95)

        def formatText(text, font, repeat=False):
            if not text:
                return ''
            if text[0] == ' ':
                text = text[1:]
            text = text.split('\n') or [text]
            if len(text) > 1 and not repeat:
                x = [formatText(t, font, True) for t in text]
                return '\n'.join(x)
            _l = len(text)
            for i in range(_l):
                while True:
                    w, h = draw.textsize(text[i], font=font)
                    if w < max_w:
                        break
                    else:
                        splitted = text[i].split(' ')
                        if len(splitted) == 1:
                            ws, hs = draw.textsize(splitted[0], font=font)
                            if ws <= max_w:
                                break
                            else:
                                new_string = 1
                                while True:
                                    splitted.append('')
                                    splitted[new_string - 1] = list(splitted[new_string - 1])
                                    ws, hs = draw.textsize(''.join(splitted[new_string - 1]), font=font)
                                    while ws > max_w:
                                        ws, hs = draw.textsize(''.join(splitted[new_string - 1]), font=font)
                                        splitted[new_string] = splitted[new_string - 1].pop(-1) + splitted[new_string]
                                    splitted[new_string - 1] = ''.join(splitted[new_string - 1])
                                    wn, hn = draw.textsize(splitted[new_string], font=font)
                                    if wn <= max_w:
                                        break
                                    else:
                                        new_string += 1
                        if len(text) == i + 1:
                            text.append('')
                        text[i + 1] = f'{text[i + 1]} {splitted.pop(0)}'
                        text[i] = ' '.join(splitted)
            if _l == len(text):
                text[-1] = text[-1].lstrip()
                if text[-1] == '':
                    text = list(text)[:-1]
                else:
                    text = list(text)
                try:
                    text[-1] = text[-1].lstrip()
                except IndexError:
                    pass
                return '\n'.join(reversed(text))
            else:
                for i in range(len(text)):
                    text[i].replace('\n', '')
                return formatText('\n'.join(list(text)), font, True)

        text1 = formatText(text1, font1)
        text2 = formatText(text2, font2)

        w1, h1 = draw.textsize(text1, font=font1)
        w2, h2 = draw.textsize(text2, font=font2)
        cur_text_h = result.size[1] - offset - font1.size - img.size[1]

        if h1 + h2 > cur_text_h:
            black_px = h1 + h2 - cur_text_h
            result = addBlack(black_px, result)
            draw = ImageDraw.Draw(result)

        draw.multiline_text(((result.size[0] - w1) / 2, img.size[1] + offset + ceil(font2.size / 2)), text1,
                            fill="white", font=font1, align="center")
        draw.multiline_text(((result.size[0] - w2) / 2, ceil(font1.size / 2) + img.size[1] + h1 + offset), text2,
                            fill="white", font=font2, align="center")

        f_path = os.path.join(tempfile.gettempdir(), name)
        result.save(f_path)
        return f_path
