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

# --- Phân loại kịch bản theo từ khoá (soi trong cả tiêu đề + nội dung, vd
# hashtag ở cuối kịch bản) — kiểm tra lần lượt theo thứ tự trong CATEGORIES,
# khớp cái nào trước dùng cái đó. Không khớp cái nào → rơi vào DEFAULT_CATEGORY.
# Mỗi nhóm trỏ thẳng vào 1 folder Drive có sẵn — KHÔNG tự tạo folder gốc mới,
# folder phải tồn tại sẵn trên Drive từ trước.
#
# Thứ tự ưu tiên: franchise CỤ THỂ (Star Wars, Fallout) luôn check TRƯỚC
# "Lore" — vì "Lore" khớp cả những tiêu đề dạng "Your Life as Every..." dùng
# chung cho nhiều franchise (Warhammer 40k mặc định, nhưng cũng có thể là
# Star Wars/Fallout nếu ghi rõ trong tên). Franchise cụ thể phải thắng trước
# để không bị Lore "vồ" mất.
CATEGORIES = [
    {
        "name": "Star Wars",
        "keyword": os.environ.get("CATEGORY_STARWARS_KEYWORD", "star wars"),
        "drive_folder_id": _get("DRIVE_FOLDER_ID_STARWARS"),
        "jira_status": os.environ.get("JIRA_STATUS_STARWARS", "POV Life"),
    },
    {
        "name": "Fallout",
        "keyword": os.environ.get("CATEGORY_FALLOUT_KEYWORD", "fallout"),
        "drive_folder_id": _get("DRIVE_FOLDER_ID_FALLOUT"),
        "jira_status": os.environ.get("JIRA_STATUS_FALLOUT", "Hidden Game Theory"),
    },
    {
        "name": "Lore",
        "keyword": os.environ.get("CATEGORY_LORE_KEYWORD", "your life as every"),
        "drive_folder_id": _get("DRIVE_FOLDER_ID_LORE"),
        "jira_status": os.environ.get("JIRA_STATUS_LORE", "Law & Disorder"),
    },
]
DEFAULT_CATEGORY = {
    "name": "Lowkey",
    "drive_folder_id": _get("DRIVE_FOLDER_ID_LOWKEY"),
    "jira_status": os.environ.get("JIRA_STATUS_LOWKEY", "Lowkey Explainer"),
}

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
