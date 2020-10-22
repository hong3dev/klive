# -*- coding: utf-8 -*-
#########################################################
# python
import os
import sys
import logging
import traceback
import json
import re
import urllib
import requests
import threading

# third-party

# sjva 공용

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelChannel
from .source_base import SourceBase

#########################################################

class SourceSBS(SourceBase):
    @classmethod
    def get_channel_list(cls):
        try:
            ret = []
            url_list = ['http://static.apis.sbs.co.kr/play-api/1.0/onair/channels', 'http://static.apis.sbs.co.kr/play-api/1.0/onair/virtual/channels']
            for url in url_list:
                data = requests.get(url).json()
                for item in data['list']:
                    c = ModelChannel(cls.source_name, item['channelid'], item['channelname'], None, True if 'type' not in item or item['type'] == 'TV' else False)
                    c.current = item['title']
                    ret.append(c)
            return ret
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return ret

    @classmethod
    def get_url(cls, source_id, quality, mode):
        try:
            from framework.common.ott import OTTSupport
            url = OTTSupport.get_sbs_url(source_id)
            if mode == 'web_play':
                return 'return_after_read', url
            return 'redirect', url
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return

    @classmethod
    def get_return_data(cls, source_id, url, mode):
        try:
            data = requests.get(url).text
            return cls.change_redirect_data(data)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return data

