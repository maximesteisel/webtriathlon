import logging
import threading
from django.conf import settings
from webtriathlon.misc import get_db_version, _Batch_mode

MAX_CONN = 15
CONN_LOCK = threading.BoundedSemaphore(MAX_CONN)

logging.basicConfig()
LOG = logging.getLogger("webtriathlon")
DEBUG=settings.DEBUG
if settings.DEBUG:
    LOG.setLevel(logging.DEBUG)
else:
    LOG.setLevel(logging.INFO)
LOG.setLevel(logging.INFO)

BATCH_MODE = _Batch_mode()


