# -*- coding: utf8 -*-
import os
import requests
from bs4 import BeautifulSoup as bs
import csv
import datetime
import time
import logging
from urllib3.connectionpool import log as urllib3_log
import sqlite3

import lxml
import json
import re

import telebot
from telebot import types
from flask import Flask, request

from threading import Thread
#from multiprocessing import Process, freeze_support
import schedule
from datetime import datetime

#freeze_support()

# Укажите токен телеграм
telegram_token = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(telegram_token, threaded=False)
secret = os.getenv("SECRET")
url_ng = os.getenv("URL_NG")


app = Flask(__name__)

def setup_webhook():
	try:
		current_webhook = bot.get_webhook_info()
		if current_webhook.url != url_ng:
			# Снимаем вебхук перед повторной установкой (избавляет от некоторых проблем)
			bot.remove_webhook()
			# Ставим заново вебхук
			bot.set_webhook(url=url_ng)
			app.logger.info(f"Вебхук оновлено {url_ng}")
		else:
			app.logger.info("Вебхук вже оновлено")
	except Exception as e:
		app.logger.info(f"Помилка при встановлені вебхук: {e}")
		
setup_webhook()
# Функція для логування
# Основний лог файлайл
logging.basicConfig(
	filename='app.log',
	encoding='utf-8',
	level=logging.DEBUG,  # Рівень логування
	format='%(asctime)s - %(levelname)s - %(message)s',  # Формат повідомлень
)
# Створюємо хендлер для консолі
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
# Додаємо хендлер для app.log
app.logger.addHandler(console_handler)
app.logger.setLevel(logging.DEBUG)


@app.after_request
def after_request(response):
     timestamp = datetime.now().strftime('[%Y-%b-%d %H:%M]')
     app.logger.info('%s %s %s %s %s %s', timestamp, request.remote_addr, request.method, request.scheme, request.full_path, response.status)
     return response


@app.route('/', methods=['POST'])
def webhook():
		read = request.stream.read().decode('utf-8')
		update = telebot.types.Update.de_json(read)
		#app.logger.info(f"Обробляється chat_id: {update.message.chat.id}")
		bot.process_new_updates([update])
		return 'ok', 200

@app.route("/", methods=["HEAD", "GET"])
def home():
	app.logger.info(f"Запит від: {request.headers.get('User-Agent')}")
	return "Сервер працює!"	
	
	
