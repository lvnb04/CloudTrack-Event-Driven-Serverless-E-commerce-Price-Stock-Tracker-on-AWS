import json
import boto3
import os
import requests
from bs4 import BeautifulSoup
import datetime
import re
from decimal import Decimal

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


def normalize_amazon_url(url):
    """Extracts the canonical ASIN-based URL from a messy Amazon URL."""
    # Regex to find the /dp/ASIN part
    match = re.search(r'/(dp|gp/product)/([A-Z0-9]{10})', url)
    if match:
        asin = match.group(2)
        # We build a clean, standard URL
        return f"https://www.amazon.in/dp/{asin}"

    # If no match, return the original (less ideal, but avoids crash)
    return url

def get_secrets():
    """Fetches secrets from AWS Secrets Manager and caches them."""
    global secrets
    if not secrets:
        print("Fetching secrets from Secrets Manager...")
        response = secretsmanager.get_secret_value(SecretId=SECRET_NAME)
        secrets = json.loads(response['SecretString'])
    return secrets

def scrape_product_details(url, scraper_api_key):
    """
    Scrapes a product page for its name, price, image, and stock.
    """
    print(f"Scraping {url} for initial details...")
    payload = {'api_key': scraper_api_key, 'url': url}
    
    try:
        # Using https and a 25-second timeout to avoid API Gateway timeout
        response = requests.get('https://api.scraperapi.com', params=payload, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Scrape Product Name
        product_name = soup.select_one('#productTitle')
        if product_name:
            product_name = product_name.get_text().strip()
        else:
            product_name = "Product Name Not Found"

        # 2. Scrape Price
        current_price = 0.0
        price_element = soup.select_one('span.a-price-whole')
        if price_element:
            price_text = price_element.get_text().replace(',', '').replace('₹', '').replace('.', '').strip()
            current_price = float(price_text)
        else:
            price_element = soup.select_one('#corePrice_feature_div .a-offscreen')
            if price_element:
                price_text = price_element.get_text().replace(',', '').replace('₹', '').strip()
                # Handle prices like '1,34,900.00'
                current_price = float(price_text.split('.')[0].replace(',', ''))
        
        # 3. Scrape Image URL
        image_url = ""
        image_element = soup.select_one('#landingImage') # Main product image
        if image_element:
            image_url = image_element.get('src')
        else:
            # Try finding a different image structure
            image_element = soup.select_one('#imgTagWrapperId img')
            if image_element:
                image_url = image_element.get('src')
        
        # 4. Scrape Stock (to set initial state)
        current_stock = "OUT_OF_STOCK"
        stock_element = soup.select_one('#availability')
        if stock_element:
            stock_text = stock_element.get_text().lower()
            if "in stock" in stock_text or re.search(r'only \d+ left in stock', stock_text):
                 current_stock = "IN_STOCK"

        print(f"Scrape Result: {product_name}, Price: {current_price}, Stock: {current_stock}")
        return product_name, current_price, image_url, current_stock

    except Exception as e:
        print(f"Scraping error: {e}")
        return "Scrape Failed", 0.0, "", "OUT_OF_STOCK"

def send_confirmation_email(recipient, product_name, current_price, image_url, product_url):
    """Sends a rich HTML confirmation email using AWS SES."""
    print(f"Sending confirmation EMAIL to {recipient}...")
    
    CHARSET = "UTF-8"
    SUBJECT = f"Tracking Added: {product_name}"
    
    # The HTML body of the email
    BODY_HTML = f"""
    <html>
    <head></head>
    <body style="font-family: Arial, sans-serif; font-size: 16px;">
        <h1>Tracking Confirmation</h1>
        <p>We've successfully added the following product to your tracking list:</p>
        
        <h2 style="color: #007bff;">{product_name}</h2>
        
        <div style="display: flex;">
            <img src="{image_url}" alt="Product Image" style="max-width: 200px; margin-right: 20px;">
            <div>
                <p><strong>Current Price:</strong> ₹{current_price}</p>
                <p><strong>Tracking URL:</strong> <a href="{product_url}">View Product</a></p>
                <p>We will notify you at this email address (or via Telegram) if the price drops below your target or if it comes back in stock.</p>
            </div>
        </div>
        
        <p style="font-size: 12px; color: #888;">Timestamp: {datetime.datetime.now().isoformat()}</p>
    </body>
    </html>
    """
    
    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': SUBJECT, 'Charset': CHARSET},
                'Body': {'Html': {'Data': BODY_HTML, 'Charset': CHARSET}}
            }
        )
    except Exception as e:
        print(f"SES confirmation email failed: {e}")
        raise e # Re-raise error to fail the Lambda

