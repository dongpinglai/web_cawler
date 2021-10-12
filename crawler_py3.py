#!/usr/bin/env python3
# coding: utf-8
import re
from seleniumwire import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedTagNameException
import socket
from contextlib import closing
import time
import platform
import os
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin
import hashlib
import json
import threading
import pymysql, pymysql.cursors


CHROME_DRIVER_PATH = '/home/uos/chromedriver'


class ChromeBrowser(object):
    def __init__(self, driver_path=CHROME_DRIVER_PATH):
        # 代理服务配置, TODO：代理blacklist：图片加载，加快速度
        # 浏览器设置
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument("--ssl-version-max")
        options.add_experimental_option(
            "excludeSwitches",
            ["ignore-certificate-errors"])
        options.add_argument("--ssl-version-max")
        options.add_argument("--start-maximized")
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--allow-insecure-localhost')
        options.add_argument('--ignore-urlfetcher-cert-requests')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--process-per-site')
        options.add_argument('--disable-images')
        options.add_argument('--single-process')
        # 文件下载放到临时目录
        profile = {"download.default_directory": "/tmp", "download.prompt_for_download": False}
        options.add_experimental_option("prefs", profile)
        # implicitly_wait_seconds = 10
        self.driver = webdriver.Chrome(driver_path, options=options)

    def __getattr__(self, name):
        return getattr(self.driver, name)

    def find_elements_attribute(self, css_selector, attr_name):
        elements = self.find_elements_by_css_selector(css_selector)
        attrs = [ele.get_attribute(attr_name) for ele in elements]
        return attrs

    def get_http_logs(self):
        logs = self.driver.requests
        return logs

    def add_request_interceptor(self, request_interceptor):
        self.driver.request_interceptor = request_interceptor


class MySelect(object):
    def __init__(self, select_webele):
        self._select= Select(select_webele)
        self.option_count = len(self._select.options)
        self._current_index = -1
    
    def __getattr__(self, attr_name):
        return getattr(self._select, attr_name)

    def send_keys(self, index):
        if 0 <= index < self.option_count:
            self._select.select_by_index(index)
            self._current_index = index
        
    def clear(self):
        '''
        多选全部清除，单选恢复默认值：第一个选项
        '''
        if self._select.is_multiple:
            self._select.deselect_all()
        else:
            self._select.select_by_index(0)


class StaticUrlsError(Exception):
    pass


class DynamicUrlsError(Exception):
    pass

def try_times(times):
    def decorate(fn):
        def wrapper(*args, **kwargs):
            for i in range(times):
                try:
                    result = fn(*args, **kwargs)
                    return result
                except Exception as e:
                    print('try_times: %s' % e)
                    continue
        return wrapper
    return decorate

class Radio(object):
    def __init__(self, webelement):
        self._webelement = webelement

    def __getattr__(self, attr_name):
        return getattr(self._webelement, attr_name)

    def send_keys(self, value):
        self._webelement.click()
    
    def clear(self):
        self._webelement.click()


class CheckBox(object):
    def __init__(self, webelement):
        self._webelement = webelement

    def __getattr__(self, attr_name):
        return getattr(self._webelement, attr_name)

    def send_keys(self, value):
        self._webelement.click()
    
    def clear(self):
        self._webelement.click()