def go_kvar(*args):
	try:
		#app.logger.info("Функція go_kvar  виконується...")
		headers = {
			"accept": "*/*",
			"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
			}

		# Укажите чат id в который необходимо отправлять данные
		telegram_chat_id = os.getenv("chat_id.KVAR")

		#Укажите URL для парсинга, так-же укажите все необходимые фильтры если необходимо
		base_url = 'https://www.olx.ua/uk/nedvizhimost/kvartiry/prodazha-kvartir/poltava/?currency=USD&search%5Bprivate_business%5D=private'

		base_url_telegram = 'https://api.telegram.org/bot'+telegram_token+'/sendMessage'

		# Генеруємо ім'я файлу з часом і датою
		#current_time = datetime.now().strftime("%d-%m-%Y_%H-%M")  # Формат: Рік-місяць-день_година-хвилина
		# Шлях до теки, де будуть зберігатися файли баз даних
		db_directory = "ad_db"
		# Перевіряємо, чи існує тека. Якщо ні — створюємо її.
		if not os.path.exists(db_directory):
			os.makedirs(db_directory)
			app.logger.info(f"Тека '{db_directory}' створена")
		# Формуємо шлях до файла бази даних всередині теки
		file_path = os.path.join(db_directory, f"ads_kkk.db")
		
		# Підключення до бази даних або створення нової
		conn = sqlite3.connect(file_path, check_same_thread=False)
		cursor = conn.cursor()
		
		# Перевірка чи є таблиця ads_kvar
		def ensure_table_exists(cursor):
			# Таблиця ads_kvar
			# Створення таблиці ads, якщо вона не існує
			cursor.execute("""
				CREATE TABLE IF NOT EXISTS ads (
					id_ads INTEGER PRIMARY KEY,
					url TEXT NOT NULL,
					title TEXT NOT NULL,
					price TEXT,
					date TEXT
				)
			""")
			conn.commit()
			# app.logger.info("Таблиця 'ads_kvar' перевірена або створена.")
		# Перевірка та створення таблиці
		ensure_table_exists(cursor)

		def olx_parse(base_url, headers):
			#app.logger.info("Розпочався парсинг сайту OLX.kvar")
			global start
			start = datetime.now()
			urls = []
			urls.append(base_url)
			ads = []
			#использую сессию
			session = requests.Session()
			request = session.get(base_url, headers=headers)
			#проверка ответа от сервера
			if request.status_code == 200:
				#app.logger.info("Успішне з'єднання з сайтом: OLX.kvar")
				soup = bs(request.content, "lxml")
				try:
					#определение последней страницы
						# Знаходимо div з атрибутом data-cy="pagination"
						pagination_div = soup.find('div', attrs={'data-cy': 'pagination'})
						# Знаходимо ul всередині pagination_div
						pagination_ul = pagination_div.find('ul')
						# Знаходимо останній li всередині ul
						last_li = pagination_ul.find_all('li')[-1]
						# Отримуємо href з елемента a всередині останнього li
						last_page_href = last_li.find('a')['href']
						# Виділяємо номер сторінки з href за допомогою регулярного виразу
						match = re.search(r'page=(\d+)', last_page_href)
						if match:
							number_of_last_page = int(match.group(1))
							app.logger.info(f"Номер останньої сторінки визначено OLX.kvar: {number_of_last_page}")
							# Ітерація по всіх сторінках
							for i in range(1, number_of_last_page + 1):
								try:
									# Розділення base_url на дві частини по USD
									base_url_parts = base_url.split('currency=USD')
									if len(base_url_parts) < 2:
										app.logger.error(f"Помилка OLX.kvar: базовий URL не містить параметра currency=USD. Base URL: {base_url}")
										continue
									# Формування нового URL з параметром page={i} після currency=USD
									url = f"{base_url_parts[0]}currency=USD&page={i}{base_url_parts[1]}"
									#app.logger.info(f"Згенеровано URL OLX.kvar:")
									# Перевірка URL перед додаванням
									if url not in urls:
										urls.append(url)
										#app.logger.info(f"URL успішно додано до списку OLX.kvar:")
									else:
										app.logger.warning(f"URL вже є у списку OLX.kvar:")
								except Exception as e:
									app.logger.error(f"Сталася помилка під час обробки сторінки OLX.kvar {i}: {e}")
						else:
							logging.error("Неможливо знайти номер останньої сторінки OLX.kvar")

				except:
					app.logger.info(f"Ітерація по сторінках не здійснена: OLX.kvar {num}")
					pass

				#итерация по всем страницам
				for url in urls:
					try:
						#app.logger.info(f"Початок обробки URL OLX.kvar:")
						request = session.get(url, headers=headers)
						soup = bs(request.content, 'lxml')
						trs = soup.find_all('div', attrs={'class': 'css-l9drzq'}) 
						#app.logger.info(f"Знайдено {len(trs)} оголошень на сторінці URL OLX.kvar")
						#поиск всех классов с объявлениями
						# Ітерація по кожному оголошенню
						for tr in trs:
							try:
								#Витяг інформації про оголошення
								dateRecord = tr.find('p', attrs={'class': 'css-vbz67q'}).text
								# забираем только сегодняшние обьявления
								if 'Сьогодні' in dateRecord:
									app.logger.info("Знайдено об'яву за сьогодні OLX.kvar")
									#Заголовок
									title = tr.find('h4', attrs={'class': 'css-1g61gc2'}).text
									app.logger.info(f"{title}")
									#Посилання
									href_a = tr.find('a', attrs={'class': 'css-1tqlkj0'})['href']
									href = "https://www.olx.ua" + href_a
									app.logger.info(f"{href}")
									#Ціна
									price = tr.find('p', attrs={'class': 'css-uj7mm0'}).text
									app.logger.info(f"{price}")
									#Номер ID
									# Відкриваємо детальну сторінку оголошення через знайдене посилання
									try:
										detail_response = session.get(href, headers=headers)
										# Логуємо статус відповіді
										app.logger.info(f"Відповідь сервера для {href}: {detail_response.status_code}")
										# Перевірка, чи запит пройшов успішно
										if detail_response.status_code == 200:
											detail_soup = bs(detail_response.content, 'lxml')
											# Спроба знайти потрібний елемент
											detail_ID_element = detail_soup.find('span', attrs={'class': 'css-w85dhy'})
											if detail_ID_element:
												detail_ID = detail_ID_element.text
												app.logger.info(f"Знайдено {detail_ID} ID OLX.kvar.AD")
												# Витягуємо ID за допомогою регулярного виразу
												re_ID = re.search(r'\d+', detail_ID)
												if re_ID:
													dataID = re_ID.group()
													app.logger.info(f"ID оголошення: {dataID}")
												else:
													app.logger.warning(f"Числове значення ID не знайдено на сторінці OLX.kvar.AD.")
											else:
												app.logger.warning(f"Елемент з класом 'css-w85dhy' не знайдено на сторінці {href}.")
										else:
											app.logger.error(f"Помилка доступу до сторінки OLX.kvar.AD. Статус сервера: {detail_response.status_code}")
									except Exception as e:
										app.logger.error(f"Помилка при обробці сторінки OLX.kvar.AD: {e}")
									if dataID:  # Перевіряємо, чи значення ID не пусте
										ads.append({
											'title': title,
											'url': href,
											'price': price,
											'id_ads': dataID,
											'date': dateRecord.strip()
										})
										#app.logger.info(f"Додано оголошення OLX.kvar: {ads}")
									else:
										app.logger.warning(f"Не вдалося додати оголошення без ID: {title}")
								else:
									#app.logger.info("Не знайдено об'яв за сьогодні OLX.kvar")
									print
							except Exception as e:
								app.logger.error(f"Помилка при ітерації оголошення на сторінці OLX.kvar: {e}")

					except Exception as e:
							app.logger.error(f"Помилка при обробці URL OLX.kvar {url}: {e}")
			else:
				app.logger.warning(f"Помилка підключення OLX.kvar, статус-код: {request.status_code}")
				app.logger.info('Error')
			end = datetime.now()
			app.logger.info(f"Time: {end-start}")
			return ads


		def send_to_db(id_ads, url, title, price, date):
		
			if int(id_ads) > 711800000:
				# Вставлення даних
				cursor.execute("INSERT INTO ads (id_ads, url, title, price, date) VALUES (?, ?, ?, ?, ?)", (id_ads, url, title, price, date))
				conn.commit()
				app.logger.info("Добавлено в БД")
			else:
				app.logger.info("Очень старое")


		def process_send(ads):
			for ad in ads:
					elem_exists = check_item_db(ad['id_ads'])
					# проверяем есть ли данный элемент в БД
					if not elem_exists and int(ad['id_ads'])>850000000:
						# Отправка в БД
						send_to_db(ad['id_ads'], ad['url'], ad['title'], ad['price'], ad['date'])
						# Отправка в телеграм
						send_telegram(ad['title'], ad['price'], ad['url'], ad['date'], ad['id_ads'])
						app.logger.info("БД дополненна")

		def check_item_db(id_ads):
			sql = 'SELECT * FROM ads WHERE id_ads=?'
			try:
				cursor.execute(sql, [(int(id_ads))])
				app.logger.info("Получено")
				return cursor.fetchone()  # Повертає результат запиту
			except sqlite3.OperationalError as e:
				app.logger.error(f"Помилка у запиті до БД: {e}")
				return None

		# Функція для надсилання повідомлення з файлом db
		#def send_db_file(telegram_chat_id, file_path):
			#with open(file_path, 'rb') as db_file:
				#bot.send_document(telegram_chat_id, db_file)
				#app.logger.info(f"Файл {file_path} успішно надіслано в Telegram!")
				
		# Функція для надсилання повідомлення з данними
		def send_telegram(title, url, price, date, id_ads):
			params = {	'chat_id': telegram_chat_id,
						'text': title+'\n'+url+'\n'+price+'\n'+date+'\n'+id_ads,	
						'parse_mode': (None, 'Markdown'),
						'reply_markup': json.dumps({"inline_keyboard":[[
										{"text":"\u267b\ufe0f","callback_data":"1"},
										{"text":"\ud83d\udcf4","callback_data":"2"},
										{"text":"\ud83c\udd71\ufe0f","callback_data":"3"}]]
										})
			}
			session = requests.Session()
			response = session.get(base_url_telegram, params=params)
			app.logger.info("Ok")

		ads = olx_parse(base_url, headers)
		process_send(ads)
		send_db_file(telegram_chat_id, file_path)
		
		app.logger.info('Все хорощо я закончил')

	except Exception as e:
		app.logger.info(f"Помилка у go_kvar: {e}")

