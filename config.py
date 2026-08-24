"""Đọc cấu hình dùng chung cho process_file.py."""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        print(f"❌ Thiếu biến môi trường bắt buộc: {name} (xem file .env.example)")
        sys.exit(1)
    return value


JIRA_BASE_URL = _get("JIRA_BASE_URL")
JIRA_EMAIL = _get("JIRA_EMAIL")
JIRA_API_TOKEN = _get("JIRA_API_TOKEN")
JIRA_PROJECT_KEY_DEFAULT = os.environ.get("JIRA_PROJECT_KEY_DEFAULT", "CONTENT")
JIRA_ISSUE_TYPE = os.environ.get("JIRA_ISSUE_TYPE", "Task")

# --- Phân loại kịch bản theo tiêu đề ---
# Tiêu đề chứa cụm từ này (không phân biệt hoa/thường) → nhóm "Lore",
# dùng thẳng folder Drive có sẵn (DRIVE_FOLDER_ID_LORE) + cột Jira
# "Law & Disorder". Còn lại → nhóm "Lowkey": folder DRIVE_FOLDER_ID_LOWKEY +
# cột "Lowkey Explainer". Không tự tạo folder mới — cả 2 folder này PHẢI đã
# tồn tại sẵn trên Drive, chỉ lấy ID trỏ thẳng vào.
CATEGORY_LORE_KEYWORD = os.environ.get("CATEGORY_LORE_KEYWORD", "your life as every")
DRIVE_FOLDER_ID_LORE = _get("DRIVE_FOLDER_ID_LORE")
JIRA_STATUS_LORE = os.environ.get("JIRA_STATUS_LORE", "Law & Disorder")
DRIVE_FOLDER_ID_LOWKEY = _get("DRIVE_FOLDER_ID_LOWKEY")
JIRA_STATUS_LOWKEY = os.environ.get("JIRA_STATUS_LOWKEY", "Lowkey Explainer")

BASE_DIR = os.path.dirname(__file__)
INBOX_DIR = os.path.join(BASE_DIR, "inbox")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
LOCK_FILE = os.path.join(BASE_DIR, ".process_file.lock")

# --- Xác thực Google Drive bằng OAuth (dùng chính tài khoản Google thật của
# bạn) — cần thiết vì Service Account trên Gmail cá nhân không có dung lượng
# lưu trữ riêng, nên up file sẽ báo lỗi "storageQuotaExceeded". ---
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
OAUTH_CLIENT_FILE = os.path.join(BASE_DIR, "oauth_client.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")


def google_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, DRIVE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(OAUTH_CLIENT_FILE):
                print(
                    f"❌ Thiếu file {OAUTH_CLIENT_FILE}. "
                    "Xem hướng dẫn tạo OAuth Client ID trong README.md."
                )
                sys.exit(1)
            print("🔐 Lần đầu chạy — trình duyệt sẽ mở ra để bạn đăng nhập Google...")
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_FILE, DRIVE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds
