import requests as r
import re
def mal_parser(html):
    name=re.search(r'\<meta property=\"og:title\" content=\"(.*?)\"\>', html)[1]
    score=re.search(r'.*?score\-label.*?\>(\d+?\.\d+?)\<.*?', html)[1]
    num_of_episodes=re.search(r'pisodes\:</span>.*?(\d+).*?\<', html, flags=re.DOTALL)[1]
    return {'name': name, 'score': score, 'num_of_episodes': num_of_episodes}

def get_anime_data(url):
    response = r.get(url)
    if response.status_code == 200:
        html=response.text
        return mal_parser(html)
    else:
        raise "Bad myanimelist api status code recieved"

