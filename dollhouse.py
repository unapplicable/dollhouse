#!/usr/bin/python

import requests, re, rfc822, sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
from pprint import pprint
from configobj import ConfigObj

class DollHouse:

	def __init__(self):
		config = ConfigObj('dollhouse.ini')
		self.tl_link = config['rss_link']
		self.database = config['database']

	def create_connection(self):
		try:
			conn = sqlite3.connect(self.database)
			return conn
		except Error as e:
			print(e)
		return None

	def add_release(self, conn, show):
		sql = "INSERT INTO releases(title, episode, quality, tags, category, date, link) VALUES(?, ?, ?, ?, ?, ?, ?)"
		cur = conn.cursor()
		cur.execute(sql, show)
		return cur.lastrowid

	def add_downloads(self, conn, show):
		sql = "INSERT INTO downloads(title, episode, release_id) VALUES(?, ?, ?)"
		cur = conn.cursor()
		cur.execute(sql, show)
		return cur.lastrowid

	def get_wishlist(self, conn):
		cur = conn.cursor()
		cur.execute("SELECT title, includeprops, excludeprops FROM wishlist")
		rows = cur.fetchall()
		return rows

	def check_if_show_exists(self, link):
		cur = conn.cursor()
		cur.execute("SELECT * FROM releases WHERE link=?", (link,))
		rows = cur.fetchall()
		if len(rows) == 0:
			return False
		else:
			return True

	def check_to_download(self, title, episode):
		cur = conn.cursor()
		cur.execute("SELECT * FROM downloads WHERE title=? AND episode=? ORDER BY episode DESC", (title,episode,))
		rows = cur.fetchall()
		if len(rows) > 0:
			return False
		return True

	def download_episode(self, link):
		print "Downloaded: %s" % (link)
		return True

	def find_releases(self, conn):
		wishlist = self.get_wishlist(conn)

		cur = conn.cursor()
		for wish in wishlist:
			title = wish[0]
			cur.execute("SELECT id, title, episode, quality, link FROM releases WHERE title=? AND date > datetime('now', '-3 days') ORDER BY title, episode, quality", (title,))
			rows = cur.fetchall()
			if len(rows) > 0:
				for row in rows:
					if self.check_to_download(row[1], row[2]):
						result = self.download_episode(row[4])
						if result:
							show = (row[1], row[2], row[0])
							id = self.add_downloads(conn, show)
							print "Marked show as downloaded: %s, %s (release_id: %s)" % (row[1], row[2], id)

	def get_feed(self):
		#req = requests.get(self.tl_link)
		#root = ET.fromstring(req.text)

		f = open("rss.xml", "r")
		feed = f.read()
		f.close()
		root = ET.fromstring(feed)

		items = root.findall('channel/item')

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
			date = datetime.fromtimestamp(rfc822.mktime_tz(rfc822.parsedate_tz(pubDate)))
			shows.append({'title': title, 'category': category, 'link': link, 'date': date.strftime("%Y-%m-%d %H:%M:%S")})


		for show in shows:
			episodedict = {}
			is_movie = False

			part = re.split("(S[0-9]+E[0-9]+)?", show['title'])
			part = map(str.strip, part)

			part = ['' if x is None else x for x in part]

			if len(part) == 1:
				seriespart = re.split("([0-9]{4}(?:\s+|\.)[0-9]{2}(?:\s+|\.)[0-9]{2})?", part[0])
				if len(seriespart) == 1:
					movies.append({'title': show['title'], 'category': show['category'], 'link': show['link'], 'date': show['date']})
					is_movie = True
				else:
					seriespart = map(str.strip, seriespart)
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

		return allshows, movies

if __name__ == '__main__':

	dh = DollHouse()

	feed = dh.get_feed()
	shows, movies = dh.parse_feed(feed)

	conn = dh.create_connection()

	with conn:

		for show in shows:
			if dh.check_if_show_exists(show['link']) is False:
				showitems = (show['title'], show['episode'], show['quality'], show['tags'], show['category'], show['date'], show['link'])
				row_id = dh.add_release(conn, showitems)
				conn.commit()
				print "Added show to releases: %s, %s, %s, %s" % (show['title'], show['episode'], show['quality'], show['date'])

		dh.find_releases(conn)

