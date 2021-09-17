# coding: utf-8
import re
from selenium import webdriver
from browsermobproxy import Server
from browsermobproxy.exceptions import ProxyServerError
from selenium.webdriver import DesiredCapabilities
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedTagNameException
import socket
from contextlib import closing
import time
import platform
import os
from Queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed


BROWSERMOB_PROXY_PATH = '/home/uos/browsermob-proxy-2.1.4/'
CHROME_DRIVER_PATH = '/home/uos/chromedriver'


class BrowserProxyServer(Server):
    """
    因代理服务器无法关闭,故实现自己的服务启动命令，跳过默认的服务启动命令(bin/目录下的shell脚本启动)
    代理服务器不支持同时启动多个,会导致无法正常分配代理服务的端口(已解决）
    """

    def __init__(
            self,
            path=BROWSERMOB_PROXY_PATH,
            options=None,
            port_range=50):
        options = options if options is not None else {}
        path_var_sep = ':'
        if platform.system() == 'Windows':
            path_var_sep = ';'
            if not path.endswith('.bat'):
                path += '.bat'

        exec_not_on_path = True
        for directory in os.environ['PATH'].split(path_var_sep):
            if(os.path.isfile(os.path.join(directory, path))):
                exec_not_on_path = False
                break

        if not os.path.isdir(path) and exec_not_on_path:
            raise ProxyServerError("Browsermob-Proxy binary couldn't be found "
                                   "in path provided: %s" % path)

        self.path = path
        self.host = 'localhost'
        port = options.get('port', 8080)
        if port == 0:
            port = self.get_free_port()
        self.port = port
        self.port_range = int(port_range)
        self.process = None
        self.command = []
        self.command += ['java',
                         '-Dapp.name=browsermob-proxy',
                         '-Dbasedir=' + path,
                         '-jar',
                         os.path.join(path,
                                      'lib/browsermob-dist-2.1.4.jar'),
                         '--proxyPortRange=%s-%s' % (self.port + 1,
                                                     self.port + self.port_range + 1),
                         '--port=%s' % self.port]

    def get_process_pid(self):
        if self.process:
            return self.process.pid
        else:
            return None

    def get_free_port(self):
        """ Get free port"""
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]


class ChromeBrowser(object):
    def __init__(self, browser_proxy_server, driver_path=CHROME_DRIVER_PATH):
        # 代理服务配置, TODO：代理blacklist：图片加载，加快速度
        self.browser_proxy_server = browser_proxy_server
        self.browser_proxy_server.start()
        # self.capabilities = DesiredCapabilities.CHROME
        # self.capabilities['acceptSslCerts'] = True
        for i in range(3):
            try:
                self.proxy = self.browser_proxy_server.create_proxy(
                    params={'trustAllServers': 'true'})
            except BaseException:
                continue
            else:
                break
        # self.proxy.add_to_capabilities(self.capabilities)
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
        options.add_argument('--proxy-server={0}'.format(self.proxy.proxy))
        # implicitly_wait_seconds = 10
        self.driver = webdriver.Chrome(driver_path, options=options)

    def __getattr__(self, name):
        return getattr(self.driver, name)

    def get(self, url, har_name=None):
        if not har_name:
            har_name = url
        self.proxy.new_har(
            har_name,
            options={
                'captureHeaders': True,
                'captureContent': True})
        self.driver.get(url)

    def quit(self):
        self.driver.quit()
        self.proxy.close()
        self.browser_proxy_server.stop()

    def get_http_log(self):
        log = self.proxy.har['log']['entries']
        return log

    def get_http_log_entries(self):
        entries = self.proxy.har['log']['entries']
        return entries


class url_not_contains(object):
    def __init__(self, url):
        self.url = url

    def __call__(self, driver):
        return self.url not in driver.current_url


class Form(object):
    def __init__(self, webelement):
        if webelement.tag_name.lower() != 'form':
            raise UnexpectedTagNameException('form tag only', webelement.tag_name)
        self.webelement = webelement
        self._text_inputs = None
        self._password_inputs = None
        self._email_inputs = None

    @property 
    def text_inputs(self):
        pass

    @property
    def password_inputs(self):
        pass

    def email_inputs(self):
        pass

    def number_inputs(self):
        pass

    def checkbox_inputs(self):
        pass

    def radio_inputs(self):
        pass

    def selects(self):
        pass

    def textarea(self):
        pass 

    def fill(self, fill, fill_type):
        pass

    def __iter__(self):
        return iter(self)

    def __next__(self):
        '''
        每次迭代，就完成一次填充
        '''
        pass


