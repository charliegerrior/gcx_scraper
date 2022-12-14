from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy

import logging
from logging.handlers import RotatingFileHandler
import os

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

from app import models

if not app.debug:
    if app.config['LOG_TO_STDOUT']:
        #stream_handler = logging.StreamHandler()
        #stream_handler.setLevel(logging.INFO)
        #app.logger.addHandler(stream_handler)
        app.logger = logging.getLogger()
        app.logger.setLevel(logging.INFO)
    else:
        if not os.path.exists('logs'):
            os.mkdir('logs')
            file_handler = RotatingFileHandler('logs/gcx.log', maxBytes=10240,
                                                   backupCount=10)
            file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)

            app.logger.setLevel(logging.INFO)
            app.logger.info('GCX startup')
