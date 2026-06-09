import os

DATA_PATH = os.getenv('DATA_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')))
