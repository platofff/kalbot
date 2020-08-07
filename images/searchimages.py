import urllib3
import json

class ImgSearch:

    def __init__(self):
        self.http = urllib3.PoolManager()

    def fetch(self, query):
        result = []
        r = self.http.request('GET', 'https://searx.fmac.xyz', fields=
        {"q": query,
         "categories": "images",
         "format": "json"
         })
        results = json.loads(r.data)['results']
        for r in results:
            if r['img_src'][-4:] in ['.gif', '.jpg', '.png']:
                if r['img_src'][:4] != "http":
                    r['img_src'] = "http:" + r['img_src']
                result.append(r['img_src'])
        return result
