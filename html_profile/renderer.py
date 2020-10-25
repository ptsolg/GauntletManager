import imgkit
import hashlib
import random

def render_html_from_string(html_string, css_path):
    options = {
        "enable-local-file-access": None,
        "height": 1000,
        "width": 1800,
        "disable-smart-width": None,
        "quality": 100,
        "zoom": 4,
        "quiet": None,
    }

    fname = f'{int(random.random()*10000)}.jpg'
    imgkit.from_string(html_string, fname, options=options, css=css_path)
    return fname
