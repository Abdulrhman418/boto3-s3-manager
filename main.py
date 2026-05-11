"""
AWS S3 Bucket Manager — Interactive CLI tool for managing S3 buckets and objects.

Features:
  - Region selection: single region or all regions
  - List / filter buckets (all, by prefix, by suffix)
  - Create buckets with validation
  - Delete buckets with safety confirmations
  - Upload / download / list objects inside buckets
  - View bucket details (region, creation date, object count)
  - Colored terminal output & formatted tables
  - File logging for audit trail
"""

import boto3
import json
import os
import sys
import logging
from datetime import datetime

# ──────────────────── Optional: dotenv & colorama ────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env support is optional

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
except ImportError:
    # Provide no-op colour stubs so the script works without colorama
    class _NoColor:
        def __getattr__(self, _):
            return ""
    Fore = Style = _NoColor()

# ──────────────────── Logging ────────────────────
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s3_manager.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────── AWS Regions ────────────────────
AWS_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "af-south-1", "ap-east-1", "ap-south-1", "ap-south-2",
    "ap-southeast-1", "ap-southeast-2", "ap-southeast-3", "ap-southeast-4",
    "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
    "ca-central-1", "ca-west-1",
    "eu-central-1", "eu-central-2", "eu-west-1", "eu-west-2", "eu-west-3",
    "eu-south-1", "eu-south-2", "eu-north-1",
    "il-central-1", "me-south-1", "me-central-1",
    "sa-east-1",
]

# ──────────────────── Pretty helpers ────────────────────
SEPARATOR = f"{Fore.CYAN}{'─' * 60}{Style.RESET_ALL}"

def header(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"{Fore.YELLOW}  {title}{Style.RESET_ALL}")
    print(SEPARATOR)

def success(msg: str) -> None:
    print(f"{Fore.GREEN}  ✔ {msg}{Style.RESET_ALL}")

def error(msg: str) -> None:
    print(f"{Fore.RED}  ✘ {msg}{Style.RESET_ALL}")

def info(msg: str) -> None:
    print(f"{Fore.CYAN}  ℹ {msg}{Style.RESET_ALL}")

def warn(msg: str) -> None:
    print(f"{Fore.YELLOW}  ⚠ {msg}{Style.RESET_ALL}")

def confirm(prompt: str) -> bool:
    """Ask for yes/no confirmation. Returns True on 'y'."""
    answer = input(f"{Fore.YELLOW}  ⚠ {prompt} (y/N): {Style.RESET_ALL}").strip().lower()
    return answer == "y"


