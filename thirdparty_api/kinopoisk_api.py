import requests as r
import json
import re

def get_id_from_url(url):
    r = r'^.*?kinopoisk.ru/film/(\d+)'
    return re.search(r, url)[1]

def get_film_data(url, token, tables=['RATING']):
    id = get_id_from_url(url)
    headers = {'X-API-KEY': token, 'accept': 'application/json'}
    param=''
    if len(tables):
        param=f'?append_to_response={"&".join(tables)}'
    response = r.get(f"https://kinopoiskapiunofficial.tech/api/v2.1/films/{id}{param}", headers=headers)
    if response.status_code == 200:
        return json.loads(response.text)
    else:
        raise "Bad kinopoisk api status code recieved"