def go_dom(*args):
	try:
		#app.logger.info("Функція go_dom виконується...")
		headers = {
			"accept": "*/*",
			"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36 OPR/60.0.3255.170"
		}

		# Укажите чат id в который необходимо отправлять данные
		telegram_chat_id = os.getenv("chat_id.DOM")

		#Укажите URL для парсинга, так-же укажите все необходимые фильтры если необходимо
		base_url = 'https://www.olx.ua/uk/nedvizhimost/doma/prodazha-domov/poltava/?currency=USD&search%5Bprivate_business%5D=private'

		base_url_telegram = 'https://api.telegram.org/bot'+telegram_token+'/sendMessage'

		# Генеруємо ім'я файлу з часом і датою
		#current_time = datetime.now().strftime("%d-%m-%Y_%H-%M")  # Формат: Рік-місяць-день_година-хвилина
		# Шлях до теки, де будуть зберігатися файли баз даних
		db_directory = "ad_db"
		# Перевіряємо, чи існує тека. Якщо ні — створюємо її.
		if not os.path.exists(db_directory):
			os.makedirs(db_directory)
			app.logger.info(f"Тека '{db_directory}' створена")
		# Формуємо шлях до файла бази даних всередині теки
		file_path = os.path.join(db_directory, f"ads_dom.db")
		
		# Підключення до бази даних або створення нової
		conn = sqlite3.connect(file_path, check_same_thread=False)
		cursor = conn.cursor()
		
		# Перевірка чи є таблиця ads_kvar
		def ensure_table_exists(cursor):
			# Таблиця ads_kvar
			# Створення таблиці ads, якщо вона не існує
			cursor.execute("""
				CREATE TABLE IF NOT EXISTS ads (
					id_ads INTEGER PRIMARY KEY,
					url TEXT NOT NULL,
					title TEXT NOT NULL,
					price TEXT,
					date TEXT
				)
			""")
			conn.commit()
			# app.logger.info("Таблиця 'ads_kvar' перевірена або створена.")
		# Перевірка та створення таблиці
		ensure_table_exists(cursor)

		def olx_parse(base_url, headers):
			#app.logger.info("Розпочався парсинг сайту OLX.dom")
			global start
			start = datetime.now()
			urls = []
			urls.append(base_url)
			ads = []
			#использую сессию
			session = requests.Session()
			request = session.get(base_url, headers=headers)
			#проверка ответа от сервера
			if request.status_code == 200:
				app.logger.info("Успішне з'єднання з сайтом: OLX.dom")
				soup = bs(request.content, "lxml")
				try:
					#определение последней страницы
						# Знаходимо div з атрибутом data-cy="pagination"
						pagination_div = soup.find('div', attrs={'data-cy': 'pagination'})
						# Знаходимо ul всередині pagination_div
						pagination_ul = pagination_div.find('ul')
						# Знаходимо останній li всередині ul
						last_li = pagination_ul.find_all('li')[-1]
						# Отримуємо href з елемента a всередині останнього li
						last_page_href = last_li.find('a')['href']
						# Виділяємо номер сторінки з href за допомогою регулярного виразу
						match = re.search(r'page=(\d+)', last_page_href)
						if match:
							number_of_last_page = int(match.group(1))
							app.logger.info(f"Номер останньої сторінки визначено OLX.dom: {number_of_last_page}")
							# Ітерація по всіх сторінках
							for i in range(1, number_of_last_page + 1):
								try:
									# Розділення base_url на дві частини по USD
									base_url_parts = base_url.split('currency=USD')
									if len(base_url_parts) < 2:
										app.logger.error(f"Помилка OLX.dom: базовий URL не містить параметра currency=USD. Base URL: {base_url}")
										continue
									# Формування нового URL з параметром page={i} після currency=USD
									url = f"{base_url_parts[0]}currency=USD&page={i}{base_url_parts[1]}"
									#app.logger.info(f"Згенеровано URL OLX.dom:")
									# Перевірка URL перед додаванням
									if url not in urls:
										urls.append(url)
										#app.logger.info(f"URL успішно додано до списку OLX.dom:")
									else:
										app.logger.warning(f"URL вже є у списку OLX.dom:")
								except Exception as e:
									app.logger.error(f"Сталася помилка під час обробки сторінки OLX.dom {i}: {e}")
						else:
							logging.error("Неможливо знайти номер останньої сторінки OLX.dom")

				except:
					app.logger.info(f"Ітерація по сторінках не здійснена: OLX.dom {num}")
					pass

				#итерация по всем страницам
				for url in urls:
					try:
						#app.logger.info(f"Початок обробки URL OLX.dom:")
						request = session.get(url, headers=headers)
						soup = bs(request.content, 'lxml')
						trs = soup.find_all('div', attrs={'class': 'css-l9drzq'}) 
						#app.logger.info(f"Знайдено {len(trs)} оголошень на сторінці URL OLX.dom")
						#поиск всех классов с объявлениями
						# Ітерація по кожному оголошенню
						for tr in trs:
							try:
								# Витяг інформації про оголошення
								dateRecord = tr.find('p', attrs={'class': 'css-vbz67q'}).text
								# забираем только сегодняшние обьявления
								if 'Сьогодні' in dateRecord:
									app.logger.info("Знайдено об'яву за сьогодні OLX.dom")
									#Заголовок
									title = tr.find('h4', attrs={'class': 'css-1g61gc2'}).text
									app.logger.info(f"{title}")
									#Посилання
									href_a = tr.find('a', attrs={'class': 'css-1tqlkj0'})['href']
									href = "https://www.olx.ua" + href_a
									app.logger.info(f"{href}")
									#Ціна
									price = tr.find('p', attrs={'class': 'css-uj7mm0'}).text
									app.logger.info(f"{price}")
									#Номер ID
									# Відкриваємо детальну сторінку оголошення через знайдене посилання
									try:
										detail_response = session.get(href, headers=headers)
										# Логуємо статус відповіді
										app.logger.info(f"Відповідь сервера для {href}: {detail_response.status_code}")
										# Перевірка, чи запит пройшов успішно
										if detail_response.status_code == 200:
											detail_soup = bs(detail_response.content, 'lxml')
											# Спроба знайти потрібний елемент
											detail_ID_element = detail_soup.find('span', attrs={'class': 'css-w85dhy'})
											if detail_ID_element:
												detail_ID = detail_ID_element.text
												app.logger.info(f"Знайдено {detail_ID} ID OLX.dom.AD")
												# Витягуємо ID за допомогою регулярного виразу
												re_ID = re.search(r'\d+', detail_ID)
												if re_ID:
													dataID = re_ID.group()
													app.logger.info(f"ID оголошення: {dataID}")
												else:
													app.logger.warning(f"Числове значення ID не знайдено на сторінці OLX.dom.AD.")
											else:
												app.logger.warning(f"Елемент з класом 'css-w85dhy' не знайдено на сторінці {href}.")
										else:
											app.logger.error(f"Помилка доступу до сторінки OLX.dom.AD. Статус сервера: {detail_response.status_code}")
									except Exception as e:
										app.logger.error(f"Помилка при обробці сторінки OLX.dom.AD: {e}")
									if dataID:  # Перевіряємо, чи значення ID не пусте
										ads.append({
											'title': title,
											'url': href,
											'price': price,
											'id_ads': dataID,
											'date': dateRecord.strip()
										})
										#app.logger.info(f"Додано оголошення OLX.dom {title} ({dataID})")
									else:
										app.logger.warning(f"Не вдалося додати оголошення без ID: {title}")
								else:
									print
									#app.logger.info("Не знайдено об'яв за сьогодні OLX.dom")
							except Exception as e:
								app.logger.error(f"Помилка при ітерації оголошення на сторінці OLX.dom: {e}")

					except Exception as e:
							app.logger.error(f"Помилка при обробці URL OLX.dom {url}: {e}")
			else:
				app.logger.warning(f"Помилка підключення OLX.dom, статус-код: {request.status_code}")
				app.logger.info('Error')
			end = datetime.now()
			app.logger.info(f"Time: {end-start}")
			return ads


		def send_to_db(id_ads, url, title, price, date):
			if int(id_ads) > 711800000:
				# Вставлення даних
				cursor.execute("INSERT INTO ads (id_ads, url, title, price, date) VALUES (?, ?, ?, ?, ?)", (id_ads, url, title, price, date))
				conn.commit()
				app.logger.info("Добавлено в БД")
			else:
				app.logger.info("Очень старое")


		def process_send(ads):
			for ad in ads:							
					elem_exists = check_item_db(ad['id_ads'])
					# проверяем есть ли данный элемент в БД
					if not elem_exists and int(ad['id_ads'])>850000000:
						# Отправка в БД
						send_to_db(ad['id_ads'], ad['url'], ad['title'], ad['price'], ad['date'])
						# Отправка в телеграм
						send_telegram(ad['title'], ad['price'], ad['url'], ad['date'], ad['id_ads'])
					app.logger.info("БД дополненна")

		def check_item_db(id_ads):
			sql = 'SELECT * FROM ads WHERE id_ads=?'
			try:
				cursor.execute(sql, [(int(id_ads))])
				app.logger.info("Получено")
				return cursor.fetchone()  # Повертає результат запиту
			except sqlite3.OperationalError as e:
				app.logger.error(f"Помилка у запиті до БД: {e}")
				return None
				
		# Функція для надсилання повідомлення з файлом db
		#def send_db_file(telegram_chat_id, file_path):
			#with open(file_path, 'rb') as db_file:
				#bot.send_document(telegram_chat_id, db_file)
				#app.logger.info(f"Файл {file_path} успішно надіслано в Telegram!")

		def send_telegram(title, url, price, date, id_ads):
			params = {	'chat_id': telegram_chat_id,
						'text': title+'\n'+url+'\n'+price+'\n'+date+'\n'+id_ads,	
						'parse_mode': (None, 'Markdown'),
						'reply_markup': json.dumps({"inline_keyboard":[[
										{"text":"\u267b\ufe0f","callback_data":"1"},
										{"text":"\ud83d\udcf4","callback_data":"2"},
										{"text":"\ud83c\udd71\ufe0f","callback_data":"3"}]]
										})
			}
			session = requests.Session()
			response = session.get(base_url_telegram, params=params)
			app.logger.info("Ok")

		ads = olx_parse(base_url, headers)
		process_send(ads)
		send_db_file(telegram_chat_id, file_path)
		
		app.logger.info('Все хорощо я закончил')

	except Exception as e:
		app.logger.info(f"Помилка у go_dom: {e}")

	



