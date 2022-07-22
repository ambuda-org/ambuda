"""The production endpoint for Ambuda.

Setup: https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-18-04
"""

from ambuda import create_app

app = create_app("production")
