import os
from flask import Flask, render_template, request, jsonify
from pony.orm import db_session, desc, select
from models import Menu, MenuItem, Thesis, FlowSubscription, Admin, Docs
from config import bot_token
import telebot
import logging


app = Flask(__name__)

bot = telebot.TeleBot(bot_token)
logger = telebot.logger
telebot.logger.setLevel(logging.DEBUG)


@app.route('/')
def main():
    return render_template('index.html')


@app.route('/update')
@db_session
def update_thesis():
    last_thesis = Thesis.select().order_by(desc(Thesis.id)).first()
    if last_thesis is None:
        return 'There is no thesises right now', 404
    elif last_thesis.text != request.args['text']:
        data = {}
        data['speaker'] = last_thesis.speaker
        data['text'] = last_thesis.text
        return jsonify(data)
    return 'Nothing to update', 404


@app.route('/promote')
def promote():
    bot.send_message('@SberRoof_chat', 'Бип-боп!🤖 Хэй, друзья!\nХотите освежить память и ознакомиться со всеми тезисами спикеров?\n' \
                     'Милости прошу в свой новый раздел "Тезисы"😉')


@app.route("/msg", methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200


@app.route("/msg")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url="https://sber-roof.herokuapp.com/msg")
    return "!", 200


@bot.message_handler(commands=['start'])
@db_session
def handle_start(message):
    '''Handling first interaction with user'''

    bot.send_message(message.chat.id, 'Я знаю все о ВЫШЕ КРЫШ! Что подсказать?🤓', reply_markup=Menu['start'].get_markup())


@bot.message_handler(commands=['admin'])
@db_session
def handle_admin(message):
    '''Admin section'''
    admin = Admin.get(chat_id=message.chat.id)
    if admin is not None:
        bot.send_message(message.chat.id,
                        'Добби хочет спросить, когда он получит носок?\nВыбирай спикера, чтобы увековечить его тезис',
                        reply_markup=Menu['speakers'].get_markup())
        admin.in_section = True
    else:
        bot.send_message(message.chat.id,
                        'Ты кто такой? Я тебя не звал! А нука возвращайся /start')


@bot.message_handler(content_types=['photo'])
@db_session
def handle_photos(message):
    if Admin.exists(chat_id=message.chat.id):
        bot.send_message(message.chat.id, 'PHOTO: ' + message.photo[-1].file_id)


@bot.message_handler(content_types=['video'])
@db_session
def handle_videos(message):
    if Admin.exists(chat_id=message.chat.id):
        bot.send_message(message.chat.id, 'VIDEO: ' + message.video.file_id)


@bot.message_handler(content_types=['document'])
@db_session
def handle_docs(message):
    if Admin.exists(chat_id=message.chat.id):
        bot.send_message(message.chat.id, 'DOCS: ' + message.document.file_id)


@bot.message_handler(content_types=['text'])
@db_session
def handle_others(message):
    '''Handle other input from user, displaying different menus'''

    m_item = MenuItem.select(lambda m: m.title == message.text).first()
    if m_item != None:
        reply(m_item, message)
    elif Admin.exists(chat_id=message.chat.id):
        admin = Admin[message.chat.id]
        if admin.in_section and admin.choosen_speaker is not None and admin.choosen_speaker is not '':
            pass
            #send_out_thesis(message)
    


def reply(item, message):
        '''Send a message with all data'''
        if item.forward_to == Menu['presentation']:
            markup = item.forward_to.get_markup()
            bot.send_message(message.chat.id, item.text, reply_markup=markup)
            for doc in Docs.select().order_by(Docs.id):
                bot.send_document(message.chat.id, doc.file_id)
            return
        if item.forward_to == Menu['start']:
            if FlowSubscription.exists(chat_id=message.chat.id):
                FlowSubscription[message.chat.id].delete()
        elif (item.belongs_to == Menu['speakers'] or item.forward_to == Menu['start']) and Admin.exists(chat_id=message.chat.id):
            admin = Admin[message.chat.id]
            if admin.in_section:
                if item.forward_to == Menu['start']:
                    admin.in_section = False
                else:
                    admin.choosen_speaker = item.title
                    return
        if item.belongs_to == Menu['speakers'] and FlowSubscription.exists(chat_id=message.chat.id):
            for thesis in Thesis.select(lambda t: t.speaker == item.title).order_by(Thesis.id):
                bot.send_message(message.chat.id, thesis.text)
            return
        if item.image_id is not None and item.image_id is not '':
            bot.send_photo(message.chat.id, item.image_id)
        if item.forward_to is not None and item.forward_to is not '':
            if item.forward_to == Menu['flow']:
                if not FlowSubscription.exists(chat_id=message.chat.id):
                    FlowSubscription(chat_id=message.chat.id)
                bot.send_message(message.chat.id, item.text, reply_markup=Menu['speakers'].get_markup())       
                return        
            markup = item.forward_to.get_markup()
            bot.send_message(message.chat.id, item.text, reply_markup=markup)
        else:
            bot.send_message(message.chat.id, item.text, parse_mode='Markdown', disable_web_page_preview=True)
        if item.video_id is not None and item.video_id is not '':
            bot.send_video(message.chat.id, item.video_id)


def send_all_thesises(message):
    for thesis in Thesis.select():
        bot.send_message(message.chat.id, '{}: "{}"'.format(thesis.speaker, thesis.text))


def send_out_thesis(message):
    thesis = Thesis(speaker=Admin[message.chat.id].choosen_speaker, text=message.text)
    for sub in FlowSubscription.select():
        bot.send_message(sub.chat_id, '{}: "{}"'.format(thesis.speaker, thesis.text))


if __name__ == '__main__':
    #bot.polling(none_stop=True)
    app.run(threaded=True, host="0.0.0.0", port=os.environ.get('PORT', 5000))
    #app.run(debug=True)
    