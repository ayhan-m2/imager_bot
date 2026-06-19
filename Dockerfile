# استفاده از نسخه رسمی پایتون
FROM python:3.10-slim

# نصب نرم‌افزارهای سیستمی (FFmpeg و LibreOffice)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# تنظیم مسیر کاری
WORKDIR /app

# کپی کردن فایل نیازمندی‌ها و نصب کتابخانه‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن بقیه فایل‌های ربات
COPY . .

# اجرای ربات (اگر اسم فایل ربات شما چیز دیگری است، کلمه main.py را تغییر دهید)
CMD ["python", "main.py"]
