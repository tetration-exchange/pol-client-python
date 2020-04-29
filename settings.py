import logging
from logging.handlers import RotatingFileHandler
import os


def init():
    global logger
    logger = logging.getLogger('tetration')

    # logging.basicConfig(stream=sys.stderr)
    os.makedirs("logs", exist_ok=True)
    log_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
    log_file = 'logs/tetration.%s.log' % str(os.getpid())
    my_handler = RotatingFileHandler(log_file, mode='a', maxBytes=5*1024*1024,
                                     backupCount=10, encoding=None, delay=0)
    my_handler.setFormatter(log_formatter)
    logger.addHandler(my_handler)
    logger.setLevel(logging.DEBUG)
