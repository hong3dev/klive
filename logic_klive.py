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
from collections import OrderedDict

# third-party
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_
from sqlalchemy.orm.attributes import flag_modified

# sjva 공용
from framework import app, db, scheduler, path_app_root, py_unicode
from framework.job import Job
from framework.util import Util

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelChannel, ModelCustom
from .source_wavve import SourceWavve
from .source_tving import SourceTving
from .source_videoportal import SourceVideoportal
from .source_everyon import SourceEveryon
from .source_streamlink import SourceStreamlink
from .source_youtubedl import SourceYoutubedl
from .source_navertv import SourceNavertv
from .source_kakaotv import SourceKakaotv
from .source_fix_url import SourceFixURL
from .source_kbs import SourceKBS
from .source_sbs import SourceSBS
from .source_mbc import SourceMBC


M3U_FORMAT = '#EXTINF:-1 tvg-id=\"%s\" tvg-name=\"%s\" tvg-logo=\"%s\" group-title=\"%s\" tvg-chno=\"%s\" tvh-chnum=\"%s\",%s\n%s\n' 
M3U_RADIO_FORMAT = '#EXTINF:-1 tvg-id=\"%s\" tvg-name=\"%s\" tvg-logo=\"%s\" group-title=\"%s\" radio=\"true\" tvg-chno=\"%s\" tvh-chnum=\"%s\",%s\n%s\n'


#########################################################

