from flask import Flask
from flask import render_template
import logging

from utils.config import Config
from utils.common import usign_init

app = Flask(__name__)

import server.views
