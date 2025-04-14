# -*- coding: utf8 -*-
import os
import requests
from bs4 import BeautifulSoup as bs
import csv
import datetime
import logging
from urllib3.connectionpool import log as urllib3_log
import sqlite3

import lxml
import json
import re

import telebot
from telebot import types
from flask import Flask, request

from datetime import datetime
import time
from time import sleep

import threading

# Спочатку встановлюємо рівень логування для urllib3
urllib3_log.setLevel(logging.WARNING)  # Відображати тільки попередження або помилки
# Функція для логування
logging.basicConfig(
    level=logging.DEBUG,  # Рівень логування
    format='%(asctime)s - %(levelname)s - %(message)s',  # Формат повідомлень
    handlers=[
        logging.FileHandler("app.log"),  # Логи у файл
        logging.StreamHandler()  # Виведення в консоль
    ]
)

# Укажите токен телеграм
telegram_token = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(telegram_token, threaded=False)
secret = os.getenv("SECRET")
url_ng = os.getenv("URL_NG")



app = Flask(__name__)

@app.route('/', methods=['POST'])
def webhook():
		read = request.stream.read().decode('utf-8')
		update = telebot.types.Update.de_json(read)
		#print(update)
		bot.process_new_updates([update])
		return 'ok', 200

@app.route("/", methods=["GET"])
def home():
	return "Сервер працює!"	
	
	