# ──────────────────── S3 Manager Class ────────────────────
class S3Manager:
    """Wraps boto3 S3 operations with error handling and logging.

    Supports two modes:
      - Single region: all operations target one specific region
      - All regions:   read operations scan every AWS region
    """

    def __init__(self, regions: list[str], aws_key: str, aws_secret: str):
        self.regions = regions
        self.all_regions_mode = len(regions) > 1
        self.aws_key = aws_key
        self.aws_secret = aws_secret

        # Primary client (first region) — used for create / single-region ops
        self.primary_region = regions[0]
        self.client = self._make_client(self.primary_region)

        # Build clients for all requested regions
        self._clients: dict[str, boto3.client] = {}
        for r in regions:
            self._clients[r] = self._make_client(r)

        mode_label = "ALL regions" if self.all_regions_mode else self.primary_region
        log.info("S3 client initialised (mode=%s, regions=%s)", mode_label, regions)

    def _make_client(self, region: str):
        return boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=self.aws_key,
            aws_secret_access_key=self.aws_secret,
        )

    # ── Internal: get buckets with region awareness ──────
    def _get_all_buckets(self) -> list[dict]:
        """Return list of bucket dicts.

        In single-region mode: returns buckets and marks each with
        its actual region.
        In all-regions mode: same, but fetches once (S3 ListBuckets
        is global) and resolves each bucket's region.
        """
        # ListBuckets is global — any client returns all buckets
        response = self.client.list_buckets()
        buckets = response.get("Buckets", [])

        if not self.all_regions_mode:
            # Single-region mode: filter to only buckets in our region
            filtered = []
            for b in buckets:
                try:
                    loc = self.client.get_bucket_location(Bucket=b["Name"])
                    bucket_region = loc.get("LocationConstraint") or "us-east-1"
                    if bucket_region == self.primary_region:
                        b["_region"] = bucket_region
                        filtered.append(b)
                except Exception:
                    pass  # Skip buckets we can't access
            return filtered
        else:
            # All-regions mode: return all buckets, resolve region
            for b in buckets:
                try:
                    loc = self.client.get_bucket_location(Bucket=b["Name"])
                    b["_region"] = loc.get("LocationConstraint") or "us-east-1"
                except Exception:
                    b["_region"] = "unknown"
            return buckets

    def _get_client_for_bucket(self, bucket_name: str):
        """Get an S3 client for the region where a bucket lives."""
        try:
            loc = self.client.get_bucket_location(Bucket=bucket_name)
            bucket_region = loc.get("LocationConstraint") or "us-east-1"
            if bucket_region in self._clients:
                return self._clients[bucket_region]
            # Create + cache a new client for this region
            client = self._make_client(bucket_region)
            self._clients[bucket_region] = client
            return client
        except Exception:
            return self.client  # Fallback to primary

    def _print_bucket_table(self, buckets, title="Buckets"):
        """Print buckets in a neat table."""
        if not buckets:
            warn("No buckets found.")
            return
        header(f"{title}  ({len(buckets)} total)")
        show_region = self.all_regions_mode
        if show_region:
            print(f"  {'#':<4} {'Name':<40} {'Region':<18} {'Created':<20}")
            print(f"  {'─'*4} {'─'*40} {'─'*18} {'─'*20}")
        else:
            print(f"  {'#':<4} {'Name':<50} {'Created':<20}")
            print(f"  {'─'*4} {'─'*50} {'─'*20}")

        for i, b in enumerate(buckets, 1):
            created = b['CreationDate'].strftime("%Y-%m-%d %H:%M") if hasattr(b['CreationDate'], 'strftime') else str(b['CreationDate'])[:16]
            if show_region:
                region = b.get("_region", "?")
                print(f"  {Fore.WHITE}{i:<4}{Style.RESET_ALL} {b['Name']:<40} {Fore.MAGENTA}{region:<18}{Style.RESET_ALL} {Fore.CYAN}{created}{Style.RESET_ALL}")
            else:
                print(f"  {Fore.WHITE}{i:<4}{Style.RESET_ALL} {b['Name']:<50} {Fore.CYAN}{created}{Style.RESET_ALL}")

    # ── List helpers ──────────────────────────────────────
    def list_all(self):
        try:
            buckets = self._get_all_buckets()
            mode = "All Regions" if self.all_regions_mode else self.primary_region
            self._print_bucket_table(buckets, f"Buckets — {mode}")
            log.info("Listed %d buckets (mode=%s)", len(buckets), mode)
        except Exception as e:
            error(f"Failed to list buckets: {e}")
            log.error("list_all failed: %s", e)

    def list_prefix(self):
        prefix = input("  Enter prefix: ").strip()
        if not prefix:
            error("Prefix cannot be empty.")
            return
        try:
            buckets = [b for b in self._get_all_buckets() if b['Name'].startswith(prefix)]
            self._print_bucket_table(buckets, f"Buckets with prefix '{prefix}'")
            log.info("Listed %d buckets with prefix '%s'", len(buckets), prefix)
        except Exception as e:
            error(f"Failed to list buckets: {e}")
            log.error("list_prefix failed: %s", e)

    def list_suffix(self):
        suffix = input("  Enter suffix: ").strip()
        if not suffix:
            error("Suffix cannot be empty.")
            return
        try:
            buckets = [b for b in self._get_all_buckets() if b['Name'].endswith(suffix)]
            self._print_bucket_table(buckets, f"Buckets with suffix '{suffix}'")
            log.info("Listed %d buckets with suffix '%s'", len(buckets), suffix)
        except Exception as e:
            error(f"Failed to list buckets: {e}")
            log.error("list_suffix failed: %s", e)

    # ── Create ────────────────────────────────────────────
    def create_bucket(self):
        name = input("  Enter bucket name: ").strip()
        if not name:
            error("Bucket name cannot be empty.")
            return

        # In all-regions mode, ask which region to create in
        if self.all_regions_mode:
            region = self._ask_target_region("Create in which region?")
            if not region:
                return
        else:
            region = self.primary_region

        try:
            client = self._clients.get(region) or self._make_client(region)
            create_args = {"Bucket": name}
            # us-east-1 does not accept LocationConstraint
            if region != "us-east-1":
                create_args["CreateBucketConfiguration"] = {"LocationConstraint": region}
            client.create_bucket(**create_args)
            success(f"Bucket '{name}' created in {region}")
            log.info("Created bucket '%s' in %s", name, region)
        except client.exceptions.BucketAlreadyExists:
            error(f"Bucket '{name}' already exists globally.")
        except client.exceptions.BucketAlreadyOwnedByYou:
            warn(f"You already own bucket '{name}'.")
        except Exception as e:
            error(f"Failed to create bucket: {e}")
            log.error("create_bucket failed: %s", e)

    # ── Delete ────────────────────────────────────────────
    def _empty_bucket(self, bucket_name: str):
        """Delete all objects (including versions) so the bucket can be removed."""
        client = self._get_client_for_bucket(bucket_name)
        try:
            paginator = client.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=bucket_name):
                objects = []
                for v in page.get("Versions", []):
                    objects.append({"Key": v["Key"], "VersionId": v["VersionId"]})
                for dm in page.get("DeleteMarkers", []):
                    objects.append({"Key": dm["Key"], "VersionId": dm["VersionId"]})
                if objects:
                    client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})
        except Exception:
            # Fallback: bucket may not have versioning
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket_name):
                objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if objects:
                    client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})

    def delete_bucket(self):
        name = input("  Enter bucket name to delete: ").strip()
        if not name:
            error("Bucket name cannot be empty.")
            return
        if not confirm(f"Delete bucket '{name}'? This cannot be undone!"):
            info("Cancelled.")
            return
        try:
            client = self._get_client_for_bucket(name)
            info("Emptying bucket before deletion...")
            self._empty_bucket(name)
            client.delete_bucket(Bucket=name)
            success(f"Bucket '{name}' deleted.")
            log.info("Deleted bucket '%s'", name)
        except Exception as e:
            error(f"Failed to delete bucket: {e}")
            log.error("delete_bucket failed: %s", e)

    def delete_prefix(self):
        prefix = input("  Enter prefix: ").strip()
        if not prefix:
            error("Prefix cannot be empty.")
            return
        try:
            targets = [b for b in self._get_all_buckets() if b['Name'].startswith(prefix)]
            if not targets:
                warn(f"No buckets match prefix '{prefix}'.")
                return
            target_names = [b['Name'] for b in targets]
            info(f"Matching buckets: {', '.join(target_names)}")
            if not confirm(f"Delete {len(targets)} bucket(s)?"):
                info("Cancelled.")
                return
            for b in targets:
                name = b['Name']
                self._empty_bucket(name)
                client = self._get_client_for_bucket(name)
                client.delete_bucket(Bucket=name)
                success(f"Deleted: {name}")
                log.info("Deleted bucket '%s' (prefix match)", name)
        except Exception as e:
            error(f"Failed during prefix delete: {e}")
            log.error("delete_prefix failed: %s", e)

    def delete_suffix(self):
        suffix = input("  Enter suffix: ").strip()
        if not suffix:
            error("Suffix cannot be empty.")
            return
        try:
            targets = [b for b in self._get_all_buckets() if b['Name'].endswith(suffix)]
            if not targets:
                warn(f"No buckets match suffix '{suffix}'.")
                return
            target_names = [b['Name'] for b in targets]
            info(f"Matching buckets: {', '.join(target_names)}")
            if not confirm(f"Delete {len(targets)} bucket(s)?"):
                info("Cancelled.")
                return
            for b in targets:
                name = b['Name']
                self._empty_bucket(name)
                client = self._get_client_for_bucket(name)
                client.delete_bucket(Bucket=name)
                success(f"Deleted: {name}")
                log.info("Deleted bucket '%s' (suffix match)", name)
        except Exception as e:
            error(f"Failed during suffix delete: {e}")
            log.error("delete_suffix failed: %s", e)

    # ── Bucket details ────────────────────────────────────
    def bucket_details(self):
        name = input("  Enter bucket name: ").strip()
        if not name:
            error("Bucket name cannot be empty.")
            return
        try:
            header(f"Details for '{name}'")

            # Region
            loc = self.client.get_bucket_location(Bucket=name)
            bucket_region = loc.get("LocationConstraint") or "us-east-1"
            info(f"Region:  {bucket_region}")

            # Use region-correct client for object listing
            client = self._get_client_for_bucket(name)

            # Object count & total size
            paginator = client.get_paginator("list_objects_v2")
            count = 0
            total_size = 0
            for page in paginator.paginate(Bucket=name):
                for obj in page.get("Contents", []):
                    count += 1
                    total_size += obj.get("Size", 0)
            info(f"Objects: {count}")
            info(f"Size:    {self._human_size(total_size)}")

            log.info("Viewed details for bucket '%s'", name)
        except Exception as e:
            error(f"Failed to get bucket details: {e}")
            log.error("bucket_details failed: %s", e)

    # ── Object operations ─────────────────────────────────
    def list_objects(self):
        name = input("  Enter bucket name: ").strip()
        if not name:
            error("Bucket name cannot be empty.")
            return
        try:
            client = self._get_client_for_bucket(name)
            paginator = client.get_paginator("list_objects_v2")
            objects = []
            for page in paginator.paginate(Bucket=name):
                objects.extend(page.get("Contents", []))

            if not objects:
                warn(f"Bucket '{name}' is empty.")
                return

            header(f"Objects in '{name}'  ({len(objects)} total)")
            print(f"  {'#':<4} {'Key':<50} {'Size':<12} {'Modified':<20}")
            print(f"  {'─'*4} {'─'*50} {'─'*12} {'─'*20}")
            for i, obj in enumerate(objects, 1):
                mod = obj['LastModified'].strftime("%Y-%m-%d %H:%M") if hasattr(obj['LastModified'], 'strftime') else str(obj['LastModified'])[:16]
                print(f"  {Fore.WHITE}{i:<4}{Style.RESET_ALL} {obj['Key']:<50} {self._human_size(obj['Size']):<12} {Fore.CYAN}{mod}{Style.RESET_ALL}")
            log.info("Listed %d objects in '%s'", len(objects), name)
        except Exception as e:
            error(f"Failed to list objects: {e}")
            log.error("list_objects failed: %s", e)

    def upload_file(self):
        bucket = input("  Enter bucket name: ").strip()
        filepath = input("  Enter local file path: ").strip()
        if not bucket or not filepath:
            error("Bucket name and file path are required.")
            return
        if not os.path.isfile(filepath):
            error(f"File not found: {filepath}")
            return
        key = input(f"  Enter S3 key (default: {os.path.basename(filepath)}): ").strip()
        if not key:
            key = os.path.basename(filepath)
        try:
            client = self._get_client_for_bucket(bucket)
            file_size = os.path.getsize(filepath)
            info(f"Uploading {self._human_size(file_size)}...")
            client.upload_file(filepath, bucket, key)
            success(f"Uploaded '{key}' to '{bucket}'")
            log.info("Uploaded '%s' → s3://%s/%s (%s)", filepath, bucket, key, self._human_size(file_size))
        except Exception as e:
            error(f"Upload failed: {e}")
            log.error("upload_file failed: %s", e)

    def download_file(self):
        bucket = input("  Enter bucket name: ").strip()
        key = input("  Enter S3 object key: ").strip()
        if not bucket or not key:
            error("Bucket name and object key are required.")
            return
        dest = input(f"  Enter local destination (default: {os.path.basename(key)}): ").strip()
        if not dest:
            dest = os.path.basename(key)
        try:
            client = self._get_client_for_bucket(bucket)
            client.download_file(bucket, key, dest)
            success(f"Downloaded s3://{bucket}/{key} → {dest}")
            log.info("Downloaded s3://%s/%s → '%s'", bucket, key, dest)
        except Exception as e:
            error(f"Download failed: {e}")
            log.error("download_file failed: %s", e)

    def delete_object(self):
        bucket = input("  Enter bucket name: ").strip()
        key = input("  Enter S3 object key to delete: ").strip()
        if not bucket or not key:
            error("Bucket name and object key are required.")
            return
        if not confirm(f"Delete object '{key}' from '{bucket}'?"):
            info("Cancelled.")
            return
        try:
            client = self._get_client_for_bucket(bucket)
            client.delete_object(Bucket=bucket, Key=key)
            success(f"Deleted '{key}' from '{bucket}'")
            log.info("Deleted object '%s' from '%s'", key, bucket)
        except Exception as e:
            error(f"Delete object failed: {e}")
            log.error("delete_object failed: %s", e)

    # ── Utility ───────────────────────────────────────────
    def _ask_target_region(self, prompt: str) -> str | None:
        """In all-regions mode, ask the user to pick a specific region for write ops."""
        header("SELECT TARGET REGION")
        for i, r in enumerate(AWS_REGIONS, 1):
            print(f"  {Fore.GREEN}{i:<3}{Style.RESET_ALL} {r}")
        choice = input(f"\n  {Fore.WHITE}{prompt} (number or region name): {Style.RESET_ALL}").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(AWS_REGIONS):
                return AWS_REGIONS[idx]
        elif choice in AWS_REGIONS:
            return choice
        error("Invalid region selection.")
        return None

    @staticmethod
    def _human_size(nbytes: int) -> str:
        """Convert bytes to human-readable string."""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(nbytes) < 1024:
                return f"{nbytes:.1f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.1f} PB"


