# Django settings for webtriathlon project.
import os, sys
import zipfile
from os.path import join, expanduser, abspath, dirname

top_dir = join(dirname(__file__), "..")
top_dir = abspath(top_dir)
external_dir = join(top_dir, "external")
sys.path.pop(0) #remove current dir
sys.path.insert(0, external_dir )
sys.path.insert(0, top_dir )
os.environ["PYTHONPATH"] = os.pathsep.join(sys.path)

LOCAL_DATA_DIR = abspath(join(dirname(__file__), "..", "data"))
DATA_DIR = os.environ.get("WT_DATA_DIR", LOCAL_DATA_DIR)

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = join(DATA_DIR, "media")
STATIC_ROOT = MEDIA_ROOT #django > 1.3

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'
STATIC_URL = MEDIA_URL

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/admin/'



CACHE_BACKEND = "dummy://"
#CACHE_MIDDLEWARE_SECONDS = 10

#For debug
ARGV=sys.argv
PATH=sys.path
ENVIRON=os.environ
FILE=__file__


ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

AUTH_PROFILE_MODULE = 'webtriathlon.addressbook.Person'

MANAGERS = ADMINS
DATABASE_PATH = expanduser("~") 
DATABASES = {
        "default": {
            "ENGINE":'django.db.backends.sqlite3',
            #"USER": "webtriathlon",
            "HOST": "127.0.0.1", # localhost doesn't work on windows
            "OPTIONS": {
                "timeout": 20,
                }
            }
        }

if os.environ.get("WT_TEST", ""):
    DEBUG = True
    DATABASES["default"]["NAME"] = join(DATABASE_PATH,
            "webtriathlon_test.sqlite")
else:
    DEBUG = False
    DATABASES["default"]["NAME"] = join(DATABASE_PATH,
            "webtriathlon.sqlite")

TEMPLATE_DEBUG = DEBUG


# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Brussels'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'fr-BE'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'e#d)vktudey9er8=ywtd$vlxg$-s*ec+hohi%k%87fz8ytexj5'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    #'django.middleware.cache.CacheMiddleware',
    #'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    #'django.middleware.cache.FetchFromCacheMiddleware',
)

ROOT_URLCONF = 'webtriathlon.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    join(DATA_DIR, "templates"),
    join(DATA_DIR, "admin", "templates"),
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    )

INTERNAL_IPS = (
     "127.0.0.1",
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.markup',
    'django.contrib.messages',
    'webtriathlon.core',
    'webtriathlon.user_site',
    'webtriathlon.admin_site',
    'webtriathlon.api',
    'webtriathlon.dynamic',
    #'webtriathlon.external.piston',
    #'south',
)
