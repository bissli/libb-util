import logging
import os


logger = logging.getLogger(__name__)


def get_asset_path(name):
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
    return os.path.join(assets, name)
