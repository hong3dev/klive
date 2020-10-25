# -*- coding: utf-8 -*-
#########################################################
# python
import os
import sys
import logging
import traceback
import json
from datetime import datetime, timedelta
# third-party
import requests
from flask import redirect

# sjva 공용
from framework import app, db, scheduler, path_app_root, path_data

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelChannel
from .source_base import SourceBase
import framework.tving.api as Tving

#########################################################


class SourceTving(SourceBase):
    @classmethod
    def prepare(cls, source_id, source_pw, arg):
        cls.login_data = None
        if source_id != '' and source_pw != '':
            cls.login_data = Tving.do_login(source_id, source_pw, '0')
       
    @classmethod
    def get_channel_list(cls):
        try:
            data = Tving.get_live_list(list_type='both')
            ret = []
            for item in data:
                if item['free']:
                    if item['title'].startswith('CH.'):
                        continue
                    #C04601 : 채널CGV, ocn, super action, ytn life, ocn                        
                    if item['id'] in ['C04601', 'C07381', 'C07382', 'C01101']:
                        continue
                    c = ModelChannel(cls.source_name, item['id'], item['title'], item['img'], True)
                    c.current = item['episode_title']
                    ret.append(c)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return ret

    @classmethod
    def get_url(cls, source_id, quality, mode):
        #logger.debug('tving get_url:%s %s %s', source_id, quality, cls.login_data)
        try:
            quality = Tving.get_quality_to_tving(quality)
            c_id = source_id
            if source_id.startswith('V'):
                c_id = source_id[1:]
            proxy = None
            if ModelSetting.get_bool('tving_use_proxy'):
                proxy = ModelSetting.get('tving_proxy_url')
            data, url = Tving.get_episode_json(c_id, quality, cls.login_data, proxy=proxy, is_live=True)

            if source_id.startswith('V'):
                return 'redirect', url
            else:
                return 'return_after_read', url
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        

    @classmethod
    def get_return_data(cls, source_id, url, mode):
        try:

            data = requests.get(url).text
            #logger.debug(data)
            temp = url.split('playlist.m3u8')
            rate = ['chunklist_b5128000.m3u8', 'chunklist_b1628000.m3u8', 'chunklist_b1228000.m3u8', 'chunklist_b1128000.m3u8', 'chunklist_b628000.m3u8', 'chunklist_b378000.m3u8']
            for r in rate:
                if data.find(r) != -1:
                    url1 = '%s%s%s' % (temp[0], r, temp[1])
                    data1 = requests.get(url1).text
                    data1 = data1.replace('media', '%smedia' % temp[0]).replace('.ts', '.ts%s' % temp[1])
                    #logger.debug(data1)
                    if mode == 'web_play':
                        data1 = cls.change_redirect_data(data1)
                    return data1
            #logger.debug(url)
            return url
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return url




    @classmethod
    def make_vod_m3u(cls):
        try:
            from lxml import etree as ET
            from system.model import ModelSetting as SystemModelSetting

            data = "#EXTM3U\n"
            root = ET.Element('tv')
            root.set('generator-info-name', "wavve")
            form = '#EXTINF:-1 tvg-id="{contentid}" tvg-name="{title}" tvh-chno="{channel_number}" tvg-logo="{logo}" group-title="티빙 최신 VOD",{title}\n{url}\n'
            ch_number = 1
            for page in range(1, ModelSetting.get_int('tving_vod_page')+1):
                vod_list = Tving.get_vod_list(page=page)["body"]["result"]
                for vod in vod_list:
                    #logger.debug(vod)
                    code = vod["vod_code"]
                    title = vod['vod_name']['ko']
                    try: logo = 'http://image.tving.com%s' % (vod['program']['image'][0]['url'])
                    except: logo = ''
                    video_url = '%s/%s/tving/api/streaming.m3u8?contentid=%s' % (SystemModelSetting.get('ddns'), package_name, code)    
                    if SystemModelSetting.get_bool('auth_use_apikey'):
                        video_url += '&apikey=%s' % SystemModelSetting.get('auth_apikey')
                    data += form.format(contentid=code, title=title, channel_number=ch_number, logo=logo, url=video_url)

                    channel_tag = ET.SubElement(root, 'channel') 
                    channel_tag.set('id', code)
                    #channel_tag.set('repeat-programs', 'true')

                    display_name_tag = ET.SubElement(channel_tag, 'display-name') 
                    display_name_tag.text = '%s(%s)' % (title, ch_number)
                    display_name_tag = ET.SubElement(channel_tag, 'display-number') 
                    display_name_tag.text = str(ch_number)

                    duration = vod['episode']['duration']
                    datetime_start = datetime.now()
                    for i in range(3):
                        datetime_stop = datetime_start + timedelta(seconds=duration+1)
                        program_tag = ET.SubElement(root, 'programme')
                        program_tag.set('start', datetime_start.strftime('%Y%m%d%H%M%S') + ' +0900')
                        program_tag.set('stop', datetime_stop.strftime('%Y%m%d%H%M%S') + ' +0900')
                        program_tag.set('channel', code)
                        datetime_start = datetime_stop

                        #program_tag.set('video-src', video_url)
                        #program_tag.set('video-type', 'HTTP_PROGRESSIVE')
                        
                        title_tag = ET.SubElement(program_tag, 'title')
                        title_tag.set('lang', 'ko')
                        title_tag.text = title

                        
                        icon_tag = ET.SubElement(program_tag, 'icon')
                        icon_tag.set('src', logo)
                        if 'synopsis' in vod['episode']:
                            desc_tag = ET.SubElement(program_tag, 'desc')
                            desc_tag.set('lang', 'ko')
                            desc_tag.text = vod['episode']['synopsis']['ko']
                    channel_tag = None
                    program_tag = None



                    ch_number += 1

            tree = ET.ElementTree(root)
            ret = ET.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8")
            return data, ret
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())  


    @classmethod
    def streaming(cls, req):
        try:
            c_id = req.args.get('contentid')
            quality = Tving.get_quality_to_tving(ModelSetting.get('tving_quality'))
            proxy = None
            if ModelSetting.get_bool('tving_use_proxy'):
                proxy = ModelSetting.get('tving_proxy_url')

            #data, url = Tving.get_episode_json(c_id, quality, cls.login_data, proxy=proxy, is_live=True)
            # 이건 vod
            data, url = Tving.get_episode_json(c_id, quality, cls.login_data, proxy=proxy)
            return redirect(url, code=302)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())  