class Form(object):
    '''
    '''
    def __init__(self, webelement):
        if webelement.tag_name.lower() != 'form':
            raise UnexpectedTagNameException('form tag only', webelement.tag_name)
        self.webelement = webelement
        self._text_inputs = []
        self._password_inputs = [] 
        self._email_inputs = []
        self._number_inputs = []
        self._checkboxes = []
        self._radios = []
        self._selects = []
        self._textares = []
        self._inputs = []
        self._iterate_count = self.get_iterate_count()

    @property
    def inputs(self):
        if not self._inputs:
            self._inputs = self.webelement.find_elements_by_css_selector('input')
        return self._inputs

    def _get_inputs(self, attr_name, attr_value):
        inputs = self.inputs
        _inputs = []
        for _input in inputs:
            if _input.get_attribute(attr_name) == attr_value:
                _inputs.append(_input)
        return _inputs

    @property 
    def text_inputs(self):
        '''
        注意事项：
            selenium存在某些站点（比如百度）使用css_selector加上type属性无法定位到元素的问题
            故改变写法，下同
        '''
        if not self._text_inputs:
            # self._text_inputs = self.webelement.find_elements_by_css_selector('input[type="text"]')
            self._text_inputs = self._get_inputs('type', 'text')
        return self._text_inputs

    @property
    def password_inputs(self):
        if not self._password_inputs:
            # self._password_inputs = self.webelement.find_elements_by_css_selector('input[type="password"]')
            self._password_inputs = self._get_inputs('type', 'password')
        return self._password_inputs

    @property
    def email_inputs(self):
        if not self._email_inputs:
            # self._email_inputs = self.webelement.find_elements_by_css_selector('input[type="email"]')
            self._email_inputs = self._get_inputs('type', 'email')
        return self._email_inputs
    
    @property
    def number_inputs(self):
        if not self._number_inputs:
            # self._number_inputs = self.webelement.find_elements_by_css_selector('input[type="number"]')
            self._number_inputs = self._get_inputs('type', 'number')
        return self._number_inputs

    @property
    def checkboxes(self):
        if not self._checkboxes:
            # _checkboxes = self.webelement.find_elements_by_css_selector('input[type="checkbox"]')
            _checkboxes = self._get_inputs('type', 'checkbox')
            self._checkboxes = [CheckBox(_checkbox) for _checkbox in _checkboxes]
        return self._checkboxes

    @property
    def radios(self):
        if not self._radios:
            # _radios = self.webelement.find_elements_by_css_selector('input[type="radio"]')
            _radios = self._get_inputs('type', 'radio')
            self._radios = [Radio(_radio) for _radio in _radios]
        return self._radios

    @property
    def selects(self):
        if not self._selects:
            _selects = self.webelement.find_elements_by_css_selector('select')
            self._selects = [MySelect(_select) for _select in _selects]
        return self._selects

    @property    
    def textareas(self):
        if not self._textares:
            self._textares = self.webelement.find_elements_by_css_selector('textarea')
        return self._textares

    def fill_text_value(self, webelements):
        text_value = '13798378765'
        for webelement in webelements:
            webelement.send_keys(text_value)
    
    def fill_password_value(self, webelements):
        password_value =  'L13798378765@qq.com'
        for webelement in webelements:
            webelement.send_keys(password_value)
    
    def fill_number_value(self, webelements):
        number_value = 13798378765 
        for webelement in webelements:
            webelement.send_keys(number_value)

    def fill_email_value(self, webelements):
        email_value = '13798378765@qq.com' 
        for webelement in webelements:
            webelement.send_keys(email_value)

    def fill_select_value(self, webelements):
        for webelement in webelements:
            current_index = webelement._current_index + 1
            webelement.send_keys(current_index)

    def fill_checkbox_value(self, webelements):
        for webelement in webelements:
            current_index = webelement._current_index + 1
            webelement.send_keys(current_index)

    def fill_radio_value(self, webelements):
        for webelement in webelements:
            current_index = webelement._current_index + 1
            webelement.send_keys(current_index)
        
    def fill(self):
        '''
        根据不同元素进行填充操作
        1.select元素，需要分多选/单选情况。多选一次填充选择所有；单选依次切换选择
        2.多选框和单选框，默认选择第一个选项
        3.其他需要输入的元素，填充默认值。
        填充的默认值纯属虚构，如有雷同，纯属意外。
        '''
        for webelements, webelement_type in [
            (self.text_inputs, 'text'),
            (self.password_inputs, 'password'),
            (self.number_inputs, 'number'),
            (self.email_inputs, 'email'),
            (self.checkboxes, 'checkbox'),
            (self.radios, 'radio'),
            (self.selects, 'select')
        ]:
            if webelements:
                getattr(self, '_'.join(['fill', webelement_type, 'value']))(webelements)
        
    def _clear(self, webelements):
        for webelement in webelements:
            webelement.clear()

    def clear(self):
        for webelements in [
            self.text_inputs, 
            self.password_inputs,
            self.email_inputs,
            self.number_inputs,
            self.checkboxes,
            self.radios,
            self.textareas,
            self.selects
        ]:
            self._clear(webelements)
        
    def get_iterate_count(self):
        '''
        根据表单中所有select元素选项组合后有多少种情况，就遍历多少次(组合次数多就有点费时！！！)
        故简单处理：所有select(单选）元素最大选项数
        '''
        iterate_count = 1
        selects = self.selects
        select_options_count = 0
        for _select in selects:
            if _select.is_multiple:
                continue
            s_opt_count =  _select.option_count
            if select_options_count < s_opt_count:
                select_options_count = s_opt_count
        if select_options_count:
            iterate_count = select_options_count
        return iterate_count



