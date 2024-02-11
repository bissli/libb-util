"""Config related settings, follows 12factor.net
"""
import os
import pathlib
import platform
import tempfile

WIN = os.name == 'nt'
WSL = 'Microsoft' in platform.release()
NIX = platform.system() == 'Linux' and not WSL

# Environment
ENVIRONMENT = None
if 'CONFIG_PROD' in os.environ:
    ENVIRONMENT = 'prod'
if 'CONFIG_DEV' in os.environ:
    ENVIRONMENT = 'dev'
if ENVIRONMENT is None:
    raise AttributeError('Missing environmnet type, set in env variables')
CHECKTTY = 'CONFIG_CHECKTTY' in os.environ
WEBAPP = 'CONFIG_WEBAPP' in os.environ


class Setting(dict):
    """Dict where d['foo'] can also be accessed as d.foo
    but also automatically creates new sub-attributes of
    type Setting. This behavior can be locked to turn off
    later. WARNING: not copy safe

    >>> cfg = Setting()
    >>> cfg.unlock() # locked after config.py load

    >>> cfg.foo.bar = 1
    >>> hasattr(cfg.foo, 'bar')
    True
    >>> cfg.foo.bar
    1
    >>> cfg.lock()
    >>> cfg.foo.bar = 2
    Traceback (most recent call last):
     ...
    ValueError: This Setting object is locked from editing
    >>> cfg.foo.baz = 3
    Traceback (most recent call last):
     ...
    ValueError: This Setting object is locked from editing
    >>> cfg.unlock()
    >>> cfg.foo.baz = 3
    >>> cfg.foo.baz
    3
    """

    _locked = False

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def __getattr__(self, name):
        """Create sub-setting fields on the fly"""
        if name not in self:
            if self._locked:
                raise ValueError('This Setting object is locked from editing')
            self[name] = Setting()
        return self[name]

    def __setattr__(self, name, val):
        if self._locked:
            raise ValueError('This Setting object is locked from editing')
        elif name not in self:
            self[name] = Setting()
        self[name] = val

    @staticmethod
    def lock():
        Setting._locked = True

    @staticmethod
    def unlock():
        Setting._locked = False


# Global
tmpdir = Setting()
tmpdir.dir = tempfile.gettempdir()
pathlib.Path(tmpdir.dir).mkdir(parents=True, exist_ok=True)

# Syslog
syslog = Setting()
syslog.host = os.getenv('CONFIG_SYSLOG_HOST')
syslog.port = os.getenv('CONFIG_SYSLOG_PORT')


# Intermedia Email
mail = Setting()
mail.domain = os.getenv('CONFIG_MAIL_DOMAIN')
mail.server = os.getenv('CONFIG_MAIL_SERVER')
mail.fromemail = os.getenv('CONFIG_MAIL_FROMEMAIL')
mail.toemail = os.getenv('CONFIG_MAIL_TOEMAIL')
mail.adminemail = os.getenv('CONFIG_MAIL_ADMINEMAIL')


# Mandrill API integration
mandrill = Setting()
mandrill.apikey = os.getenv('CONFIG_MANDRILL_APIKEY')
mandrill.smtp = os.getenv('CONFIG_MANDRILL_SMTP','smtp.mandrillapp.com')
mandrill.url = os.getenv('CONFIG_MANDRILL_URL', 'https://mandrillapp.com/api/1.0/')


if __name__ == '__main__':
    __import__('doctest').testmod()
