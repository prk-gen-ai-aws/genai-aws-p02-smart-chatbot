# ============================================================
# Remote Backend Configuration — Project 2 v1
# Uses shared S3 bucket for state + native S3 lock file
# ============================================================
terraform {
  backend "s3" {
    bucket       = "prk-terraform-state-ACCOUNT-ID"
    key          = "p02-ph1-chatbot/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
