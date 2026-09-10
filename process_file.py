"""
Đọc (các) file kịch bản đã duyệt (xuất từ Claude chat) → phân loại theo từ
khoá → tạo folder trên Drive (trong đúng folder nhóm) + upload Google Docs →
tạo task trên Jira ở đúng cột nhóm đó, có link tới folder Drive.

Cách dùng:

  1) Xử lý 1 file cụ thể:
       python process_file.py duong/dan/toi/kich_ban.md

  2) Không truyền gì cả → quét toàn bộ file .md trong thư mục inbox/,
     xử lý từng file, xong cái nào move cái đó sang thư mục processed/:
       python process_file.py

Định dạng file đầu vào (xem chi tiết ở cuối master_prompt.md):

    # Tiêu đề kịch bản

    Nội dung kịch bản...

Phân loại theo từ khoá (soi cả tiêu đề lẫn nội dung, kể cả hashtag ở cuối
kịch bản — xem config.py để đổi từ khoá / cột Jira / thêm nhóm mới):

  - Chứa "your life as every"  → folder DRIVE_FOLDER_ID_LORE, cột "Law & Disorder"
  - Chứa "star wars"           → folder DRIVE_FOLDER_ID_STARWARS, cột "POV Life"
  - Chứa "fallout"             → folder DRIVE_FOLDER_ID_FALLOUT, cột "Hidden Game Theory"
  - Còn lại                    → folder DRIVE_FOLDER_ID_LOWKEY, cột "Lowkey Explainer"

Cả 4 folder này PHẢI đã tồn tại sẵn trên Drive — script chỉ tạo folder con
đánh số bên trong, KHÔNG tự tạo folder gốc mới.
"""

from __future__ import annotations

import fcntl
import glob
import io
import os
import re
import shutil
import sys
from datetime import datetime

import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

import config

FOLDER_MIME = "application/vnd.google-apps.folder"
DOC_MIME = "application/vnd.google-apps.document"


class ParseError(Exception):
    pass


