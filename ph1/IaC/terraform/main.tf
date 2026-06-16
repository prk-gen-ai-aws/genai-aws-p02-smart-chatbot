# ============================================================
# Project 2 — Smart Q&A Chatbot
# Terraform Infrastructure
# Resources: S3, DynamoDB, IAM, Lambda, API Gateway, SSM
# ============================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Random suffix for globally unique S3 bucket name ──
resource "random_id" "suffix" {
  byte_length = 4
}

# ── Local values ──
locals {
  prefix      = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "prk"
  }
}

# ============================================================
# S3 Bucket — minimal (Lambda package storage)
# ============================================================
resource "aws_s3_bucket" "chatbot" {
  bucket = "${local.prefix}-docs-${random_id.suffix.hex}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "chatbot" {
  bucket                  = aws_s3_bucket.chatbot.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "chatbot" {
  bucket = aws_s3_bucket.chatbot.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ============================================================
# DynamoDB Table — conversation session memory
# ============================================================
resource "aws_dynamodb_table" "sessions" {
  name         = "${local.prefix}-sessions-${substr(var.aws_account_id, -4, -1)}-tf-v1"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.common_tags
}

# ============================================================
# SSM Parameter — Bedrock model ID
# ============================================================
resource "aws_ssm_parameter" "bedrock_model_id" {
  name        = "/prk/genai/${var.project_name}/bedrock-model-id"
  type        = "String"
  value       = var.bedrock_model_id
  description = "Bedrock model ID for P02 chatbot"
  overwrite   = true
  tags        = local.common_tags
}

# ============================================================
# IAM Role — Lambda execution (least privilege)
# ============================================================
resource "aws_iam_role" "lambda_execution" {
  name = "${local.prefix}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_custom" {
  name = "${local.prefix}-lambda-policy"
  role = aws_iam_role.lambda_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBSessionAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.sessions.arn
      },
      {
        Sid    = "BedrockInvokeModel"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/*",
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:${var.aws_region}:${var.aws_account_id}:inference-profile/*",
          "arn:aws:bedrock:us-east-1::inference-profile/*"
        ]
      },
      {
        Sid    = "SSMReadModelId"
        Effect = "Allow"
        Action = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/prk/genai/*"
      },
      {
        Sid    = "MarketplaceSubscription"
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe",
          "aws-marketplace:Unsubscribe"
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================================
# Lambda Function — chatbot handler
# ============================================================
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../../lambda/handler.py"
  output_path = "${path.module}/../../lambda/handler.zip"
}

resource "aws_lambda_function" "chatbot" {
  function_name    = "${local.prefix}-handler"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.sessions.name
      SSM_MODEL_PARAM     = aws_ssm_parameter.bedrock_model_id.name
      AWS_REGION_NAME     = var.aws_region
      MAX_MESSAGES        = tostring(var.max_messages)
      SESSION_TTL_HOURS   = tostring(var.session_ttl_hours)
    }
  }
  tags = local.common_tags
}

# ============================================================
# API Gateway — REST API
# ============================================================
resource "aws_api_gateway_rest_api" "chatbot" {
  name        = "${local.prefix}-api"
  description = "P02 Smart Chatbot API"
  tags        = local.common_tags
}

resource "aws_api_gateway_resource" "chat" {
  rest_api_id = aws_api_gateway_rest_api.chatbot.id
  parent_id   = aws_api_gateway_rest_api.chatbot.root_resource_id
  path_part   = "chat"
}

resource "aws_api_gateway_method" "chat_post" {
  rest_api_id   = aws_api_gateway_rest_api.chatbot.id
  resource_id   = aws_api_gateway_resource.chat.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.chatbot.id
  resource_id             = aws_api_gateway_resource.chat.id
  http_method             = aws_api_gateway_method.chat_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.chatbot.invoke_arn
}

resource "aws_api_gateway_deployment" "chatbot" {
  rest_api_id = aws_api_gateway_rest_api.chatbot.id
  depends_on  = [aws_api_gateway_integration.lambda]
}

resource "aws_api_gateway_stage" "chatbot" {
  rest_api_id   = aws_api_gateway_rest_api.chatbot.id
  deployment_id = aws_api_gateway_deployment.chatbot.id
  stage_name    = var.environment
  tags          = local.common_tags
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chatbot.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.chatbot.execution_arn}/*/*"
}