class LogicKlive(object):
    source_list = None
    channel_list = None

    @staticmethod
    def channel_list2(req):
        try:
            from_site = False
            if 'from_site' in req.form:
                from_site = (req.form['from_site']  == 'true')
            ret = LogicKlive.get_channel_list(from_site=from_site)
            logger.debug('channel_list :%s', len(ret))
            return [x.as_dict() for x in ret]
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def channel_load_from_site():
        try:
            LogicKlive.source_list = OrderedDict()
            if ModelSetting.get_bool('use_wavve'):
                LogicKlive.source_list['wavve'] = SourceWavve('wavve', ModelSetting.get('wavve_id'), ModelSetting.get('wavve_pw'), None)
            if ModelSetting.get_bool('use_tving'):
                LogicKlive.source_list['tving'] = SourceTving('tving', ModelSetting.get('tving_id'), ModelSetting.get('tving_pw'), '0')
            if ModelSetting.get_bool('use_videoportal'):
                LogicKlive.source_list['videoportal'] = SourceVideoportal('videoportal', None, None, None)
            #if ModelSetting.get_bool('use_everyon'):
            #    LogicKlive.source_list['everyon'] = SourceEveryon('everyon', None, None, None)
            if ModelSetting.get_bool('use_kbs'):
                LogicKlive.source_list['kbs'] = SourceKBS('kbs', None, None, None)
            if ModelSetting.get_bool('use_sbs'):
                LogicKlive.source_list['sbs'] = SourceSBS('sbs', None, None, None)
            if ModelSetting.get_bool('use_mbc'):
                LogicKlive.source_list['mbc'] = SourceMBC('mbc', None, None, None)
            if ModelSetting.get_bool('use_youtubedl'):
                LogicKlive.source_list['youtubedl'] = SourceYoutubedl('youtubedl', None, None, None)
            if ModelSetting.get_bool('use_streamlink'):
                LogicKlive.source_list['streamlink'] = SourceStreamlink('streamlink', None, None, None)
            if ModelSetting.get_bool('use_navertv'):
                LogicKlive.source_list['navertv'] = SourceNavertv('navertv', None, None, None)
            if ModelSetting.get_bool('use_kakaotv'):
                LogicKlive.source_list['kakaotv'] = SourceKakaotv('kakaotv', None, None, None)
            if ModelSetting.get_bool('use_fix_url'):
                LogicKlive.source_list['fix_url'] = SourceFixURL('fix_url', None, None, None)
            

            LogicKlive.channel_list = []
            for key, source in LogicKlive.source_list.items():
                for i in range(3):
                    tmp = source.get_channel_list()
                    if len(tmp) != 0:
                        break
                    time.sleep(3)
                logger.debug('%s : %s', key, len(tmp))
                for t in tmp:
                    if t.current is not None:
                        t.current = t.current.replace('<', '&lt;').replace('>', '&gt;')
                    LogicKlive.channel_list.append(t)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            
    @staticmethod
    def get_channel_list(from_site=False):
        logger.debug('get_channel_list :%s', from_site)
        try:
            if LogicKlive.channel_list is None or from_site:
                LogicKlive.channel_load_from_site()
            return LogicKlive.channel_list
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())   


    @staticmethod
    def custom():
        try:
            # 전체 EPG 목록 채널
            import epg
            total_channel_list = epg.ModelEpgMakerChannel.get_channel_list()
            logger.debug("custom epg channel list : %s", len(total_channel_list))
            tmp = []
            setting_list = db.session.query(ModelSetting).all()
            arg = Util.db_list_to_dict(setting_list)
            for x in total_channel_list:
                #if (arg['use_wavve'] == 'True' and x.wavve_id is not None) or (arg['use_tving'] == 'True' and x.tving_id is not None) or (arg['use_videoportal'] == 'True' and x.videoportal_id is not None) or (arg['use_everyon'] == 'True' and x.everyon_id is not None):
                if (arg['use_wavve'] == 'True' and x.wavve_id is not None) or (arg['use_tving'] == 'True' and x.tving_id is not None) or (arg['use_videoportal'] == 'True' and x.videoportal_id is not None) or (arg['use_everyon'] == 'True' and x.everyon_id is not None):
                    tmp.append(x)
            
            # 이 목록에 없는 방송은 넣는다.. 스포츠, 라디오?
            # 자동설정
            tmp2 = [x.as_dict() for x in tmp]

            append_list = []
            index = 9000
            for ch in LogicKlive.channel_list:
                find = False
                for t in tmp2:
                    #logger.debug(t)
                    try:
                        if (ch.source == 'wavve' and ch.source_id == t['wavve_id']) or (ch.source == 'tving' and ch.source_id == t['tving_id']) or (ch.source == 'videoportal' and ch.source_id == t['videoportal_id']) or (ch.source == 'everyon' and ch.source_id == t['everyon_id']):
                            find = True
                            break
                    except:
                        logger.debug(t)
                if find == False:
                    #logger.debug('%s %s' % (ch.source, ch.title))
                    entity = {}
                    index += 1
                    entity['id'] = str(index)
                    entity['name'] = ch.title
                    entity['wavve_name'] = entity['wavve_id'] = entity['wavve_number'] = None
                    entity['tving_name'] = entity['tving_id'] = entity['tving_number'] = None
                    entity['videoportal_name'] = entity['videoportal_id'] = entity['videoportal_number'] = None
                    entity['everyon_name'] = entity['everyon_id'] = entity['everyon_number'] = None

                    if ch.source in ['wavve', 'tving', 'videoportal']:#, 'everyon']:
                        entity['%s_id' % ch.source] = ch.source_id
                        entity['%s_name' % ch.source] = ch.title
                        entity['category'] = ch.source
                    if ch.source in ['youtubedl', 'streamlink', 'navertv', 'kakaotv', 'fix_url', 'kbs', 'sbs', 'mbc']:
                        entity['user_source'] = ch.source
                        entity['user_source_id'] = ch.source_id
                        entity['user_source_name'] = ch.title
                        entity['auto'] = 'user_source'
                        entity['category'] = ch.source
                    append_list.append(entity)
            logger.debug(u'추가 갯수:%s', len(append_list))
            logger.debug(u'EPG:%s', len(tmp2))
            tmp2 = tmp2 + append_list
            logger.debug(u'TOTAL:%s', len(tmp2))
            #return total_channel_list
            #tmp2 = [x.as_dict() for x in tmp]


            #logger.debug(tmp2)
            for x in tmp2:
                if arg['use_wavve'] == 'True' and x['wavve_id'] is not None:
                    x['auto'] = 'wavve'
                elif arg['use_tving'] == 'True' and x['tving_id'] is not None:
                    x['auto'] = 'tving'
                elif arg['use_videoportal'] == 'True' and x['videoportal_id'] is not None:
                    x['auto'] = 'videoportal'
                #elif arg['use_everyon'] == 'True' and x['everyon_id'] is not None:
                #    x['auto'] = 'everyon'

                if x['wavve_id'] is not None:
                    entity = db.session.query(ModelCustom).filter(ModelCustom.source == 'wavve').filter(ModelCustom.source_id == x['wavve_id']).first()
                    if entity is not None:
                        x['wavve_number'] = entity.number
                if x['tving_id'] is not None:
                    entity = db.session.query(ModelCustom).filter(ModelCustom.source == 'tving').filter(ModelCustom.source_id == x['tving_id']).first()
                    if entity is not None:
                        x['tving_number'] = entity.number
                if x['videoportal_id'] is not None:
                    entity = db.session.query(ModelCustom).filter(ModelCustom.source == 'videoportal').filter(ModelCustom.source_id == x['videoportal_id']).first()
                    if entity is not None:
                        x['videoportal_number'] = entity.number
                #if x['everyon_id'] is not None:
                #    entity = db.session.query(ModelCustom).filter(ModelCustom.source == 'everyon').filter(ModelCustom.source_id == x['everyon_id']).first()
                #    if entity is not None:
                #        x['everyon_number'] = entity.number
                if 'user_source' in x:
                    entity = db.session.query(ModelCustom).filter(ModelCustom.source == x['user_source']).filter(ModelCustom.source_id == x['user_source_id']).first()
                    if entity is not None:
                        x['user_source_number'] = entity.number
            return tmp2
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def get_url(source, source_id, quality, mode):
        try:
            from .logic import Logic
            if LogicKlive.source_list is None:
                LogicKlive.channel_load_from_site()
            if quality is None or quality == 'default':
                if source == 'wavve':
                    quality = ModelSetting.get('wavve_quality')
                elif source == 'tving':
                    quality = ModelSetting.get('tving_quality')
            return LogicKlive.source_list[source].get_url(source_id, quality, mode)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def get_return_data(source, source_id, url, mode):
        try:
            logger.debug(source)
            logger.debug(source_id)
            logger.debug(url)
            logger.debug(mode)

            #for ins in LogicKlive.source_list:
            #    if ins.
            return LogicKlive.source_list[source].get_return_data(source_id, url, mode)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_m3uall():
        try:
            from system.model import ModelSetting as SystemModelSetting
            apikey = None
            if SystemModelSetting.get_bool('auth_use_apikey'):
                apikey = SystemModelSetting.get('auth_apikey')
            m3u = '#EXTM3U\n'
            idx = 1
            for c in LogicKlive.get_channel_list():
                url = '{ddns}/{package_name}/api/url.m3u8?m=url&s={source}&i={source_id}'.format(ddns=SystemModelSetting.get('ddns'), package_name=package_name, source=c.source, source_id=c.source_id)
                if apikey is not None:
                    url += '&apikey=%s' % apikey
                if c.is_tv:
                    m3u += M3U_FORMAT % (c.source+'|' + c.source_id, c.title, c.icon, c.source, idx, idx, c.source + ' ' + c.title, url)
                else:
                    m3u += M3U_RADIO_FORMAT % (c.source+'|'+c.source_id, c.title, c.icon, c.source, idx, idx, c.source + ' ' + c.title, url)
                idx += 1
            return m3u
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod 
    def custom_save(req):
        try:
            ret = {}
            db.session.query(ModelCustom).delete()
            count = 0
            for key, value in req.form.items():
                #logger.debug('Key:%s Value:%s %s', key, value, [key])
                if value == "True":
                    mc = ModelCustom()
                    #mc.epg_id, mc.source, mc.source_id, mc.title, number = key.split('|')
                    mc.epg_id, mc.epg_name, mc.group, mc.source, mc.source_id, mc.title, number = key.split('|')
                    mc.epg_name = u'%s' % mc.epg_name
                    mc.title = u'%s' % mc.title
                    mc.group = u'%s' % mc.group
                    if number == 'undefined' or number == 'null':
                        mc.number = 0
                    else:
                        mc.number = int(number)
                    db.session.add(mc)
                    count += 1
            LogicKlive.reset_epg_time()
            db.session.commit()
            ret['ret'] = 'success'
            ret['data'] = count
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret['ret'] = 'exception'
            ret['data'] = str(e)
        return ret

    @staticmethod 
    def get_saved_custom():
        try:
            saved_channeld_list = LogicKlive.get_saved_custom_instance()
            tmp = [x.as_dict() for x in saved_channeld_list]
            return tmp
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod 
    def get_saved_custom_instance():
        try:
            #ret = {}
            query = db.session.query(ModelCustom)
            query = query.order_by(ModelCustom.number)
            query = query.order_by(ModelCustom.epg_id)
            saved_channeld_list = query.all()
            return saved_channeld_list
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod 
    def custom_edit_save(req):
        try:
            count = 0
            for key, value in req.form.items():
                #logger.debug('%s %s', key, value)
                tmp = key.split('|')
                mc = db.session.query(ModelCustom).filter(ModelCustom.source == tmp[0]).filter(ModelCustom.source_id == tmp[1]).with_for_update().first()
                if mc is not None:
                    if tmp[2] == 'quality':
                        mc.quality = value
                    elif tmp[2] == 'number':
                        mc.number = int(value)
                    elif tmp[2] == 'group':
                        mc.group = u'%s' % value
            db.session.commit()            
            LogicKlive.reset_epg_time()
            return LogicKlive.get_saved_custom()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def reset_epg_time():
        try:
            import epg
            epg.LogicNormal.make_xml(package_name)
        except Exception as e: 
            #logger.error('Exception:%s', e)
            #logger.error(traceback.format_exc())
            logger.debug('NOT IMPORT EPG!!!')


    @staticmethod 
    def custom_delete(req):
        try:
            ret = {}
            count = 0
            key = req.form['id']
            tmp = key.split('|')
            db.session.query(ModelCustom).filter(ModelCustom.source == tmp[0]).filter(ModelCustom.source_id == tmp[1]).delete()
            db.session.commit()
            return LogicKlive.get_saved_custom()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_m3u(for_tvh=False, m3u_format=None, group=None):
        try:
            #logger.debug(m3u_format)
            from system.model import ModelSetting as SystemModelSetting
            apikey = None
            if SystemModelSetting.get_bool('auth_use_apikey'):
                apikey = SystemModelSetting.get('auth_apikey')
            ddns = SystemModelSetting.get('ddns')
            m3u = '#EXTM3U\n'
            query = db.session.query(ModelCustom)
            query = query.order_by(ModelCustom.number)
            query = query.order_by(ModelCustom.epg_id)
            saved_channeld_list = query.all()
            
            for c in saved_channeld_list:
                url = '%s/%s/api/url.m3u8?m=url&s=%s&i=%s&q=%s' % (ddns, package_name, c.source, c.source_id, c.quality)
                if apikey is not None:
                    url += '&apikey=%s' % apikey
                #if c.epg_entity.is_tv:
                if for_tvh:
                    #pipe:///usr/bin/ffmpeg -loglevel fatal -i [RTSP주소] -vcodec copy -acodec copy -metadata service_provider=xxx -metadata service_name=yyy -f mpegts -tune zerolatency pipe:1
                    #url = 'pipe://%s -i "%s" -c copy -metadata service_provider=sjva_klive -metadata service_name="%s" -f mpegts -tune zerolatency pipe:1' % ('ffmpeg', url, c.title)
                    url = 'pipe://%s -i "%s" -c copy -metadata service_provider=sjva_klive -metadata service_name="%s" -c:v copy -c:a aac -b:a 128k -f mpegts -tune zerolatency pipe:1' % ('ffmpeg', url, c.title)

                #m3u += M3U_FORMAT % (c.source+'|' + c.source_id, c.title, c.epg_entity.icon, c.source, c.source + ' ' + c.title, url)

                import epg
                ins = epg.ModelEpgMakerChannel.get_instance_by_name(c.epg_name)
                #m3u += M3U_FORMAT % (c.source+'|' + c.source_id, c.title, c.epg_entity.icon, c.source, c.title, url)
                icon = '' if ins is None else ins.icon
                if icon is None:
                    icon = c.icon
                #if c.is_tv:
                #    #m3u += M3U_FORMAT % (c.source+'|' + c.source_id, c.title, c.icon, c.group, idx, idx, c.source + ' ' + c.title, url)
                #    m3u += M3U_FORMAT % (c.source+'|' + c.source_id, c.title, c.icon, c.group, c.number, c.number, c.title, url)
                #else:
                #    m3u += M3U_RADIO_FORMAT % (c.source+'|'+c.source_id, c.title, c.icon, c.group, idx, idx, c.source + ' ' + c.title, url)
                #logger.debug(c.group)
                tvg_name = c.title
                if m3u_format == '1':
                    tvg_name = '%s. %s' % (str(c.number).zfill(3), c.title)
                group_name = c.group
                if group is not None:
                    group_name = '' if group == 'EMPTY' else group
                m3u += M3U_FORMAT % (c.source+'|' + c.source_id, tvg_name, icon, group_name, c.number, c.number, c.title, url)


                
                
            return m3u
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())