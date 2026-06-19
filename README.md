# Smart Q&A Chatbot
Serverless Q&A chatbot with conversation memory on AWS — powered by Amazon Bedrock.

A Streamlit chat interface that remembers your conversation across multiple turns. Ask follow-up questions naturally — the chatbot uses Amazon DynamoDB to store your session history and sends the full conversation to Amazon Bedrock with every message.

Real-world use case: internal knowledge assistants, customer support bots, and any application where context-aware multi-turn conversation matters.

[View on GitHub](https://github.com/prk-gen-ai-aws/genai-aws-p02-smart-chatbot)

---

## How It Works

1. You type a message in the Streamlit chat UI — a unique session ID (UUID) is generated when you open the app
2. Your message and session ID are sent to API Gateway via POST /chat
3. AWS Lambda reads your full conversation history from Amazon DynamoDB using the session ID
4. Lambda appends your new message and sends the complete history to Amazon Bedrock (Claude Haiku 4.5)
5. Bedrock generates a context-aware response — it reads the entire conversation before replying
6. Lambda saves the updated conversation back to DynamoDB (TTL: 24 hours, sliding window: last 10 messages)
7. Response travels back through API Gateway to Streamlit and is displayed in the chat

The AI model ID is stored in AWS SSM Parameter Store — upgrade the model by changing one parameter, no code changes needed.

Note: The Streamlit app runs locally on your machine. Only the backend (Lambda, API Gateway, DynamoDB, SSM) runs in AWS.

Note: Switching between Terraform and CloudFormation deployments only requires updating API_GATEWAY_URL and DYNAMODB_TABLE_NAME in your .env file — the same Streamlit app works for both.

---

## Architecture

Architecture diagram: ph1/docs/architecture-ph1.png

Components:
- Streamlit (local) sends POST request to API Gateway with session ID
- API Gateway triggers Lambda
- Lambda reads session history from DynamoDB, appends new message
- Lambda fetches model ID from SSM, then calls Bedrock with full history
- Bedrock (Claude Haiku 4.5) returns context-aware response
- Lambda saves updated history to DynamoDB (24hr TTL, last 10 messages)
- Response travels back through Lambda and API Gateway to Streamlit

---

## Project Structure

    genai-aws-p02-smart-chatbot/
    ph1/                         <- phase 1
      app/                       <- Streamlit UI (runs locally)
        main.py                  <- chat app entry point
        requirements.txt         <- app dependencies
      lambda/                    <- Lambda function code
        handler.py               <- session memory + Bedrock integration
        requirements.txt         <- Lambda dependencies
        package/                 <- gitignored (build artifacts)
        handler.zip              <- gitignored (deployment package)
      IaC/
        terraform/               <- Terraform IaC
        cloudformation/          <- CloudFormation IaC
      sample-conversations/      <- ready-to-use test conversation scripts
      docs/                      <- architecture diagrams
    README.md
    VERSIONS.md
    .gitignore
    .env.example
    .streamlit/
      config.toml                <- project root level, sets 10MB upload limit

---

## Tech Stack

- Frontend: Streamlit (Python) - runs locally on your machine
- API: Amazon API Gateway (REST)
- Compute: AWS Lambda (Python 3.12)
- AI: Amazon Bedrock - Claude Haiku 4.5
- Session Memory: Amazon DynamoDB (PAY_PER_REQUEST, TTL: 24hrs)
- Config: AWS SSM Parameter Store
- IaC: Terraform + CloudFormation (both provided)
- Language: Python 3.12

---

## Terraform vs CloudFormation

Both options deploy identical application infrastructure. Choose based on your preference.

Terraform:
- State management: You manage state (S3 remote state + lock file)
- S3 bucket naming: Uses random_id suffix - always safe to destroy and recreate
- DynamoDB naming: Full standard with tf + iteration suffix
- Portability: Works across cloud providers
- Best for: Multi-cloud teams or when you want explicit state control

CloudFormation:
- State management: AWS manages state internally - no backend setup needed
- S3 bucket naming: Uses AccountSuffix + DeploymentVersion parameters
- DynamoDB naming: Full standard with cf + iteration suffix
- Portability: AWS only
- Best for: AWS-native teams or when you want simpler state management

Key difference on destroy and recreate:
- Terraform: destroy and reapply always works - random_id generates a new unique suffix automatically
- CloudFormation: after destroy, increment DeploymentVersion parameter (v1 -> v2) before redeploying

Switching between TF and CF:
- The same Streamlit app works for both deployments
- After deploying with either tool, update API_GATEWAY_URL and DYNAMODB_TABLE_NAME in .env with the output values
- Run streamlit run ph1/app/main.py - no other changes needed

---

## Prerequisites

- AWS account with CLI configured (aws configure)
- Python 3.12+
- Terraform installed (for Terraform deployment only)
- The repo includes .env.example at the root - copy it to .env after deployment and fill in your values
- First-time Bedrock activation (one-time per AWS account):
  Go to AWS Console -> Amazon Bedrock -> Playgrounds -> Chat
  Select Claude Haiku 4.5 -> send any message
  This activates your account for Anthropic models

---

## Fork and Deploy - Complete Guide

If you are forking this repo and deploying to your own AWS account, follow these steps in order.

### Before you start

Step 1 - Create and activate a Python virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Step 2 - Install app dependencies:

    pip install -r ph1/app/requirements.txt

---

### Option A: Deploy with Terraform

Step 1 - Set up the shared Terraform backend first (one-time):

Fork and deploy this repo first: https://github.com/prk-gen-ai-aws/terraform-backend
This creates the S3 bucket used to store Terraform state. Follow the README in that repo.

Step 2 - Fill in your values:

    cd ph1/IaC/terraform
    cp terraform.tfvars.example terraform.tfvars

Edit terraform.tfvars and fill in:
- aws_region: your AWS region (e.g. us-east-1)
- aws_account_id: your 12-digit AWS account ID
- project_name: keep as-is or customize
- environment: dev
- bedrock_model_id: us.anthropic.claude-haiku-4-5-20251001-v1:0
  (verify this is active in your account: aws bedrock list-inference-profiles --region us-east-1)
- session_ttl_hours: 24
- max_messages: 10

    cp backend.tfvars.example backend.tfvars

Edit backend.tfvars and fill in:
- bucket: name of the S3 bucket created by your terraform-backend deployment

Step 3 - Deploy infrastructure:

    terraform init -backend-config=backend.tfvars
    terraform plan
    terraform apply

Step 4 - Get outputs:

    terraform output

Step 5 - Deploy Lambda code:

    cd ../../..
    mkdir -p ph1/lambda/package/
    cp ph1/lambda/handler.py ph1/lambda/package/
    pip install -r ph1/lambda/requirements.txt -t ph1/lambda/package/
    cd ph1/lambda/package
    zip -r ../handler.zip .
    cd ../../..
    aws lambda update-function-code --function-name <lambda_function_name from output> --zip-file fileb://ph1/lambda/handler.zip

Step 6 - Configure environment:

    cp .env.example .env

Edit .env and fill in:
- API_GATEWAY_URL: from terraform output api_gateway_url
- DYNAMODB_TABLE_NAME: from terraform output dynamodb_table_name

---

### Option B: Deploy with CloudFormation (simpler - no backend setup needed)

Step 1 - Deploy stack:

    aws cloudformation deploy \
      --template-file ph1/IaC/cloudformation/template.yaml \
      --stack-name p02-ph1-chatbot-dev \
      --parameter-overrides \
        AccountSuffix=<last-4-digits-of-your-account-id> \
        DeploymentVersion=v1 \
      --capabilities CAPABILITY_NAMED_IAM \
      --region us-east-1

Step 2 - Get outputs:

    aws cloudformation describe-stacks --stack-name p02-ph1-chatbot-dev --query Stacks[0].Outputs

Step 3 - Deploy Lambda code:

    mkdir -p ph1/lambda/package/
    cp ph1/lambda/handler.py ph1/lambda/package/
    pip install -r ph1/lambda/requirements.txt -t ph1/lambda/package/
    cd ph1/lambda/package
    zip -r ../handler.zip .
    cd ../../..
    # Use LambdaFunctionName from Step 2 outputs
    aws lambda update-function-code --function-name <LambdaFunctionName from Step 2> --zip-file fileb://ph1/lambda/handler.zip

Step 4 - Configure environment:

    cp .env.example .env

Edit .env and fill in:
- API_GATEWAY_URL: from stack outputs (ApiGatewayUrl)
- DYNAMODB_TABLE_NAME: from stack outputs (DynamoDBTableName)

---

### Run the App (same for both options)

    source .venv/bin/activate
    streamlit run ph1/app/main.py

Note: Upload limit is set to 10MB via .streamlit/config.toml at project root.

---

## Sample Conversations

Ready-to-use conversation scripts are in ph1/sample-conversations/

- aws-basics.txt - Tests memory across EC2 and pricing topics
- serverless-basics.txt - Tests memory across Lambda concepts

Ask questions one by one and observe how the chatbot remembers context across turns.

### How session memory works

Simple explanation:
DynamoDB acts like a notebook for each conversation. When you open the app, a unique session ID is generated (like a notebook cover). Every message is written into that notebook. On each new message, Lambda reads the full notebook and sends it to Bedrock - so the AI knows everything discussed earlier.

Technical details:
- Partition key: session_id (UUID string, generated per browser session)
- Messages stored as a list of role/content pairs
- TTL: auto-expires after 24 hours (DynamoDB native TTL)
- Sliding window: only last 10 messages kept to manage context window size and cost
- Two users chatting simultaneously get completely separate sessions - full isolation

---

## Cost Estimate

All components are serverless - you pay only for what you use.

- Amazon Bedrock (Claude Haiku 4.5): approx USD 0.001 per message
- AWS Lambda: Free tier covers development usage
- API Gateway: Free tier covers development usage
- Amazon DynamoDB: negligible cost for development usage (PAY_PER_REQUEST, approx USD 0.00 for low volume)
- SSM Parameter Store: Free (standard tier)
- Total (development): less than USD 1.00 per month

---

## Things to Consider at Scale

Security:
- Add API keys or Amazon Cognito for user authentication
- VPC endpoints to keep Bedrock and DynamoDB traffic off the public internet
- Encrypt DynamoDB table with customer-managed KMS key

Scalability:
- DynamoDB auto-scales with PAY_PER_REQUEST billing
- Lambda reserved concurrency to prevent runaway costs
- Request Bedrock throughput quota increases for high-volume usage

High Availability:
- DynamoDB global tables for multi-region session persistence
- Lambda retry with exponential backoff
- API Gateway throttling to protect backend

Cost:
- DynamoDB on-demand pricing - pay only for reads/writes
- Session TTL auto-expires old data - no manual cleanup needed
- Prompt caching for repeated conversation patterns

Performance:
- Async processing via SQS for long-running conversations
- Streaming responses via API Gateway WebSocket for better UX
- Reduce MAX_MESSAGES if latency increases with long conversations

---

## AWS Documentation References

- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html
- Amazon DynamoDB: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html
- DynamoDB TTL: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html
- AWS Lambda: https://docs.aws.amazon.com/lambda/latest/dg/welcome.html
- Amazon API Gateway: https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html
- AWS SSM Parameter Store: https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html
- Terraform AWS Provider: https://registry.terraform.io/providers/hashicorp/aws/latest/docs

---

## Version History

See VERSIONS.md for details on phase history and changes.

---

> Part of an ongoing series exploring Gen AI on AWS - applying real-world architecture patterns from serverless foundations to multi-agent agentic systems.
>
> Browse all projects: https://github.com/prk-gen-ai-aws
