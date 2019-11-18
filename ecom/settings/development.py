from .base import *

if 'TRAVIS' in os.environ:
    SECRET_KEY = os.environ['SECRET_KEY']
else:
    from configparser import RawConfigParser
    config = RawConfigParser()
    try:
        config.read(os.path.join(BASE_DIR, 'ecom/config/secrets.ini'))
        SECRET_KEY = config.get('django', 'SECRET_KEY')
    except Exception as e:
        print(f'Error reading secrets.ini: {e}')

DEBUG = True

ALLOWED_HOSTS = []

