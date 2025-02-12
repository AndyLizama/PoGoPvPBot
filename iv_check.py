# -*- coding: utf-8 -*-
import logging
logging.basicConfig(filename='log.log', format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger('Info')
import pandas as pd
import database
import language_support

#The json file of currently supported language responses
jsonresponse = language_support.responses
    

"""
If the user has given IVs additional to the pokemon we want to see where this IV distribution ranks
When the user does not give IVs, return the optimal IVs for that pokemon
@param pokemon_name: The name of the pokemon that we are interested in 
@param att: The attack stat of the pokemon
@param de: The defense stat of the pokemon (def is predefined)
@param sta: The stamina stat of the pokemon 
@param responses: The json responses of the current language
@return: A formatted response for the IV distribution of this pokemon
"""
def iv_given(pokemon_name, initial_language, responses, att=None, de=None, sta=None):
    try:            
        df = pd.read_csv('ranking/'+pokemon_name+'.csv')
        #Check, if we want to get optimal IVs or given
        if att is None:
            row = df.loc[df['rank'] == 1]
            response = responses['iv_optimal']
        #Find the Pokemon with the give IV-Distribution
        else:
            iv = str(att) + ' ' + str(de) + ' ' + str(sta)
            row = df.loc[df['ivs'] == iv]
            response = responses['iv_given']

        #Compute the Stat product on the fly 
        optimal_stat_product = df.iloc[0]['stat-product']
        percent = round((100/optimal_stat_product)*row.iloc[0]['stat-product'], 2)
        index_worst = df.shape[0]-1
        percent_worst = round((100/optimal_stat_product)*df.iloc[index_worst]['stat-product'], 2)
        
        local_name = get_local_name(pokemon_name, initial_language)
        response = response.format(local_name.capitalize(), row.iloc[0]['rank'])
        response += responses['iv_stats']
        response = response.format(row.iloc[0]['ivs'], row.iloc[0]['cp'], row.iloc[0]['maxlevel'], row.iloc[0]['stat-product'], percent, percent_worst)
        return response
    #We cannot find this pokemon
    except:
        response = responses['iv_no_pokemon']
        return response.format(pokemon_name)

def get_local_name(eng_name, col_index):
    name = eng_name.lower().capitalize()
    df = pd.read_csv('pokemon_info/translations.csv')
    idx = df.where(df == name).dropna(how='all').index
    try:
        return df.loc[idx[0], col_index]
    except:
        logger.info("Cannot find local name for (%s)", local_name)


def get_english_name(local_name, group_language):
    name = local_name.lower().capitalize()
    df = pd.read_csv('pokemon_info/translations.csv')
    idx = df.where(df == name).dropna(how='all').index
    #Drop all entries which don't match the local name
    localized = df.where(df == name).dropna(how='all')
    #Return a tuple of the first appearance of the name
    index_tuple = list(df[localized.notnull()].stack().index)
    different_language = True
    for nationality in index_tuple:
        if nationality[1] == group_language or nationality[1] not in language_support.supported_languages:
            different_language = False
            break
    try:
        return df.iloc[localized.index[0], 0], index_tuple[0][1], different_language
    except:
        logger.info("Cannot find english name for (%s)", local_name)
    
"""
This message takes a single pokemon and returns the whole family as a list
"""        
def get_pokemon_family(pokemon_name, group_language):
    eng_name, initial_language, different_language = get_english_name(pokemon_name, group_language)
    eng_name = eng_name.capitalize()
    df = pd.read_csv('pokemon_info/evolutions.csv')
    index = df.where(df == eng_name).dropna(how='all').index
    return df.loc[index[0]].dropna(), initial_language, different_language

"""
This method is called when the user types /iv
- It retrieves the language
- checks, if we want to enable or disable iv checks in groups
- checks, if IV queries are allowed in this group 
- Performs an IV request
"""    
def iv_rank(update, context):
    #Retrieve the current language
    language = database.get_language(update.message.chat_id)
    responses = jsonresponse[language]
    logger.info('IV request by %s with query %s', update._effective_user.username, context.args)
    #Check, if IV queries should be en-/disabled in this group
    if len(context.args) == 1 and (context.args[0] == 'enable' or context.args[0] == 'disable'):
        logger.info("/IV %s by %s", context.args[0] , update._effective_user.username)
        #En-/disable IV queries for this group
        database.toggle_groups(update, context, 'IV')
        return
    #If we are in a group and dont want ivs queries are disabled we just delete the request and return
    if update.message.chat_id < 0 and not database.group_enabled(update.message.chat_id, 'IV'):
        logger.info("Disabled /iv request attempted by (%s)", update._effective_user.username)
        context.bot.delete_message(chat_id=update.message.chat_id,message_id=update.message.message_id)
        return
    
    #The user didn't specify a pokemon
    if(len(context.args) == 0):
        logger.info("Invalid pokemon")
        response = responses['iv_no_argument']
        context.bot.send_message(parse_mode='HTML', chat_id=update.message.chat_id, text=response)
    else:
        try:
            if context.args[0][0] is '+':
                evolutions, initial_language, different_language = get_pokemon_family(context.args[0][1:], language)
            else:
                
                evolutions, initial_language, different_language = get_english_name(context.args[0], language)
                evolutions = [evolutions]
            for evo in evolutions:
                #If the user just specified a Pokemon - Return the optimal distribution
                if(len(context.args) == 1):
                   response = iv_given(evo.lower(), initial_language, responses)
                #If the user gave IVs with the pokemon - Return where this one ranks
                elif(len(context.args) == 4):
                    att = normalize_iv(context.args[1])
                    de = normalize_iv(context.args[2])
                    sta = normalize_iv(context.args[3])
                    response = iv_given(evo.lower(), initial_language, responses, att, de, sta)
                logger.info('Return %s', response.encode("utf-8"))
                
                if different_language:
                    language_hint = responses['language_hint']
                    context.bot.send_message(parse_mode='HTML', chat_id=update.message.chat_id, text=responses['language_hint'])

                #Send the response to the user
                context.bot.send_message(parse_mode='HTML', chat_id=update.message.chat_id, text=response)


        #We got some weird input which we cannot perform
        except:
            logger.info("Could not perform /iv request")
            response = responses['iv_error']
            context.bot.send_message(parse_mode='HTML', chat_id=update.message.chat_id, text=response)

"""
This method converts a given IV in a number in the range 0..15.
It accepts standard numbers (no operation is done), hexadecimal representation, or the circled
numbers (white background/black background) that is used in apps such as CalcyIV.
"""    
def normalize_iv(iv):
    if(isinstance(iv, str) and iv.isdecimal()):
        # Note: we're not checking if the value is in the range 0..15.
        return iv
    else:
        # Try to convert from common app representations.
        # Hexadecimal:
        val = "0123456789ABCDEF".find(iv)
        if (val != -1):
            return val
        # Rounded white numbers
        if (iv == "⓪" or iv == "⓿"):
            return 0
        elif (iv == "①" or iv == "❶"):
            return 1
        elif (iv == "②" or  iv == "❷"):
            return 2
        elif (iv == "③" or iv == "❸"):
            return 3
        elif (iv == "④" or iv == "❹"):
            return 4
        elif (iv == "⑤" or iv == "❺"):
            return 5
        elif (iv == "⑥" or iv == "❻"):
            return 6
        elif (iv == "⑦" or iv == "❼"):
            return 7
        elif (iv == "⑧" or iv == "❽"):
            return 8
        elif (iv == "⑨" or iv == "❾"):
            return 9
        elif (iv == "⑩" or iv == "❿"):
            return 10
        elif (iv == "⑪" or iv == "⓫"):
            return 11
        elif (iv == "⑫" or iv == "⓬"):
            return 12
        elif (iv == "⑬" or iv == "⓭"):
            return 13
        elif (iv == "⑭" or iv == "⓮"):
            return 14
        elif (iv == "⑮" or iv == "⓯"):
            return 15
        else:
            return iv
