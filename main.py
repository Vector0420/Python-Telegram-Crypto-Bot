from web3 import Web3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler
from telegram.ext import filters
import requests
import math
from bitcoinaddress import Address
# from telegram.error import TelegramError
# import logging
# import schedule
# import time
# import asyncio
 
# Connect to an Ethereum node
web3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/cb1c41d69b4044599889a61be57224a4'))

user = {}
user_state = {}
ethScanApiKey = "WTMYNSTIAMY42SQ9WIGK6EKVE3SHU5ZSHF"
infura_url = 'https://mainnet.infura.io/v3/cb1c41d69b4044599889a61be57224a4'
usdt_addr = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
usdc_addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
IS_STARTED_CHECK = False

BTC_USD = 64323.99
ETH_USD = 3152.53
USDT_USD = 0.999695
USDC_USD = 1
gas_prices = {
    'Low': {'price': 0, 'time': 10},
    'Average': {'price': 0, 'time': 3},
    'Fast': {'price': 0, 'time': 30},
}

ADD_ETH_TEXT = "ADD_ETH_TEXT"
REMOVE_ETH_TEXT = "REMOVE_ETH_TEXT"
REMOVE_BTC_TEXT = "REMOVE_BTC_TEXT"
GAS_PRICE_TEXT = "GAS_PRICE_TEXT"
COINS_TEXT = "COINS_TEXT"
ADD_BTC_TEXT = "ADD_BTC_TEXT"

msg_template = f'''                             
🚨 <b>New TX: VAR_NAME (VAR_ADDRESS)</b>
💵 VAR_AMOUNT / VAR_USD_AMOUNT
📈 Fee: VAR_FEE | 🔗: <a href="VAR_TX_LINK">LINK</a>
🛫 <a href="VAR_SEND_LINK">VAR_SEND_ADDRESS</a> ➡️ 🛬 <a href="VAR_RECEIVE_LINK">VAR_RECEIVE_ADDRESS</a>'''

def number_with_commas(x):
    return f"{x:,}"

def validate_btc_address(address):
    try:
        addr = Address(address)
        return True
    except ValueError:
        return False

def get_token_price(context: CallbackContext):
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        data = response.json()
        if data.get('data', {}).get('amount'):
            global BTC_USD
            BTC_USD = float(data['data']['amount'])
    except Exception as e:
        print("Error while getting BTC price:", e)

    try:
        response = requests.get("https://api.coinbase.com/v2/prices/ETH-USD/spot")
        data = response.json()
        if data.get('data', {}).get('amount'):
            global ETH_USD
            ETH_USD = float(data['data']['amount'])
    except Exception as e:
        print("Error while getting ETH price:", e)

    try:
        response = requests.get("https://api.coinbase.com/v2/prices/USDT-USD/spot")
        data = response.json()
        if data.get('data', {}).get('amount'):
            global USDT_USD
            USDT_USD = float(data['data']['amount'])
    except Exception as e:
        print("Error while getting USDT price:", e)

    try:
        response = requests.get("https://api.coinbase.com/v2/prices/USDC-USD/spot")
        data = response.json()
        if data.get('data', {}).get('amount'):
            global USDC_USD
            USDC_USD = float(data['data']['amount'])
    except Exception as e:
        print("Error while getting USDC price:", e)

def get_gas_prices(context: CallbackContext):
    try:
        # Check if the connection is successful
        if not web3.is_connected():
            print("Failed to connect to Infura")
            return
        
        gas_price = web3.eth.gas_price

        # Convert gas price from Wei to Gwei for better readability
        gas_price_gwei = web3.from_wei(gas_price, 'gwei')

        gas_price_gwei = math.ceil(gas_price_gwei)

        global gas_prices
        gas_prices = {
            'Low': {'price': math.floor(gas_price_gwei * 0.9), 'time': 10},
            'Average': {'price': gas_price_gwei, 'time': 3},
            'Fast': {'price': math.ceil(gas_price_gwei * 1.2), 'time': 30}
        }
        
    except Exception as e:
        print("Error while getting gas prices:", e)

def is_token_address_valid(address):

    try:
        # Use the instance `web3` instead of the class `Web3`
        web3.to_checksum_address(address)
        return True
    except ValueError:
        return False
    
def decode_token_transfer_input(input_data):
    if input_data[:10] == '0xa9059cbb':
        address_hex = input_data[10:74]  # Next 32 bytes after method ID
        amount_hex = input_data[74:138]  # Next 32 bytes after address
        to_address = Web3.to_checksum_address('0x' + address_hex[-40:])
        amount = int(amount_hex, 16) / (10 ** 6)  # Adjust based on the token's actual decimals
        return (to_address, amount)
    else:
        return (None, None)
    