# Обработчик нажатий на кнопки 
@bot.callback_query_handler(func=lambda call: True) 
def callback_worker(call):
		# Если нажали на 1 кнопку
		if call.data == '3':
			cid = call.message.chat.id
			mid = call.message.message_id 
			tex = call.message.text
			markup = types.InlineKeyboardMarkup()
			markup.row(
				types.InlineKeyboardButton("\u267b\ufe0f", callback_data='1'),
				types.InlineKeyboardButton("\ud83d\udcf4", callback_data='2'),
				types.InlineKeyboardButton("\ud83c\udd71\ufe0f 1", callback_data='3'))
			bot.edit_message_text(chat_id=cid, message_id=mid, text=tex, reply_markup=markup)
		# Если нажали на 2 кнопку
		elif call.data == '2': 
			cid = call.message.chat.id
			mid = call.message.message_id 
			tex = call.message.text
			markup = types.InlineKeyboardMarkup()
			markup.row(
				types.InlineKeyboardButton("\u267b\ufe0f", callback_data='1'),
				types.InlineKeyboardButton("\ud83d\udcf4 1", callback_data='2'),
				types.InlineKeyboardButton("\ud83c\udd71\ufe0f", callback_data='3'))
			bot.edit_message_text(chat_id=cid, message_id=mid, text=tex, reply_markup=markup)
		# Если нажали на 3 кнопку
		else:
			cid = call.message.chat.id
			mid = call.message.message_id 
			tex = call.message.text
			markup = types.InlineKeyboardMarkup()
			markup.row(types.InlineKeyboardButton("\u267b\ufe0f 1", callback_data='1'),
				types.InlineKeyboardButton("\ud83d\udcf4", callback_data='2'),
				types.InlineKeyboardButton("\ud83c\udd71\ufe0f", callback_data='3'))
			bot.edit_message_text(chat_id=cid, message_id=mid, text=tex, reply_markup=markup)
		
