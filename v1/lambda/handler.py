"""
Project 2 — Smart Q&A Chatbot
Lambda Handler — placeholder
Real implementation coming next step
"""

def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': '{"message": "Chatbot handler placeholder"}'
    }