# ──────────────────── Menu System ────────────────────
def show_main_menu(mode_label: str):
    header(f"S3 BUCKET MANAGER  ─  {mode_label}")
    options = [
        ("1", "List Buckets"),
        ("2", "Create Bucket"),
        ("3", "Delete Bucket(s)"),
        ("4", "Bucket Details"),
        ("5", "Object Operations"),
        ("0", "Exit"),
    ]
    for key, label in options:
        print(f"  {Fore.GREEN}{key}{Style.RESET_ALL} — {label}")

def show_list_menu():
    header("LIST BUCKETS")
    for key, label in [("1","All"), ("2","By prefix"), ("3","By suffix")]:
        print(f"  {Fore.GREEN}{key}{Style.RESET_ALL} — {label}")

def show_delete_menu():
    header("DELETE BUCKETS")
    for key, label in [("1","Single bucket"), ("2","By prefix"), ("3","By suffix")]:
        print(f"  {Fore.GREEN}{key}{Style.RESET_ALL} — {label}")

def show_object_menu():
    header("OBJECT OPERATIONS")
    for key, label in [("1","List objects"), ("2","Upload file"), ("3","Download file"), ("4","Delete object")]:
        print(f"  {Fore.GREEN}{key}{Style.RESET_ALL} — {label}")


