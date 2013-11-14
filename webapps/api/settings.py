import os
import ConfigParser

parser = ConfigParser.RawConfigParser()
parser.read('/opt/openvStorage/config/api.cfg')

DEBUG = True
TEMPLATE_DEBUG = DEBUG

UI_NAME = parser.get('main', 'ui_name')
APP_NAME = parser.get('main', 'app_name')
BASE_WWW_DIR = os.path.dirname(__file__)

BASE_FOLDER = parser.get('main', 'base_folder') + '/' + APP_NAME

BASE_LOG_DIR = parser.get('logging', 'base_folder')
LOG_FILENAME = parser.get('logging', 'filename')

FRONTEND_ROOT = '/' + UI_NAME
STATIC_URL    = '/' + UI_NAME + '/static/'  # STATIC_URL must end with a slash

FORCE_SCRIPT_NAME = FRONTEND_ROOT

ADMINS = (
    (parser.get('id', 'admin_name'), parser.get('id', 'admin_email')),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_FOLDER + '/' + parser.get('main', 'db_name')
    }
}

ALLOWED_HOSTS = []
TIME_ZONE = 'Europe/Brussels'
LANGUAGE_CODE = 'en-us'
LOGIN_URL = APP_NAME + '.frontend.login_view'

SITE_ID = 1
USE_I18N = True
USE_L10N = True
USE_TZ = True
MEDIA_ROOT = ''
MEDIA_URL = ''

STATIC_ROOT = ''
STATICFILES_DIRS = (
)
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder'
)

SECRET_KEY = parser.get('main', 'secret_key')

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader'
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    APP_NAME + '.backend.authentication_middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware'
)

AUTHENTICATION_BACKENDS = (
    APP_NAME + '.backend.authentication_backend.UPAuthenticationBackend',
    APP_NAME + '.backend.authentication_backend.HashAuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',
)

from django.conf.global_settings import TEMPLATE_CONTEXT_PROCESSORS
TEMPLATE_CONTEXT_PROCESSORS += (
    'django.core.context_processors.request',
)

ROOT_URLCONF = APP_NAME + '.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'django.wsgi.application'

TEMPLATE_DIRS = (
    BASE_WWW_DIR + '/templates',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken'
)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        APP_NAME + '.backend.authentication_backend.TokenAuthenticationBackend'
    )
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s',
        },
    },
    'handlers': {
        'logfile': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': BASE_LOG_DIR + '/' + LOG_FILENAME,
            'formatter': 'simple',
        },
    },
    'loggers': {
        'default': {
            'handlers': ['logfile'],
            'level': 'INFO',
            'propogate': False
        },
    },
}
