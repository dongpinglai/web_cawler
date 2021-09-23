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
        
    def clear_select(self):
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
            webelement.send_keys(current_index)

    def fill_radio_value(self, webelements):
        for webelement in webelements:
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


class Crawler(object):
    '''
    动态、静态结合查找url
    '''
    def __init__(self, crawl_thread_num=5, handle_thread_num=5,
                 max_running_time=60 * 20):
        self.pending_urls = set()
        self.complete_urls = set()
        self.pending_complete_urls = set()
        self.crawling_url_queue = Queue()
        self.log_entry_queue = Queue()
        self.crawl_thread_num = crawl_thread_num
        self.handle_thread_num = handle_thread_num
        self.max_running_time = max_running_time
        self.allow_domains = set()
        self.saved_url_hashes = set()

    @property
    def ignore_suffix(self):
        """The url with ignore_suffix will not be spider."""
        return [
            'png', 'jpg', 'gif', 'jpeg', 'pdf', 'ico', 'doc', 'docx', 'xsl',
            'ppt', 'txt', 'zip', 'rar', 'tar', 'tgz', 'bz', 'gz', 'chm',
            'dll', 'exe', 'mp3', 'rm', 'asf', 'mov', 'ttf', 'rmvb', 'rtf',
            'ra', 'mp4', 'wma', 'wmv', 'xps', 'mht', 'msi', 'flv', 'xls',
            'ld2', 'ocx', 'url', 'avi', 'swf', 'db', 'bmp', 'psd', 'iso',
            'ape', 'cue', 'u32', 'ucd', 'pk', 'lrc', 'm4v', 'nrg', 'cd', 'bmp',
            'cnn', 'm3u', 'tif', 'mpeg', 'srt', 'chs', 'cab', 'pps',  'mpg',
            'wps','js', 'css', 'ashx'
        ]

    def parse_url(self, url):
        parse_result = urlparse(url)
        return parse_result

    def get_domain(self, url):
        parse_result = self.parse_url(url)
        return parse_result.netloc
    
    def start(self, start_urls, allowed_subdomain=False, debug=False, max_url_count=10):
        if debug:
            self.crawl_thread_num = 1
            self.handle_thread_num = 1
        for s_url in start_urls:
            self.add_allow_domain(s_url, allowed_subdomain)
            self.crawling_url_queue.put(s_url)
        self.crawl_pool = ThreadPoolExecutor(self.crawl_thread_num)
        self.hande_next_urls_pool = ThreadPoolExecutor(self.handle_thread_num)
        start_time = time.time()
        print('start_time: ', time.ctime(start_time))
        futures = []
        url_count = 0
        while True:
            if (time.time() - start_time) > self.max_running_time:
                break
            if url_count >= max_url_count:
                break
            try:
                url = self.crawling_url_queue.get(timeout=5)
            except Empty:
                # TODO：制定一个sleep检查机制，满足某个条件后，提前结束爬虫
                time.sleep(.5)
                continue
            # 确保已经爬取和正在爬取的url，不会重复提交给爬取线程
            pending_complete_urls = self.pending_complete_urls
            if url in pending_complete_urls:
                continue
            self.pending_urls.add(url)
            print('submit url to crawling ...', url)
            future = self.crawl_pool.submit(self.crawl, url)
            futures.append(future)
            url_count += 1

        for fs in as_completed(futures):
            print(fs.result())
        print("to be shutdown...")
        self.crawl_pool.shutdown()
        self.hande_next_urls_pool.shutdown()
        # 主线程结束前的收尾工作
        # 关闭数据库连接


    def crawl(self, url):
        try:
            browser = ChromeBrowser()
            # 设置抓取的日志的url范围
            self.add_driver_scopes(browser)
            print('crawl', url)
            browser.get(url)
            wait = WebDriverWait(browser.driver, 5, 0.5)
            wait.until(EC.title_is)
            print('get static urls...')
            static_urls = self.get_static_urls(browser)
            self.hande_next_urls_pool.submit(self.handle_next_urls, static_urls, 'static')
            print('get dynamic urls...')
            dynamic_urls = self.get_dynamic_urls(browser)
            self.hande_next_urls_pool.submit(self.handle_next_urls, dynamic_urls, 'dynamic')
            # 当前url已经爬取完成,
            # 是否需要加锁？？
            self.complete_urls.add(url)
            self.pending_urls.discard(url)
            self.pending_complete_urls = self.pending_urls.union(
                self.complete_urls)
        except (StaticUrlsError, DynamicUrlsError) as e:
            raise e
        except Exception as e:
            print('crawl error', e)
        finally:
            browser.quit()

    @try_times(3)
    def get_static_urls(self, browser):
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
        return static_urls

    @try_times(3)
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
        possible_click_elements.extend(a_tags)
        possible_click_elements.extend(buttons)
        possible_click_elements.extend(input_tags)
        possible_click_elements.extend(elements_with_on_click)
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
        current_handles = browser.window_handles
        for _ in range(iterate_count):
            for f_click_ele in form_click_elements:
                my_form.clear()
                my_form.fill()
                # print('click_form.....', f_click_ele.get_attribute('value'), f_click_ele.get_attribute('text'))
                self._do_click(browser, current_win_handle, f_click_ele)
                self.close_some_page(browser, current_handles)

    def click_other_elements(self, browser, click_elements):
        '''
        直接点击元素
        '''
        current_win_handle = browser.current_window_handle
        current_handles = browser.window_handles
        for click_ele in click_elements:
            self._do_click(browser, current_win_handle, click_ele)
            self.close_some_page(browser, current_handles)

    def switch_to_current_win_handle(self, browser, current_win_handle):
        browser.switch_to.window(current_win_handle)
        current_url = browser.current_url
        WebDriverWait(browser.driver, 5, 0.5).until(EC.url_to_be(current_url))

    def _do_click(self, browser, current_win_handle, click_element):
        '''
        执行点击操作，会出现以下情况：
            1.出现模态框/通知/确认
        '''
        self.switch_to_current_win_handle(browser, current_win_handle)
        current_url = browser.current_url
        ac_chs = ActionChains(browser.driver)
        # print('do_click', browser.window_handles)
        try:
            # ac_chs.move_to_element(click_element).key_down(
            #     Keys.CONTROL).click(click_element).perform()
            ac_chs.key_down(
                Keys.CONTROL).click(click_element).key_up(Keys.CONTROL).perform()
        except Exception as e:
            # print(click_element.get_attribute('text'), click_element.get_attribute('value'), e)
            pass

    def close_some_page(self, browser, current_handles):
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
                wait = WebDriverWait(browser.driver, 0.5)
                wait.until(EC.new_window_is_opened(current_handles))
                # wait.until_not(EC.url_contains('about:blank'))
                # wait.until(EC.title_is)
                # wait.until(url_not_contains('about:blank'))
            except TimeoutException as e:
                pass
            else:
                new_url = browser.current_url
                # print('go to close new_url', new_url)
                browser.close()

    def add_allow_domain(self, url, allowed_subdomain=False):
        '''
        parameters:
            allowed_subdomain: 是否爬取子域名
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
                dynamic_urls.append(entry)
        return dynamic_urls
    
    def handle_next_urls(self, urls, url_type):
        '''
        处理当前页面中获取的对静态和动态链接。
        一般说，浏览器页面url都是使用get请求，故将get请求的动态url和静态url, 去重后加入到待爬取队列中
        这里需要注意：
            1.爬虫需要爬取的url和需要保存到数据库的url数据是有很差异的。
            爬虫要爬取的是页面url，需要保存的url数据包含且不限于页面url，还有页面操作发起的请求url数据
        static_urls: 字符串列表
        dynamic_urls: 字典列表
        
        '''
        next_urls = set()
        to_save_urls = []
        for url in urls:
            print(url_type, url)
            if url_type == 'static':
                next_urls.add(url)
            else: 
                method = d_url.method
                if method == 'GET':
                    _url = url.url
                    next_urls.add(_url)
            self.collect_save_urls(to_save_urls, url, url_type)
        for next_url in next_urls:
            print('next_url: ', next_url)
            self.crawling_url_queue.put(next_url)
        # 保存url数据
        print('to save urls ...')
        self.save_urls(to_save_urls)

    def collect_save_urls(self, to_save_urls, url, url_type):
        print('collect save urls ...')
        import pdb; pdb.set_trace()
        if url_type == 'dynamic':
            url = json.dumps(url).encode('utf-8')
        else:
            url = url.encode('utf-8')
        url_md5_digest = hashlib.md5(url).hexdigest()
        if url_md5_digest not in self.saved_url_hashes:
           to_save_urls.append(url) 
           self.saved_url_hashes()

    def save_urls(self, urls):
        '''
        保存链接数据
        通过hash去重
        '''
        for url in urls:
            print('in save_urls: ', url, sep='\n')

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
        if href_val and href_val.endswith(('logout', 'logout/')):
            flag = True
            return flag
        if text_val and re.match(
                u'logout|close|关闭|退出|关闭系统|退出系统', text_val):
            flag = True
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

        


if __name__ == '__main__':
    crawler = Crawler()
    start_urls = ['https://www.baidu.com']
    start_urls = ['http://172.16.110.232/DVWA/login.php']
    crawler.start(start_urls, debug=True)
