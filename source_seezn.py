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
                'Host': 'api.seezntv.com',
                'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
                'sec-ch-ua-mobile': '?0',
                'HTTP_CLIENT_IP': 'undefined',
                'X-APP-VERSION': '92.0.4515.131',
                'X-OS-VERSION': 'NT 10.0',
                'X-OS-TYPE': 'Windows',
                'X-DEVICE-MODEL': 'Chrome',
                'Accept': 'application/json',
                'Access-Control-Allow-Headers': 'Authentication',
                'Origin': 'https://www.seezntv.com',
                'Sec-Fetch-Site': 'same-site',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty',
                'Referer': 'https://www.seezntv.com/'
            }

    default_header2 = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
                'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
                'sec-ch-ua-mobile': '?0',
                'Accept': '*/*',
                'Origin': 'https://www.seezntv.com',
                'Sec-Fetch-Site': 'same-site',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty',
                'Referer': 'https://www.seezntv.com/'
            }

    ch_quality = dict()

    
    @classmethod
    def prepare(cls, source_id, source_pw, arg):
        pass


    @classmethod
    def get_channel_list(cls):
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]
            header = cls.default_header
            header['timestamp'] = timestamp
            header['transactionid'] = timestamp+'000000000000001'
            # logger.debug(header)
            ret = []
            data = requests.get('https://api.seezntv.com/svc/menu/app6/api/epg_chlist?category_id=1', headers=header).json()
            for item in data['data']['list'][0]['list_channel']:
                # 성인 채널 여부
                if item['adult_yn'] == 'Y' and ModelSetting.get('seezn_adult') == 'False':
                    continue
                # bitrate_info
                cls.ch_quality[item['ch_no']] = item['bit_rate_info'].split(',')

                c = ModelChannel(cls.source_name, item['ch_no'], item['service_ch_name'], item['ch_image_list'], (item['type']!='AUDIO_MUSIC'))
                # DRM 채널 여부
                if item['cj_drm_yn'] == 'Y':
                    c.is_drm_channel = True
                    if ModelSetting.get('seezn_include_drm') == 'False':
                        continue

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
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]
            header = cls.default_header
            header['timestamp'] = timestamp
            header['transactionid'] = timestamp+'000000000000001'
            
            q = {'FHD': '4000', 'HD': '2000', 'SD': '1000'}
            # 일부 홈쇼핑 채널은 최대 2000이라고 리턴하지만 실제 4000도 재생됨
            # quality = f'{q[quality]}' if q[quality] in cls.ch_quality[source_id] else f'{cls.ch_quality[source_id][0]}'
            quality = f'{q[quality]}' if len(cls.ch_quality[source_id]) != 1 else f'{cls.ch_quality[source_id][0]}'
            
            # 로그인 정보 없을시 epg_prepaly로, 3~4분 가량 재생됨
            pre = ''
            if len(ModelSetting.get('seezn_cookie')) < 1:
                logger.debug('no valid cookie')
                pre = 'pre'
            else:
                header['x-omas-response-cookie'] = ModelSetting.get('seezn_cookie')

            live_url = f'https://api.seezntv.com/svc/menu/app6/api/epg_{pre}play?ch_no={source_id}&bit_rate=S&bit_rate_option={quality}&protocol=https&istest=0'
            # logger.debug(header)
            logger.debug(live_url)

            # 시즌 프록시
            # 재생 주소 가져올 때만 사용
            if ModelSetting.get('seezn_use_proxy') == 'True':
                proxies = {'http': ModelSetting.get('seezn_proxy_url'), 'https': ModelSetting.get('seezn_proxy_url')}
            else:
                proxies = None
            
            ch_info = requests.get(live_url, headers=header, proxies=proxies).json()
            logger.debug(ch_info)
            if ch_info['meta']['code'] == '200':
                logger.debug('재생 권한 가능')
                
                if ch_info['data']['drm_token'] != "":
                    return cls.get_drm_data(ch_info)
                url = ch_info['data']['live_url']
            else:

                logger.debug('재생권한 없음, 해외 IP 등등')

                # 재생권한 없음, 해외 IP 등등
                raise Exception(ch_info['meta'])

            if mode == 'web_play':
                return 'return_after_read', url
            
            # 해외 서버, 해외 클라이언트에서도 url만 가져오면 redirect로 재생 가능 확인
            return 'redirect', url

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @classmethod
    def get_return_data(cls, source_id, url, mode):
        try:
            header = cls.default_header2
            header['Sec-Fetch-Site'] = 'cross-site'

            req_data = requests.get(url, verify=False, allow_redirects=False, headers=header)
            # logger.debug(req_data.status_code)
            if req_data.status_code == 301: # 시즌 제공 채널
                redirect_url = req_data.headers['location']
                data = requests.get(redirect_url, verify=False, headers=header).text
                data1 = re.sub('\w+.m3u8', redirect_url.split('.m3u8')[0]+'.m3u8', data)
                
                return data1

            elif req_data.status_code == 302: # 홈쇼핑 및 기타
                header['Sec-Fetch-Site'] = 'same-site'
                redirect_url = req_data.headers['location']
                data = requests.get(redirect_url, headers=header).text
                data1 = re.sub('segments', redirect_url.split('live')[0]+'live/segments', data)

                return data1

            elif req_data.status_code == 200: # CJ 제공 채널
                data1 = req_data.text
                url2 = re.sub('\w+.m3u8', url.split('playlist.m3u8')[0]+'chunklist.m3u8', data1[data1.find('chunklist'):])
                data2 = requests.get(url2, headers=header).text
                data3 = re.sub('media-', url2.split('chunklist.m3u8')[0]+'media-', data2)

                return data3

            logger.debug(url)
            return url

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

        return req_data.text


    def get_drm_data(ch_info):
        try:
            data = dict()
            ret = {}
            ret['uri'] = ch_info['data']['live_url']+'manifest.mpd'
            ret['drm_scheme'] = 'widevine'
            ret['drm_license_uri'] = 'https://otm.drmkeyserver.com/widevine_license'
            ret['drm_key_request_properties'] = {
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
                'origin': 'https://www.seezntv.com',
                'referer': 'https://www.seezntv.com/',
                'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
                'sec-ch-ua-mobile': '?0',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'AcquireLicenseAssertion' : ch_info['data']['drm_token'],
                }

            data['play_info'] = ret
            # logger.debug(data)
            return data


        except Exception as exception:
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())