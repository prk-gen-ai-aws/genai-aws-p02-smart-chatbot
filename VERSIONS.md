# Version History

## ph1 (Current)
- Serverless Q&A chatbot with DynamoDB session memory
- Single phase — Terraform + CloudFormation both provided
- S3 bucket uses random_id suffix (Terraform) for safe destroy/recreate
- CloudFormation uses AccountSuffix + DeploymentVersion for unique naming
- **Use ph1 for all deployments**

## Key Design Decisions
- Session memory: DynamoDB PAY_PER_REQUEST with 24hr TTL
- Context window: sliding window of last 10 messages
- Session isolation: UUID per browser session
- Model config: SSM Parameter Store (single source of truth)
