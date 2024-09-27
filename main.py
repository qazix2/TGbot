import telebot
import random
import requests
from datetime import datetime, timedelta
import sqlite3

# Токен бота
TOKEN = '7235619947:AAGNvj_LTl1B9W3IdRpmvX-JEtBKUIk9iDk'
bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных SQLite
conn = sqlite3.connect('soberup.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц, если их нет
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY, 
                    username TEXT, 
                    score REAL, 
                    last_use DATETIME,
                    group_id INTEGER,
                    pulls REAL DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS groups (
                    group_id INTEGER PRIMARY KEY, 
                    group_name TEXT, 
                    total_score REAL)''')

# Переменные для курса
exchange_rate = None
last_update = None

def update_exchange_rate():
    global exchange_rate, last_update
    if last_update is None or (datetime.now() - last_update).total_seconds() > 300:  # 5 минут
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")  # Пример API
        data = response.json()
        exchange_rate = data['rates']['RUB']
        last_update = datetime.now()

# Функция, которая выдает случайные очки от 0.3 до 3.0 и обновляет базу данных
@bot.message_handler(commands=['soberup'])
def sober_up(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    now = datetime.now()
    group_id = message.chat.id  # Используем ID чата как ID группы

    cursor.execute('SELECT score, last_use FROM users WHERE user_id = ?',
                   (user_id, ))
    result = cursor.fetchone()

    if result is None:
        score = random.uniform(0.3, 3.0)
        cursor.execute(
            'INSERT INTO users (user_id, username, score, last_use, group_id) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, score, now, group_id))
        conn.commit()
        bot.reply_to(
            message,
            f"{username}, вы отрезвели на {round(score, 2)} промили!")

        # Обновляем информацию о группе
        cursor.execute('SELECT total_score FROM groups WHERE group_id = ?',
                       (group_id, ))
        group_result = cursor.fetchone()
        if group_result is None:
            cursor.execute(
                'INSERT INTO groups (group_id, group_name, total_score) VALUES (?, ?, ?)',
                (group_id, message.chat.title, score))
        else:
            cursor.execute(
                'UPDATE groups SET total_score = total_score + ? WHERE group_id = ?',
                (score, group_id))
        conn.commit()
    else:
        last_use, score = result[1], result[0]
        if last_use is not None and now - datetime.strptime(
                last_use, '%Y-%m-%d %H:%M:%S.%f') < timedelta(hours=1):
            remaining_time = timedelta(hours=1) - (
                now - datetime.strptime(last_use, '%Y-%m-%d %H:%M:%S.%f'))
            bot.reply_to(
                message,
                f"Подождите еще {str(remaining_time).split('.')[0]} до покупки боржоми."
            )
        else:
            new_score = random.uniform(0.3, 3.0)
            cursor.execute(
                'UPDATE users SET score = score + ?, last_use = ? WHERE user_id = ?',
                (new_score, now, user_id))
            conn.commit()
            bot.reply_to(
                message,
                f"{username}, вы отрезвели на {round(new_score, 2)} промили! Теперь у вас - {round(score + new_score, 2)} промиль."
            )

            # Обновляем информацию о группе
            cursor.execute(
                'UPDATE groups SET total_score = total_score + ? WHERE group_id = ?',
                (new_score, group_id))
            conn.commit()

# Функция, которая выводит топ игроков
@bot.message_handler(commands=['top'])
def show_top(message):
    cursor.execute(
        'SELECT username, score FROM users ORDER BY score DESC LIMIT 10')
    top_users = cursor.fetchall()

    if top_users:
        response = "🏆 Топ игроков за всё время:\n\n"
        for i, (username, score) in enumerate(top_users, start=1):
            response += f"{i}. {username} — -{round(score, 2)} промиль\n"
    else:
        response = "Топ игроков пока пуст."

    bot.reply_to(message, response)

# Функция, которая выводит топ групп за всё время
@bot.message_handler(commands=['top_groups'])
def show_top_groups(message):
    cursor.execute(
        'SELECT group_name, total_score FROM groups ORDER BY total_score DESC LIMIT 10'
    )
    top_groups = cursor.fetchall()

    if top_groups:
        response = "🏆 Топ групп по трезвости за всё время:\n\n"
        for i, (group_name, total_score) in enumerate(top_groups, start=1):
            response += f"{i}. {group_name} — -{round(total_score, 2)} промиль\n"
    else:
        response = "Топ групп пока пуст."

    bot.reply_to(message, response)

# Функция, которая выводит топ групп за сегодня
@bot.message_handler(commands=['top_groups_today'])
def show_top_groups_today(message):
    today_start = datetime.now().replace(hour=0,
                                         minute=0,
                                         second=0,
                                         microsecond=0)
    cursor.execute(
        '''SELECT g.group_name, SUM(u.score) 
                      FROM users u 
                      JOIN groups g ON u.group_id = g.group_id 
                      WHERE u.last_use >= ? 
                      GROUP BY g.group_id 
                      ORDER BY SUM(u.score) DESC LIMIT 10''', (today_start, ))
    top_groups_today = cursor.fetchall()

    if top_groups_today:
        response = "🏆 Топ групп по трезвости за сегодня:\n\n"
        for i, (group_name, total_score) in enumerate(top_groups_today,
                                                      start=1):
            response += f"{i}. {group_name} — -{round(total_score, 2)} промиль\n"
    else:
        response = "Топ групп за сегодня пока пуст."

    bot.reply_to(message, response)

# Функция для получения курса доллара к рублю
@bot.message_handler(commands=['kurs'])
def show_kurs(message):
    update_exchange_rate()
    if exchange_rate:
        pull_to_promile = round(exchange_rate / 10, 2)  # Пример для 1 пулла
        bot.reply_to(message, f"1 пулл стоит {pull_to_promile:.2f} промили.")
    else:
        bot.reply_to(message, "Не удалось получить курс пулла к промили.")

# Функция для отображения количества пуллов
@bot.message_handler(commands=['pulls'])
def show_pulls(message):
    user_id = message.from_user.id
    cursor.execute('SELECT pulls FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result is None:
        bot.reply_to(message, "У вас пока нет пуллов.")
    else:
        pulls = result[0]
        bot.reply_to(message, f"У вас {round(pulls, 2)} пуллов на счету.")

# Функция перевода пуллов другому пользователю
@bot.message_handler(commands=['transfer'])
def transfer_pulls(message):
    user_id = message.from_user.id
    try:
        # Разделяем сообщение, чтобы получить данные
        _, target_username, amount_str = message.text.split()
        amount = float(amount_str)

        # Проверяем баланс пользователя
        cursor.execute('SELECT pulls FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result is None or result[0] < amount or result[0]  < 0 or amount < 0:
            bot.reply_to(message, "Недостаточно пуллов на счете.")
            return

        # Ищем пользователя-получателя
        cursor.execute('SELECT user_id FROM users WHERE username = ?', (target_username,))
        target_result = cursor.fetchone()
        if target_result is None:
            bot.reply_to(message, "Получатель не найден.")
            return

        target_user_id = target_result[0]

        # Обновляем балансы
        cursor.execute('UPDATE users SET pulls = pulls - ? WHERE user_id = ?', (amount, user_id))
        cursor.execute('UPDATE users SET pulls = pulls + ? WHERE user_id = ?', (amount, target_user_id))
        conn.commit()

        bot.reply_to(message, f"Вы успешно перевели {round(amount, 2)} пуллов пользователю {target_username}.")

    except ValueError:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /transfer <username> <amount>")
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка при переводе пуллов.")

# Функция для обмена промилей на пуллы по курсу
@bot.message_handler(commands=['exchange'])
def exchange_promile_to_pulls(message):

    user_id = message.from_user.id
    update_exchange_rate()

    # Проверяем баланс пользователя
    cursor.execute('SELECT score, pulls FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result is None:
        bot.reply_to(message, "У вас нет промилей для обмена.")
        return

    promile_score, current_pulls = result

    # Рассчитываем, сколько пуллов можно получить за промили
    pull_to_promile = round(exchange_rate / 10, 2)  # Пример: 1 пулл за определенное количество промилей

    if promile_score < pull_to_promile:
        bot.reply_to(message, f"Недостаточно промилей для обмена. Нужно хотя бы {pull_to_promile:.2f} промилей.")
    else:
        # Вычитаем количество промилей и добавляем пуллы
        new_pulls = promile_score // pull_to_promile
        new_score = promile_score % pull_to_promile

        cursor.execute('UPDATE users SET score = ?, pulls = pulls + ? WHERE user_id = ?',
                       (new_score, new_pulls, user_id))
        conn.commit()

        bot.reply_to(message, f"Вы обменяли {round(promile_score - new_score, 2)} промилей на {int(new_pulls)} пуллов. Теперь у вас {round(new_score, 2)} промилей и {round(current_pulls + new_pulls, 2)} пуллов.")

# Функция для помощи с командами
@bot.message_handler(commands=['help'])
def help(message):
    bot.reply_to(message, """Команды:
/top - топ 10 игроков
/top_groups - топ 10 групп
/top_groups_today - топ 10 групп за сегодня
/soberup - получить промили
/kurs - узнать курс
/pulls - посмотреть количество пуллов
/transfer <username> <amount> - перевести пуллы другому пользователю
/exchange - обменять промили на пуллы
/help - это сообщение.""")

# Запуск бота
bot.polling(none_stop=True)