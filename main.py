from app.application import create_app
from settings import load_settings

app = create_app(load_settings())
