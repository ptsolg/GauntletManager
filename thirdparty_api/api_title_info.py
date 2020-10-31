import requests
import re

import thirdparty_api.kinopoisk_api as kinopoisk_api
import thirdparty_api.mal_api as mal_api

class ApiTitleInfo:
    def __init__(self, name, score):
        self.name = name
        self.score = score

    @staticmethod
    def from_url(url, config):
        score = None
        name = None
        print(re.search(r'kinopoisk', url))
        if re.search(r'kinopoisk', url):
            json = kinopoisk_api.get_film_data(url, config['kinopoisk_api_token'])
            name = json['data']['nameEn']
            score = json['rating']['rating']
            return ApiTitleInfo(name, score)
        elif re.search(r'anime', url):
            # json = await todo add
            # name = json[<>][<>]
            # score = json[<>][<>]
            pass
        else:
            return None