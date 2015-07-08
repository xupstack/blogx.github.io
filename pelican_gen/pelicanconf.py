#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals

AUTHOR = u'ectech'
SITENAME = u'58\u5546\u4e1a\u6280\u672f\u56e2\u961f'
SITEURL = ''

OUTPUT_PATH = '../'

TIMEZONE = 'Asia/Shanghai'

DEFAULT_LANG = u'cn'

THEME = 'theme-neat'

STATIC_PATHS = ['images']

DATE_FORMATS = {
    'en': '%Y-%m-%d',
    'cn': '%Y-%m-%d'
}

LOCALE = "C"

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None

# Blogroll
LINKS =  (('Pelican', 'http://getpelican.com/'),
          ('Python.org', 'http://python.org/'),
          ('Jinja2', 'http://jinja.pocoo.org/'),
          ('You can modify those links in your config file', '#'),)

# Social widget
SOCIAL = (('You can add links in your config file', '#'),
          ('Another social link', '#'),)

DEFAULT_PAGINATION = 30

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True
