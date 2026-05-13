# FROM: chọn "image" nền — python:3.12-slim là Python 3.12
# bản "slim" = nhỏ gọn, không có các tool thừa
FROM python:3.12-slim

# WORKDIR: đặt thư mục làm việc bên trong container
# Mọi lệnh sau đây đều chạy trong /app
WORKDIR /app

# COPY requirements.txt trước (tách riêng để tận dụng Docker cache)
# Lý do: nếu chỉ thay đổi code .py, Docker không cần cài lại thư viện
COPY requirements.txt .

# RUN: chạy lệnh trong quá trình build image
# --no-cache-dir: không lưu cache pip → image nhỏ hơn
RUN pip install --no-cache-dir -r requirements.txt

# COPY toàn bộ code vào container
# Dấu . đầu = thư mục hiện tại trên máy host
# Dấu . cuối = /app trong container (WORKDIR)
COPY . .

# CMD: lệnh chạy khi container khởi động
# Chạy main.py một lần rồi thoát (exit 0 nếu thành công)
CMD ["python", "main.py"]