def start_background_scheduler():
	if not schedule.jobs: #Щоб не запускався двічі
		try:
			Thread(target=go_kvar, daemon=True).start()
			Thread(target=go_dom, daemon=True).start()
			#app.logger.info("Потік для планувальника запущено.")
		except Exception as e:
			app.logger.error(f"Помилка запуску планувальнику: {e}")			

@bot.message_handler(commands=['help'])
def process_help_command(message):
	bot.reply_to(message, "Якщо ви не бачите кнопки. - потрібно відправити команду /start")

@bot.message_handler(commands=['start'])
def send_welcome(message):
	# Створюємо меню
	keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
	button_run = types.KeyboardButton('🏢 🏠')
	keyboard.add(button_run)

	# Відправляємо повідомлення з меню
	bot.send_message(message.chat.id, " ", reply_markup=keyboard)

# Обробник натискань кнопок
@bot.message_handler(func=lambda message: message.text == '🏢 🏠')
def handle_kvar_button(message):
	try:
		#bot.reply_to(message, "Відповідь надсилається в чат 🏢 🏠")
		start_background_scheduler()
		bot.send_chat_action(message.chat.id, 'typing')
  # Викликаємо функцію go_kvar
	except Exception as e:
		bot.reply_to(message, f"Сталася помилка: {e}")
		app.logger.error(f"Помилка після натискання кнопки{e}")