def select_region_mode() -> list[str]:
    """Ask the user to choose between single-region or all-regions mode."""
    header("REGION SELECTION")
    print(f"  {Fore.GREEN}1{Style.RESET_ALL} — Single region  (all operations in one region)")
    print(f"  {Fore.GREEN}2{Style.RESET_ALL} — All regions     (operations across every AWS region)")

    choice = input(f"\n  {Fore.WHITE}Choose mode (1/2): {Style.RESET_ALL}").strip()

    if choice == "2":
        info("Mode: ALL REGIONS — operations will span every AWS region.")
        return list(AWS_REGIONS)

    # Default: single region
    env_region = os.getenv("AWS_DEFAULT_REGION", "").strip()
    if env_region:
        info(f"Region from .env: {env_region}")
        use_env = input(f"  {Fore.WHITE}Use '{env_region}'? (Y/n): {Style.RESET_ALL}").strip().lower()
        if use_env != "n":
            return [env_region]

    # Show numbered list of regions
    header("AVAILABLE REGIONS")
    for i, r in enumerate(AWS_REGIONS, 1):
        print(f"  {Fore.GREEN}{i:<3}{Style.RESET_ALL} {r}")
    print()
    selection = input(f"  {Fore.WHITE}Enter region number or name (default: us-east-1): {Style.RESET_ALL}").strip()

    if selection.isdigit():
        idx = int(selection) - 1
        if 0 <= idx < len(AWS_REGIONS):
            return [AWS_REGIONS[idx]]
    elif selection in AWS_REGIONS:
        return [selection]
    elif not selection:
        return ["us-east-1"]

    warn(f"Unrecognised input '{selection}', defaulting to us-east-1")
    return ["us-east-1"]


