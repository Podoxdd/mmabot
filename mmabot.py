#!/usr/bin/env python3
import random
import sys
import configparser
from google.cloud import bigquery
from discord.ext import commands


configfilepath = 'mmabot.cfg'

config = configparser.ConfigParser()
config.read(configfilepath)

gcpproject = config.get('default', 'gcpproject')
token = config.get('default', 'token')
currency = config.get('default', 'currency')
dbclient = bigquery.Client(gcpproject)
bot = commands.Bot(command_prefix='!')


# TODO: figure out how to structure fight events in gcp
events = {'ufc249': {'odds': [({'khabib', -275}, {'tony': 235})], 'bets': []}}
current_event = 'ufc249'

def add_new_user(userid):
    add_query_text = 'insert into mmabot.balances (userid, balance) values (%s, 0);' % userid
    add_query = dbclient.query(add_query_text)
    return add_query.result()

def balance_lookup(userid):
    query_text = 'select balance from mmabot.balances where userid = %s;' % (userid)
    query = dbclient.query(query_text)
    query_result = query.result()
    # unwind the results
    rows = [row for row in query_result]
    # add the user if they're not there already 
    if len(rows) == 0:
        print('No results for %s - adding them' % (userid))
        add_new_user(userid)
        bal = 0
    elif len(rows) == 1:
        print('Found one result.')
        bal = rows[0].get('balance')
    else:
        print('This should not happen. Userid %s has multiple rows in DB. Exiting.' % (userid))
        sys.exit(1)
    print('User %s has a balance of %s' % (userid, bal))
    return bal


def balance_add(userid, amount):
    bal = balance_lookup(userid)
    new_bal = bal + amount
    add_balance_text = 'update mmabot.balances set balance = %s where userid = %s;' % (new_bal, userid)
    add_balance_query = dbclient.query(add_balance_text)
    print('Updating Balance: %s' % (add_balance_text))
    res = add_balance_query.result()
    return res
    

def balance_subtract(userid, amount):
    bal = balance_lookup(userid)
    new_bal = bal - amount
    sub_balance_text = 'update mmabot.balances set balance = %s where userid = %s;' % (new_bal, userid)
    sub_balance_query = dbclient.query(sub_balance_text)
    print('Updating Balance: %s' % (sub_balance_text))
    res = sub_balance_query.result()
    return res


def store_bet(userid, bet_amount, bet_fighter):
    bet_instance = {'userid': userid,
        'bet_amount': bet_amount,
        'bet_fighter': bet_fighter
    }
    balance_subtract(userid, bet_amount)
    events[current_event]['bets'].append(bet_instance)
    return bet_instance


def process_odds(fighter_name):
    odds = {'khabib': 1, 'tony': 5}
    if fighter_name not in odds:
        return None
    else:
        return odds.get(fighter_name)


@bot.event
async def on_ready():
    print(f'{bot.user.name} started')


@bot.command(name='balance', help='Shows your current available balance')
async def balance(ctx):
    current_balance = balance_lookup(ctx.author.id)
    response = '<@%s> - your balance is %s %s' % (
        ctx.author.id,
        current_balance,
        currency
    )
    await ctx.send(response)
    return


@bot.command(name='bet', help='Use to place a bet; syntax: !bet [amount] [fighter]')
async def bet(ctx):
    current_balance = balance_lookup(ctx.author.id)
    # below we're splitting the user's command into a 3-part
    # list and grabbing the second and third positions so we can
    # grab the amount and the fighter. TODO: make this more
    # resilient against crazy inputs like negatives.
    try:
        bet_input = ctx.message.content.split(' ')
        bet_amount = int(bet_input[1])
        bet_fighter = str(bet_input[2].lower())
    except:
        # handle failures in splitting the input into 3 parts
        # and marking the second position as an integer
        response = '<@%s> - Bad input. Use `!help` for proper syntax.' % (ctx.author.id)
        await ctx.send(response)
        return
    # make sure the user has enough `currency` for the bet
    if bet_amount < 1:
        response = '<@%s> - You can\'t bet zero or a negative value, dipshit.' % (ctx.author.id)
        await ctx.send(response)
        return
    if bet_amount > current_balance:
        response = '<@%s> - not enough %s for that. Balance: %s' % (
            ctx.author.id,
            currency,
            current_balance
        )
        await ctx.send(response)
        return
    # process_odds checks to see if the fighter exists in the odds and
    # returns a NoneType if they don't
    bet_odds = process_odds(bet_fighter)
    # if the fighter is found...
    if bet_odds is not None:
        store_bet(ctx.author.id, bet_amount, bet_fighter)
        current_balance = current_balance - bet_amount
        response = '<@%s> - Bet placed. Current balance: %s %s' % (
            ctx.author.id,
            current_balance,
            currency
        )
        await ctx.send(response)
        print(events)
        return
    # if the fighter doesn't exist in the odds table
    else:
        response = '<@%s> - no fighter named %s found.' % (ctx.author, bet_fighter)
        await ctx.send(response)
        return


@bot.command(name='bets', help='List your current bets')
async def bets(ctx):
    return 


@bot.command(name='retract', help='Retract bet; syntax: !retract khabib')
async def retract(ctx):
    return


@bot.command(name='claim', help='Claim 100 free currency per event')
async def claim(ctx):
    '''
    TODO: Have this only work once per event. For now, it's the wild west. Anyone
    Can claim whatever they want as often as they want. 
    '''
    balance_add(ctx.author.id, 100)
    new_balance = balance_lookup(ctx.author.id)
    response = '<@%s> - Adding 100 %s to your balance. Your new balance is %s.' % (ctx.author.id, currency, new_balance)
    await ctx.send(response)
    return 


@bot.command(name='rank', help='Display your overall betting rank based on balance')
async def rank(ctx):
    return


@bot.command(name='top10', help='Display the top 10 balances on the server')
async def topten(ctx):
    return


@bot.command(name='flipacoin', help='Flip a coin. Randomly returns heads or tails.')
async def flipacoin(ctx):
    coin_sides = ('Heads', 'Tails')
    results = random.choice(coin_sides)
    response = '<@%s> - coin flip results: %s' % (ctx.author, results)
    await ctx.send(response)
    return


bot.run(token)
