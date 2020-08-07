import yaml
import os

from google_images_search import GoogleImagesSearch


class ImgSearch:
    _gis: GoogleImagesSearch

    def __init__(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'googleapi.yaml')) as c:
            if not (os.environ['GAPI_KEY'] and os.environ['GPROJECT_CX']):
                config = yaml.safe_load(c)
            else:
                config = { 'dev_api_key': os.environ['GAPI_KEY'], 'project_cx': os.environ['GPROJECT_CX'] }
            self._gis = GoogleImagesSearch(config['dev_api_key'], config['project_cx'], validate_images=True)

    def fetch(self, query, count):
        result = []
        self._gis.search({'q': query, 'num': count, 'safe': 'off'})
        for image in self._gis.results():
            result.append(image.url)
        return result
