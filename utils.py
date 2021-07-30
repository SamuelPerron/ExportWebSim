import requests
import os
from dotenv import load_dotenv

load_dotenv()

ROOT_URL = os.environ.get('ROOT_URL')

def login():
    session = requests.Session()

    data = {
        'login': os.environ.get('LOGIN'),
        'pwd': os.environ.get('PASSWORD'),
        'token': ''
    }
    session.post(f'{ROOT_URL}/Site/Connect/', data)

    return session