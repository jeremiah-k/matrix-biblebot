import requests
from bs4 import BeautifulSoup
import configparser

# Load the configuration
config = configparser.ConfigParser()
config.read('biblegateway.conf')

async def get_passage(passage, version="NKJV"):
    url = config['URL']['passage'].format(passage, version)
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    passage_text = soup.select_one('.passage-text').text
    return passage_text.strip()

async def get_verse_of_the_day(version="NKJV"):
    url = config['URL']['votd'].format(version)
    response = requests.get(url).json()
    return response['votd']['text'], response['votd']['reference']