class Crawler(object):
    def __init__(self, crawl_thread_num=5, log_thread_num=5,
                 max_running_time=60 * 20):
        self.pending_urls = set()
        self.complete_urls = set()
        self.crawling_url_queue = Queue()
        self.log_entry_queue = Queue()
        self.crawl_thread_num = crawl_thread_num
        self.log_thread_num = log_thread_num
        self.max_running_time = max_running_time

    def crawl(self, url):
        print('crawl', url)
        server = BrowserProxyServer(BROWSERMOB_PROXY_PATH, options={'port': 0})
        browser = ChromeBrowser(server)
        browser.get(url)
        print('get next urls')
        next_urls = self.get_next_urls(browser)
        for next_url in next_urls:
            print('next_url: ', next_url)
            self.crawling_url_queue.put(next_url)
        self.complete_urls.add(url)
        self.pending_urls.discard(url)
        print('process log entry..', time.ctime())
        self.log_entry_pool.submit(self.process_log_entry, browser)

    def submit_click_element(self, click_element, form):
        '''
        判断click_element 是否在某个form标签中
        '''
        flag = False
        form_click_elements = self.find_form_click_elements(form)
        for form_ck_ele in form_click_elements:
            if for_ck_ele.id == click_element.id:
                flag = True
                break
        return flag        

    def logout_click_element(self, click_element):
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

    def get_form_elements(self, browser):
        '''
        获取当前页面中的form标签
        '''
        forms = browser.find_elements_by_css_selector('form')
        return forms

       
    def find_possible_click_elements(self, element):
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
        return possible_click_elements

    def find_form_click_elements(form):
        '''
        form表单中的点击元素
        '''
        possible_ck_eles = self.find_possible_click_elements(form)
        form_click_elements.extend(possible_ck_eles)
        return form_click_elements

    def get_click_elements(self, browser):
        possible_click_elements = self.find_possible_click_elements(browser)
        forms = self.get_form_elements(browser)
        click_elements = []
        for ck_ele in possible_click_elements:
            # 过滤可以能是退出操作的点击元素
            if self.logout_click_element(ck_ele):
                possible_click_elements.remove(ck_ele)
                continue
            else:
                # 获取表单提交操作的点击元素
                for form in forms:
                    if self.submit_click_element(ck_ele, form):
                        # 如果是表单提交操作的点击元素，需要填充表单元素的值
                        # 填充值表单的值（多种填充方案)
                        click_elements.append(('submit', ck_ele, form))
                        continue
                # 非表单提交操作的点击元素        
                click_elements.append(('normal', ck_ele, None))
            # print(ck_ele.get_attribute('text'), ck_ele.tag_name,ck_ele.get_attribute('href'))
        return click_elements

    def get_next_urls(self, browser):
        current_win_handle = browser.current_window_handle
        current_url = browser.current_url
        new_page_urls = set()
        click_elements = self.get_click_elements(browser)
        for element_type, click_ele, form in click_elements:
            ac_chs = ActionChains(browser.driver)
            try:
                # 如果是表单提交操作的点击元素，需要给表单填充值之后，再做点击操作
                # 一个表单可能会有多次填充
                # TODO：表单的填充方案
                if element_type == 'submit':
                    pass
                else:    
                    ac_chs.move_to_element(click_ele).key_down(
                        Keys.CONTROL).click().perform()
            except Exception as e:
                print(e)
                print 'click error', click_ele.tag_name, click_ele.get_attribute('text'), click_ele.get_attribute('href')
                continue
            # 检测是否打开了新页面，如果打开了，获取新页面url，然后关闭新页面
            # 如果没有打开新页面则，continue
            print 'after click ', click_ele.tag_name, click_ele.get_attribute('text'), click_ele.get_attribute('href')
            for win_handle in browser.window_handles:
                if win_handle == current_win_handle:
                    print('current_url', browser.current_url)
                    continue
                else:
                    print('go to switch window...')
                    browser.switch_to.window(win_handle)
                    # 需要等待一定时间，保障点击后新页面打开
                    wait = WebDriverWait(browser.driver, 2, 0.5)
                    wait.until(url_not_contains('about:blank'))
                    new_url = browser.current_url
                    print('new_url', new_url)
                    browser.close()
                    if new_url != current_url and new_url not in new_page_urls:
                        new_page_urls.add(new_url)
                    browser.switch_to.window(current_win_handle)
        return new_page_urls

    def start(self, start_urls):
        for s_url in start_urls:
            self.crawling_url_queue.put(s_url)
        self.crawl_pool = ThreadPoolExecutor(self.crawl_thread_num)
        self.log_entry_pool = ThreadPoolExecutor(self.log_thread_num)
        start_time = time.time()
        print('start_time: ', time.ctime(start_time))
        while True:
            if (time.time() - start_time) > self.max_running_time:
                break
            self.pending_complete_urls = self.pending_urls.union(
                self.complete_urls)
            pending_complete_urls = self.pending_complete_urls
            try:
                url = self.crawling_url_queue.get(timeout=5)
            except Empty:
                continue
            if url not in pending_complete_urls:
                self.pending_urls.add(url)
                self.crawl_pool.submit(self.crawl, url)
        print("to be shutdown...")
        self.crawl_pool.shutdown()
        self.log_entry_pool.shutdown()

    def process_log_entry(self, browser):
        entries = browser.get_http_log_entries()
        for entry in entries:
            url = entry['request']['url']
            print(url)
        browser.quit()

    def save_entries(self, entries):
        pass

    def filter_entry(self, entry):
        pass


if __name__ == '__main__':
    crawler = Crawler()
    start_urls = ['https://www.baidu.com']
    crawler.start(start_urls)
