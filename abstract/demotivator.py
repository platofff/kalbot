import os
from tempfile import gettempdir
from math import floor, ceil
from random import choice
from string import ascii_letters
from urllib import request
from urllib.error import HTTPError, URLError

from wand.color import Color
from wand.drawing import Drawing
from wand.exceptions import MissingDelegateError
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

    def create(self, url: str, text1: str, text2: list, name: str = None) -> str:
        if not name:
            name = self._get_name()
        draw = Drawing()
        draw.stroke_color = Color('white')
        try:
            r = request.urlopen(url).read()
            img = Image(blob=r)
        except (HTTPError, URLError, MissingDelegateError):
            return ''
        img.transform(resize='1500x1500>')
        img.transform(resize='300x300<')

        dem1 = self._dem_text(img, text1, self.BIG_FONT_SIZE, 'serif')
        dem2 = [self._dem_text(img, text, self.SM_FONT_SIZE, 'sans') for text in text2]

        output = Image(width=dem1.width,
                       height=dem1.height + sum([dem.height for dem in dem2]) + img.height + floor(0.12 * img.width),
                       background=Color('black'))
        img_left = floor(0.05 * img.width)
        img_top = floor(0.05 * img.width)
        draw.stroke_width = ceil(img.width / 500)
        k = draw.stroke_width * 4
        draw.polygon([(img_left - k, img_top - k),
                      (img_left + img.width + k, img_top - k),
                      (img_left + img.width + k, img_top + img.height + k),
                      (img_left - k, img_top + img.height + k)])  # Square polygon around image
        draw(output)
        output.composite(image=img, left=img_left, top=img_top)
        img_height = floor(0.07 * img.width + img.height)
        output.composite(image=dem1, left=0, top=img_height)
        h = img_height + dem1.height
        for dem in dem2:
            output.composite(image=dem, left=0, top=h)
            h += dem.height
        f_path = os.path.join(gettempdir(), name)
        output.save(filename=f_path)
        return f_path
