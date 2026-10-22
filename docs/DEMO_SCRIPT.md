# Kịch bản quay demo 2 phút

**TeamLoveTheSun · RMIT_SGS · C2**

Chuẩn bị trước khi quay: chạy setup/UI theo README; mở hai browser profile riêng, một profile cấu hình Admin A và profile kia Admin B. Không quay màn hình nhập JWT, private key, terminal chứa token hay file PEM. Hai profile giúp không phải thay credential giữa video.

| Thời gian | Màn hình / thao tác | Nội dung trình bày |
| --- | --- | --- |
| 00:00–00:15 | Tiêu đề dự án, Overview | “Chúng tôi là TeamLoveTheSun, RMIT_SGS, challenge C2. QUORUM biến thay đổi đặc quyền thành quyết định có hai quản trị viên.” |
| 00:15–00:30 | Policies, giải thích JSON hiện tại | “Một tài khoản admin bị lộ hoặc thao tác nhầm không nên tự mình thay đổi chính sách cho cả hệ thống.” |
| 00:30–00:50 | Admin A sửa `limits.value`, gửi yêu cầu; mở hàng đợi | “Thay đổi được đưa vào trạng thái chờ, chưa được thực thi.” Không nhầm trường trong policy với hạn mức vận hành riêng của `POST /limits`. |
| 00:50–01:05 | Admin A thử ký yêu cầu của mình | Hiển thị thông báo từ chối: người tạo không thể tự phê duyệt. |
| 01:05–01:25 | Chuyển profile Admin B, chọn yêu cầu, ký | “Một quản trị viên khác kiểm tra nội dung và ký payload phê duyệt. Backend xác minh rồi mới thực thi.” |
| 01:25–01:40 | Policies và Audit | Cho thấy JSON/phiên bản mới và sự kiện phê duyệt được lưu; không khẳng định audit bất biến trước người sở hữu máy. |
| 01:40–01:55 | Administrators và mô tả TideCloak | “Bản nộp dùng Plan C: JWT và chữ ký Ed25519 cục bộ mô phỏng luồng. TideCloak là lớp identity/governance dự kiến; chưa kết nối live.” |
| 01:55–02:00 | Tên đội và repo | “Từ quyền lực của một tài khoản sang quyết định có đối soát. Source và hướng dẫn chạy nằm trong repository.” |

Xuất H.264/AAC `.mp4`, khoảng 2 phút và dưới 100 MB. Xem lại hình lẫn tiếng trước khi upload; không đưa bản gốc có credential vào repo public. Không khẳng định có threshold multisig, distributed key custody hay Merkle tree hoàn chỉnh trong prototype này.
