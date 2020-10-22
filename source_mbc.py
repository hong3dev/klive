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

class SourceMBC(SourceBase):
    ch_list = [
        '1|무한도전24|http://vodmall.imbc.com/util/player/onairurlutil_mudo.ashx?type=m|Y',
        '2|MBC 표준FM|sfm|N',
        '3|MBC FM4U|mfm|N',
        '4|MBC 올댓뮤직|chm|N',
    ]

    @classmethod
    def get_channel_list(cls):
        try:
            ret = []
            for item in SourceMBC.ch_list:
                tmp = item.split('|')
                c = ModelChannel(cls.source_name, tmp[0], tmp[1], None, True if tmp[3]=='Y' else False)
                ret.append(c)
            return ret
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return ret

    @classmethod
    def get_url(cls, source_id, quality, mode):
        try:
            for item in SourceMBC.ch_list:
                tmp = item.split('|')
                if tmp[0] == source_id:
                    if tmp[3] == 'Y':
                        url = tmp[2]
                    else:
                        url = 'http://miniplay.imbc.com/AACLiveURL.ashx?protocol=M3U8&channel=%s&agent=android&androidVersion=24' % tmp[2]
                    break
            url = requests.get(url).text.strip()
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

