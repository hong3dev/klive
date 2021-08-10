# -*- coding: utf-8 -*-
#########################################################
# python
import os
import sys
import logging
import traceback
import json
import re
from datetime import datetime, timedelta
import urllib

# third-party
import requests
from flask import redirect

# sjva 공용
from framework import app, db, scheduler, path_app_root, path_data

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelChannel
from .source_base import SourceBase

#########################################################


class SourceSeezn(SourceBase):
    default_header = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
                'Accept': 'application/json',
            }
    
    @classmethod
    def prepare(cls, source_id, source_pw, arg):
        pass

    @classmethod
    def get_channel_list(cls):
        try:
            ret = []
            data = requests.get('https://api.seezntv.com/svc/menu/app6/api/epg_chlist?category_id=1', headers=cls.default_header).json()
            for item in data['data']['list'][0]['list_channel']:
                c = ModelChannel(cls.source_name, item['ch_no'], item['service_ch_name'], item['ch_image_list'], (item['type']!='AUDIO_MUSIC'))
                if item['cj_drm_yn'] == 'Y':
                    c.is_drm_channel = True

                c.current = urllib.parse.unquote_plus(item['program_name'])
                ret.append(c)
            
            
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        # logger.debug(ret)
        return ret

    @classmethod
    def get_url(cls, source_id, quality, mode):
        try:
            qual = {'FHD': '4000', 'HD': '2000', 'SD': '1000'}
            quality = qual[ModelSetting.get('seezn_quality')]
            
            # 오디오 채널은 고정일까? 매번 가져오는건 비효율..
            # audio_ch = requests.get('https://api.seezntv.com/svc/menu/app6/api/epg_chlist?category_id=12&istest=0', headers=cls.default_header).json()['data']['list'][0]['list_channel']
            # audio_chs = [ch['ch_no'] for ch in audio_ch]
            audio_chs = ['701', '332', '718', '720', '716', '731', '729', '335', '733', '734', '732', '330', '333', '717', '730', '721', '722', '465', '466']
            if source_id in audio_chs:
                quality = '128'
            
            pre = ''
            if len(ModelSetting.get('seezn_cookie')) < 1:
                logger.debug('no cookie')
                pre = 'pre'

            live_url = f'https://api.seezntv.com/svc/menu/app6/api/epg_{pre}play?ch_no={source_id}&bit_rate=S&bit_rate_option={quality}&protocol=https&istest=0'
            
            header = {'x-omas-response-cookie': ModelSetting.get('seezn_cookie')}
            ch_info = requests.get(live_url, headers=header).json()
            if ch_info['meta']['code'] == '200':
                url = ch_info['data']['live_url']
            else:
                logger.debug(ch_info['meta'])
                pass
                # live_url = ''

            if mode == 'web_play':
                return 'return_after_read', url
            return 'redirect', url

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @classmethod
    def get_return_data(cls, source_id, url, mode):
        try:
            req_data = requests.get(url, verify=False, allow_redirects=False)
            if req_data.status_code != 200:
                redirect_url = req_data.headers['location']
                data1 = requests.get(redirect_url, verify=False).text
                data1 = re.sub('\w+.m3u8', redirect_url.split('.m3u8')[0]+'.m3u8', data1)
                if mode == 'web_play':
                    data1 = cls.change_redirect_data(data1)
                return data1
            else:
                data1 = req_data.text
                url2 = re.sub('\w+.m3u8', url.split('playlist.m3u8')[0]+'chunklist.m3u8', data1[data1.find('chunklist'):])
                data2 = requests.get(url2).text
                data3 = re.sub('media-', url2.split('chunklist.m3u8')[0]+'media-', data2)
                if mode == 'web_play':
                    data1 = cls.change_redirect_data(data3)
                return data3
            # logger.debug(url)
            return url
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return req_data.text