#@bot.message_handler(func=lambda message: message.text == '🏠 Дома')
#def handle_dom_button(message):
	#try:
		#bot.reply_to(message, "Відповідь надсилається в чат 🏠 Дома")
		#go_dom()  # Викликаємо функцію go_dom
	#except Exception as e:
		#bot.reply_to(message, f"Сталася помилка: {e}")
		#app.logger.error(f"Помилка після натискання кнопки go_dom {e}")

@bot.message_handler(commands=['run'])
def run_command(message):
		try:
		start_background_scheduler()
		bot.send_chat_action(message.chat.id, 'typing')
	except Exception as e:
		app.logger.error(f"Помилка для chat_id {message.chat.id}: {e}")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
	try:
		bot.reply_to(message, message.text)
	except Exception as e:
		app.logger.error(f"Помилка для chat_id {message.chat.id}: {e}")
		
	

# Функція для запуску планувальника
#def run_scheduler():
	#try:
		#app.logger.info("Планувальник запущений.")
		#schedule.every(5).hours.do(go_kvar)
		#schedule.every(5).hours.do(go_dom)
		#while True:
			#schedule.run_pending()
			#app.logger.info("Задачі в очикуванні")
			#time.sleep(60)
	#except Exception as e:
		#app.logger.error(f"Помилка в функції планувальнику: {e}")
		
	# Запуск планувальника в окремому процесі
	#scheduler_process = Process(target=run_scheduler)
	#scheduler_process.start()  # Додано запуск процесу
	
