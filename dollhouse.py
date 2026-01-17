#!/usr/bin/python3

import requests, re, email, psycopg2, os, sys
import logging, logging.handlers
import xml.etree.ElementTree as ET
from datetime import datetime
from pprint import pprint
from configobj import ConfigObj

class DollHouse:

	def __init__(self, config_path):
		config = ConfigObj(config_path)
		self.tl_link = config['rss_link']
		self.database = config['database']
		self.save_dir = config['save_dir']

	def create_connection(self):
		try:
			conn = psycopg2.connect(self.database)
			return conn
		except Error as e:
			log.error(e)
		return None

	def setup_logger(self):
		logger = logging.getLogger('DollHouse')
		formatter = logging.Formatter(fmt='%(name)s: %(message)s')
		logger.setLevel(logging.DEBUG)
		handler = logging.handlers.SysLogHandler(address = '/dev/log')
		handler.setFormatter(formatter)
		logger.addHandler(handler)
		return logger

	def add_release(self, conn, show):
		sql = "INSERT INTO releases(title, episode, quality, tags, category, date, link) VALUES(%s, %s, %s, %s, %s, %s, %s) RETURNING id"
		cur = conn.cursor()
		cur.execute(sql, show)
		return cur.fetchone()[0]

	def add_downloads(self, conn, show):
		sql = "INSERT INTO downloads(title, episode, release_id) VALUES(%s, %s, %s) RETURNING id"
		cur = conn.cursor()
		cur.execute(sql, show)
		return cur.fetchone()[0]

	def get_wishlist(self, conn):
		cur = conn.cursor()
		cur.execute("SELECT title, min_episode, includeprops, excludeprops FROM wishlist")
		rows = cur.fetchall()
		return rows

	def check_if_show_exists(self, conn, link):
		cur = conn.cursor()
		cur.execute("SELECT check_release_exists(%s)", (link,))
		return cur.fetchone()[0]

	def check_to_download(self, conn, title, episode):
		cur = conn.cursor()
		cur.execute("SELECT is_not_downloaded(%s, %s)", (title, episode))
		return cur.fetchone()[0]

	def download_episode(self, link):
		req = requests.get(link)
		filename = re.findall('filename="(.+)"', req.headers['content-disposition'])
		path = os.path.join(self.save_dir, os.path.basename((filename[0])))
		f = open(path, 'wb')
		f.write(req.content)
		f.close()
		log.info("Downloaded %s -> %s" % (link, path))
		return True

	def find_releases(self, conn):
		cur = conn.cursor()
		cur.execute("SELECT * FROM find_matching_releases()")
		rows = cur.fetchall()
		
		for row in rows:
			# row: (release_id, title, episode, quality, link, tags, wishlist_id)
			release_id, title, episode, quality, link, tags, wishlist_id = row
			result = self.download_episode(link)
			if result:
				show = (title, episode, release_id)
				download_id = self.add_downloads(conn, show)
				try:
					log.info("Marked show as downloaded: %s, %s (release_id: %s)" % (title, episode, download_id))
				except NameError:
					pass  # log not available in test context

	def get_feed(self):
		req = requests.get(self.tl_link)
		log.debug("%s status_code: %s" % (self.tl_link, req.status_code))
		root = ET.fromstring(req.text.encode('utf-8'))

		#f = open("rss.xml", "r")
		#feed = f.read()
		#f.close()
		#root = ET.fromstring(feed)

		items = root.findall('channel/item')
		log.info("Fetched %s items" % (len(items)))

		return items

	def parse_feed(self, feed):
		shows = []
		movies = []
		allshows = []

		for item in feed:
			title = item.findtext('title')
			category = item.findtext('category')
			link = item.findtext('link')
			pubDate = item.findtext('pubDate')
			if pubDate == "":
				desc = item.findtext('description')
				added = re.search("Added: ([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})", desc)
				date = datetime.strptime(added.group(1), '%Y-%m-%d %H:%M:%S')
			else:
				parsed = email.utils.parsedate_tz(pubDate)
				date = datetime.fromtimestamp(email.utils.mktime_tz(parsed))

			show = {'title': title, 'category': category, 'link': link, 'date': date.strftime("%Y-%m-%d %H:%M:%S")}
			shows.append(show)


		for show in shows:
			episodedict = {}
			is_movie = False

			part = re.split("(S[0-9]+E[0-9]+)", show['title'])
			#part = map(str.strip, part)
			part = ['' if x is None else x for x in part]
			part = [p.strip() for p in part]


			if len(part) == 1:
				seriespart = re.split("([0-9]{4}(?:\\s+|\\.)[0-9]{2}(?:\\s+|\\.)[0-9]{2})", part[0])
				if len(seriespart) == 1:
					movies.append({'title': show['title'], 'category': show['category'], 'link': show['link'], 'date': show['date']})
					is_movie = True
				else:
					#seriespart = map(str.strip, seriespart)
					seriespart = [s.strip() for s in seriespart]
					episodedict.update({'title': seriespart[0]})
					episodedict.update({'episode': seriespart[1]})
					episodedict.update({'tags': seriespart[2]})
			else:
				episodedict = {'title': part[0]}
				if is_movie is False:
					episodedict.update({'episode': part[1]})
					episodedict.update({'tags': part[2]})

			if is_movie is False:
				episodedict.update({'category': show['category']})
				episodedict.update({'link': show['link']})
				episodedict.update({'date': show['date']})
				episodedict.update({'quality': 'Unknown'})

			if episodedict:
				allshows.append(episodedict)




		for item in allshows:
			if '1080p' in item['tags']:
				item['quality'] = '1080p'
			elif '720p' in item['tags']:
				item['quality'] = '720p'
			elif '2160p' in item['tags']:
				item['quality'] = '2160p';

		return allshows, movies

if __name__ == '__main__':
	os.chdir(os.path.dirname(os.path.abspath(__file__)))
	dh = DollHouse(sys.argv[1] if len(sys.argv) > 1 else 'dollhouse.ini')
	log = dh.setup_logger()
	log.debug("Started")

	feed = dh.get_feed()
	shows, movies = dh.parse_feed(feed)

	conn = dh.create_connection()

	with conn:

		for show in shows:
			if dh.check_if_show_exists(conn, show['link']) is False:
				showitems = (show['title'], show['episode'], show['quality'], show['tags'], show['category'], show['date'], show['link'])
				row_id = dh.add_release(conn, showitems)
				conn.commit()
				log.info("New release: %s, %s, %s, %s %s" % (show['title'], show['episode'], show['quality'], show['date'], show['link']))

		dh.find_releases(conn)

	log.debug("Finished")
