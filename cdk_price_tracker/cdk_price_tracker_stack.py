from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as apigw_integrations,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager
)
from constructs import Construct

class CdkPriceTrackerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- 1. Define the DynamoDB Table ---
        
        product_table = dynamodb.Table(
            self, "CdkProductTable",
            
            # Set the partition key (primary key) to 'ProductURL' which is a String
            partition_key=dynamodb.Attribute(
                name="ProductURL",
                type=dynamodb.AttributeType.STRING
            ),
            
            # Use On-Demand (Pay Per Request) billing.
            # This is serverless and perfect for unpredictable load.
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            
            # Set the removal policy.
            # RemovalPolicy.DESTROY means the table will be deleted
            # when we run 'cdk destroy'. This is good for development.
            # The default is RETAIN, which is safer for production.
            removal_policy=RemovalPolicy.DESTROY
        )

        # --- 2. Define the S3 Bucket for the Frontend ---
        
        frontend_bucket = s3.Bucket(
            self, "CdkFrontendBucket",
            
            website_index_document="index.html",
            
            #Giving the Bucket Public access
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                ignore_public_acls=False,
                block_public_policy=False,
                restrict_public_buckets=False
            ),
            
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Manually add the public read policy,
        frontend_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[f"{frontend_bucket.bucket_arn}/*"],
                principals=[iam.AnyPrincipal()] # 'Principal': '*'
            )
        )

        # --- 3. Deploy the Frontend Files to the S3 Bucket ---
        
        s3_deployment.BucketDeployment(
            self, "CdkDeployFrontend",
            sources=[s3_deployment.Source.asset("./assets/frontend")],
            destination_bucket=frontend_bucket
        )


        # --- 4. Import Existing Resources ---
        
        # Import your existing Secrets Manager secret
        # !! REPLACE 'YOUR_MANUAL_SECRET_NAME' with your secret's name !!
        app_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "CdkImportedSecret",
            "YOUR_MANUAL_SECRET_NAME"
        )

        # Import your existing Lambda Layer
        # !! REPLACE 'YOUR_MANUAL_LAYER_ARN' with your layer's ARN !!
        scraper_layer = _lambda.LayerVersion.from_layer_version_arn(
            self, "CdkImportedLayer",
            "YOUR_MANUAL_LAYER_ARN"
        )

        # --- 5. Define the "addProduct" Lambda Function ---
        
        add_product_lambda = _lambda.Function(
            self, "CdkAddProductLambda",
            
            # Use the Python 3.12 runtime
            runtime=_lambda.Runtime.PYTHON_3_12,
            
            # Point to the code in your 'assets/lambda' folder
            code=_lambda.Code.from_asset("assets/lambda"),
            
            # Set the handler (file_name.function_name)
            handler="addProduct.lambda_handler",
            
            # Attach the layer with 'requests' and 'bs4'
            layers=[scraper_layer],
            
            # Set environment variables
            environment={
                "TABLE_NAME": product_table.table_name,
                "SECRET_NAME": app_secret.secret_name,
                "SENDER_EMAIL": "YOUR_VERIFIED_SENDER_EMAIL" # Or import from a config
            },
            
            # Set timeout (scraping can be slow)
            timeout=Duration.seconds(30)
        )

        # --- 6. Define the "scrapePrice" Lambda Function ---
        
        scrape_price_lambda = _lambda.Function(
            self, "CdkScrapePriceLambda",
            
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset("assets/lambda"),
            handler="scrapePrice.lambda_handler",
            layers=[scraper_layer],
            
            environment={
                "TABLE_NAME": product_table.table_name,
                "SECRET_NAME": app_secret.secret_name,
                "SENDER_EMAIL": "YOUR_VERIFIED_SENDER_EMAIL"
            },
            
            # This function loops and needs a long timeout
            timeout=Duration.minutes(15)
        )

        # --- 7. Grant Permissions ---
        
        # Grant permissions for the 'addProduct' Lambda
        product_table.grant_write_data(add_product_lambda)
        app_secret.grant_read(add_product_lambda)
        add_product_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                resources=["*"] # For this project, a broad policy is fine
            )
        )

        # Grant permissions for the 'scrapePrice' Lambda
        product_table.grant_read_write_data(scrape_price_lambda) # Needs read (scan) and write (update)
        app_secret.grant_read(scrape_price_lambda)
        scrape_price_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                resources=["*"]
            )
        )

        # --- 8. Define the API Gateway ---

        http_api = apigw.HttpApi(
            self, "CdkHttpApi",
            api_name="CdkPriceTrackerApi",
            # This configures CORS.
            cors_preflight={
                "allow_headers": ["Content-Type"],
                "allow_methods": [apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
                "allow_origins": ["*"]
            }
        )

        # --- 9. Define the API Gateway Integration ---

        # This connects the API to the Lambda function
        add_product_integration = apigw_integrations.HttpLambdaIntegration(
            "CdkAddProductIntegration",
            add_product_lambda
        )

        # --- 10. Define the API Route ---

        # This creates the '/product' route with the POST method
        http_api.add_routes(
            path="/product",
            methods=[apigw.HttpMethod.POST],
            integration=add_product_integration
        )

        # --- 11. Define the EventBridge Schedule ---

        # This creates the "rate(1 day)" schedule
        schedule = events.Schedule.rate(Duration.days(1))

        # --- 12. Define the EventBridge Rule ---

        # This connects the schedule to the 'scrapePrice' Lambda
        events.Rule(
            self, "CdkScraperScheduleRule",
            schedule=schedule,
            targets=[targets.LambdaFunction(scrape_price_lambda)]
        )

        # --- 13. Output the URLs ---

        # This will print the final URLs in your terminal after deployment
        
        CfnOutput(
            self, "CdkWebsiteURL",
            description="The URL of the frontend website",
            value=frontend_bucket.bucket_website_url
        )

        CfnOutput(
            self, "CdkApiEndpoint",
            description="The API endpoint for the frontend to call",
            value=f"{http_api.url}product" # We add the /product path
        )
