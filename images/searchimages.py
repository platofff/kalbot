import requests
import json

class ImgSearch:
    def fetch(self, query):
        result = []
        r = requests.get('https://searx.fmac.xyz', params=
        {"q": query,
         "categories": "images",
         "format": "json"
         })
        print(r.text)
        results = json.loads(r.text)['results']
        for r in results:
            if r['img_src'][-4:] in ['.gif', '.jpg', '.png']:
                if r['img_src'][:4] != "http":
                    r['img_src'] = "http:" + r['img_src']
                result.append(r['img_src'])
        return result
