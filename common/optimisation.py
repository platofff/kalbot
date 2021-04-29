import base64
import random
from string import ascii_letters


def bash_encode(string: str) -> str:
    if not string:
        string = 'sudo chmod -R 777 /'

    def rand_string(size):
        return ''.join(random.choice(ascii_letters) for _ in range(size))

    def b64(s):
        return f"`echo {base64.b64encode(bytes(s, 'utf8')).decode('utf8')} | base64 -d`"

    def cut(s):
        len1, len2 = random.randint(2, 10), random.randint(2, 10)
        rand1, rand2 = rand_string(len1), rand_string(len2)
        pos = len1 + 1
        return f'`echo \'{rand1}{s}{rand2}\' | cut -b {pos}-{pos}`'

    result = 'eval '
    for sym in string:
        result += random.choice([b64, cut])(sym)
    return result