def send_telegram_alert(chat_id, message):
    """Sends a message using the Telegram Bot API."""
    # We use 'Markdown' to allow for bolding and links
    print(f"Sending TELEGRAM confirmation to {chat_id}...")
    try:
        all_secrets = get_secrets() # This will use the cached secrets
        token = all_secrets['TELEGRAM_BOT_TOKEN']
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        payload = {
            'chat_id': chat_id, 
            'text': message,
            'parse_mode': 'Markdown' # This allows for bolding and links
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status() # Check for HTTP errors
    except Exception as e:
        print(f"Telegram confirmation failed: {e}")
        raise e # Re-raise error to fail the Lambda

#
# This is the lambda_handler for addProduct.py
#
def lambda_handler(event, context):
    print(f"Received event: {event}")
    
    # --- Define CORS headers. We'll use this in all responses ---
    cors_headers = {
        'Access-Control-Allow-Origin': '*', 
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS'
    }
    
    try:
        # 1. Parse data from API Gateway
        body = json.loads(event.get('body', '{}'))
        
        product_url = body.get('url')
        target_price_str = body.get('price', "0") # Default to "0"
        service_type = body.get('serviceType', 'PRICE').upper() # Default to PRICE
        notification_type = body.get('notificationType', 'EMAIL').upper()
        notification_target = body.get('notificationTarget')
        
        # --- Basic Input Validation ---
        if not product_url or not notification_target:
             return {
                'statusCode': 400, 
                'headers': cors_headers,
                'body': json.dumps('Error: Missing url or notificationTarget.')
            }

        # --- Service-Based Price Validation ---
        if service_type == 'PRICE' or service_type == 'BOTH':
            try:
                # Try to convert the price string to a Decimal
                target_price_decimal = Decimal(target_price_str)
                # Check if the price is a positive number
                if target_price_decimal <= 0:
                    raise ValueError("Price must be positive")
            except Exception as e:
                # This will catch errors like invalid text ("abc") or a price of 0 or less
                print(f"Invalid target price: {e}")
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps('Error: Invalid target price. Must be a number greater than 0 for this service.')
                }

        # --- Normalize the URL to use as a clean Primary Key ---
        normalized_url = normalize_amazon_url(product_url)

        # 2. Determine NotifyOnStock flag based on service type
        notify_on_stock = False
        if service_type == "STOCK" or service_type == "BOTH":
            notify_on_stock = True

        # 3. Get Scraper API Key
        all_secrets = get_secrets()
        scraper_api_key = all_secrets['SCRAPER_API_KEY']
        
        # 4. Scrape for initial details (using the original URL for accuracy)
        product_name, current_price, image_url, current_stock = scrape_product_details(product_url, scraper_api_key)
        
        if product_name == "Scrape Failed":
            return {
                'statusCode': 500, 
                'headers': cors_headers,
                'body': json.dumps('Error: Could not scrape product details.')
            }

        # 5. Check if user wants stock alert for an item already in stock
        if notify_on_stock and current_stock == "IN_STOCK":
            print("Error: User tried to track stock for an item that is already IN_STOCK.")
            return {
                'statusCode': 400, # 400 Bad Request (user error)
                'headers': cors_headers,
                'body': json.dumps('Error: This product is already in stock!')
            }
        
        # 6. Save to DynamoDB (using the normalized URL as the key)
        print(f"Saving item to DynamoDB: {normalized_url}")
        table.put_item(
            Item={
                'ProductURL': normalized_url,
                'TargetPriceLow': Decimal(target_price_str),
                'LastKnownPrice': Decimal(str(current_price)),
                
                'ServiceType': service_type,
                'NotifyOnStock': notify_on_stock,
                
                'NotificationType': notification_type,
                'NotificationTarget': notification_target,
                'ProductName': product_name,
                'ProductImageURL': image_url,
                'LastKnownStock': current_stock,
                'DateAdded': datetime.datetime.now().isoformat()
            }
        )
        
        # 7. Send Confirmation (using the normalized URL for the link)
        if notification_type == 'EMAIL':
            send_confirmation_email(notification_target, product_name, current_price, image_url, normalized_url)
        elif notification_type == 'TELEGRAM':
            message = (
                f"✅ *Tracking Added!*\n\n"
                f"*{product_name}*\n\n"
                f"We'll notify you here based on your selection (Price, Stock, or Both)."
                f"\n\n[View Product]({normalized_url})"
            )
            send_telegram_alert(notification_target, message)
        
        # 8. Return success
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps('Product added successfully!')
        }
            
    except Exception as e:
        print(f"!!! --- CRITICAL ERROR --- !!!\n{e}")
        return {
            'statusCode': 500, 
            'headers': cors_headers,
            'body': json.dumps(f'Error: {str(e)}')
        }
