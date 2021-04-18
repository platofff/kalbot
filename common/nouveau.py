from typing import Optional
from urllib import request

from wand.image import Image


class Nouveau:
    @staticmethod
    def create(url: str) -> Optional[bytes]:
        img = Image(blob=request.urlopen(url).read())
        img.transform(resize='500x500>')
        img.format = 'jpeg'
        img.compression_quality = 7
        return img.make_blob()
