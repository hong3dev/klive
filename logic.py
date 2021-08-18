# -*- coding: utf-8 -*-
#########################################################
# python
import os
import datetime
import traceback
import logging
import subprocess
import time
import re
import json
import requests
import urllib
import lxml.html
import threading
from enum import Enum

# third-party
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_
from time import sleep

# sjva 공용
from framework.logger import get_logger
from framework import app, db, scheduler, path_app_root
from framework.job import Job
from framework.util import Util
from system.logic import SystemLogic

# 패키지
from .model import ModelSetting, ModelChannel
from .logic_klive import LogicKlive

# 로그
package_name = __name__.split('.')[0]
logger = get_logger(package_name)

#########################################################

class Logic(object):
    db_default = {
        'db_version' : '3',
        'use_wavve' : 'True',
        'wavve_quality' : 'HD',
        'wavve_streaming_type' : '1',
        'wavve_vod_page' : '5',

        'use_tving' : 'False',
        'tving_quality' : 'HD',
        'tving_vod_page' : '5',
        'tving_include_drm' : 'False',

        'show_seezn': 'False',
        'use_seezn' : 'False',
        'seezn_quality' : 'FHD',
        'seezn_include_drm': 'False',
        'seezn_cookie': '',
        'seezn_adult': 'False',
        'seezn_use_proxy': 'False',
        'seezn_proxy_url': '',

        'use_videoportal' : 'True',

        'use_everyon' : 'True',

        'use_youtubedl' : 'False',
        'youtubedl_use_proxy' : 'False',
        'youtubedl_proxy_url' : '',
        'youtubedl_list' : u'1|한국프로야구1|https://twitch.tv/kbo1\n2|한국프로야구2|https://twitch.tv/kbo2\n3|한국프로야구3|https://twitch.tv/kbo3\n4|한국프로야구4|https://twitch.tv/kbo4\n5|한국프로야구5|https://twitch.tv/kbo5\n6|유투브 1|YOUTUBE_1\n7|유투브 2|YOUTUBE_2\n8|유투브 3|YOUTUBE_3\n9|유투브 11|YOUTUBE_11\n10|유투브 100|YOUTUBE_100\n11|YTN|https://youtube.com/watch?v=U_sYIKWhJvk\n12|연합뉴스TV|https://www.youtube.com/watch?v=oul5ldEUbHk\n13|THE K-POP|https://youtube.com/watch?v=0Cs_o3daYR8\n14|장군의 아들|https://youtube.com/watch?v=EidX2DPPSBw\n',

        'use_streamlink' : 'False',
        'streamlink_quality' : 'best',
        'streamlink' : 'False',
        'streamlink_list' : u'1|한국프로야구1|https://twitch.tv/kbo1\n2|한국프로야구2|https://twitch.tv/kbo2\n3|한국프로야구3|https://twitch.tv/kbo3\n4|한국프로야구4|https://twitch.tv/kbo4\n5|한국프로야구5|https://twitch.tv/kbo5\n6|2010년 히트곡|https://dailymotion.com/video/x77q22e',

        'use_navertv' : 'False',
        'navertv_list' : u'1|스포츠 야구1|SPORTS_ad1|1080\n2|스포츠 야구2|SPORTS_ad2|1080\n3|스포츠 야구3|SPORTS_ad3|1080\n4|스포츠 야구4|SPORTS_ad4|1080\n5|스포츠 야구5|SPORTS_ad5|1080\n6|스포츠 Spocado|SPORTS_ch7|1080\n7|스포츠 sbsgolf|SPORTS_ch15|1080\n11|연합뉴스TV|https://tv.naver.com/l/44267\n12|TBS|https://tv.naver.com/l/43164|720\n',

        'use_kakaotv' : 'False',
        'kakaotv_list' : u'1|KBS24|https://tv.kakao.com/channel/3193314/livelink/7742194\n2|추억의 90년대 가요|https://tv.kakao.com/channel/3112354/livelink/7836404',

        'use_fix_url' : 'False',
        'fix_url_list' : u'1|TBS FM|http://tbs.hscdn.com/tbsradio/fm/playlist.m3u8|N\n2|TBS eFM|http://tbs.hscdn.com/tbsradio/efm/playlist.m3u8|N\n3|CBS 음악FM|http://aac.cbs.co.kr/cbs939/_definst_/cbs939.stream/playlist.m3u8|N\n4|CBS 표준FM|http://aac.cbs.co.kr/cbs981/_definst_/cbs981.stream/playlist.m3u8|N\n5|EBS FM|http://58.229.187.43/fmradiobandiaod/bandiappaac/playlist.m3u8|N\n6|EBS foreign|http://110.10.122.10/iradio/iradiolive_m4a/playlist.m3u8|N\n7|국방TV|http://mediaworks.dema.mil.kr:1935/live_edge/cudo.sdp/playlist.m3u8|Y',

        'use_kbs' : 'False',
        'use_mbc' : 'False',
        'use_sbs' : 'False',

    }

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
            Logic.migration()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        
    @staticmethod
    def plugin_load():
        try:
            Logic.db_init()
            from .plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))   

            def func():
                LogicKlive.channel_load_from_site()
            t = threading.Thread(target=func, args=())
            t.setDaemon(True)
            t.start()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def plugin_unload():
        try:
            pass
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    

    @staticmethod
    def migration():
        try:
            if ModelSetting.get('db_version') == '1':
                import sqlite3
                db_file = os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name)
                connection = sqlite3.connect(db_file)
                cursor = connection.cursor()
                query = 'ALTER TABLE %s_channel ADD is_drm_channel INT' % (package_name)
                cursor.execute(query)
                connection.close()
                ModelSetting.set('db_version', '2')
                db.session.flush()
            if ModelSetting.get('db_version') == '2':
                import sqlite3
                db_file = os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name)
                connection = sqlite3.connect(db_file)
                cursor = connection.cursor()
                query = 'ALTER TABLE %s_custom ADD is_drm_channel INT' % (package_name)
                cursor.execute(query)
                connection.close()
                ModelSetting.set('db_version', '3')
                db.session.flush()
            #db_version = ModelSetting.get('db_version')
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