def check_user(context: CallbackContext):
    job_context = context.job.context
    user_id = job_context['user_id']
    chat_id = job_context['chat_id']
    user_data = user[user_id]
    for address in user_data['addresses']:
        if not address['isBtc']:
            latest_block_num = web3.eth.get_block_number()

            start_block = address['lastBlock']

            if start_block == -1:
                start_block = latest_block_num
                
            if start_block > latest_block_num:
                continue

            address['lastBlock'] = latest_block_num + 1

            print('ETH', start_block, latest_block_num)

            relevant_transactions = []
            for block_number in range(start_block, latest_block_num + 1):
                block = web3.eth.get_block(block_number, full_transactions=True)
                for tx in block.transactions:
                    to_address, amount = decode_token_transfer_input(tx['input'].hex())
                    if (tx['to'] and tx['to'] == address['address']) or (to_address and to_address == address['address']) :
                        relevant_transactions.append(tx)

            print('ETH_DATA', relevant_transactions)

            for txn in relevant_transactions:
                txn_receipt = web3.eth.get_transaction_receipt(txn.hash)
                if txn_receipt.status == 1:
                    if txn['to'] == address['address']:
                        to_address = address['address']
                        amount = float(Web3.from_wei(txn['value'], 'ether'))
                        usd_amount = float(amount) * ETH_USD
                        amount = f"{amount:.5f}"
                        amount_type = "ETH"
                    else:
                        to_address, amount = decode_token_transfer_input(txn['input'].hex())
                        if txn['to'] == usdt_addr:
                            usd_amount = float(amount) * USDT_USD
                            amount = f"{amount:.2f}"
                            amount_type = "USDT"
                        else:
                            usd_amount = float(amount) * USDC_USD
                            amount = f"{amount:.2f}"
                            amount_type = "USDC"

                    msg = msg_template
                    msg = msg.replace("VAR_NAME", address['name'])
                    msg = msg.replace("VAR_ADDRESS", address['address'][-5:])
                    msg = msg.replace("VAR_SEND_ADDRESS", f"{txn['from'][:6]}...{txn['from'][-4:]}")
                    msg = msg.replace("VAR_SEND_LINK", f"https://etherscan.io/address/{txn['from']}")
                    msg = msg.replace("VAR_RECEIVE_ADDRESS", f"{txn['to'][:6]}...{to_address[-4:]}")
                    msg = msg.replace("VAR_RECEIVE_LINK", f"https://etherscan.io/address/{to_address}")
                    
                    fee = web3.from_wei(txn['gasPrice'] * txn_receipt.gasUsed, 'ether')
                    usd_fee = f"{(float(fee) * ETH_USD):.2f}"
                    if amount_type == 'USDT':
                        fee = float(fee) * ETH_USD / USDT_USD
                        fee = f"{float(fee):.2f}"
                    elif amount_type == 'USDC':
                        fee = float(fee) * ETH_USD / USDC_USD
                        fee = f"{float(fee):.2f}"
                    else:
                        fee = f"{float(fee):.5f}"
                    if txn['from'].lower() == address['address'].lower():
                        msg = msg.replace("VAR_AMOUNT", f"-{amount} {amount_type}")
                        msg = msg.replace("VAR_SENT_RECEIVED", "Sent")
                        msg = msg.replace("VAR_USD_AMOUNT", f"-${(usd_amount):.2f} USD")
                    else:
                        msg = msg.replace("VAR_AMOUNT", f"+{amount} {amount_type}")
                        msg = msg.replace("VAR_SENT_RECEIVED", "Received")
                        msg = msg.replace("VAR_USD_AMOUNT", f"+${(usd_amount):.2f} USD")
                    msg = msg.replace("VAR_FEE", f"{fee} {amount_type} ($" + f"{usd_fee}" + ")")
                    msg = msg.replace("VAR_TX_LINK", f"https://etherscan.io/tx/{txn.hash.hex()}")

                    context.bot.send_message(chat_id, msg, parse_mode="HTML", disable_web_page_preview=True)
            return
        else:
            response = requests.get("https://blockchain.info/latestblock")
            latest_block_data = response.json()
            latest_block_num = latest_block_data['height'] - 1
            btc_data_response = requests.get(f"https://blockchain.info/rawaddr/{address['address']}?limit=100")
            if btc_data_response.status_code != 200:
                print(f"Failed to fetch BTC data: {btc_data_response.status_code}")
                continue
            
            btc_data = btc_data_response.json()
            
            start_block = address['lastBlock']

            if start_block == -1:
                start_block = latest_block_num

            print("BTC", start_block, latest_block_num)

            if start_block > latest_block_num:
                continue

            address['lastBlock'] = latest_block_num + 1

            for item in btc_data['txs']:
                if (item['block_index'] is not None) and (item['block_index'] < start_block):
                    continue
                print('BTC_DATA', item)
                msg = msg_template
                msg = msg.replace("VAR_NAME", address['name'])
                msg = msg.replace("VAR_ADDRESS", address['address'][-5:])
                input_addr = item['inputs'][0]['prev_out']['addr']
                msg = msg.replace("VAR_SEND_ADDRESS", f"{input_addr[:6]}...{input_addr[-4:]}")
                msg = msg.replace("VAR_SEND_LINK", f"https://blockstream.info/address/{input_addr}")
                output_addr = item['out'][0]['addr']
                msg = msg.replace("VAR_RECEIVE_ADDRESS", f"{output_addr[:6]}...{output_addr[-4:]}")
                msg = msg.replace("VAR_RECEIVE_LINK", f"https://blockstream.info/address/{output_addr}")
                amount = float(item['result'] / 10**8)
                fee = float(item['fee'] / 10**8)

                if amount < 0:
                    msg = msg.replace("VAR_AMOUNT", f"-{abs(amount):.8f} BTC")
                    msg = msg.replace("VAR_SENT_RECEIVED", "Sent")
                    msg = msg.replace("VAR_USD_AMOUNT", f"-${abs(amount * BTC_USD):.2f} USD")
                else:
                    msg = msg.replace("VAR_AMOUNT", f"+{amount:.8f} BTC")
                    msg = msg.replace("VAR_SENT_RECEIVED", "Received")
                    msg = msg.replace("VAR_USD_AMOUNT", f"+${(amount * BTC_USD):.2f} USD")

                msg = msg.replace("VAR_FEE", f"{fee:.8f} BTC (${(fee * BTC_USD):.2f})")
                msg = msg.replace("VAR_TX_LINK", f"https://www.blockonomics.co/#/search?q={item['hash']}&addr={address['address']}")

                context.bot.send_message(chat_id, msg, parse_mode="HTML", disable_web_page_preview=True)
            return
            
