import json
import boto3
import os
import requests
from bs4 import BeautifulSoup
import re

# --- Initialize AWS Clients ---
dynamodb = boto3.resource('dynamodb')
secretsmanager = boto3.client('secretsmanager')
ses = boto3.client('ses', region_name='ap-south-1') # <-- !! REPLACE with your SES region !!

# --- Get Environment Variables ---
TABLE_NAME = os.environ['TABLE_NAME']
SECRET_NAME = os.environ['SECRET_NAME']
SENDER_EMAIL = os.environ['SENDER_EMAIL']

# --- Global Dictionaries ---
secrets = {} # To cache secrets
table = dynamodb.Table(TABLE_NAME)

def get_secrets():
    """Fetches secrets from AWS Secrets Manager and caches them."""
    global secrets
    if not secrets:
        print("Fetching secrets from Secrets Manager...")
        response = secretsmanager.get_secret_value(SecretId=SECRET_NAME)
        secrets = json.loads(response['SecretString'])
    return secrets

def scrape_product(url, scraper_api_key):
    """
    Scrapes a product page using ScraperAPI and returns price, stock, and name.
    
    !! --- THIS FUNCTION IS THE MOST FRAGILE --- !!
    Amazon/Flipkart change their HTML daily. These CSS selectors WILL break.
    You must update them by right-clicking on the page and "Inspect Element".
    """
    print(f"Scraping {url}...")
    
    # Payload for ScraperAPI
    payload = {'api_key': scraper_api_key, 'url': url}
    
    try:
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=30)
        response.raise_for_status() # Raise an error for bad responses
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- Scrape Logic ---
        # These are examples for "Amazon.in".
        
        # 1. Scrape Product Name
        product_name = soup.select_one('#productTitle')
        if product_name:
            product_name = product_name.get_text().strip()
        else:
            product_name = "Product Name Not Found"

        # 2. Scrape Price
        current_price = 0.0
        # Try finding the main price
        price_element = soup.select_one('span.a-price-whole')
        if price_element:
            # Remove '₹' , ',' and '.' and convert to float
            price_text = price_element.get_text().replace(',', '').replace('₹', '').replace('.', '').strip()
            current_price = float(price_text)
        else:
            # Try finding a different price format (e.g., deal price)
            price_element = soup.select_one('#corePrice_feature_div .a-offscreen')
            if price_element:
                price_text = price_element.get_text().replace(',', '').replace('₹', '').strip()
                # Price in offscreen span might be like '₹59,999.00', need to handle .00
                current_price = float(price_text.split('.')[0])
        
        # 3. Scrape Stock
        current_stock = "OUT_OF_STOCK"
        stock_element = soup.select_one('#availability')
        if stock_element:
            stock_text = stock_element.get_text().lower()
            if "in stock" in stock_text:
                current_stock = "IN_STOCK"
            # Handle "Only 5 left in stock", etc.
            elif re.search(r'only \d+ left in stock', stock_text):
                 current_stock = "IN_STOCK"

        print(f"Result: {product_name}, Price: {current_price}, Stock: {current_stock}")
        return product_name, current_price, current_stock

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        return None, 0.0, "OUT_OF_STOCK"
    except Exception as e:
        print(f"Scraping error: {e}")
        return None, 0.0, "OUT_OF_STOCK"

def send_email_alert(recipient, subject, body):
    """Sends an email using AWS SES."""
    print(f"Sending EMAIL to {recipient}...")
    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
    except Exception as e:
        print(f"SES email failed: {e}")

def send_telegram_alert(chat_id, message):
    """Sends a message using the Telegram Bot API."""
    print(f"Sending TELEGRAM to {chat_id}...")
    try:
        secrets = get_secrets()
        token = secrets['TELEGRAM_BOT_TOKEN']
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram alert failed: {e}")