def go_kvar(*args):
	while True:
		time_now = datetime.now()
		#print("time_now =", time_now)
		time_string = time_now.strftime("%H:%M:%S") #dt_string = time_now.strftime("%d/%m/%Y %H:%M:%S")
		#print("time =", time_string)
		t = tuple(int(i) for i in time_string.split(':'))

		if 8 < t[0] < 20:
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
					print(f"Тека '{db_directory}' створена")
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
					# logging.info("Таблиця 'ads_kvar' перевірена або створена.")
				# Перевірка та створення таблиці
				ensure_table_exists(cursor)

				def olx_parse(base_url, headers):
					logging.info("Розпочався парсинг сайту OLX.kvar")
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
						logging.info("Успішне з'єднання з сайтом: OLX.kvar")
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
									logging.info(f"Номер останньої сторінки визначено OLX.kvar: {number_of_last_page}")
									# Ітерація по всіх сторінках
									for i in range(1, number_of_last_page + 1):
										try:
											# Розділення base_url на дві частини по USD
											base_url_parts = base_url.split('currency=USD')
											if len(base_url_parts) < 2:
												logging.error(f"Помилка OLX.kvar: базовий URL не містить параметра currency=USD. Base URL: {base_url}")
												continue
											# Формування нового URL з параметром page={i} після currency=USD
											url = f"{base_url_parts[0]}currency=USD&page={i}{base_url_parts[1]}"
											#logging.info(f"Згенеровано URL OLX.kvar:")
											# Перевірка URL перед додаванням
											if url not in urls:
												urls.append(url)
												#logging.info(f"URL успішно додано до списку OLX.kvar:")
											else:
												logging.warning(f"URL вже є у списку OLX.kvar:")
										except Exception as e:
											logging.error(f"Сталася помилка під час обробки сторінки OLX.kvar {i}: {e}")
								else:
									logging.error("Неможливо знайти номер останньої сторінки OLX.kvar")

						except:
							logging.info(f"Ітерація по сторінках не здійснена: OLX.kvar {num}")
							pass

						#итерация по всем страницам
						for url in urls:
							try:
								#logging.info(f"Початок обробки URL OLX.kvar:")
								request = session.get(url, headers=headers)
								soup = bs(request.content, 'lxml')
								trs = soup.find_all('div', attrs={'class': 'css-l9drzq'}) 
								#logging.info(f"Знайдено {len(trs)} оголошень на сторінці URL OLX.kvar")
								#поиск всех классов с объявлениями
								# Ітерація по кожному оголошенню
								for tr in trs:
									try:
										#Витяг інформації про оголошення
										dateRecord = tr.find('p', attrs={'class': 'css-vbz67q'}).text
										# забираем только сегодняшние обьявления
										if 'Сьогодні' in dateRecord:
											logging.info("Знайдено об'яву за сьогодні OLX.kvar")
											#Заголовок
											title = tr.find('h4', attrs={'class': 'css-1g61gc2'}).text
											logging.info(f"{title}")
											#Посилання
											href_a = tr.find('a', attrs={'class': 'css-1tqlkj0'})['href']
											href = "https://www.olx.ua" + href_a
											logging.info(f"{href}")
											#Ціна
											price = tr.find('p', attrs={'class': 'css-uj7mm0'}).text
											logging.info(f"{price}")
											#Номер ID
											# Відкриваємо детальну сторінку оголошення через знайдене посилання
											try:
												detail_response = session.get(href, headers=headers)
												# Логуємо статус відповіді
												logging.info(f"Відповідь сервера для {href}: {detail_response.status_code}")
												# Перевірка, чи запит пройшов успішно
												if detail_response.status_code == 200:
													detail_soup = bs(detail_response.content, 'lxml')
													# Спроба знайти потрібний елемент
													detail_ID_element = detail_soup.find('span', attrs={'class': 'css-w85dhy'})
													if detail_ID_element:
														detail_ID = detail_ID_element.text
														logging.info(f"Знайдено {detail_ID} ID OLX.kvar.AD")
														# Витягуємо ID за допомогою регулярного виразу
														re_ID = re.search(r'\d+', detail_ID)
														if re_ID:
															dataID = re_ID.group()
															logging.info(f"ID оголошення: {dataID}")
														else:
															logging.warning(f"Числове значення ID не знайдено на сторінці OLX.kvar.AD.")
													else:
														logging.warning(f"Елемент з класом 'css-w85dhy' не знайдено на сторінці {href}.")
												else:
													logging.error(f"Помилка доступу до сторінки OLX.kvar.AD. Статус сервера: {detail_response.status_code}")
											except Exception as e:
												logging.error(f"Помилка при обробці сторінки OLX.kvar.AD: {e}")
											if dataID:  # Перевіряємо, чи значення ID не пусте
												ads.append({
													'title': title,
													'url': href,
													'price': price,
													'id_ads': dataID,
													'date': dateRecord.strip()
												})
												logging.info(f"Додано оголошення OLX.kvar: {ads}")
											else:
												logging.warning(f"Не вдалося додати оголошення без ID: {title}")
										else:
											#logging.info("Не знайдено об'яв за сьогодні OLX.kvar")
											print
									except Exception as e:
										logging.error(f"Помилка при ітерації оголошення на сторінці OLX.kvar: {e}")

							except Exception as e:
									logging.error(f"Помилка при обробці URL OLX.kvar {url}: {e}")
					else:
						logging.warning(f"Помилка підключення OLX.kvar, статус-код: {request.status_code}")
						print('Error')
					end = datetime.now()
					print(f"Time: {end-start}")
					return ads


				def send_to_db(id_ads, url, title, price, date):
				
					if int(id_ads) > 711800000:
						# Вставлення даних
						cursor.execute("INSERT INTO ads (id_ads, url, title, price, date) VALUES (?, ?, ?, ?, ?)", (id_ads, url, title, price, date))
						conn.commit()
						print("Добавлено в БД")
					else:
						print("Очень старое")


				def process_send(ads):
					for ad in ads:
							elem_exists = check_item_db(ad['id_ads'])
							# проверяем есть ли данный элемент в БД
							if not elem_exists and int(ad['id_ads'])>850000000:
								# Отправка в БД
								send_to_db(ad['id_ads'], ad['url'], ad['title'], ad['price'], ad['date'])
								# Отправка в телеграм
								send_telegram(ad['title'], ad['price'], ad['url'], ad['date'], ad['id_ads'])
								print("БД дополненна")

				def check_item_db(id_ads):
					sql = 'SELECT * FROM ads WHERE id_ads=?'
					try:
						cursor.execute(sql, [(int(id_ads))])
						print("Получено")
						return cursor.fetchone()  # Повертає результат запиту
					except sqlite3.OperationalError as e:
						logging.error(f"Помилка у запиті до БД: {e}")
						return None

				# Функція для надсилання повідомлення з файлом db
				def send_db_file(telegram_chat_id, file_path):
					with open(file_path, 'rb') as db_file:
						bot.send_document(telegram_chat_id, db_file)
						print(f"Файл {file_path} успішно надіслано в Telegram!")
						
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
					print ("Ok")

				ads = olx_parse(base_url, headers)
				process_send(ads)
				send_db_file(telegram_chat_id, file_path)
				
				print ('Все хорощо я закончил')
				time.sleep(7200) #7200 sec
				print("time =", t)
		else:
			print('sleep 46800 sec')
			time.sleep(46800)


