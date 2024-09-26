import telnetlib
import time
import re
from telegram.ext import Application
import os
import sys
import socket
import logging
import json
import asyncio
from datetime import datetime, timedelta
import pytz

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Log startup message
logging.info("Pi-hole Telegram Notifier script starting...")

# Configuration from environment variables
PIHOLE_HOST = os.environ.get('PIHOLE_HOST', 'localhost')
PIHOLE_PORT = int(os.environ.get('PIHOLE_PORT', 4711))
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Set timezone
TIMEZONE = pytz.timezone('Asia/Singapore')

# Log configuration
logging.info(f"Configuration: PIHOLE_HOST={PIHOLE_HOST}, PIHOLE_PORT={PIHOLE_PORT}, TIMEZONE={TIMEZONE}")

# Initialize Telegram bot
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

def connect_to_pihole():
    max_retries = 5
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            logging.info(f"Attempting to connect to Pi-hole at {PIHOLE_HOST}:{PIHOLE_PORT}")
            ip_address = socket.gethostbyname(PIHOLE_HOST)
            logging.info(f"Resolved {PIHOLE_HOST} to IP: {ip_address}")
            tn = telnetlib.Telnet(ip_address, PIHOLE_PORT, timeout=100)
            logging.info(f"Successfully connected to {ip_address}:{PIHOLE_PORT}")
            return tn
        except Exception as e:
            logging.error(f"An error occurred while connecting: {e}")
        
        if attempt < max_retries - 1:
            logging.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            raise ConnectionError(f"Failed to connect to Pi-hole after {max_retries} attempts")

async def send_notification(message):
    logging.info(f"Sending notification: {message}")
    await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

def get_all_queries(tn, keywords=['instagram']):
    try:
        tn.write(b">getallqueries (5000)\n")
        response = tn.read_until(b"\n---EOM---\n", timeout=10).decode("utf-8")
        queries = response.strip().split("\n")[:-1]  # Remove the last "---EOM---" line
        
        current_time = datetime.now(TIMEZONE)
        five_minutes_ago = current_time - timedelta(minutes=5)
        
        # Filter queries containing the specified keywords and less than 5 minutes old
        filtered_queries = [
            query.split() for query in queries 
            if any(keyword in query.lower() for keyword in keywords) and
            datetime.fromtimestamp(int(query.split()[0]), TIMEZONE) > five_minutes_ago
        ]
        
        return filtered_queries
    except Exception as e:
        logging.error(f"Error getting queries: {e}")
        return []

def format_queries(queries):
    formatted = "Recent Pi-hole Queries (last 5 minutes):\n\n"
    for query in queries:
        query_time = datetime.fromtimestamp(int(query[0]), TIMEZONE)
        formatted += f"Time: {query_time.strftime('%Y-%m-%d %H:%M:%S %Z')}, Domain: {query[2]}, Client: {query[3]}, Status: {query[4]}\n"
    return formatted

async def main():
    while True:
        try:
            tn = connect_to_pihole()
            if tn is None:
                raise Exception("Pi-hole not connected")
            logging.info("Connected to Pi-hole. Retrieving queries...")
            
            while True:
                queries = get_all_queries(tn, keywords=['instagram'])
                if queries:
                    message = format_queries(queries)
                    await send_notification(message)
                else:
                    logging.info("No queries in the last 5 minutes")
                
                # Wait for 5 minutes before the next query
                await asyncio.sleep(300)
                
        except Exception as e:
            logging.error(f"An error occurred: {e}")
        finally:
            if tn is not None:
                tn.close()
        
        logging.info("Waiting 30 seconds before attempting to reconnect...")
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())