#
# This is the new lambda_handler for scrapePrice.py
#
def lambda_handler(event, context):
    print("--- Starting Price Tracker Run ---")
    
    try:
        # Get secrets
        all_secrets = get_secrets()
        scraper_api_key = all_secrets['SCRAPER_API_KEY']
        
        # 1. Get all products from DynamoDB
        response = table.scan()
        items = response.get('Items', [])
        print(f"Found {len(items)} items to track.")
        
        alerts_sent = 0
        
        # 2. Loop through each product and check
        for item in items:
            product_url = item['ProductURL']
            target_price = float(item.get('TargetPriceLow', 0)) # Get TargetPrice, default to 0
            notify_on_stock = item.get('NotifyOnStock', False)
            last_stock = item.get('LastKnownStock', 'OUT_OF_STOCK')
            notification_type = item.get('NotificationType', 'EMAIL')
            notification_target = item.get('NotificationTarget')
            
            # Get the service type, default to PRICE for old items
            service_type = item.get('ServiceType', 'PRICE')

            if not notification_target:
                print(f"Skipping {product_url}: No notification target.")
                continue

            # 3. Scrape the product
            name, price, stock = scrape_product(product_url, scraper_api_key)
            
            if not name: # Scrape failed
                print(f"Scrape failed for {product_url}, skipping.")
                continue

            alert_subject = ""
            alert_body = ""
            alert_needed = False

            # 4. Check for alerts BASED ON SERVICE TYPE
            
            # --- SERVICE 1: STOCK ONLY ---
            if service_type == 'STOCK':
                if notify_on_stock and stock == "IN_STOCK" and last_stock == "OUT_OF_STOCK":
                    alert_subject = f"Back in Stock! {name}"
                    alert_body = f"{name} is back in stock at ₹{price}!\n\nBuy now: {product_url}"
                    item['NotifyOnStock'] = False # Mark as done
                    alert_needed = True
            
            # --- SERVICE 2: PRICE ONLY ---
            elif service_type == 'PRICE':
                if price > 0 and price < target_price:
                    alert_subject = f"Price Drop Alert! {name}"
                    alert_body = f"Price drop! {name} is now ₹{price}!\nYour target was ₹{target_price}.\n\nBuy now: {product_url}"
                    alert_needed = True
                    # We can remove this item after a price alert
                    # table.delete_item(Key={'ProductURL': product_url}) 

            # --- SERVICE 3: BOTH ---
            elif service_type == 'BOTH':
                price_alert = (price > 0 and price < target_price)
                stock_alert = (notify_on_stock and stock == "IN_STOCK" and last_stock == "OUT_OF_STOCK")
                
                if price_alert or stock_alert:
                    alert_subject = f"Alert! {name}"
                    alert_body = ""
                    if price_alert:
                        alert_body += f"Price drop! Now ₹{price} (target was ₹{target_price}).\n"
                    if stock_alert:
                        alert_body += f"It's also back in stock!\n"
                        item['NotifyOnStock'] = False # Mark as done
                    
                    alert_body += f"\nBuy now: {product_url}"
                    alert_needed = True

            # 5. Send notifications
            if alert_needed:
                if notification_type == 'EMAIL':
                    send_email_alert(notification_target, alert_subject, alert_body)
                elif notification_type == 'TELEGRAM':
                    send_telegram_alert(notification_target, alert_body)
                
                alerts_sent += 1
            
            # 6. Update the item's state (stock) for the *next* run
            table.update_item(
                Key={'ProductURL': product_url},
                UpdateExpression="SET LastKnownStock = :s, NotifyOnStock = :n",
                ExpressionAttributeValues={
                    ':s': stock,
                    ':n': item['NotifyOnStock'] # Update this in case it was set to False
                }
            )

        print(f"--- Run Complete. {alerts_sent} alerts sent. ---")
        return {'statusCode': 200, 'body': json.dumps(f'Scan complete. {alerts_sent} alerts sent.')}

    except Exception as e:
        print(f"!!! --- CRITICAL ERROR --- !!!\n{e}")
        return {'statusCode': 500, 'body': json.dumps(f'Error: {str(e)}')}