def go_dom(*args):
	while True:
		time_now = datetime.now()
		#print("time_now =", time_now)
		time_string = time_now.strftime("%H:%M:%S") #dt_string = time_now.strftime("%d/%m/%Y %H:%M:%S")
		#print("time =", time_string)
		t = tuple(int(i) for i in time_string.split(':'))

		if 8 < t[0] < 20:
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
					print(f"Тека '{db_directory}' створена")
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
					# logging.info("Таблиця 'ads_kvar' перевірена або створена.")
				# Перевірка та створення таблиці
				ensure_table_exists(cursor)

				def olx_parse(base_url, headers):
					logging.info("Розпочався парсинг сайту OLX.dom")
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
						logging.info("Успішне з'єднання з сайтом: OLX.dom")
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
									logging.info(f"Номер останньої сторінки визначено OLX.dom: {number_of_last_page}")
									# Ітерація по всіх сторінках
									for i in range(1, number_of_last_page + 1):
										try:
											# Розділення base_url на дві частини по USD
											base_url_parts = base_url.split('currency=USD')
											if len(base_url_parts) < 2:
												logging.error(f"Помилка OLX.dom: базовий URL не містить параметра currency=USD. Base URL: {base_url}")
												continue
											# Формування нового URL з параметром page={i} після currency=USD
											url = f"{base_url_parts[0]}currency=USD&page={i}{base_url_parts[1]}"
											#logging.info(f"Згенеровано URL OLX.dom:")
											# Перевірка URL перед додаванням
											if url not in urls:
												urls.append(url)
												#logging.info(f"URL успішно додано до списку OLX.dom:")
											else:
												logging.warning(f"URL вже є у списку OLX.dom:")
										except Exception as e:
											logging.error(f"Сталася помилка під час обробки сторінки OLX.dom {i}: {e}")
								else:
									logging.error("Неможливо знайти номер останньої сторінки OLX.dom")

						except:
							logging.info(f"Ітерація по сторінках не здійснена: OLX.dom {num}")
							pass

						#итерация по всем страницам
						for url in urls:
							try:
								#logging.info(f"Початок обробки URL OLX.dom:")
								request = session.get(url, headers=headers)
								soup = bs(request.content, 'lxml')
								trs = soup.find_all('div', attrs={'class': 'css-l9drzq'}) 
								#logging.info(f"Знайдено {len(trs)} оголошень на сторінці URL OLX.dom")
								#поиск всех классов с объявлениями
								# Ітерація по кожному оголошенню
								for tr in trs:
									try:
										# Витяг інформації про оголошення
										dateRecord = tr.find('p', attrs={'class': 'css-vbz67q'}).text
										# забираем только сегодняшние обьявления
										if 'Сьогодні' in dateRecord:
											logging.info("Знайдено об'яву за сьогодні OLX.dom")
											#Заголовок
											title = tr.find('h4', attrs={'class': 'css-1g61gc2'}).text
											logging.info(f"{title}")
											#Посилання
											href_a = tr.find('a', attrs={'class': 'css-1tqlkj0'})['href']
											href = "https://www.olx.ua" + href_a
											logging.info(f"{href}")
											#Ціна
											price = tr.find('p', attrs={'class': 'css-uj7mm0'}).text
											logging.info(f"{price}")
											#Номер ID
											# Відкриваємо детальну сторінку оголошення через знайдене посилання
											try:
												detail_response = session.get(href, headers=headers)
												# Логуємо статус відповіді
												logging.info(f"Відповідь сервера для {href}: {detail_response.status_code}")
												# Перевірка, чи запит пройшов успішно
												if detail_response.status_code == 200:
													detail_soup = bs(detail_response.content, 'lxml')
													# Спроба знайти потрібний елемент
													detail_ID_element = detail_soup.find('span', attrs={'class': 'css-w85dhy'})
													if detail_ID_element:
														detail_ID = detail_ID_element.text
														logging.info(f"Знайдено {detail_ID} ID OLX.dom.AD")
														# Витягуємо ID за допомогою регулярного виразу
														re_ID = re.search(r'\d+', detail_ID)
														if re_ID:
															dataID = re_ID.group()
															logging.info(f"ID оголошення: {dataID}")
														else:
															logging.warning(f"Числове значення ID не знайдено на сторінці OLX.dom.AD.")
													else:
														logging.warning(f"Елемент з класом 'css-w85dhy' не знайдено на сторінці {href}.")
												else:
													logging.error(f"Помилка доступу до сторінки OLX.dom.AD. Статус сервера: {detail_response.status_code}")
											except Exception as e:
												logging.error(f"Помилка при обробці сторінки OLX.dom.AD: {e}")
											if dataID:  # Перевіряємо, чи значення ID не пусте
												ads.append({
													'title': title,
													'url': href,
													'price': price,
													'id_ads': dataID,
													'date': dateRecord.strip()
												})
												logging.info(f"Додано оголошення OLX.kvar: {title} ({dataID})")
											else:
												logging.warning(f"Не вдалося додати оголошення без ID: {title}")
										else:
											print
											#logging.info("Не знайдено об'яв за сьогодні OLX.dom")
									except Exception as e:
										logging.error(f"Помилка при ітерації оголошення на сторінці OLX.dom: {e}")

							except Exception as e:
									logging.error(f"Помилка при обробці URL OLX.dom {url}: {e}")
					else:
						logging.warning(f"Помилка підключення OLX.dom, статус-код: {request.status_code}")
						print('Error')
					end = datetime.now()
					print(f"Time: {end-start}")
					return ads


				def send_to_db(id_ads, url, title, price, date):
					if int(id_ads) > 711800000:
						# Вставлення даних
						cursor.execute("INSERT INTO ads (id_ads, url, title, price, date) VALUES (?, ?, ?, ?, ?)", (id_ads, url, title, price, date))
						conn.commit()
						print("Добавлено в БД")
					else:
						print("Очень старое")


				def process_send(ads):
					for ad in ads:							
							elem_exists = check_item_db(ad['id_ads'])
							# проверяем есть ли данный элемент в БД
							if not elem_exists and int(ad['id_ads'])>850000000:
								# Отправка в БД
								send_to_db(ad['id_ads'], ad['url'], ad['title'], ad['price'], ad['date'])
								# Отправка в телеграм
								send_telegram(ad['title'], ad['price'], ad['url'], ad['date'], ad['id_ads'])
							print("БД дополненна")

				def check_item_db(id_ads):
					sql = 'SELECT * FROM ads WHERE id_ads=?'
					try:
						cursor.execute(sql, [(int(id_ads))])
						print("Получено")
						return cursor.fetchone()  # Повертає результат запиту
					except sqlite3.OperationalError as e:
						logging.error(f"Помилка у запиті до БД: {e}")
						return None
						
				# Функція для надсилання повідомлення з файлом db
				def send_db_file(telegram_chat_id, file_path):
					with open(file_path, 'rb') as db_file:
						bot.send_document(telegram_chat_id, db_file)
						print(f"Файл {file_path} успішно надіслано в Telegram!")

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
					print ("Ok")

				ads = olx_parse(base_url, headers)
				process_send(ads)
				send_db_file(telegram_chat_id, file_path)
				
				print ('Все хорощо я закончил')
				time.sleep(7200) #7200 sec
				print("time =", t)
		else:
			print('sleep 46800 sec')
			time.sleep(46800)


	



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
		


@bot.message_handler(commands=['help'])
def process_help_command(message):
	bot.reply_to(message, "Напиши мне что-нибудь, и я отпрпавлю этот текст тебе в ответ!")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
	bot.reply_to(message, message.text)
		
# Снимаем вебхук перед повторной установкой (избавляет от некоторых проблем)
bot.remove_webhook()
# Ставим заново вебхук
bot.set_webhook(url=url_ng)		
	
if __name__ == "__main__":
	threading.Thread(target=go_kvar, args=(1,)).start()
	threading.Thread(target=go_dom, args=(1,)).start()
	#Встановлюємо порт із змінної середовища або використовуємо порт за замовчуванням
	PORT = int(os.getenv("PORT", 10000))
	app.run(host="0.0.0.0", port=PORT)