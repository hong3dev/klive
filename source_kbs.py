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

class SourceKBS(SourceBase):
    @classmethod
    def get_channel_list(cls):
        try:
            ret = []
            data = requests.get('http://onair.kbs.co.kr').text
            idx1 = data.find('var channelList = JSON.parse') + 30
            idx2 = data.find(');', idx1)-1
            data = data[idx1:idx2].replace('\\', '')
            data = json.loads(data)
            for channel in data['channel']:
                for channel_master in channel['channel_master']:
                    c = ModelChannel(cls.source_name, channel_master['channel_code'], channel_master['title'], channel_master['image_path_channel_logo'], True if channel_master['channel_type'] == 'TV' else False)
                    c.current = ''
                    ret.append(c)

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return ret

    @classmethod
    def get_url(cls, source_id, quality, mode):
        try:
            from framework.common.ott import OTTSupport
            url = OTTSupport.get_kbs_url(source_id)
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