class url_not_contains(object):
    def __init__(self, url):
        self.url = url

    def __call__(self, driver):
        return self.url not in driver.current_url


def sequence2str(seq, has_quota=False):
    str_list = ['(']
    for item in seq:
        if has_quota:
            str_list.append('"')
            str_list.append(item)
            str_list.append('"')
        else:
            str_list.append(item)
        str_list.append(',')
    else:
        str_list.pop(-1)
        str_list.append(')')
    return ''.join(str_list)


class DbManage(object):
    def __init__(self, config_type=None):
        self.config = self.get_db_config(config_type)
        self.db_user = self.config['db_user']
        self.db_password = self.config['db_password']
        self.db_host = self.config['db_host']
        self.db_port = int(self.config['db_port']) if self.config['db_port'] else 3306
        self.db_name = self.config['db_name']
        self._connection = None
        self.place_hold = '%s'

    def get_db_config(self, config_type):
        '''
        # 用于测试先硬编码数据库配置
        '''
        db_config = {
            'db_host': '172.16.110.189', 
            'db_port': 33066, 
            'db_user': 'root',
            'db_password':'Qxh28Ct5LJTcuFL7', 
            'db_name':'security',
        }
        return db_config

    def connect(self):
        if self._connection is None:
            self._connection = pymysql.connect(
                host=self.db_host,
                port=self.db_port, 
                user=self.db_user,
                password=self.db_password,
                db=self.db_name,
                cursorclass=pymysql.cursors.DictCursor)
        return self._connection

    def execute(self, sql, args=None):
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, args)
        except Exception as e:
            connection.rollback()
            print('mysql execute (%s, %s) error: %s' % (sql, args, e))
        else:
            connection.commit()
            return cursor

    def executemany(self, sql, args):
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.executemany(sql, args)
        except Exception as e:
            connection.rollback()
            print('mysql executemany (%s, %s)error: %s' % (sql, args, e))
        else:
            connection.commit()
            return cursor
        
    def fetchone(self, sql, args=None):
        cursor = self.execute(sql, args)
        with cursor:
            result = cursor.fetchone()
            return result

    def fetchall(self, sql, args=None):
        cursor = self.execute(sql, args)
        with cursor:
            result = cursor.fetchall()
            return result

    def insert(self, table_name, fields, args=None):
        sql_statement = """
        INSERT INTO %s %s VALUES %s
        """
        place_hold = [self.place_hold] * len(fields)
        sql_statement = sql_statement % (table_name, sequence2str(fields), sequence2str(place_hold))
        cursor = self.execute(sql_statement, args)
        with cursor:
            result = cursor.fetchall()
            return result

    def insertmany(self, table_name, fields, args):
        sql_statement = """
        INSERT INTO %s %s VALUES %s
        """
        place_hold = [self.place_hold] * len(fields)
        sql_statement = sql_statement % (table_name, sequence2str(fields), sequence2str(place_hold))
        cursor = self.executemany(sql_statement, args)
        with cursor:
            result = cursor.fetchall()
            return result

    def insert(self, sql, args):
        with cursor:
            result = cursor.fetchall()
            return result
    
    def close(self):
        if self._connection:
            self._connection.close()
        


