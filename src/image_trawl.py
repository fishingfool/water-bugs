import pandas as pd
import numpy as np
import string
from bs4 import BeautifulSoup
from collections import deque
import requests
import re
import time
import pickle
from skimage.io import imread, imsave

# This webscraper is custom built to collect images from troutnut.com
# It proceeds through the following steps:
#       1. The URLs for the pages I'm interested in are all
#          formatted as "http://www.troutnut.com/hatch/"+ a
#          number specific to the order of insect/ + the order of
#          insect/ + the page number + "#specimens"
#          i.e. -
#          http://www.troutnut.com/hatch/13/Insect-Plecoptera-Stoneflies
#          I have the numbers and orders stored in a json file, these
#          are read in.
#       2. I create a deque to store the urls I'll be grabbing on my
#          first pass. Troutnut has a forum setup. With the URL I created
#          above, I'll be directed to the first page of that insect order's
#          sub-forum. Each page of that sub-forum has 10 topics - each
#          corresponding to a different specimen. I go through the
#          pages for each sub-forum, and collect the URLs for the specimen
#          pages, appending them to the deque.
#       3. Once these have been collected, I go through the deque and visit
#          each of the urls in turn. I identify the images, collect the meta
#          data for each specimen, and store both image and metadata in a
#          directory specific to the order of the insect.

class imageScraper():

    def __init__(self):
        # read in the url data we'll need later (the formatting of
        # the url for each order we're interested in), and create a
        # deque for storing the urls for specimen pages.
        self.data_setup()
        self.Q = deque()

        # reading in the information stored in urlinfo.json
        # We'll use this to create the urls we'll visit during our
        # first pass through.
    def data_setup(self):
        self.data_dict = pd.read_json('urlinfo.json')
        self.insect_list = self.data_dict.orders.values
        self.tn_num = self.data_dict.tn_nums.values

    # This appends the urls for the specimen pages to our queue.
    def pg_urls(self):
        p = self.html.find_all('a',attrs={'class':'vl'})
        for i in range(len(p)):
            new_url = p[i].attrs['href']
            if new_url not in self.Q:
                self.Q.append(new_url)
            else:
                break

    # this looks at the current page, finds the highest page in the
    # forum from a navigation bar at the bottom, and calls pg_urls
    def page_scan(self):
        req = requests.get(self.url)
        self.html = BeautifulSoup(req.content,'html.parser')
        s = self.html.find_all('div', attrs={'class':'pld'})
        if self.new_order == True:
            self.max_page = int(re.findall('[0-9]+$',s[0].get_text())[0])
            self.new_order = False
        self.pg_urls()

    # this incriments the url of a sub-forum, moving to the next page

    def url_increment(self):
        # note - this is brilliant, but only if the url ends with '/'
        time.sleep(2)
        old_end = re.findall('[a-z0-9#]+$',self.url)
        print('old end',old_end)
        if len(old_end) > 0:
            old_end = old_end[0]
            new_num = str(int(re.findall('[0-9]+',old_end)[0]) + 1)
            self.url = self.url.replace(old_end,'{}#specimens'.format(new_num))
        else:
            self.url = self.url + '2#specimens'
        print('url:', self.url)

    # This is the function that you call for a first pass through the
    # website. It takes the information from the urlinfo.json file and
    # uses them to build the 10 urls for the sub-forums on troutnut.
    # It goes through the pages of that subforum until it reaches
    # the max page, and then it moves on to the next sub-forum.
    def iter_order(self):
        for (num,ins) in zip(self.tn_num,self.insect_list):
            print('Beginning:',ins)
            self.url = "http://www.troutnut.com/hatch/{}/{}/".format(num,ins)
            self.new_order = True
            self.page_scan()
            for pg in range(self.max_page):
                print('page {} of {}'.format(pg,self.max_page))
                self.url_increment()
                self.page_scan()
        self.pickle_queue_master()

        # Don't pay too much attention to this - this is just
        # a recovery option for if something gets messed up. I was
        # tinkering with the code, fixing bugs, making improvements
        # as I went along.
        # It rebuilds the queue for a specific insect order, that way
        # I don't have to run the entire thing a second time
    def repopulate_queue(self):
        self.unpickle_queue()
        number = input("num -->")
        print('Beginning...')
        row = self.data_dict.loc[int(number)]
        num = row[2]
        ins = row[1]
        self.url = "http://www.troutnut.com/hatch/{}/{}/".format(num,ins)
        self.new_order = True
        self.page_scan()
        print('setup complete, entering loop...')
        for pg in range(self.max_page):
            print('page {} of {}'.format(pg,self.max_page))
            self.url_increment()
            self.page_scan()
        print('pickling queue...')
        self.pickle_queue_master()
        print('complete')

        # pickles the queue so that I can exit the code and come
        # back to it, picking up where I left off.
        # useful for tinkering.
    def pickle_queue(self):
        with open('Q.pkl','wb') as f:
            pickle.dump(self.Q,f)

        # recovers the previously pickled queue
    def unpickle_queue(self):
        with open('Q.pkl','rb') as f:
            self.Q = pickle.load(f)

        # backup of the queue
    def pickle_queue_master(self):
        with open('Q_master.pkl','wb') as f:
            pickle.dump(self.Q,f)
        self.pickle_queue()
        # unpickle backup
    def unpickle_master(self):
        with open('Q_master.pkl','rb') as f:
            self.Q = pickle.load(f)
        self.pickle_queue()

    # This is to be run after iter_order()
    # This goes through the queue that we built in inter_order(),
    # grabs the images from each page, grabs the metadata from each
    # page and for each specimen, and saves both the images and the
    # metadata to a directory specified in urlinfo.json

    def scrape(self):
        self.unpickle_queue()
        print('Image queue loaded...')
        while len(self.Q) > 0:
            print('Grabbing images...')
            self.grab_images()
            time.sleep(3)

    # this is misleadingly named - it grabs the images and the metadata
    # scrape will call this function until the queue is empty.
    def grab_images(self):
        self.url = self.Q.popleft()
        req = requests.get(self.url)
        html = BeautifulSoup(req.content, 'html.parser')
        a = html.find_all('img', attrs={'class':'i'})
        order_url = html.find_all('a', attrs={'itemprop':'url'})[3]['href']
        order_val = order_url.split('/')[5]
        t = html.find_all('span', attrs = {'itemprop':'title'})
        order_dir = self.data_dict[self.data_dict.orders == order_val].directory.values[0]
        print('Found images in',order_url)
        meta_info = []
        for i in range(len(a)):
            b = a[i]
            src = b.attrs['src']
            c = [b.attrs['name'],b.attrs['title'],b.attrs['alt'],src]
            taxo = [x.get_text() for x in t[3:]]
            d = ';'.join(c+taxo+['\n'])
            meta_info.append(d)
            img_arr = imread(requests.get(src, stream=True).raw)
            imsave("../data/troutnut/{}/{}.jpg".format(order_dir,a[i]['name']), img_arr)
        print(len(a), "images saved successfully")
        with open("../data/troutnut/{}/meta.txt".format(order_dir),"a") as f:
            for i in range(len(meta_info)):
                #f.write(image_name[i]+','+source_info[i]+','+source_info[i]+','+source_info_alt+','+image_url[i])
                f.write(meta_info[i])
        print('Updated metadata.')
        self.pickle_queue()
        print('Updated queue')
















# #
