# coding: utf-8

from selenium import webdriver
from browsermobproxy import Server
from browsermobproxy.exceptions import ProxyServerError
from selenium.webdriver import DesiredCapabilities
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
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
	def __init__(self, path=BROWSERMOB_PROXY_PATH, options=None, port_range=50):
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
		self.command += ['java', '-Dapp.name=browsermob-proxy', '-Dbasedir=' + path, '-jar', os.path.join(path, 'lib/browsermob-dist-2.1.4.jar'), '--proxyPortRange=%s-%s' % (self.port + 1, self.port + self.port_range + 1), '--port=%s' % self.port]

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
		# 代理服务配置
		self.browser_proxy_server = browser_proxy_server
		self.browser_proxy_server.start()
		self.capabilities = DesiredCapabilities.CHROME
		self.capabilities['acceptSslCerts'] = True
		for i in range(3):
			try:
				self.proxy = self.browser_proxy_server.create_proxy(params={'trustAllServers':'true'})
			except:
				continue
			else:
				break
		self.proxy.add_to_capabilities(self.capabilities)
		# 浏览器设置
		options = webdriver.ChromeOptions()
		options.add_argument('--headless')
		options.add_argument("--ssl-version-max")
		options.add_experimental_option("excludeSwitches", ["ignore-certificate-errors"])
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
		self.proxy.new_har(har_name, options={'captureHeaders': True, 'captureContent': True})
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


class Crawler(object):
	def __init__(self, crawl_thread_num=5, log_thread_num=5, max_running_time=60*2):
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
		next_urls = self.get_next_urls(browser)
		for next_url in next_urls:
			self.crawling_url_queue.put(next_url)
		self.complete_urls.add(url)
		self.pending_urls.discard(url)
		print('process log entry..', time.ctime())
		self.log_entry_pool.submit(self.process_log_entry, browser)

	def get_next_urls(self, browser):
		current_url = browser.current_url
		print('get_next_urls', time.ctime())
		# 点击元素，如果会在新标签页打开新页面	
		next_urls = []
		return next_urls
	
	def open_new_page(self, browser):
		click_elements = []
		a_tags = browser.find_elements_by_css_selector('a[href]')
		input_tags = browser.find_elements_by_css_selector('input[type="submit"]')
		elements_with_onClick = browser.find_elements_by_css_selector('[onclick]')
		click_elements.extend(a_tags)
		action	
		ac_chs = action_chains.ActionChains(browser.driver)
		for click_ele in click_elements:
			ac_chs.move_to_element(click_ele).key_down(keys.Keys.CONTROL).click()

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
			self.pending_complete_urls = self.pending_urls.union(self.complete_urls)	
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