# ──────────────────── Main ────────────────────
def main():
    print(f"\n{Fore.CYAN}{'═' * 60}")
    print(f"  AWS S3 Bucket Manager")
    print(f"{'═' * 60}{Style.RESET_ALL}")

    # ── Credential check ──
    aws_key = os.getenv("AWS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET")
    if not aws_key or not aws_secret:
        error("AWS_KEY_ID and AWS_SECRET must be set as environment variables.")
        info("Tip: create a .env file from .env.example")
        sys.exit(1)

    # ── Region selection ──
    regions = select_region_mode()
    all_mode = len(regions) > 1
    mode_label = f"{Fore.MAGENTA}ALL REGIONS{Style.RESET_ALL}" if all_mode else f"{Fore.MAGENTA}{regions[0]}{Style.RESET_ALL}"
    info(f"Operating in: {mode_label}")

    mgr = S3Manager(regions, aws_key, aws_secret)

    menu_label = "All Regions" if all_mode else regions[0]

    while True:
        show_main_menu(menu_label)
        choice = input(f"\n  {Fore.WHITE}Choose option: {Style.RESET_ALL}").strip()

        if choice == "1":
            show_list_menu()
            sub = input(f"  {Fore.WHITE}Choose: {Style.RESET_ALL}").strip()
            {"1": mgr.list_all, "2": mgr.list_prefix, "3": mgr.list_suffix}.get(sub, lambda: error("Invalid option"))()

        elif choice == "2":
            mgr.create_bucket()

        elif choice == "3":
            show_delete_menu()
            sub = input(f"  {Fore.WHITE}Choose: {Style.RESET_ALL}").strip()
            {"1": mgr.delete_bucket, "2": mgr.delete_prefix, "3": mgr.delete_suffix}.get(sub, lambda: error("Invalid option"))()

        elif choice == "4":
            mgr.bucket_details()

        elif choice == "5":
            show_object_menu()
            sub = input(f"  {Fore.WHITE}Choose: {Style.RESET_ALL}").strip()
            {"1": mgr.list_objects, "2": mgr.upload_file, "3": mgr.download_file, "4": mgr.delete_object}.get(sub, lambda: error("Invalid option"))()

        elif choice == "0":
            info("Goodbye!")
            log.info("Session ended by user")
            break

        else:
            error("Invalid choice — please pick a number from the menu.")


if __name__ == "__main__":
    main()
