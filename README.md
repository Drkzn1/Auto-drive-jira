# Kịch bản Automation — Claude Chat → Drive (Google Docs, đánh số) + Jira

## Kiến trúc

```
Bạn chat với Claude → viết + tự duyệt kịch bản ngay trong chat
                                ↓
                    Xuất ra file .md đúng định dạng
                                ↓
                    Bỏ vào thư mục inbox/
                                ↓
              python process_file.py
                                ↓
        ┌───────────────────────┴───────────────────────┐
        ↓                                                ↓
  Drive: tạo folder "NN_Tên kịch bản"           Jira: tạo task ở project VE
  (số tự tăng theo folder đã có),                → mô tả có link folder Drive
  upload Google Docs vào trong                   → tự chuyển sang cột
                                                      "Law & Disorder"
```

---

## 0. Cài đặt môi trường

```bash
cd kich-ban-automation
source venv/bin/activate        # venv đã được tạo sẵn
pip install -r requirements.txt
```

---

## 1. Xác thực Google Drive — dùng OAuth (tài khoản thật của bạn)

> ⚠️ **Không dùng Service Account** cho phần này — Service Account trên Gmail
> cá nhân không có dung lượng lưu trữ riêng, sẽ báo lỗi
> `storageQuotaExceeded` ngay khi upload. Phải xác thực bằng chính tài khoản
> Google của bạn để dùng dung lượng Drive thật.

### Tạo OAuth Client ID (chỉ làm 1 lần)

1. Vào [console.cloud.google.com](https://console.cloud.google.com) → chọn project → **APIs & Services → Credentials**
2. Nếu chưa có, bấm **Configure consent screen**:
   - App name: bất kỳ
   - User support email + Contact email: email của bạn
   - User type: **External**
   - Vào mục **Audience** → **Test users** → **+ ADD USERS** → thêm email Google của bạn
3. Quay lại **Credentials** → **+ CREATE CREDENTIALS → OAuth client ID**
   - Nếu hỏi API: chọn **Google Drive API** → **User data**
   - **Application type**: **Desktop app**
   - Đặt tên bất kỳ → **Create**
4. Ở popup hiện ra, bấm **Download JSON** ngay (đóng popup là mất luôn secret, phải tạo lại)
5. Đổi tên file tải về thành `oauth_client.json`, để vào thư mục `kich-ban-automation/`

### Đăng nhập lần đầu

Lần đầu chạy `process_file.py`, trình duyệt sẽ tự mở ra để bạn đăng nhập +
cấp quyền Drive. Sau khi đồng ý, file `token.json` được tạo tự động — **các
lần chạy sau không cần đăng nhập lại** (tự refresh token khi hết hạn).

Nếu `token.json` bị lỗi/hết hạn hẳn, chỉ cần xoá file đó rồi chạy lại để
đăng nhập lại từ đầu:
```bash
rm token.json
```

---

## 2. Setup Google Drive (folder gốc)

1. Tạo (hoặc dùng có sẵn) **1 folder gốc** trên Drive để chứa toàn bộ kịch bản
   — mỗi kịch bản sẽ tự động có 1 folder con riêng bên trong, đặt tên dạng
   `NN_Tên kịch bản` (số thứ tự tự tăng dựa trên folder con lớn nhất đã có)
2. Vì dùng tài khoản thật của bạn (không phải Service Account), **không cần
   share quyền** gì cả — bạn đã là chủ sở hữu sẵn
3. Lấy Folder ID từ URL:
   ```
   drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz
                                    └──────── Folder ID ────────┘
   ```
4. Điền vào `.env`: `DRIVE_FOLDER_ID`

---

## 3. Lấy Jira API Token

1. Vào [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. **Create API token** → copy token
3. Điền vào `.env`:
   - `JIRA_BASE_URL` — domain Jira, vd `https://ten-cong-ty.atlassian.net`
   - `JIRA_EMAIL` — email đăng nhập Jira
   - `JIRA_API_TOKEN` — token vừa tạo
   - `JIRA_PROJECT_KEY_DEFAULT` — mã project mặc định, vd `VE`
   - `JIRA_ISSUE_TYPE` — loại issue, vd `Task`
   - `JIRA_TARGET_STATUS` — cột trên board mà task mới sẽ tự chuyển tới sau
     khi tạo, vd `Law & Disorder` (phải khớp **chính xác** tên cột trong Jira)

---

## 4. Cách dùng hàng ngày

### Bước A — Viết & duyệt kịch bản (trong Claude chat như bình thường)

Sau khi kịch bản đã ok, yêu cầu Claude xuất theo đúng định dạng (xem hướng
dẫn chi tiết ở cuối `master_prompt.md`):

```
# Cách nuôi mèo con mới về nhà

(toàn bộ nội dung kịch bản)
```

Copy kết quả → lưu thành file `.md` (ví dụ `nuoi-meo-con.md`).

### Bước B — Bỏ file vào `inbox/`

Kéo/lưu file `.md` vừa tạo vào thư mục `inbox/` trong project. Có thể bỏ
nhiều file cùng lúc — chạy 1 lần xử lý hết, số thứ tự tự tăng tuần tự.

### Bước C — Chạy script

```bash
cd kich-ban-automation
source venv/bin/activate
python process_file.py
```

Với mỗi file, script sẽ:
- Tính số thứ tự tiếp theo (dựa trên folder con lớn nhất đã có trong Drive)
- Tạo folder `NN_Tên kịch bản` trong folder gốc
- Upload kịch bản vào trong dưới dạng **Google Docs** (mở/sửa được ngay)
- Tạo task Jira (mô tả = nội dung kịch bản + link folder Drive)
- Tự động chuyển task sang cột `JIRA_TARGET_STATUS`
- Move file `.md` gốc sang `processed/` (kèm timestamp)

Kết quả in ra Terminal có link Drive + link Jira cho từng kịch bản.

**Xử lý 1 file cụ thể** (không cần bỏ vào `inbox/`, và không tự move file):
```bash
python process_file.py duong/dan/toi/kich_ban.md
```

---

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân |
|---|---|
| `storageQuotaExceeded` | Đang dùng Service Account thay vì OAuth — xem lại mục 1 |
| `Không tìm thấy dòng tiêu đề bắt đầu bằng '#'` | File thiếu dòng đầu bắt đầu bằng `# ` — xem đúng định dạng ở cuối `master_prompt.md` |
| `Không tìm thấy đường chuyển trạng thái tới 'X'` | Sai chính tả `JIRA_TARGET_STATUS`, hoặc workflow hiện tại của issue không cho phép chuyển thẳng tới cột đó từ trạng thái ban đầu — task vẫn được tạo, chỉ là nằm ở cột mặc định |
| `401` khi tạo Jira | Sai `JIRA_EMAIL` / `JIRA_API_TOKEN`, hoặc token đã bị thu hồi |
| `400` khi tạo Jira, báo project không tồn tại | Sai `JIRA_PROJECT_KEY_DEFAULT` trong `.env` |
| Trình duyệt không tự mở khi chạy lần đầu | Copy URL in ra ở Terminal, dán vào trình duyệt thủ công |
