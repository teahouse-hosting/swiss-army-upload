"""
Mock server for counter.teahouse.cafe
"""

from flask import Flask

app = Flask(__name__)


@app.route("/user/")
def user_info(): ...


@app.route("/auth/whoami/")
def whoami(): ...


@app.route("/upload/get-s3-config")
def get_s3_config(): ...
