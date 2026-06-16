"""
Project 2 — Smart Q&A Chatbot
Lambda Handler — session management + Bedrock integration
Session memory stored in DynamoDB with 24hr TTL
"""

import json
import os
import time
import boto3
from datetime import datetime, timezone

# ── AWS clients ──
region = os.environ.get('AWS_REGION_NAME', 'us-east-1')
bedrock_client = boto3.client('bedrock-runtime', region_name=region)
dynamodb = boto3.resource('dynamodb', region_name=region)
ssm_client = boto3.client('ssm', region_name=region)

# ── Environment variables ──
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
SSM_MODEL_PARAM     = os.environ.get('SSM_MODEL_PARAM')
MAX_MESSAGES        = int(os.environ.get('MAX_MESSAGES', '10'))
SESSION_TTL_HOURS   = int(os.environ.get('SESSION_TTL_HOURS', '24'))


def get_model_id() -> str:
    """Read model ID from SSM Parameter Store."""
    response = ssm_client.get_parameter(Name=SSM_MODEL_PARAM)
    return response['Parameter']['Value']


def get_session(session_id: str) -> list:
    """Read conversation history from DynamoDB."""
    t0 = time.time()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    response = table.get_item(Key={'session_id': session_id})
    messages = response.get('Item', {}).get('messages', [])
    print(f"TIMING: DynamoDB read took {time.time()-t0:.2f}s, {len(messages)} messages")
    return messages


def save_session(session_id: str, messages: list):
    """Save conversation history to DynamoDB with TTL."""
    t0 = time.time()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    ttl = int(time.time()) + (SESSION_TTL_HOURS * 3600)
    table.put_item(Item={
        'session_id': session_id,
        'messages': messages,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'ttl': ttl
    })
    print(f"TIMING: DynamoDB write took {time.time()-t0:.2f}s")


def trim_messages(messages: list) -> list:
    """Keep only the last MAX_MESSAGES messages (sliding window)."""
    if len(messages) > MAX_MESSAGES:
        messages = messages[-MAX_MESSAGES:]
    return messages


def invoke_bedrock(messages: list, model_id: str) -> str:
    """Call Amazon Bedrock with full conversation history."""
    t0 = time.time()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0.7,
        "system": "You are a helpful AI assistant. Answer questions clearly and concisely. If you do not know something, say so honestly.",
        "messages": messages
    })
    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=body,
        contentType='application/json',
        accept='application/json'
    )
    response_body = json.loads(response['body'].read())
    answer = response_body['content'][0]['text']
    print(f"TIMING: Bedrock invoke took {time.time()-t0:.2f}s")
    return answer


def lambda_handler(event, context):
    """Main Lambda entry point."""
    t0 = time.time()
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        session_id = body.get('session_id')
        user_message = body.get('message', '').strip()

        if not session_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'session_id is required'})
            }

        if not user_message:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'message is required'})
            }

        # Get model ID from SSM
        model_id = get_model_id()

        # Read session history from DynamoDB
        messages = get_session(session_id)

        # Append new user message
        messages.append({
            'role': 'user',
            'content': user_message
        })

        # Trim to max messages
        messages = trim_messages(messages)

        # Call Bedrock with full history
        assistant_response = invoke_bedrock(messages, model_id)

        # Append assistant response
        messages.append({
            'role': 'assistant',
            'content': assistant_response
        })

        # Save updated session to DynamoDB
        save_session(session_id, messages)

        print(f"TIMING: total {time.time()-t0:.2f}s")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'response': assistant_response,
                'session_id': session_id,
                'message_count': len(messages),
                'model_id': model_id
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
