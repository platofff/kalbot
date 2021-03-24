import os
from tempfile import gettempdir
from math import floor, ceil
from random import choice
from string import ascii_letters
from urllib import request

from wand.color import Color
from wand.drawing import Drawing
from wand.font import Font
from wand.image import Image


class Demotivator:
    BIG_FONT_SIZE = 0.052
    SM_FONT_SIZE = 0.036

    @classmethod
    def _get_name(cls) -> str:
        while True:
            name = ''.join([choice(ascii_letters) for _ in range(4)]) + '.png'
            if not os.path.exists(os.path.join(gettempdir(), name)):
                return name

    @classmethod
    def _dem_text(cls, img: Image, txt: str, font_k: float, font: str) -> Image:
        dem = Image(height=1000, width=floor(img.width * 1.1))
        dem.options['pango:align'] = 'center'
        dem.options['pango:wrap'] = 'word'
        dem.options['pango:single-paragraph'] = 'true'
        dem.options['trim:edges'] = 'south'
        dem.font = Font(font)
        dem.font_size = floor(font_k * dem.width)
        text = f"<span color='#ffffff'>{txt}</span>"
        dem.background_color = Color('black')
        dem.pseudo(dem.width, dem.height, pseudo=f"pango:{text}")
        dem.trim(color=Color('black'))
        return dem

    def create(self, url: str, text1: str, text2: str, name: str = _get_name()) -> str:
        draw = Drawing()
        draw.stroke_color = Color('white')
        r = request.urlopen(url).read()
        img = Image(blob=r)
        img.transform(resize='1500x1500>')

        dem1 = self._dem_text(img, text1, self.BIG_FONT_SIZE, 'serif')
        dem2 = self._dem_text(img, text2, self.SM_FONT_SIZE, 'sans')

        output = Image(width=dem1.width,
                       height=dem1.height + dem2.height + img.height + floor(0.12 * img.width),
                       background=Color('black'))
        img_left = floor(0.05 * img.width)
        img_top = floor(0.05 * img.width)
        draw.stroke_width = ceil(img.width / 1000) * 4
        half_stroke = floor(draw.stroke_width / 4)
        draw.polygon([(img_left - half_stroke, img_top - half_stroke),
                      (img_left + img.width, img_top - half_stroke),
                      (img_left + img.width, img_top + img.height),
                      (img_left - half_stroke, img_top + img.height)])  # Square polygon around image
        draw(output)
        output.composite(image=img, left=img_left, top=img_top)
        img_height = floor(0.07 * img.width + img.height)
        output.composite(image=dem1, left=0, top=img_height)
        output.composite(image=dem2, left=0, top=img_height + dem1.height)
        f_path = os.path.join(gettempdir(), name)
        output.save(filename=f_path)
        return f_path
