from flask import Flask
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

import asu.views
