Bissli Utilities Module
=======================

![libb](https://github.com/bissli/libb/raw/master/bissli.jpg "Bissli - via wikipedia https://en.wikipedia.org/wiki/Bissli")

Contents
--------

- `util.py`: general programming utility functions
- `weblib.py`: web programming utility functions, esp. web.py and flask
- `log.py`: extensions to logging module, for colorizing output, email alerts ..
- `console.py`: unix and windows console colorizing support

Environemntal Variables
-----------------------
`config.py`
```
CONFIG_PROD (
or CONFIG_DEV
or CONFIG_QA
or CONFIG_UAT
)

Apptype:
- CONFIG_WEBAPP
- CONFIG_CHECKTTY

Enable mail:
- CONFIG_MAIL_DOMAIN
- CONFIG_MAIL_SERVER
- CONFIG_MAIL_FROMEMAIL
- CONFIG_MAIL_TOEMAIL
- CONFIG_MAIL_ADMINEMAIL
- CONFIG_MANDRILL_APIKEY

Enable syslog:
- CONFIG_SYSLOG_HOST
- CONFIG_SYSLOG_PORT

Tempdir:
- CONFIG_TMPDIR

Logging:
- CONFIG_LOG_MODULES_EXTRA
- CONFIG_LOG_MODULES_IGNORE
```
