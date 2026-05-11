# AWS S3 Bucket Manager

Interactive CLI tool for managing AWS S3 buckets and objects, built with **boto3**.

## Features

| Category | Operations |
|----------|-----------|
| **Buckets — List** | All buckets, filter by prefix, filter by suffix |
| **Buckets — Create** | Create with region-aware config |
| **Buckets — Delete** | Single, by prefix, by suffix (with confirmation) |
| **Bucket Details** | Region, object count, total size |
| **Objects** | List, upload, download, delete |
| **Safety** | Confirmation prompts on all destructive ops |
| **Logging** | Every action logged to `s3_manager.log` |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up credentials (copy and edit)
cp .env.example .env
# → fill in AWS_KEY_ID, AWS_SECRET, and optionally AWS_DEFAULT_REGION

# 3. Run
python learn_s3.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AWS_KEY_ID` | ✅ | — | IAM access key |
| `AWS_SECRET` | ✅ | — | IAM secret key |
| `AWS_DEFAULT_REGION` | ❌ | `us-east-1` | AWS region |

## Project Structure

```
boto3/
├── learn_s3.py          # Main application
├── requirements.txt     # Python dependencies
├── .env.example         # Credential template
├── .gitignore           # Keeps secrets out of git
├── s3_list_response.json# Sample API response (reference)
└── README.md            # This file
```
