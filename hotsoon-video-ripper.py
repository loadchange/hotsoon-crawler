# -*- coding: utf-8 -*-

import os
import sys
import codecs

import requests
from six.moves import queue as Queue
from threading import Thread
import json

# Setting timeout
TIMEOUT = 10

# Retry times
RETRY = 5

# Numbers of downloading threads concurrently
THREADS = 10


class DownloadWorker(Thread):
    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            uri, target_folder = self.queue.get()
            self.download(uri, target_folder)
            self.queue.task_done()

    def download(self, uri, target_folder):
        try:
            if uri is not None:
                self._download(uri, target_folder)
        except TypeError:
            pass

    def _download(self, uri, target_folder):
        file_name = uri + '.mp4'
        file_path = os.path.join(target_folder, file_name)
        if not os.path.isfile(file_path):
            download_url = 'https://api.huoshan.com/hotsoon/item/video/_playback/?{0}'
            download_params = {
                'video_id': uri,
                'line': '1',
                'app_id': '1112',
                'vquality': 'normal',
                'quality': '720p'
            }
            download_url = download_url.format('&'.join([key + '=' + download_params[key] for key in download_params]))
            print("Downloading %s from %s.\n" % (file_name, download_url))
            retry_times = 0
            while retry_times < RETRY:
                try:
                    resp = requests.get(download_url, stream=True, timeout=TIMEOUT)
                    if resp.status_code == 403:
                        retry_times = RETRY
                        print("Access Denied when retrieve %s.\n" % download_url)
                        raise Exception("Access Denied")
                    with open(file_path, 'wb') as fh:
                        for chunk in resp.iter_content(chunk_size=1024):
                            fh.write(chunk)
                    break
                except:
                    # try again
                    pass
                retry_times += 1
            else:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                print("Failed to retrieve %s from %s.\n" % download_url)


class CrawlerScheduler(object):

    def __init__(self, items):
        self.numbers = []
        self.challenges = []
        for i in range(len(items)):
            if items[i].startswith('#'):
                self.challenges.append(items[i][1:])
            else:
                self.numbers.append(items[i])
        self.queue = Queue.Queue()
        self.scheduling()

    def scheduling(self):
        # create workers
        for x in range(THREADS):
            worker = DownloadWorker(self.queue)
            # Setting daemon to True will let the main thread exit
            # even though the workers are blocking
            worker.daemon = True
            worker.start()

        for number in self.numbers:
            self.download_videos(number)

    def download_videos(self, number):
        self._download_user_media(number)
        self.queue.join()
        print("Finish Downloading All the videos from %s" % number)

    def _search(self, keyword):
        base_url = "https://hotsoon.snssdk.com/hotsoon/search/?{0}"
        params = {
            'iid': '28631515648',
            'ac': 'WIFI',
            'os_api': '18',
            'app_name': 'live_stream',
            'channel': 'App%20Store',
            'idfa': '00000000-0000-0000-0000-000000000000',
            'device_platform': 'iphone',
            'live_sdk_version': '3.6.1',
            'vid': '2ED370A7-F09C-4C9E-90F5-872D57F3127C',
            'openudid': '20dae85eeac1da35a69e2a0ffeaeef41c78a2e97',
            'device_type': 'iPhone8,2',
            'version_code': '3.6.1',
            'os_version': '11.3',
            'screen_width': '1242',
            'aid': '1112',
            'device_id': '46166717995',
            'q': keyword,
            'offset': '0',
            'count': '20',
            'from_label': 'search',
            'user_action': 'initiative'
        }
        search_url = base_url.format('&'.join([key + '=' + params[key] for key in params]))
        response = requests.get(search_url, headers={
            'Host': 'hotsoon.snssdk.com',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 11_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E216 AliApp(TUnionSDK/1.3.1) live_stream_3.6.1 JsSdk/2.0 NetType/WIFI Channel/App Store'
        })

        results = json.loads(response.content.decode('utf-8'))
        if results.get('status_code') == 0 and results.get('data') and len(results.get('data')):
            return results.get('data')[0]
        return None

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'zh-CN,zh;q=0.9',
        'cache-control': 'max-age=0',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Mobile/15A372 Safari/604.1',
    }

    def _download_user_media(self, number):

        user_info = self._search(number)
        if not user_info:
            print("Number %s does not exist" % number)
            return
        user_info = user_info.get('user')
        user_id = str(user_info.get('id'))
        current_folder = os.getcwd()
        target_folder = os.path.join(current_folder, 'download/%s' % user_id)
        if not os.path.isdir(target_folder):
            os.mkdir(target_folder)

        video_list = []
        user_video_url = "https://reflow.huoshan.com/share/load_videos/?{0}"
        user_video_params = {
            'user_id': user_id,
            'count': '21'
        }

        def get_video_list(offset=0, max_time=None):
            user_video_params['offset'] = str(offset)
            if max_time:
                user_video_params['max_time'] = str(max_time)
            url = user_video_url.format('&'.join([key + '=' + user_video_params[key] for key in user_video_params]))
            res = requests.get(url, headers=self.headers)
            contentJson = json.loads(res.content.decode('utf-8'))
            for video in contentJson.get('data', {}).get('items', []):
                video_list.append(video)
            extra = contentJson.get('extra')
            if extra.get('has_more'):
                get_video_list(offset + 21, extra.get('max_time'))

        get_video_list()

        if len(video_list) == 0:
            print("There's no video in number %s." % number)
            return

        print("\nHotsoon number %s, video number %d\n\n" % (number, len(video_list)))

        try:
            for item in video_list:
                uri = item['video']['uri']
                self.queue.put((uri, target_folder))
        except KeyError:
            return
        except UnicodeDecodeError:
            print("Cannot decode response data from URL %s" % user_video_url)
            return


def usage():
    print("1. Please create file user-number under this same directory.\n"
          "2. In user-number.txt, you can specify hotsoon number separated by "
          "comma/space/tab/CR. Accept multiple lines of text\n"
          "3. Save the file and retry.\n\n"
          "Sample File Content:\nnumber1,number2\n\n"
          "Or use command line options:\n\n"
          "Sample:\npython hotsoon-video-ripper.py number1,number2\n\n\n")
    print(u"未找到user-number.txt文件，请创建.\n"
          u"请在文件中指定火山号，并以 逗号/空格/tab/表格鍵/回车符 分割，支持多行.\n"
          u"保存文件并重试.\n\n"
          u"例子: 火山号1,火山号2\n\n"
          u"或者直接使用命令行参数指定url\n"
          u"例子: python hotsoon-video-ripper.py 火山号1,火山号2")


def parse_sites(fileName):
    with open(fileName, "rb") as f:
        txt = f.read().rstrip().lstrip()
        txt = codecs.decode(txt, 'utf-8')
        txt = txt.replace("\t", ",").replace("\r", ",").replace("\n", ",").replace(" ", ",")
        txt = txt.split(",")
    numbers = list()
    for raw_site in txt:
        site = raw_site.lstrip().rstrip()
        if site:
            numbers.append(site)
    return numbers


if __name__ == "__main__":
    content = None

    if len(sys.argv) < 2:
        # check the sites file
        filename = "user-number.txt"
        if os.path.exists(filename):
            content = parse_sites(filename)
        else:
            usage()
            sys.exit(1)
    else:
        content = sys.argv[1].split(",")

    if len(content) == 0 or content[0] == "":
        usage()
        sys.exit(1)
    CrawlerScheduler(content)
