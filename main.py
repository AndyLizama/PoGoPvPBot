# -*- coding: utf-8 -*-
import logging
logging.basicConfig(filename='log.log', format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger('Info')
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import json 
import iv_check
import silph
import pvp_poll
import re
import database
import requests
import trainernames
import language_support as lan
pvprequests = {}
competitors = {}

""" Load the token that we use to communicate with our bot """
with open('config.json') as json_config_file:
    config = json.load(json_config_file)
""" Load the responses by our bot for each languages """
responses = lan.responses
""" Load the currently supported languages """
supported_languages = lan.supported_languages

""" Initialise our Telegram tools"""    
updater = Updater(config['token'], use_context=True)
job = updater.job_queue
dispatcher = updater.dispatcher

""" 
This part until start is just an easter egg
"""
def get_dog():
    contents = requests.get('https://random.dog/woof.json').json()
    url = contents['url']
    return url

def get_cat():
    contents = requests.get('http://aws.random.cat/meow').json()
    url = contents['file']
    return url

def get_image_url(pic):
    allowed_extension = ['jpg','jpeg','png']
    file_extension = ''
    while file_extension not in allowed_extension:
        if pic == 'cat':
            url = get_cat()
        else:
            url = get_dog()
        file_extension = re.search("([^.]*)$",url).group(1).lower()
    return url

def meow(update, context):
    url = get_image_url('cat')
    context.bot.send_photo(chat_id=update.message.chat_id, photo=url)    

def bop(update, context):
    url = get_image_url('dog')
    context.bot.send_photo(chat_id=update.message.chat_id, photo=url)    

""" 
Send the start message to a user is he starts the bot. This message is also sent 
when a user types /help
"""
def start(update, context):
    language = database.get_language(update.message.chat_id)
    response = ''
    response = response.join(responses[language]['start'])
    context.bot.send_message(parse_mode='Markdown', chat_id=update.message.chat_id, text=response)    

"""
Change the language setting of a group/user
"""
def language(update, context):
    #Make sure that we only handle messages that we can speak
    if len(context.args) == 1 and context.args[0].lower() in supported_languages:
        database.toggle_groups(update, context, 'Language')
    #If we reject the input we try to delete the users message and let him know which languages we speak
    else:
        try:
            context.bot.delete_message(chat_id=update.message.chat_id,message_id=update.message.message_id)
        except:
            logger.info("Cannot delete message Chat:%s MessageID:%s", update.message.chat_id, update.message.message_id)
        #Get the language that we are speaking in this group and tell the user which languages we can speak
        language = database.get_language(update.message.chat_id)
        response = responses[language]['language_not_supported']
        response = response.format(supported_languages)
        bot_message = context.bot.send_message(parse_mode='Markdown', chat_id=update.message.chat_id, text=response)

""" 
Just a notice that Silph ranks are disabled until there is an open API
"""        
def silph_rank(update, context):
    try:
        context.bot.delete_message(chat_id=update.message.chat_id,message_id=update.message.message_id)
    except:
        logger.info("Cannot delete message Chat:%s MessageID:%s", update.message.chat_id, update.message.message_id)
    language = database.get_language(update.message.chat_id)
    bot_message = context.bot.send_message(chat_id=update.message.chat_id, text=responses[language]['rank_disabled'])
    job.run_once(delete_message, 30, context=(bot_message.chat_id, bot_message.message_id))

"""
Deletes a message 
Called as a job which is executed with some delay to enable the user to read the response
"""
def delete_message(context):
    try:
        context.bot.delete_message(chat_id=context.job.context[0], message_id=context.job.context[1])
        logger.info("Deleted message %s %s", context.job.context[0], context.job.context[1])
    except:
        logger.info("Cannot delete message %s %s", context.job.context[0], context.job.context[1])

"""
Any commands that we cannot process will just be deleted and a notice to the user.
The response will be deleted after 30 seconds
"""        
#def unknown(update, context):
#    try:
#        context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
#    except:
#        logger.info("Cannot delete message Chat:%s MessageID:%s", update.message.chat_id, update.message.message_id)
#    bot_message = context.bot.send_message(chat_id=update.message.chat_id, text="I'm sorry! I don't understand that command. You can get a list of commands with /help.")
#    job.run_once(delete_message, 30, context=(bot_message.chat_id, bot_message.message_id))

#def test(update, context):
#    context.bot.sendGame(chat_id=update.message.chat_id, game_short_name='PvPSimulator')
#    print('Test')

#def callback(update, context):
#    context.bot.answer_callback_query(update.callback_query.id, url="https://www.gamee.com/game-bot/9lEE0Oh-22e00710a2e28256ba019865f2b7e186d3abb749#tgShareScoreUrl=tgb://share_game_score?hash=zmCEIujbgBWbyMMPqeLL")
#    print()

def main():
    logger.info('Started bot')
    
    #Easter egg commands
    dispatcher.add_handler(CommandHandler('pbp',bop))
    dispatcher.add_handler(CommandHandler('pcp',meow))
    
    #/start and /help to give the introduction
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))

    #Create a pvp request
    updater.dispatcher.add_handler(CommandHandler('pvp', pvp_poll.pvp))
    #Add/removes a competitor if he clicks on fight
    updater.dispatcher.add_handler(CallbackQueryHandler(pvp_poll.add_competitor, pattern='fight'))
    #Deletes a pvp request - TODO: Admins should be able to delete requests
    updater.dispatcher.add_handler(CallbackQueryHandler(pvp_poll.delete_poll, pattern='delete'))
    #Check if tehre are any outdated pvp requests which we want to delete
    auto_del = job.run_repeating(pvp_poll.auto_delete, interval=900, first=0)
    
    #Start the game sim
    #updater.dispatcher.add_handler(CommandHandler('test', test))
    #updater.dispatcher.add_handler(CallbackQueryHandler(callback))
    
    #Handle /iv
    dispatcher.add_handler(CommandHandler("iv", iv_check.iv_rank))    
    
    #Handle /language
    dispatcher.add_handler(CommandHandler("language", language))    

    #Handle /rank
    dispatcher.add_handler(CommandHandler("rank", silph_rank))

    #Set trainername and trainercode
    dispatcher.add_handler(CommandHandler("trainername", trainernames.add_trainername))
    dispatcher.add_handler(CommandHandler("trainercode", trainernames.add_trainercode))


    #This is the last methon and should be used to refer to info
    #unknown_handler = MessageHandler(Filters.command, unknown)
    #dispatcher.add_handler(unknown_handler)    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()