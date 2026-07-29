# Tesseract dự phòng tùy chọn

Tesseract không chặn PaddleOCR và không phải engine mặc định. Người dùng bình
thường chỉ cần nhấn **Cài đặt** trong card Tesseract dự phòng. Ứng dụng tải
component từ GitHub Release của chính `NovWyatt/checkparking`, xác minh SHA-256
của archive và từng file, giải nén versioned vào LocalAppData, chạy
`tesseract --version`, kiểm tra `eng`/`osd` và OCR smoke trước khi kích hoạt.

Khi phiên bản mới có manifest đã xác minh, nút chính chuyển thành **Cập nhật**.
Version cũ được giữ nguyên để rollback. Nếu tải, hash, DLL, traineddata hoặc
smoke thất bại, staging bị xóa và PaddleOCR vẫn hoạt động bình thường.
