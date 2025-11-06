# CloudTrack
### An Event-Driven, Serverless E-commerce Price & Stock Tracker Built on AWS

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![AWS CDK](https://img.shields.io/badge/AWS_CDK-v2-FF9900?logo=aws-cdk&logoColor=white)
![AWS Serverless](https://img.shields.io/badge/AWS-Serverless-FF9900?logo=amazonaws&logoColor=white)
![Event-Driven](https://img.shields.io/badge/Event--Driven-true-lightgrey)

CloudTrack is a full-stack, serverless application that automatically monitors e-commerce product prices and stock availability. Users submit a product URL via a web interface and can choose to be notified of a price drop, a restock, or both. A daily automated process scrapes the product, and if an alert is triggered, the system sends an instant notification via Email or Telegram. The entire infrastructure—from the S3-hosted frontend to the API, Lambda functions, and database—is defined and deployed as a single, automated stack using the AWS CDK.

---
## 🚀 Live Demo

**[➡️ Watch the Project Demo and Walkthrough](https://drive.google.com/file/d/11J-Dj1URNgt57tqgOq-jaJCImRLWNR6j/view?usp=sharing)**

---

### 📸 Application Snapshots

1. **Successful API Call (Frontend UI)**
<img src="https://github.com/user-attachments/assets/7e8dae0d-8168-4cb8-a61b-3df65b16cd15" width="600" alt="UI">
<br><br>

2. **Email Confirmation**
<img src="https://github.com/user-attachments/assets/20dc41dc-8ac4-41c8-96c8-3ec50e2dbd2b" width="600" alt="Email Confirmation">
<br><br>

3. **Telegram Confirmation**
<img src="https://github.com/user-attachments/assets/b86fd042-9b75-4f90-9c62-1f94f4144960" width="500" alt="Telegram Confirmation">
<br><br>

4. **Price Drop Alert**
<img src="https://github.com/user-attachments/assets/52bf42c9-3f92-4679-9d4b-bfdf730d9518" width="500" alt="Price Drop Alert">

---

## ✨ Key Features

* 🎯 **Dynamic Tracking Services:** Users can select one of three tracking modes:
    1.  **Price Tracking:** Get an alert when a product's price drops below a set target.
    2.  **Stock Tracking:** Get a one-time alert when an out-of-stock item becomes available.
    3.  **Both:** Get a combined alert for either event.
* 📬 **Multi-Channel Notifications:** Receive instant confirmation and alert messages via **Amazon SES (Email)** or **Telegram**.
* 🤖 **Smart Validation Logic:** The application is stateless but smart. The API scrapes product data *on ingestion* and will return a `400 Bad Request` error if a user tries to track the stock for an item that is already *in stock*, preventing a bad request from ever entering the database.
* ⚙️ **Fully Automated & Serverless:** A "set it and forget it" system. An **AWS EventBridge** schedule runs the scraper daily with no manual intervention. The entire application is 100% serverless, meaning it costs virtually nothing when not in use.
* 🚀 **Infrastructure as Code (IaC):** The *entire* application stack—from the S3 frontend to the API, Lambdas, and database—is defined in a single Python file using the **AWS CDK**. This allows for reliable, repeatable, and automated deployments.

---

## 🏗️ Architecture Deep Dive

The entire application is built on a "two-flow" serverless, event-driven model:

1.  **Flow 1 (The "Ingestion" API):** A real-time, user-facing flow for adding new products.
2.  **Flow 2 (The "Scheduled Worker"):** An automated, backend flow for checking prices and sending alerts.

<img width="1578" height="1250" alt="awsarchpng" src="https://github.com/user-attachments/assets/d0bcc980-85df-4696-a08e-7cb448e90fb2" />

### 1. 💰 Cost & Scalability (AWS Free Tier)

This architecture is designed to be **extremely cost-effective**. For the vast majority of personal projects, this application can be run entirely within the **AWS Free Tier**.

* **AWS Lambda:** 1 million free requests per month.
* **API Gateway (HTTP API):** 1 million free calls per month.
* **DynamoDB:** 25 GB of storage. By using **On-Demand (Pay Per Request) Billing**, the application costs $0 when idle.
* **Amazon S3:** 5 GB of free storage.
* **Amazon EventBridge:** 14 million free events per month.
* **Amazon SES:** 1,000 free emails per month when called from a Lambda function.

This means you can run a powerful, scalable application that checks thousands of products per day for virtually **$0.00**.

### 2. 💡 Core Software Design Principles 

This project was built adhering to key SOLID principles, making the architecture robust, maintainable, and extensible.

* **Single Responsibility Principle (SRP):**
    Each component in the architecture has one, and only one, reason to change.
    * **`addProduct` Lambda:** Its *single responsibility* is to ingest, validate, and save a new product. Its one "reason to change" is if the business logic for *adding* a product changes.
    * **`scrapePrice` Lambda:** Its *single responsibility* is to check existing products. Its one "reason to change" is if the *alerting* logic changes.
    * **`cdk_price_tracker_stack.py`:** Its *single responsibility* is to define infrastructure. It knows nothing about scraping or business logic.
    This separation ensures that a failure in one part (like the `scrapePrice` worker) has zero impact on another (like the `addProduct` API).

* **Open-Closed Principle (OCP):**
    The application is "open for extension, but closed for modification." The core logic is decoupled from its specific tools.
    * **Swappable Scraper:** The `scrapePrice` Lambda's job is *orchestration*. If I want to switch from `ScraperAPI` to `BrightData`, I only need to modify the internal `scrape_product` helper function. The main Lambda handler and its surrounding logic remain **unchanged**.
    * **Swappable Notifications:** The alert logic is a simple router. If I want to add `Twilio (SMS)` or `Slack` notifications, I simply add a new `elif notification_type == 'SMS':` block and a `send_sms_alert()` function. The existing, working Email and Telegram code is **never modified**, eliminating the risk of regression.

* **Dependency Inversion Principle (DIP):**
    High-level modules do not depend on low-level modules; both depend on abstractions.
    * **High-Level Module:** The main `lambda_handler` in `scrapePrice.py`, which contains the core business logic (scan, loop, check, alert).
    * **Low-Level Module:** The `boto3` client for SES or the `requests` call to the Telegram API.
    * **Abstraction:** My helper functions (`send_email_alert()`, `send_telegram_alert()`).
    The `lambda_handler` only depends on the `send_email_alert()` abstraction, not on the `boto3` implementation. This allows me to completely change *how* emails are sent (e.g., switch to SendGrid) just by modifying the helper function, without touching the main business logic.

### 3. ⚙️ Why This Design? (Service-by-Service Breakdown)

* **Why AWS CDK?**
    Infrastructure as Code (IaC) is the modern standard for cloud deployment. Instead of manually clicking in the AWS console (which is error-prone and not repeatable), I chose to define the entire stack in Python. This allows for 100% reproducible deployments, version control (via Git), and automated CI/CD pipelines. The CDK "synthesizes" this Python code into a robust AWS CloudFormation template.

* **Why Two Lambda Functions? (SRP)**
    As described in the SOLID principles, the application is split into two functions (`addProduct` and `scrapePrice`) to ensure a clean separation of concerns. This makes the system more resilient, as a failure in the backend worker (Flow 2) does not affect the user-facing API (Flow 1).

* **Why API Gateway (HTTP API)?**
    I needed a public "front door" for my `addProduct` Lambda. I chose the **HTTP API** over the older REST API because it's up to 70% cheaper, has lower latency, and is simpler to configure for a basic Lambda proxy, which was all I needed.

* **Why DynamoDB (NoSQL)?**
    My data is a simple key-value store (`ProductURL` ➡️ `data`). I don't need complex relational joins. A NoSQL, serverless database like **DynamoDB** is the perfect fit. Using **On-Demand (Pay Per Request) Billing** is the most critical feature, as it allows the table to scale from zero requests to thousands per second and back down, with no provisioned capacity to manage.

* **Why EventBridge?**
    I needed a reliable, serverless "cron job" to trigger my `scrapePrice` Lambda. **EventBridge** is the "central nervous system" for AWS Event-Driven Architectures (EDAs) and is the native solution for scheduled events.

* **Why a 3rd Party Scraper API? (The Most Important Decision)**
    Scraping sites like Amazon directly from an AWS Lambda is nearly impossible and destined to fail.
    1.  **IP Blocking:** Amazon instantly blocks requests from AWS datacenter IP addresses.
    2.  **CAPTCHAs & JS Rendering:** Amazon uses JavaScript to load prices and serves CAPTCHAs to block bots. `BeautifulSoup` (bs4) can't run JavaScript, and `Selenium` (a full browser) is too large and slow for a Lambda package.
    3.  **Maintenance Nightmare:** Amazon changes its HTML layout and CSS selectors *weekly* to break scrapers.
    I solved this by outsourcing the most fragile part of the app to a service (like ScraperAPI) whose *entire job* is to manage these problems. My Lambda's job is simply **orchestration**, not scraping.

* **Why Secrets Manager & SES?**
    **Secrets Manager** allows me to securely store and inject my API keys and bot tokens at runtime, keeping them out of my source code. **SES** is a powerful, managed service that allows me to send thousands of emails for pennies, with high deliverability (i.e., not going to spam).

### 4. 🔒 Security & Permissions (IAM)

A key part of this project is adhering to the **Principle of Least Privilege**. The AWS CDK automatically creates IAM Roles for each Lambda function, but they don't get permissions for *everything*.

The CDK's `grant_read_data()` (for Secrets Manager) and `grant_read_write_data()` (for DynamoDB) are high-level "constructs" that automatically create the correct policies.

However, to send email, I had to **manually add a custom policy** to each Lambda's execution role. This ensures the Lambdas can *only* access SES and no other services unnecessarily.

Here is the JSON for the custom IAM policy statement that the CDK attaches to both Lambda roles:
```json
{
  "Effect": "Allow",
  "Action": "ses:SendEmail",
  "Resource": "*"
}
```
*(Note: In a production environment with multiple apps, this `Resource` would be restricted to a specific SES identity ARN.)*

---

## 🛠️ Tech Stack

| Category | Technology |
| :--- | :--- |
| **Cloud** | AWS (Lambda, API Gateway, DynamoDB, S3, EventBridge, SES, Secrets Manager, IAM) |
| **IaC** | AWS CDK (Python) |
| **Backend** | Python |
| **Frontend** | HTML, CSS, JavaScript (Vanilla) |
| **External APIs** | ScraperAPI, Telegram Bot API |

---

## 🗂️ Project Structure

```bash
.
├── assets/                    # Holds all our application code
│   ├── frontend/              # Vanilla JS frontend website
│   │   ├── index.html       # The main HTML page
│   │   ├── script.js        # Frontend logic and API calls
│   │   └── style.css        # All styling
│   └── lambda/                # Python code for our Lambda functions
│       ├── addProduct.py      # Lambda for the "Add Product" flow
│       └── scrapePrice.py     # Lambda for the "Price Check" flow
├── cdk_price_tracker/         # The CDK app's Python module
│   ├── __init__.py
│   └── cdk_price_tracker_stack.py # This one file defines ALL infrastructure
├── .gitignore                 # Tells Git what to ignore (e.g., .venv)
├── app.py                     # The CDK app entry point
├── cdk.json                   # CDK configuration file
├── LICENSE                    # The MIT License file
├── README.md                  # This file
└── requirements.txt           # Python dependencies for the CDK app
```

---

## 🚀 Setup & Deployment

This project is built to be deployed with the AWS CDK.

#### 1. Prerequisites
* Node.js (v16+)
* Python (v3.12+)
* AWS CLI installed and configured (run `aws configure`)

#### 2. Manual AWS Setup (One-time only)

This is the only manual part. The CDK needs three resources to be created first.

* **Amazon SES:**
    1.  Go to the SES console and click "Verified identities."
    2.  Verify an email address (e.g., `you@example.com`). This will be your `SENDER_EMAIL`.
    3.  **IMPORTANT:** By default, your SES account is in a **Sandbox**. This means you can *only* send emails *to* other verified addresses.
    4.  **To go to Production:** You must request production access from the SES console. This involves explaining your use case (e.g., "This is a personal project to send price alerts to myself and friends who opt-in"). Once approved, you can email any address.

* **AWS Secrets Manager:**
    1.  Go to the Secrets Manager console and create a new secret.
    2.  Store two "Key-Value" pairs:
        * `SCRAPER_API_KEY`: `(your_scraper_api_key)`
        * `TELEGRAM_BOT_TOKEN`: `(your_telegram_bot_token)`
    3.  Note the **name** of your secret (e.g., `PriceTrackerSecrets`).

* **AWS Lambda Layer (Local Setup):**
    Your Lambda functions need the `requests` and `beautifulsoup4` libraries. You will need to create a Layer for them.
    1.  On your local machine, create a folder and install the packages:
        ```bash
        mkdir -p my-scraper-layer/python
        pip install requests beautifulsoup4 -t ./my-scraper-layer/python
        ```
    2.  Zip the *contents* of the `my-scraper-layer` folder (the `python` directory):
        ```bash
        cd my-scraper-layer
        zip -r ../scraper_layer.zip .
        cd ..
        ```
    3.  Go to the Lambda console > "Layers" > "Create Layer".
    4.  Name it (e.g., `ScraperLayer`), upload your `scraper_layer.zip` file, and select the `Python 3.12` runtime.
    5.  Once created, click on your new layer and **copy its Version ARN**.

#### 3. Configure the CDK Code
* Clone this repository.
* Open `cdk_price_tracker/cdk_price_tracker_stack.py`.
* Update the placeholder values in the `__init__` method with the resources you just created:
    * `YOUR_MANUAL_SECRET_NAME` ➡️ Your secret name (e.g., `PriceTrackerSecrets`)
    * `YOUR_MANUAL_LAYER_ARN` ➡️ The full Layer Version ARN you copied.
    * `YOUR_VERIFIED_SENDER_EMAIL` ➡️ The email you verified with SES.

#### 4. Deploy the Stack
* Create and activate a Python virtual environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
* Bootstrap your AWS account for CDK (one-time command per region):
    ```bash
    cdk bootstrap
    ```
* Deploy the application:
    ```bash
    cdk deploy
    ```
* The terminal will ask you to confirm security changes. Review them and press `y`.
* When finished, the terminal will output two URLs: `CdkApiEndpoint` and `CdkWebsiteURL`.

#### 5. Final Frontend Configuration
* The CDK deployed your website with a placeholder API URL. It needs to be updated with the *real* URL.
* Copy the `CdkApiEndpoint` output from your terminal.
* Open `assets/frontend/script.js` and paste this URL into the `API_ENDPOINT` variable.
* Run `cdk deploy` **one more time**. The CDK is smart and will detect only the S3 bucket needs updating, so this will be very fast.

Your website is now live at the `CdkWebsiteURL`!

---

## 🔮 Future Work

This project has a strong foundation for more features:

* **User Authentication:** Use **AWS Cognito** to add user sign-up and login. This would involve updating the API Gateway to use a Cognito Authorizer and adding a `UserID` as a primary or sort key in DynamoDB to secure user data.
* **Price History Dashboard:** Modify the `scrapePrice` Lambda to *append* the new price to a list in DynamoDB instead of just overwriting it. A new `GET /products/{id}` API route could fetch this history, which a frontend (using Chart.js) could then display as a graph.
* **ML Price Prediction:** Once price history is being collected, this time-series data could be fed into **Amazon SageMaker**. A simple model (like ARIMA or Prophet) could be trained and exposed via a new Lambda function to predict if a price is likely to drop further.
* **CI/CD Pipeline:** Create a **GitHub Actions** workflow (`.github/workflows/deploy.yml`) that automatically lints, tests, and runs `cdk deploy --require-approval never` on every push to the `main` branch, creating a fully automated deployment pipeline.

---

## 🗑️ Project Shutdown

To avoid ongoing costs, you can destroy the entire application stack with one command.

```bash
cdk destroy
```

---

## 🤝 Contributing

Contributions are welcome! This project was built for learning and as a portfolio piece. If you have ideas for improvements or find a bug, please feel free to:

1.  Open an issue to discuss what you would like to change.
2.  Fork the repository and create a new branch.
3.  Make your changes and open a pull request.

---

## 📜 License

This project is licensed under the **MIT License**.

This means you are free to use, copy, modify, and distribute this code for your own projects, including for commercial use. The only requirement is that you include the original copyright and license notice in any copy of the software.

See the [LICENSE](LICENSE) file for full details.
