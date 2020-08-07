import requests
import json

class ImgSearch:
    _servers = [
        "https://searx.xyz",
        "https://searx.privatenet.cf",
        "https://searx.gnu.style",
        "https://searx.be",
        "https://searx.nevrlands.de"
    ]    
    def fetch(self, query):
        result = []
        results = []
        for server in self._servers:
            try:
                r = requests.get(server, params=
                    {"q": query,
                    "categories": "images",
                    "format": "json"
                })
                print(r.text)
                results = json.loads(r.text)['results']
                self._servers.pop(self._servers.index(server))
                self._servers = [server] + self._servers
            except json.decoder.JSONDecodeError:
                continue
        for r in results:
            if r['img_src'][-4:] in ['.gif', '.jpg', '.png']:
                if r['img_src'][:4] != "http":
                    r['img_src'] = "http:" + r['img_src']
                result.append(r['img_src'])
        return result
