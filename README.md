# 🪣 AWS S3 Bucket Manager

> **Interactive CLI tool for managing AWS S3 buckets and objects, built with Python & boto3.**

A powerful, color-coded command-line interface for everyday S3 operations — from simple bucket listing to full security audits across all AWS regions.

---

## ✨ Features

### 🗂️ Bucket Management
| Operation | Description |
|-----------|-------------|
| **List All** | View all buckets (single region or across all regions) |
| **Filter by Prefix** | Find buckets starting with a specific string |
| **Filter by Suffix** | Find buckets ending with a specific string |
| **Create Bucket** | Create with automatic region-aware configuration |
| **Delete Single** | Delete a bucket with safety confirmation |
| **Delete by Prefix/Suffix** | Batch-delete matching buckets (with confirmation) |
| **Bucket Details** | View region, object count, and total size |

### 📦 Object Operations
| Operation | Description |
|-----------|-------------|
| **List Objects** | Browse all objects in a bucket with size & modified date |
| **Upload File** | Upload local files with custom S3 key support |
| **Download File** | Download objects to a local path |
| **Delete Object** | Remove objects with confirmation prompt |

### 🔍 Search & Audit *(Advanced — `s3-manager.py`)*
| Filter | Description |
|--------|-------------|
| **Owner Name** | Search buckets by owner (substring match) |
| **ACL Status** | Filter public vs. private ACL buckets |
| **Versioning** | Find Enabled / Suspended / Disabled |
| **Encryption** | Filter by SSE-S3 (AES256), SSE-KMS, or unencrypted |
| **Public Access Block** | Check if all public access is blocked |
| **Logging** | Find buckets with/without access logging |
| **Tags** | Search by tag key or key=value pair |
| **Region** | Filter by AWS region |
| **Lifecycle Rules** | Find buckets with/without lifecycle policies |
| **Bucket Policy** | Check for attached bucket policies |
| **Full Audit** | Comprehensive metadata view of all buckets |
| **🔒 Security Audit** | Auto-detect risky configurations (public ACL, no encryption, etc.) |

### 🌍 Region Modes
- **Single Region** — All operations scoped to one AWS region
- **All Regions** — Scan and manage buckets across every AWS region

### 🛡️ Safety & Logging
- ⚠️ Confirmation prompts on all destructive operations
- 📝 Every action logged to `s3_manager.log` for audit trails
- 🎨 Color-coded terminal output with formatted tables

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Abdulrhman418/boto3-s3-manager.git
cd boto3-s3-manager

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up credentials
cp .env.example .env
# Edit .env and fill in your AWS_KEY_ID and AWS_SECRET

# 4. Run the basic manager
python main.py

# 5. Or run the advanced manager (with search & audit)
python s3-manager.py
```

---

## 🔐 Environment Variables

Create a `.env` file in the project root:

```env
AWS_KEY_ID=your-access-key-id
AWS_SECRET=your-secret-access-key
AWS_DEFAULT_REGION=us-east-1    # optional, defaults to us-east-1
```

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `AWS_KEY_ID` | ✅ | — | IAM access key ID |
| `AWS_SECRET` | ✅ | — | IAM secret access key |
| `AWS_DEFAULT_REGION` | ❌ | `us-east-1` | Default AWS region |

> ⚠️ **Never commit credentials to git.** The `.gitignore` already excludes `.env` and `access key.txt`.

---

## 📁 Project Structure

```
boto3-s3-manager/
├── main.py              # Core S3 manager — buckets & objects
├── s3-manager.py        # Advanced manager — adds search & security audit
├── requirements.txt     # Python dependencies (boto3, dotenv, colorama)
├── .env.example         # Credential template (copy to .env)
├── .gitignore           # Excludes secrets, logs, and generated files
└── README.md            # This file
```

---

## 🧰 Dependencies

| Package | Purpose |
|---------|---------|
| `boto3` ≥ 1.34.0 | AWS SDK for Python |
| `python-dotenv` ≥ 1.0.0 | Load `.env` credentials |
| `colorama` ≥ 0.4.6 | Cross-platform colored terminal output |

---

## 📸 Menu Preview

```
════════════════════════════════════════════════════════════
  AWS S3 Bucket Manager
════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────
  S3 BUCKET MANAGER  ─  us-east-1
────────────────────────────────────────────────────────────
  1 — List Buckets
  2 — Create Bucket
  3 — Delete Bucket(s)
  4 — Bucket Details
  5 — Object Operations
  6 — Search & Audit Buckets
  0 — Exit
```

---

## 📝 License

This project is open source and available for personal and educational use.

---

## 👤 Author

**Abdulrhman** — [GitHub](https://github.com/Abdulrhman418)
