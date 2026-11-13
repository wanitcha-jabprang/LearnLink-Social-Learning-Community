# LearnLink

LearnLink คือเว็บชุมชนสำหรับผู้เรียน ใช้แบ่งปันความรู้ ค้นหาโพสต์ และเรียนรู้ร่วมกันในชุมชน

## ลิงก์ระบบ

- **Production URL:** https://learnlink-social-learning-community-production.up.railway.app/

## ฟีเจอร์หลัก

- สมัครสมาชิก เข้าสู่ระบบ และตั้งค่า MFA
- สร้างโพสต์ แสดงความคิดเห็น กดถูกใจ บันทึกโพสต์ และติดตามผู้ใช้
- สร้างและเข้าร่วมชุมชนสาธารณะหรือส่วนตัว
- จัดการโปรไฟล์ รูปโปรไฟล์ และรูปปก

## เทคโนโลยี

- Python 3.13 และ Django 5.2
- MySQL 8.4 สำหรับการทำงานปกติ และ SQLite สำหรับชุดทดสอบ
- Pillow สำหรับตรวจสอบและประมวลผลรูปภาพ
- WhiteNoise สำหรับให้บริการ static files
- Docker Compose สำหรับรันแอปและบริการที่ต้องใช้ในเครื่อง

## เริ่มใช้งานด้วย Docker Compose

1. สร้างไฟล์ `.env` จากตัวอย่าง:

   ```powershell
   Copy-Item .env.example .env
   ```

2. แก้ค่าใน `.env` ให้เหมาะกับเครื่อง โดยเฉพาะ `SECRET_KEY`,
   `DB_PASSWORD` และ `MYSQL_ROOT_PASSWORD`
3. สร้างและเริ่มบริการ:

   ```powershell
   docker compose up --build
   ```

4. เปิดเว็บที่ <http://localhost:8000>

Compose จะเริ่ม MySQL, ClamAV และเว็บแอป พร้อมรัน migrations และเก็บ static
files ก่อนเริ่มเว็บ หากต้องการหยุดบริการ กด `Ctrl+C` แล้วใช้ `docker compose down`

## ทดสอบ

จากโฟลเดอร์ `src`:

```powershell
python manage.py check --settings=config.test_settings
python manage.py test --settings=config.test_settings
```

## โครงสร้างโปรเจกต์

```text
src/
  common/       ส่วนกลาง เช่น validation และ utilities
  community/    ชุมชนและการจัดการสมาชิก
  config/       Django settings และ URL configuration
  core/         ฟังก์ชันส่วนกลางและ security middleware
  feed/         ฟีดและการค้นหา
  post/         โพสต์และปฏิสัมพันธ์
  users/        บัญชี โปรไฟล์ และการยืนยันตัวตน
```

## CI/CD และ Deploy

GitHub Actions รันทดสอบ Django, Bandit, pip-audit และ Docker build เมื่อมี Pull
Request หรือ push เข้า `main` ส่วนการ Deploy ไป Railway production และ ZAP
Baseline scan จะทำหลัง push เข้า `main` เมื่อกำหนด GitHub Secrets/Variables
ตามที่ workflow ต้องการแล้ว