def parse_script_file(path: str) -> dict:
    """Tách title (dòng '# ...' đầu tiên) và nội dung kịch bản (phần còn lại).
    jira_project luôn lấy từ JIRA_PROJECT_KEY_DEFAULT trong .env — không cần
    khai báo trong từng file."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    lines = raw.splitlines()
    title = ""
    content_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            title = line.strip().lstrip("#").strip()
            content_start = i + 1
            break

    if not title:
        raise ParseError(
            "Không tìm thấy dòng tiêu đề bắt đầu bằng '#'. "
            "Xem đúng định dạng ở cuối master_prompt.md."
        )

    content = "\n".join(lines[content_start:]).strip()
    if not content:
        raise ParseError("Nội dung kịch bản (sau dòng tiêu đề) đang trống.")

    return {"title": title, "jira_project": config.JIRA_PROJECT_KEY_DEFAULT, "content": content}


def categorize(title: str, content: str) -> dict:
    """Xác định nhóm dựa trên từ khoá — soi cả tiêu đề lẫn nội dung (bắt được
    cả hashtag như #StarWars ở cuối kịch bản). Khớp lần lượt theo thứ tự
    trong config.CATEGORIES, cái nào khớp trước dùng cái đó; không khớp gì
    thì rơi về config.DEFAULT_CATEGORY. Trả về dict {name, drive_folder_id,
    jira_status} — trỏ thẳng vào 1 folder Drive có sẵn, KHÔNG tự tạo folder
    mới."""
    haystack = f"{title}\n{content}".lower()
    for category in config.CATEGORIES:
        if category["keyword"].lower() in haystack:
            return category
    return config.DEFAULT_CATEGORY


def get_next_seq_number(drive, parent_id: str) -> int:
    """Quét các folder con trong `parent_id`, tìm số thứ tự lớn nhất
    (dạng "NN_Tên...") rồi trả về số tiếp theo. Nếu chưa có folder nào
    đúng định dạng, bắt đầu từ 1."""
    result = (
        drive.files()
        .list(
            q=(
                f"'{parent_id}' in parents "
                f"and mimeType='{FOLDER_MIME}' and trashed=false"
            ),
            fields="files(name)",
            pageSize=1000,
        )
        .execute()
    )
    max_num = 0
    for f in result.get("files", []):
        m = re.match(r"^(\d+)_", f["name"])
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num + 1


def create_script_folder(drive, parent_id: str, seq_num: int, title: str) -> tuple[str, str]:
    """Tạo folder con "NN_Tên kịch bản" trong `parent_id`.
    Trả về (folder_id, webViewLink)."""
    folder_name = f"{seq_num:02d}_{title}"
    metadata = {"name": folder_name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
    folder = drive.files().create(body=metadata, fields="id, webViewLink").execute()
    return folder["id"], folder["webViewLink"]


def upload_doc_into_folder(drive, folder_id: str, title: str, content: str) -> tuple[str, str]:
    """Upload nội dung dạng Google Docs (không phải .txt) vào trong folder.
    Trả về (file_id, webViewLink)."""
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")), mimetype="text/plain", resumable=False
    )
    metadata = {"name": title, "parents": [folder_id], "mimeType": DOC_MIME}
    file = (
        drive.files()
        .create(body=metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )
    return file["id"], file["webViewLink"]


def create_jira_task(title: str, jira_project: str, folder_link: str) -> str:
    """Tạo task Jira (ở status mặc định của workflow). Mô tả chỉ có link
    folder Drive (dạng link bấm được), không dán nội dung kịch bản vào.
    Trả về issue_key."""
    url = f"{config.JIRA_BASE_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": jira_project},
            "summary": title,
            "issuetype": {"name": config.JIRA_ISSUE_TYPE},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Drive: "},
                            {
                                "type": "text",
                                "text": f"{title} folder",
                                "marks": [
                                    {"type": "link", "attrs": {"href": folder_link}}
                                ],
                            },
                        ],
                    }
                ],
            },
        }
    }
    resp = requests.post(
        url,
        json=payload,
        auth=(config.JIRA_EMAIL, config.JIRA_API_TOKEN),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["key"]


def move_issue_to_status(issue_key: str, target_status: str) -> bool:
    """Chuyển issue sang đúng cột `target_status` (vd 'Law & Disorder').
    Trả về True nếu chuyển thành công, False nếu không tìm thấy transition
    phù hợp (issue vẫn được tạo bình thường, chỉ là nằm ở cột mặc định)."""
    url = f"{config.JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions"
    resp = requests.get(url, auth=(config.JIRA_EMAIL, config.JIRA_API_TOKEN), timeout=15)
    resp.raise_for_status()

    transitions = resp.json().get("transitions", [])
    match = next(
        (t for t in transitions if t["to"]["name"].lower() == target_status.lower()), None
    )
    if not match:
        available = ", ".join(t["to"]["name"] for t in transitions)
        print(
            f"   ⚠️  Không tìm thấy đường chuyển trạng thái tới '{target_status}' "
            f"từ trạng thái hiện tại. Các trạng thái có thể chuyển tới: {available}"
        )
        return False

    resp = requests.post(
        url,
        json={"transition": {"id": match["id"]}},
        auth=(config.JIRA_EMAIL, config.JIRA_API_TOKEN),
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return True


def process_one(path: str, drive, seq_cache: dict, move_when_done: bool) -> bool:
    print(f"\n➡️  Đang xử lý: {path}")
    try:
        parsed = parse_script_file(path)
    except ParseError as e:
        print(f"   ❌ Lỗi định dạng file: {e}")
        return False

    category = categorize(parsed["title"], parsed["content"])
    parent_id = category["drive_folder_id"]
    print(f"   🏷️  Phân loại: {category['name']}")

    if parent_id not in seq_cache:
        seq_cache[parent_id] = get_next_seq_number(drive, parent_id)
    seq_num = seq_cache[parent_id]

    folder_name = f"{seq_num:02d}_{parsed['title']}"
    print(f"   📁 Đang tạo folder Drive: {folder_name}")
    folder_id, folder_link = create_script_folder(drive, parent_id, seq_num, parsed["title"])

    print("   📤 Đang upload kịch bản (Google Docs) vào folder...")
    upload_doc_into_folder(drive, folder_id, parsed["title"], parsed["content"])
    print(f"   ✅ Drive: {folder_link}")

    print(f"   🎫 Đang tạo task Jira (project {parsed['jira_project']})...")
    issue_key = create_jira_task(parsed["title"], parsed["jira_project"], folder_link)
    jira_link = f"{config.JIRA_BASE_URL}/browse/{issue_key}"
    print(f"   ✅ Jira: {issue_key} — {jira_link}")

    target_status = category["jira_status"]
    print(f"   🔀 Đang chuyển task sang cột '{target_status}'...")
    moved = move_issue_to_status(issue_key, target_status)
    if moved:
        print(f"   ✅ Đã chuyển sang '{target_status}'")

    seq_cache[parent_id] += 1

    if move_when_done:
        os.makedirs(config.PROCESSED_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(config.PROCESSED_DIR, f"{ts}-{os.path.basename(path)}")
        shutil.move(path, dest)
        print(f"   📦 Đã move file gốc sang: {dest}")

    return True


def main():
    args = sys.argv[1:]

    # Khoá file — tránh 2 tiến trình (vd cron + chạy tay cùng lúc) đua nhau
    # xử lý chung 1 file, gây trùng folder Drive / trùng task Jira.
    lock_fd = open(config.LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("⏳ Một tiến trình process_file.py khác đang chạy rồi — bỏ qua lần này.")
        return

    try:
        drive = build("drive", "v3", credentials=config.google_credentials())

        files = args if args else sorted(glob.glob(os.path.join(config.INBOX_DIR, "*.md")))
        if not files:
            print(f"✅ Không có file nào trong {config.INBOX_DIR}/ cần xử lý.")
            return

        print(f"🔎 Sẽ xử lý {len(files)} file...")
        seq_cache: dict = {}  # cache: folder_id -> số thứ tự tiếp theo (trong batch này)
        ok_count = 0
        for path in files:
            if process_one(path, drive, seq_cache, move_when_done=not bool(args)):
                ok_count += 1

        print(f"\n🎉 Xong: {ok_count}/{len(files)} file xử lý thành công.")
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    main()
