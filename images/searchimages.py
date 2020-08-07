import requests
import json

SERVERS = [
"https://searx.xyz",
"https://searx.privatenet.cf",
"https://searx.gnu.style",
"https://searx.be",
"https://searx.nevrlands.de"
]

class ImgSearch:
    def fetch(self, query):
        result = []
        results = []
        for server in SERVERS:
            try:
                r = requests.get(server, params=
                    {"q": query,
                    "categories": "images",
                    "format": "json"
                })
                results = json.loads(r.text)['results']
            except JSONDecodeError:
                continue
        for r in results:
            if r['img_src'][-4:] in ['.gif', '.jpg', '.png']:
                if r['img_src'][:4] != "http":
                    r['img_src'] = "http:" + r['img_src']
                result.append(r['img_src'])
        return result
