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

class NavertvItem:
    ch_list = None

    def __init__(self, id, title, url, quality):
        self.id = id.strip()
        self.title = title.strip()
        self.url = url.strip()
        self.quality = quality.strip()
        NavertvItem.ch_list[id] = self

class SourceNavertv(SourceBase):
    @classmethod
    def get_channel_list(cls):
        try:
            tmp = ModelSetting.get('navertv_list')
            NavertvItem.ch_list = {}
            ret = []
            for item in tmp.split('\n'):
                if item.strip() == '':
                    continue
                tmp2 = item.split('|')
                if len(tmp2) < 3:
                    continue
                c = ModelChannel(cls.source_name, tmp2[0], tmp2[1], None, True)
                quality = '720' if len(tmp2) == 3 else tmp2[3]
                NavertvItem(tmp2[0], tmp2[1], tmp2[2], quality)
                c.current = ''
                ret.append(c)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return ret

    @classmethod
    def get_url(cls, source_id, quality, mode):
        try:
            logger.debug('source_id:%s, quality:%s, mode:%s', source_id, quality, mode)
            target_url = NavertvItem.ch_list[source_id].url
            from framework.common.ott import OTTSupport

            if quality == 'default':
                quality = NavertvItem.ch_list[source_id].quality
            elif quality == 'SD':
                quality = '480'
            elif quality == 'FHD':
                quality = '1080'


            url = OTTSupport.get_naver_url(target_url, quality)
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