class Crawler(object):
    '''
    动态、静态结合查找url
    '''
    def __init__(self, task_id, domain_id, crawl_thread_num=5,
                 max_running_time=60 * 30):
        self.task_id = task_id
        self.domain_id = domain_id
        self.db = DbManage()
        self.task = self.get_task()
        self.cookies = self.task.get('cookies', '')
        self.start_urls = self._start_urls()
        self.pending_urls = set()
        self.complete_urls = set()
        self.pending_complete_urls = set()
        self.next_urls = set()
        self._pending_complete_urls_lock = threading.Lock()
        self._next_urls_lock = threading.Lock()
        self.crawling_url_queue = Queue()
        self.log_entry_queue = Queue()
        self.crawl_thread_num = self.task['thread'] if self.task['thread'] > crawl_thread_num else crawl_thread_num
        self.max_url_count = self.task['max_url_count']
        self.max_running_time = max_running_time
        self.allow_domains = set()
        self._saved_url_lock = threading.Lock()
        self.saved_url_hashes = set()

    def _start_urls(self):
        """Get the start urls of spider"""
        table_name = 'bd_web_domain_%s' % self.task_id
        # select the domain active, i.e. the domain can be request successfully
        sql = "SELECT * FROM `{}` WHERE `id`=%s AND `active`>0".format(table_name)
        # 用于测试
        sql = "SELECT * FROM `{}` WHERE `id`=%s AND `active`>=0".format(table_name)
        domain = self.db.fetchone(sql, (self.domain_id,))
        urls = [domain['domain'].strip()] if domain else []
        # TODO: add login test url if login enable
        if self.task['login_enable']:
            urls.append(self.task['login_test_url'])
        return urls

    def delete_data(self):
        """Delete data of the url table."""
        sql = "TRUNCATE TABLE `bd_web_url_%s`" % self.task_id
        self.db.execute(sql)

    def get_task(self):
        """Get the message of the task from the table: bd_web_task_manage."""
        table_name = 'bd_web_task_manage'
        sql = "SELECT * FROM `%s` WHERE `id`=%s" % (table_name, self.task_id)
        task = self.db.fetchone(sql)
        return task

    @property
    def ignore_suffix(self):
        """The url with ignore_suffix will not be spider."""
        return [
            '.png', '.jpg', '.gif', '.jpeg', '.pdf', '.ico', '.doc', '.docx', '.xsl',
            '.ppt', '.txt', '.zip', '.rar', '.tar', '.tgz', '.bz', '.gz', '.chm',
            '.dll', '.exe', '.mp3', '.rm', '.asf', '.mov', '.ttf', '.rmvb', '.rtf',
            '.ra', '.mp4', '.wma', '.wmv', '.xps', '.mht', '.msi', '.flv', '.xls',
            '.ld2', '.ocx', '.url', '.avi', '.swf', '.db', '.bmp', '.psd', '.iso',
            '.ape', '.cue', '.u32', '.ucd', '.pk', '.lrc', '.m4v', '.nrg', '.cd', '.bmp',
            '.cnn', '.m3u', '.tif', '.mpeg', '.srt', '.chs', '.cab', '.pps',  '.mpg',
            '.wps', '.js', '.css', '.ashx', '.svg'
        ]

    @property
    def block_suffix(self):
        return (
            '.png', '.jpg', '.gif', '.jpeg', '.pdf', '.ico', '.doc', '.docx', '.xsl',
            '.ppt', '.txt', '.zip', '.rar', '.tar', '.tgz', '.bz', '.gz', '.chm',
            '.dll', '.exe', '.mp3', '.rm', '.asf', '.mov', '.ttf', '.rmvb', '.rtf',
            '.ra', '.mp4', '.wma', '.wmv', '.xps', '.mht', '.msi', '.flv', '.xls',
            '.ld2', '.ocx', '.url', '.avi', '.swf', '.db', '.bmp', '.psd', '.iso',
            '.ape', '.cue', '.u32', '.ucd', '.pk', '.lrc', '.m4v', '.nrg', '.cd', '.bmp',
            '.cnn', '.m3u', '.tif', '.mpeg', '.srt', '.chs', '.cab', '.pps',  '.mpg',
            '.wps', '.ashx', '.svg' 
        )

    def interceptor(self, request):
        block_suffix = self.block_suffix
        if request.path.endswith(block_suffix):
            request.abort()

    def parse_url(self, url):
        parse_result = urlparse(url)
        return parse_result

    def get_domain(self, url):
        parse_result = self.parse_url(url)
        return parse_result.netloc

    def add_cookies(self, browser):
        cookies = self.cookies
        if cookies:
            cookie_list = cookies.split(';')
            cookie_parts = [cookie.strip().split('=') for cookie in cookie_list if cookie.strip()]
            cookie_dicts = [{'name': name.strip(), 'value': value.strip()} for (name, value) in cookie_parts if name.strip() and value.strip()]
            for cookie_dict in cookie_dicts:
                browser.add_cookie(cookie_dict)
    
    def start(self, allowed_subdomain=False, debug=False):
        if not self.task['spider_enable']:
            return
        start_urls = self.start_urls
        if debug:
            self.crawl_thread_num = 1
        for s_url in start_urls:
            self.add_allow_domain(s_url, allowed_subdomain)
            self.crawling_url_queue.put(s_url)
        self.crawl_pool = ThreadPoolExecutor(self.crawl_thread_num)
        start_time = time.time()
        print('start_time: ', time.ctime(start_time))
        futures = []
        url_count = 0
        while True:
            if (time.time() - start_time) > self.max_running_time:
                break
            if url_count >= self.max_url_count:
                break
            try:
                url = self.crawling_url_queue.get(timeout=2)
            except Empty:
                # TODO：制定一个sleep检查机制，满足某个条件后，提前结束爬虫
                time.sleep(.5)
                continue
            # 确保已经爬取和正在爬取的url，不会重复提交给爬取线程
            with self._pending_complete_urls_lock:
                pending_complete_urls = self.pending_complete_urls
                if url in pending_complete_urls:
                    continue
                self.pending_urls.add(url)
                # print('submit url: ', url)
                self.crawl_pool.submit(self.crawl, url)
                # future = self.crawl_pool.submit(self.crawl, url)
                # futures.append(future)
                url_count += 1

        # for fs in as_completed(futures):
        #     print('future result', fs.result())
        print("to be shutdown...", time.ctime())
        self.crawl_pool.shutdown()
        # 主线程结束前的收尾工作
        # 关闭数据库连接
        self.db.close()
        print('crawler finished at ', time.ctime())


    def crawl(self, url):
        try:
            browser = ChromeBrowser()
            # 设置抓取的日志的url范围
            self.add_driver_scopes(browser)
            browser.add_request_interceptor(self.interceptor)
            print('crawl', url)
            # 由于设置cookie前必须访问一下页面
            # 故需要设置完cookie后再访问页面
            cookies = self.cookies
            if cookies:
                browser.get(url)
                self.add_cookies(browser)
                browser.get(url)
            else:
                browser.get(url)
            wait = WebDriverWait(browser.driver, 5, 0.5)
            wait.until(EC.title_is)
            static_urls = self.get_static_urls(browser, url)
            self.handle_next_urls(static_urls, 'static')
            dynamic_urls = self.get_dynamic_urls(browser)
            self.handle_next_urls(dynamic_urls, 'dynamic')
            # 当前url已经爬取完成,
            # 是否需要加锁？？
            with self._pending_complete_urls_lock:
                self.complete_urls.add(url)
                self.pending_urls.discard(url)
                self.pending_complete_urls = self.pending_urls.union(
                    self.complete_urls)
        except Exception as e:
            print('crawl error: ', url, e)
            raise e
        finally:
            browser.delete_all_cookies()
            browser.quit()
            print('crawl url finished', url)
            self.crawling_url_queue.task_done()

    # @try_times(3)
    def get_static_urls(self, browser, referer):
        '''
        静态urls：即在页面完全展示后即可获取
        从标签中直接获取的urls，比如: 
            <a href='相对地址/绝对地址'>, 
            <img src='相对地址/绝对地址'>
            <script src='相对地址/绝对地址'>
            <iframe src='相对地址/绝对地址'>
        如果全部由动态点击操作完后，也是能获取的，即可以都改为动态获取,但是为了避免一些暗链
        '''
        a_hrefs = browser.find_elements_attribute('a[href]', 'href')
        img_srcs = browser.find_elements_attribute('img[src]', 'src')
        script_srcs = browser.find_elements_attribute('script[src]', 'src')
        iframe_srcs = browser.find_elements_attribute('iframe[src]', 'src')
        all_possible_static_urls = []
        for urls in [a_hrefs, img_srcs, script_srcs, iframe_srcs]:
            urls = self.filter_ignore_urls(urls)
            all_possible_static_urls.extend(urls)
        static_urls = set()
        current_url = browser.current_url
        for url in all_possible_static_urls:
            url = self.to_absolute_url(url, current_url) 
            static_urls.add(url)
        static_urls = self.filter_not_allowed_domain_urls(static_urls)
        static_url_datas = []
        for s_url in static_urls:
            params = self.trans_get_url_params(s_url) 
            if 'logout' in s_url:
                continue
            if params:
                s_url =  self.remove_query_from_url(s_url)
            url_data = {'referer': referer, 'url': s_url, 'method': 'GET', 'domain_id': self.domain_id, 'params': params}  
            static_url_datas.append(url_data)
        return static_url_datas

    # @try_times(3)
    def get_dynamic_urls(self, browser):
        '''
        动态urls: 需要进行某些操作（比如点击），需要通过http请求报文获取
        从浏览器的请求日志中获取urls，比如：
            1.form表单的提交操作,产生的url。form表单需要先填充后提交，
            form表单提交之后的刷新问题处理：优先处理其他直接点击的元素，如果有多个form表单的情况下需要重新获取form然后处理
            2.其他的可以直接点击操作的元素产生的url
        '''
        all_click_elements = self.find_all_click_elements(browser)
        forms = self.find_form_elements(browser)
        all_form_click_elements = []
        form_and_form_clicks = []
        for form in forms:
            form_click_elements = self.find_form_click_elements(form)
            all_form_click_elements.extend(form_click_elements)
            form_and_form_clicks.append((form, form_click_elements))
        not_form_click_elements = self.find_not_form_click_elements(all_click_elements, all_form_click_elements)
        # 完成点击操作，以便记录http请求日志
        self.click_other_elements(browser, not_form_click_elements)
        # 操作form表单
        for form, form_click_elements in form_and_form_clicks:
            self.click_form_submit(browser, form, form_click_elements)
        # 处理http请求日志
        dynamic_urls = self.process_log_entry(browser)
        return dynamic_urls

    def find_form_elements(self, browser):
        '''
        获取当前页面中的form标签
        '''
        forms = browser.find_elements_by_css_selector('form')
        return forms
     
    def _find_possible_click_elements(self, element):
        '''
        找到某个元素范围内的可能的点击元素
        '''
        possible_click_elements = []
        a_tags = element.find_elements_by_css_selector('a')
        buttons = element.find_elements_by_css_selector('button')
        input_tags = element.find_elements_by_css_selector(
            'input[type="submit"]')
        elements_with_on_click = element.find_elements_by_css_selector(
            '[onclick]')
        input_buttons = element.find_elements_by_css_selector(
            'input[type="button"]')
        possible_click_elements.extend(a_tags)
        possible_click_elements.extend(buttons)
        possible_click_elements.extend(input_tags)
        possible_click_elements.extend(elements_with_on_click)
        possible_click_elements.extend(input_buttons)
        # 过滤点退出点击操作的元素
        possible_click_elements = self.filter_logout_element(possible_click_elements)
        return possible_click_elements

    def find_all_click_elements(self, browser):
        return self._find_possible_click_elements(browser)

    def find_form_click_elements(self, form):
        '''
        form表单中的点击元素
        '''
        return self._find_possible_click_elements(form)

    def find_not_form_click_elements(self, all_click_elements, all_form_click_elements):
        all_form_click_element_ids = [ele.id for ele in all_form_click_elements]
        not_form_click_elements = []
        for click_ele in all_click_elements:
            if click_ele.id not in all_form_click_element_ids:
                not_form_click_elements.append(click_ele)
        return not_form_click_elements

    def to_absolute_url(self, url, current_url):
        return urljoin(current_url, url)

    def click_form_submit(self, browser, form, form_click_elements):
        '''
        填充表单后，点击元素
        '''
        my_form = Form(form)
        iterate_count = my_form._iterate_count
        current_win_handle = browser.current_window_handle
        current_url = browser.current_url
        current_handles = browser.window_handles
        for _ in range(iterate_count):
            for f_click_ele in form_click_elements:
                my_form.clear()
                my_form.fill()
                self.switch_to_current_win_handle(browser, current_win_handle, current_url)
                if current_url != browser.current_url:
                    continue
                self._do_click(browser, current_win_handle, f_click_ele)
                self.close_some_page(browser, current_handles, current_win_handle, current_url)

    def click_other_elements(self, browser, click_elements):
        '''
        直接点击元素
        '''
        current_win_handle = browser.current_window_handle
        current_url = browser.current_url
        current_handles = browser.window_handles
        for click_ele in click_elements:
            self.switch_to_current_win_handle(browser, current_win_handle, current_url)
            if current_url != browser.current_url:
                continue
            self._do_click(browser, current_win_handle, click_ele)
            self.close_some_page(browser, current_handles, current_win_handle, current_url)

    def switch_to_current_win_handle(self, browser, current_win_handle, current_url):
        browser.switch_to.window(current_win_handle)
        WebDriverWait(browser.driver, 2, 0.5).until(EC.url_to_be(current_url))

    def _do_click(self, browser, current_win_handle, click_element):
        '''
        执行点击操作，会出现以下情况：
            1.出现模态框/通知/确认
        '''
        ac_chs = ActionChains(browser.driver)
        try:
            # ac_chs.move_to_element(click_element).key_down(
            #     Keys.CONTROL).click(click_element).perform()
            ac_chs.key_down(
                Keys.CONTROL).click(click_element).key_up(Keys.CONTROL).perform()
        except Exception as e:
            pass

    def close_some_page(self, browser, current_handles, current_win_handle, current_url):
        # 检测是否打开了新页面，如果打开了新页面，需要等待新页面url重现，然后关闭新页面. 新页面url不在此次获取, 在后续的http请求日志中获取，
        # 如果没有新页打开，结束操作
        opened_new = EC.new_window_is_opened(current_handles)(browser.driver)
        if not opened_new:
            return
        window_handles = browser.window_handles
        for win_handle in window_handles[1:]:
            # 需要等待一定时间，保障点击后新页面打开
            try:
                browser.switch_to.window(win_handle)
                wait = WebDriverWait(browser.driver, 1.5, 0.5)
                # wait.until(EC.new_window_is_opened(current_handles))
                wait.until_not(EC.url_contains('about:blank'))
                # wait.until(EC.title_is)
                # wait.until(url_not_contains('about:blank'))
            except TimeoutException as e:
                pass
            else:
                # new_url = browser.current_url
                # print('go to close new_url', new_url)
                browser.close()
        # 只要切换过页面，一定要回到当前页面
        # self.switch_to_current_win_handle(browser, current_win_handle, current_url)

    def add_allow_domain(self, url, allowed_subdomain=False):
        '''
        parameters:
            allowed_subdomain: 是否爬取子域名

        TODO: 当url域名为ip表示时怎么处理
        '''
        domain = self.get_domain(url)
        if allowed_subdomain:
            domain_parts = domain.split('.')
            allow_domain = '.'.join([domain_parts[-2:]])
        else:
            allow_domain = domain
        if allow_domain not in self.allow_domains:
            self.allow_domains.add(allow_domain)

    def add_driver_scopes(self, browser):
        driver_scopes = []
        for domain in self.allow_domains:
            domain_pattern = '.*%s.*' % domain
            driver_scopes.append(domain)
        browser.driver.scopes = driver_scopes
        
    def process_log_entry(self, browser):
        '''
        获取http请求日志中的url，将符合的条件的url(包含get/post请求)放入待爬取队列
        '''
        logs = browser.get_http_logs()
        # 获取动态url
        dynamic_urls = []
        for entry in logs:
            host = entry.host
            path = entry.path
            if host in self.allow_domains and not self.url_endswith_ignore(path):
                url = entry
                url_data = {}
                _url = url.url
                if 'logout' in _url:
                    continue
                method = url.method
                url_data['referer'] = url.headers.get('Referer', '')
                if method == 'GET':
                    params = url.querystring
                    if params:
                        _url = self.remove_query_from_url(_url)
                elif method == 'POST':
                    params = url.params
                    _url_parse = self.parse_url(_url)
                    if _url_parse.query:
                        self.add_query_to_params(_url_parse, params)
                        _url = self.remove_query_from_url(_url)
                    params = self.trans_post_url_params(params)
                url_data['domain_id'] = self.domain_id
                url_data['url'] = _url
                url_data['method'] = method
                url_data['params'] = params
                dynamic_urls.append(url_data)
        return dynamic_urls
    
    def handle_next_urls(self, urls, url_type):
        '''
        处理当前页面中获取的对静态和动态链接。
        一般说，浏览器页面url都是使用get请求，故将get请求的动态url和静态url, 去重后加入到待爬取队列中
        这里需要注意：
            1.爬虫需要爬取的url和需要保存到数据库的url数据是有很差异的。
            爬虫要爬取的是页面url，需要保存的url数据包含且不限于页面url，还有页面操作发起的请求url数据
        urls: 字典列表 
        urls: 字典列表
        
        '''
        url_datas = []
        for url_data in urls:
            method = url_data.get('method')
            if method == 'GET':
                _url = url_data.get('url')
                _params = url_data.get('params', '')
                if _params:
                    _url = '?'.join([_url, _params])
                if _url:
                    with self._next_urls_lock:
                        next_urls = self.next_urls
                        if _url not in next_urls:
                            next_urls.add(_url)
                            # print('put next_url into crawling_url_queue: ', _url)
                            self.crawling_url_queue.put(_url)
            self.collect_save_url_data(url_datas, url_data)
        # 保存url数据
        if url_datas:
            self.save_urls(url_datas)
            
    def add_query_to_params(self, url, params):
        url_parse = self.parse_url(url)
        if url_parse.query:
            _params = self.query2params(url_parse.query)
            params.update(_params)
        return params

    def query2params(self, query):
        params = {}
        if not query:
            return params
        parts = query.split('&')
        parts = [part.split('=') for part in parts] 
        parts = [(part[0], part[1]) for part in parts if len(part) == 2]
        for p, v in parts:
            _p = p.strip()
            _v = v.strip()
            if _p and _v:
                params[_p] = _v
        return params

    def remove_query_from_url(self, url):
        url_parse = self.parse_url(url)
        if url_parse.query:
            new_url_parse = url_parse._replace(query='')
            url = new_url_parse.geturl()
        return url

    def trans_get_url_params(self, url):
        url_parse_res = self.parse_url(url)
        return url_parse_res.query

    def trans_post_url_params(self, params):
        params_list = []
        for name, value in params.items():
            params_list.append({"name": name, "value": value, "type": "multible"})
        if not params_list:
            return ''
        return json.dumps(params_list)

    def get_params_fields(self, url_data):
        method = url_data.get('method')
        params = url_data.get('params')
        if not params:
            return []
        if method == 'GET':
            params = self.query2params(params)
            params_fields = list(params.keys())
        elif method == 'POST':
            params_list  = json.loads(params)
            params_fields = [p.get('name') for p in params_list if p and p.get('name')]
        if not params:
            return []
        params_fields.sort()
        return params_fields

    def collect_save_url_data(self, url_datas, url_data):
        ''' 
        保存链接数据
        通过hash去重
        '''
        url = url_data['url']
        method = url_data['method']
        params = url_data['params']
        if method == 'GET':
            url_data_string = '_'.join([url, params, method])
        else:
            params_fields = self.get_params_fields(url_data)
            url_data_string = '_'.join([url, "_".join(params_fields), method])
        url_md5_digest = hashlib.md5(url_data_string.encode('utf-8')).hexdigest()
        with self._saved_url_lock:
            if url_md5_digest not in self.saved_url_hashes:
                url_datas.append(url_data) 
                self.saved_url_hashes.add(url_md5_digest)

    def save_urls(self, url_datas):
        '''
        批量保存url数据
        '''
        count = len(url_datas)
        print('save_url', count)
        step = 100
        for start_idx in range(0, count, step):
            stop_idx = start_idx + step
            _datas = url_datas[start_idx: stop_idx]
            args = []
            fields = ('domain_id', 'url', 'referer', 'params', 'method')
            for u_d in _datas:
                _args = u_d['domain_id'], u_d['url'], u_d['referer'], u_d['params'], u_d['method']
                args.append(_args)
            table_name = 'bd_web_url_' + str(self.task_id)
            self.db.insertmany(table_name, fields, args)

    def url_endswith_ignore(self, url):
        flag = False
        ignore_suffix = tuple(self.ignore_suffix)
        if url.endswith(ignore_suffix):
            flag = True
        return flag

    def is_logout_click_element(self, click_element):
        '''
        判断click_element是否是退出操作的点击元素
        '''
        flag = False
        href_val = click_element.get_attribute('href')
        text_val = click_element.get_attribute('text')
        value_val = click_element.get_attribute('value')
        logout_pattern = u'logout|close|reset|关闭|退出|关闭系统|退出系统'
        if href_val and re.search(logout_pattern, href_val.lower()):
            flag = True
            return flag
        if text_val and re.search(
                logout_pattern, text_val.lower()):
            flag = True
            return flag
        if value_val and re.search(
                logout_pattern, value_val.lower()):
            flag = True
            return flag
        return flag  

    def filter_logout_element(self, elements):
        elements = filter(lambda element: not self.is_logout_click_element(element), elements) 
        return list(elements)

    def filter_ignore_urls(self, urls):
        '''
        过滤掉一些不爬取链接：比如图片、视频，文件(js, css 等）扩展名结尾的链接
        '''
        urls = filter(lambda url: not self.url_endswith_ignore(url), urls)
        return list(urls)

    def filter_not_allowed_domain_urls(self, urls):   
        urls = filter(lambda url: urlparse(url).netloc in self.allow_domains, urls)
        return list(urls)

        
def main(task_id, domain_id, debug):
    crawler = Crawler(task_id, domain_id)
    crawler.delete_data()
    # start_urls = ['https://www.baidu.com']
    # start_urls = ['http://172.16.110.232/DVWA/login.php']
    crawler.start(debug=debug)
    


if __name__ == '__main__':
    import sys
    task_id = sys.argv[1]
    domain_id = sys.argv[2]
    if len(sys.argv) == 4:
        debug = True
    else:
        debug = False
    main(task_id, domain_id, debug)
