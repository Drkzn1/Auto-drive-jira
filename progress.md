# Progress Log — Kịch bản Automation

Nhật ký tiến độ dự án: đã làm gì, quyết định nào, còn vướng gì. Cập nhật file
này mỗi khi có thay đổi lớn để không bị mất ngữ cảnh giữa các phiên làm việc.

---

## 📌 Trạng thái hiện tại: **Hoạt động ổn định**

Pipeline đầy đủ, đã test end-to-end nhiều lần, đang chạy tự động qua cron
mỗi 5 phút. Repo đã đẩy lên GitHub: https://github.com/Drkzn1/Auto-drive-jira

---

## 🏗️ Kiến trúc

```
Claude chat (viết + tự duyệt kịch bản)
        ↓ xuất file .md (# Tiêu đề + nội dung)
   inbox/ (thả file vào, hoặc kéo vào shortcut Desktop)
        ↓ cron chạy mỗi 5 phút (hoặc chạy tay: python process_file.py)
   Phân loại theo tiêu đề:
     - Chứa "your life as every" → nhóm LORE
     - Còn lại                   → nhóm LOWKEY
        ↓                                    ↓
   Drive: 05_Lore & Disorder/          Drive: 06_Lowkey Explainer/
     NN_Tên kịch bản/ (Google Docs)      NN_Tên kịch bản/ (Google Docs)
        ↓                                    ↓
   Jira: task, cột "Law & Disorder"    Jira: task, cột "Lowkey Explainer"
   (mô tả = link folder Drive, project VE)
        ↓
   file gốc move sang processed/
```

---

## ✅ Đã hoàn thành

- [x] Script `process_file.py`: parse file `.md` → phân loại → tạo folder Drive (Google Docs) → tạo task Jira → chuyển cột → move file
- [x] Xác thực Google Drive qua **OAuth** (không dùng Service Account — tài khoản cá nhân không có storage quota, gây lỗi `storageQuotaExceeded`)
- [x] OAuth app đã **Publish sang Production** (Google Cloud Console) — token không còn tự hết hạn sau 7 ngày như lúc còn ở "Testing"
- [x] Jira: tạo task qua REST API v3, tự động transition sang đúng cột qua `/transitions` endpoint
- [x] Phân loại 3 nhóm (Lore & Disorder / Star Wars / Lowkey Explainer) dựa theo từ khoá — soi cả tiêu đề lẫn nội dung (bắt được hashtag như `#StarWars` ở cuối kịch bản), khớp theo thứ tự ưu tiên trong `config.CATEGORIES`, không khớp gì → rơi về `DEFAULT_CATEGORY`. Trỏ thẳng vào folder Drive có sẵn của người dùng (`DRIVE_FOLDER_ID_LORE` / `DRIVE_FOLDER_ID_STARWARS` / `DRIVE_FOLDER_ID_LOWKEY`), **không** tự tạo folder gốc mới. Thêm nhóm mới chỉ cần thêm 1 entry vào `config.CATEGORIES`.
- [x] Đánh số thứ tự tự động (`NN_Tên kịch bản`), riêng theo từng nhóm
- [x] Cron job (`*/5 * * * *`) tự quét `inbox/`, không cần chạy tay
- [x] **Khoá file (lock)** chống race condition khi cron + chạy tay trùng thời điểm
- [x] Shortcut Desktop `📁 Inbox Kịch Bản` (symlink) để kéo-thả nhanh
- [x] Git repo riêng, đẩy lên GitHub (private): https://github.com/Drkzn1/Auto-drive-jira — không lộ secret nào (`.env`, `oauth_client.json`, `token.json`, `cron.log` đều gitignore)

---

## 🧠 Quyết định quan trọng & lý do

| Quyết định | Lý do |
|---|---|
| Không dùng Claude API để sinh kịch bản, chỉ dùng để up + tạo task | Người dùng muốn tự viết/duyệt kịch bản trong chat Claude như cũ, tool chỉ lo phần "chân tay" |
| OAuth thay vì Service Account | Service Account trên Gmail cá nhân không có dung lượng Drive riêng → lỗi storage quota ngay khi upload |
| File Drive dạng Google Docs thật, không phải `.txt` | Người dùng muốn mở/sửa trực tiếp trong Google Docs |
| Bỏ Google Sheet hàng đợi duyệt | Người dùng đã tự duyệt kịch bản ngay trong chat trước khi đưa file, không cần duyệt lại lần 2 |
| Format file chỉ còn `# Tiêu đề` + nội dung (bỏ frontmatter `---`) | Đơn giản hoá, dễ yêu cầu Claude chat xuất đúng định dạng |
| Mô tả Jira chỉ có link folder Drive, không dán nguyên kịch bản | Theo yêu cầu người dùng — gọn, đỡ trùng lặp nội dung |
| Trỏ thẳng ID 2 folder Drive có sẵn thay vì tìm-kiếm-theo-tên | Ban đầu code tự tìm/tạo folder theo tên gây lỗi tạo nhầm folder lồng + lạc sang Shared Drive khác — trỏ ID trực tiếp loại bỏ hẳn nhập nhằng |

---

## ⚠️ Vấn đề đã gặp & cách xử lý

1. **`storageQuotaExceeded`** khi dùng Service Account → chuyển sang OAuth (tài khoản thật)
2. **Token OAuth tự hết hạn sau 7 ngày** (app ở chế độ "Testing") → Publish app sang "Production" trên Google Cloud Console
3. **Tạo nhầm folder lồng / lạc sang Shared Drive khác** khi thêm logic phân loại → bỏ kiểu tìm-hoặc-tạo-theo-tên, trỏ thẳng ID folder có sẵn
4. **Race condition**: cron + chạy tay cùng lúc → trùng folder/task → thêm file lock (`fcntl.flock`) chặn chạy song song

---

## 🔧 Việc còn tồn đọng (không gấp)

- [ ] 3 task Jira test bị kẹt không xoá được do thiếu quyền (`VE-233`, `VE-235`, `VE-236`) — cần người dùng tự xoá tay trên Jira, hoặc nhờ admin cấp quyền delete cho trạng thái "Lowkey Explainer"
- [ ] venv đang chạy Python 3.9 (đã EOL) — Google liên tục cảnh báo (`FutureWarning`), không ảnh hưởng chức năng nhưng nên nâng cấp Python khi rảnh
- [ ] Chưa có cơ chế thông báo (Slack/email) khi cron chạy lỗi — hiện tại lỗi chỉ nằm trong `cron.log`, phải tự mở xem

---

## 📂 Cấu trúc file trong repo

```
kich-ban-automation/
├── master_prompt.md     # Master prompt viết kịch bản + hướng dẫn định dạng xuất file
├── config.py             # Đọc .env, xác thực Google OAuth
├── process_file.py       # Script chính: parse → phân loại → Drive → Jira
├── requirements.txt
├── .env.example           # Template — copy thành .env rồi điền giá trị thật
├── inbox/                  # Thả file .md kịch bản đã duyệt vào đây
├── processed/               # File đã xử lý xong tự move vào đây
├── README.md                 # Hướng dẫn setup từ A-Z
└── progress.md                # File này
```

---

## 🔜 Nếu tiếp tục làm gì đó, bắt đầu từ đây

Khi mở lại phiên làm việc mới, đọc file này trước để nắm bối cảnh, sau đó xem
`README.md` để biết chi tiết setup, và `process_file.py` là nơi toàn bộ logic
xử lý nằm ở đó.
