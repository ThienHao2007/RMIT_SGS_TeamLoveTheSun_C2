# Nộp bài — TeamLoveTheSun / RMIT_SGS / C2

## Yêu cầu đối chiếu từ ban tổ chức

Nguồn: https://tide.org/unlocked/#challenge

- Repository GitHub **Public**, chứa mã nguồn và video demo.
- README mở đầu bằng Project overview tối đa **300 từ**, có một câu mô tả và đủ 5 mục của mẫu chính thức; hướng dẫn Setup ở phần riêng.
- Video **2 phút**, định dạng **MP4**, dung lượng **dưới 100 MB**.
- Nộp link repository qua form chính thức: https://forms.gle/HRHYjnqB86j1LFS97
- Plan C cho phép mô phỏng tích hợp. README khai báo rõ đây là mô phỏng cục bộ, không phải TideCloak đang chạy thật.

`TeamLoveTheSun_RMIT_SGS_C2` là tên repo đề xuất để nhận diện đội, không phải quy tắc đặt tên bắt buộc từ trang hướng dẫn. Thông tin thành viên/email đăng ký không được tự điền thay đội; cung cấp theo các trường thực tế của form.

## Các bước đưa lên GitHub

1. Đăng nhập GitHub, chọn **New repository**.
2. Đặt tên `TeamLoveTheSun_RMIT_SGS_C2`, chọn **Public**. Không tạo thêm README hay license tự động vì bộ file đã có README và đội chưa chọn license.
3. Dùng GitHub Desktop: clone repo vừa tạo về một thư mục mới, rồi copy **nội dung bên trong** thư mục bộ nộp vào checkout đó. README phải nằm ngay root repo, không nằm trong một thư mục lồng thêm.
4. Kiểm tra danh sách thay đổi: phải có các file ẩn `.github/`, `.gitignore`, `.mcp.json`, cùng `api/`, `ui/`, `scripts/`, `tests/`, `demo/`, `docs/`, `keys/.gitkeep`, setup scripts và các file cấu hình root.
5. Không đưa `.venv/`, `node_modules/`, `ui/dist/`, `.tools/`, `quorum.db`, JWT, `.env`, `keys/*.pem`, `keys/*.pub`, video gốc hay tài liệu cá nhân lên repo. `.gitignore` hỗ trợ việc này, nhưng vẫn cần xem danh sách trước khi commit.
6. Commit và **Push origin**. Không chỉ upload một file ZIP: ban giám khảo cần thấy README và source trực tiếp trong repo. Nếu upload bằng giao diện web, giữ nguyên cấu trúc thư mục và kiểm tra các dotfile không bị bỏ sót. Video trên 25 MB cần Git/GitHub Desktop thay vì web upload.
7. Mở URL repo trong cửa sổ ẩn danh để xác nhận repo Public, README hiển thị đúng, link MP4 tải được và video phát được.
8. Clone repo sang thư mục khác; chạy setup và demo theo README để kiểm tra file đã upload đủ.
9. Mở form chính thức, điền thông tin đội **TeamLoveTheSun**, địa điểm **RMIT_SGS**, challenge **C2** vào các trường tương ứng, và dán URL repo thực tế. Kiểm tra hạn nộp trên trang/ban tổ chức trước khi gửi. Việc chuẩn bị bộ file không tự động nộp form.

## Video đi kèm

`demo/TeamLoveTheSun_RMIT_SGS_C2.mp4` là bản xử lý từ video đội cung cấp: che các đoạn thiết lập credential/editor, bỏ khung trình duyệt ngoài ứng dụng, tăng tốc 1,06 lần để dưới 2 phút, và nén H.264/AAC. Bản gốc không nằm trong bộ upload.

Xem lại toàn bộ video, gồm cả âm thanh, trước khi công khai. Các khóa xuất hiện trong video gốc cần được coi là đã lộ; không tái sử dụng chúng ngoài môi trường demo. Bộ nộp không chứa những khóa đó và tạo khóa mới khi setup.

## Checklist trước khi nhấn Submit

- [ ] Repo Public, mở được khi không đăng nhập.
- [ ] README ở root; tên đội/campus/challenge chính xác.
- [ ] Project overview đủ 5 mục, không quá 300 từ; Setup tách riêng.
- [ ] Video MP4 dưới 100 MB, khoảng 2 phút, nghe/xem rõ; đã xem lại bản che thông tin.
- [ ] Không có private key, JWT, database hoặc lịch sử commit chứa secret.
- [ ] Fresh clone chạy được UI và `demo.py`.
- [ ] Mô tả Plan C và giới hạn bảo mật đúng, không khẳng định có TideCloak live.
- [ ] Đã gửi URL repository qua form chính thức và lưu xác nhận nộp.