def send_start_message(update: Update, context: CallbackContext):
    if update.message:
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
        user_id = update.callback_query.from_user.id
    else:
        return
    
    if user_id not in user:
        user[user_id] = {
            'addresses': [],
            'enabled': False,
            'intervalId': None,
            'coins': [],
        }
        user_state[user_id] = "handled"

    user_data = user[user_id]
    addresses = user_data['addresses']
    enabled = user_data['enabled']

    address_text = "\n\n".join(f"<b>Name:</b> {addr['name']} \n<b>Address:</b> <code>{addr['address']}</code>" for addr in addresses) if addresses else "No addresses."
    response = f"<b>Welcome to Wallet Monitor Bot!</b>\nOur platform supports only BTC, ETH, USDT, and USDC at this time.\n\n<b>Addresses:</b>\n{address_text}"

    keyboard = [
        [InlineKeyboardButton("➕ Add ETH Address", callback_data=f"{user_id}_addETHAddress"),
         InlineKeyboardButton("➕ Add BTC Address", callback_data=f"{user_id}_addBTCAddress")
        ],
        [InlineKeyboardButton("❌ Remove ETH Address", callback_data=f"{user_id}_removeETHAddress"),
         InlineKeyboardButton("❌ Remove BTC Address", callback_data=f"{user_id}_removeBTCAddress")
        ],
        [InlineKeyboardButton("⛽️ Gas Price", callback_data=f"{user_id}_gasPrice"),
         InlineKeyboardButton("💰 Coins", callback_data=f"{user_id}_coins")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(chat_id=chat_id, text=response, parse_mode='HTML', reply_markup=reply_markup)

def add_eth_address(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = int(query.data.split("_")[0])

    user_state[user_id] = ADD_ETH_TEXT
    response = "🔴 Input the Ethereum wallet address you want to monitor and wallet name.\nExample: 0x000000000000 - DEPLOYER"
    keyboard = [[InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = query.edit_message_text(text=response, reply_markup=reply_markup)
    user_state[f'message_id_to_delete_{user_id}'] = message.message_id

def add_btc_address(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = int(query.data.split("_")[0])

    user_state[user_id] = ADD_BTC_TEXT
    response = "🔴 Input the Bitcoin wallet address and name you want to monitor."
    keyboard = [[InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = query.edit_message_text(text=response, reply_markup=reply_markup)
    user_state[f'message_id_to_delete_{user_id}'] = message.message_id

def remove_eth_address(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = int(query.data.split("_")[0])

    user_state[user_id] = REMOVE_ETH_TEXT
    response = "🔴 Input the Ethereum wallet name you want to remove."
    keyboard = [[InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = query.edit_message_text(text=response, reply_markup=reply_markup)
    user_state[f'message_id_to_delete_{user_id}'] = message.message_id

def remove_btc_address(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = int(query.data.split("_")[0])

    user_state[user_id] = REMOVE_BTC_TEXT
    response = "🔴 Input the Ethereum wallet name you want to remove."
    keyboard = [[InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = query.edit_message_text(text=response, reply_markup=reply_markup)
    user_state[f'message_id_to_delete_{user_id}'] = message.message_id

def gas_price(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = int(query.data.split("_")[0])

    user_state[user_id] = GAS_PRICE_TEXT
    response = f'''<code>🚀 Fast    - {gas_prices['Fast']['price']} gwei (~ {gas_prices['Fast']['time']} sec)</code>
<code>🚗 Average - {gas_prices['Average']['price']} gwei (~ {gas_prices['Average']['time']} min)</code>
<code>🐢 Low     - {gas_prices['Low']['price']} gwei (> {gas_prices['Low']['time']} min)</code>'''
    keyboard = [[InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = query.edit_message_text(text=response, parse_mode='HTML', reply_markup=reply_markup)
    user_state[f'message_id_to_delete_{user_id}'] = message.message_id


def coins(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = int(query.data.split("_")[0])

    user_state[user_id] = COINS_TEXT
    response = "🔴 Enter coin symbol or name (e.g BTC, LINK)."
    keyboard = [[InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = query.edit_message_text(text=response, parse_mode='HTML', reply_markup=reply_markup)
    user_state[f'message_id_to_delete_{user_id}'] = message.message_id

def handle_text_input(update: Update, context: CallbackContext):
    global IS_STARTED_CHECK
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    if user_id in user_state and user_state[user_id] == GAS_PRICE_TEXT:
        return
    
    if (user_id in user_state and user_state[user_id] == "handled") or user_state == {}:
        return

    print(user_id, user_state, user_id in user_state, user_state[user_id])
    
    print('###################')

    context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    message_id_to_delete = user_state.get(f'message_id_to_delete_{user_id}')
    if message_id_to_delete:
        context.bot.delete_message(chat_id=chat_id, message_id=message_id_to_delete)
        del user_state[f'message_id_to_delete_{user_id}']

    if user_id in user_state and user_state[user_id] == ADD_ETH_TEXT:
        address_data = update.message.text.split("-")
        if len(address_data) > 1:
            address = address_data[0].strip()
            name = address_data[1].strip()
            if is_token_address_valid(address) and name:
                user[user_id]['addresses'].append({
                    'name': name,
                    'address': address,
                    'isBtc': False,
                    'lastBlock': -1,
                })
                user[user_id]['enabled'] = True
                if IS_STARTED_CHECK == False:
                    context.job_queue.run_repeating(check_user, interval=20, context={'user_id': user_id, 'chat_id': chat_id})
                IS_STARTED_CHECK = True
                update.effective_chat.id = chat_id
                update.effective_user.id = user_id
                send_start_message(update, context)
                user_state[user_id] = "handled"
                return
        user_state[user_id] = "handled"
        context.bot.send_message(chat_id=chat_id, text = "Please input the valid address and name.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]
            ]))
        return
    
    if user_id in user_state and user_state[user_id] == REMOVE_ETH_TEXT:
        wallet_name = update.message.text.strip()
        addresses = user[user_id]['addresses']
        address_data = [item for item in addresses if item['name'] == wallet_name and not item['isBtc']]
        if len(address_data) > 0:
            user[user_id]['addresses'] = [
                item for item in addresses if not (item['name'] == wallet_name and not item['isBtc'])
            ]
            update.effective_chat.id = chat_id
            update.effective_user.id = user_id
            send_start_message(update, context)
            user_state[user_id] = "handled"
            return
        user_state[user_id] = "handled"
        # update.message.reply_text("Please input the valid wallet name.",
        #     reply_markup=InlineKeyboardMarkup([
        #         [InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]
        #     ]))
        context.bot.send_message(chat_id=chat_id, text = "Please input the valid wallet name.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]
            ]))
        return
    
    if user_id in user_state and user_state[user_id] == ADD_BTC_TEXT:
        address_data = update.message.text.split("-")
        if len(address_data) > 1:
            address = address_data[0].strip()
            name = address_data[1].strip()
            if validate_btc_address(address) and name:
                user[user_id]['addresses'].append({
                    'name': name,
                    'address': address,
                    'isBtc': True,
                    'lastBlock': -1,
                })
                user[user_id]['enabled'] = True
                if IS_STARTED_CHECK == False:
                    context.job_queue.run_repeating(check_user, interval=20, context={'user_id': user_id, 'chat_id': chat_id})
                IS_STARTED_CHECK = True
                update.effective_chat.id = chat_id
                update.effective_user.id = user_id
                send_start_message(update, context)
                user_state[user_id] = "handled"
                return
        user_state[user_id] = "handled"
        context.bot.send_message(chat_id=chat_id, text = "Please input the valid address and name.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]
            ]))
        return
    
    if user_id in user_state and user_state[user_id] == REMOVE_BTC_TEXT:
        wallet_name = update.message.text.strip()
        addresses = user[user_id]['addresses']
        address_data = [item for item in addresses if item['name'] == wallet_name and item['isBtc']]
        if len(address_data) > 0:
            user[user_id]['addresses'] = [
                item for item in addresses if not (item['name'] == wallet_name and item['isBtc'])
            ]
            update.effective_chat.id = chat_id
            update.effective_user.id = user_id
            send_start_message(update, context)
            user_state[user_id] = "handled"
            return
        user_state[user_id] = "handled"
        context.bot.send_message(chat_id=chat_id, text = "Please input the valid wallet name.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]
            ]))
        return
    
    if user_id in user_state and user_state[user_id] == COINS_TEXT:
        coin_name = update.message.text.strip()
        price = -1
        try:
            url = f'https://api.coinbase.com/v2/prices/{coin_name}-USD/spot'
            response = requests.get(url)
            response_json = response.json()
            # Navigate through the nested JSON response to get the amount
            if 'data' in response_json and 'amount' in response_json['data']:
                price = float(response_json['data']['amount'])
        except requests.exceptions.RequestException as e:
            print("Error while getting BTC price")
        if price != -1:
            user_state[user_id] = "handled"
            context.bot.send_message(chat_id=chat_id, text = f"<code>{coin_name}</code> is <b>{price}</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]
                ]))
            return
        user_state[user_id] = "handled"
        context.bot.send_message(chat_id=chat_id, text = "Please input the valid coin name.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Go Back", callback_data=f"{user_id}_start")]
            ]))
        return

    # elif user_state.get(user_id) == "handled":
    #     print('&&&&&')
    #     update.message.reply_text("You have already added an address. Use the menu to perform other actions.")

def handle_start_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    user_id = int(query.data.split('_')[0])
    chat_id = query.message.chat_id

    context.bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)

    update.effective_chat.id = chat_id
    update.effective_user.id = user_id
    
    send_start_message(update, context)


def setup_dispatcher(dp):
    dp.add_handler(CommandHandler('start', send_start_message))
    dp.add_handler(CallbackQueryHandler(handle_start_callback, pattern=r'\d+_start'))
    dp.add_handler(CallbackQueryHandler(add_eth_address, pattern=r'\d+_addETHAddress'))
    dp.add_handler(CallbackQueryHandler(remove_eth_address, pattern=r'\d+_removeETHAddress'))
    dp.add_handler(CallbackQueryHandler(gas_price, pattern=r'\d+_gasPrice'))
    dp.add_handler(CallbackQueryHandler(add_btc_address, pattern=r'\d+_addBTCAddress'))
    dp.add_handler(CallbackQueryHandler(remove_btc_address, pattern=r'\d+_removeBTCAddress'))
    dp.add_handler(CallbackQueryHandler(coins, pattern=r'\d+_coins'))
    dp.add_handler(MessageHandler(filters.Filters.text & ~filters.Filters.command, handle_text_input))
    

def main():

    # Replace 'YOUR_TOKEN' with the token you got from BotFather
    print ("Server is started.")

    TOKEN = '7029839129:AAFRC0XT6mcDdnIWyxT_c2CFxFbzOvbW6Vc'
    updater = Updater(TOKEN, use_context = True)
    dp = updater.dispatcher
    setup_dispatcher(dp)

    jq = updater.job_queue
    jq.run_repeating(get_token_price, interval=20, first=0)
    jq.run_repeating(get_gas_prices, interval=20, first=1)

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()