# สถาปัตยกรรมแบบแบ่งตามฟีเจอร์

แต่ละฟีเจอร์ของ Django รวมเลเยอร์ที่เกี่ยวข้องไว้ภายในโฟลเดอร์เดียวกัน:

```text
<feature>/
  presentation/       views, URLs และ forms ที่เกี่ยวข้องกับ HTTP
  application/        use cases และ workflow ของฟีเจอร์
  domain/             กฎธุรกิจที่ไม่ต้องพึ่ง Django ORM
  infrastructure/
    persistence/      Django models และการทำงานจริงของ repository
    storage/          ตัวเชื่อมต่อสำหรับจัดเก็บไฟล์และตรวจสอบไฟล์อัปโหลด
  migrations/         Django migrations (คงไว้ที่โฟลเดอร์หลักของ app)
```

ฟีเจอร์ที่มีในปัจจุบัน ได้แก่ `users`, `feed`, `community`, `post` และ `core`
ส่วน `config` ใช้ตั้งค่าและประกอบส่วนต่าง ๆ ของโปรเจกต์ และ `common`
ใช้เก็บ abstractions ที่ Django ใช้ร่วมกัน

โค้ดใน `presentation` เรียกใช้ application services; application services
ใช้ domain policies และ repositories ที่ส่งเข้ามาเป็น dependencies;
ส่วน `infrastructure` ดูแลการ query และบันทึกข้อมูลผ่าน ORM รวมถึงการจัดเก็บไฟล์

App configuration ของ Django โหลด models จาก
`infrastructure.persistence.models` โดยตรง ขณะที่ URL หลักของโปรเจกต์ include
`presentation.urls` ของแต่ละฟีเจอร์ ไฟล์ `admin.py`, `apps.py`
และโฟลเดอร์ `migrations/` ยังคงอยู่ที่โฟลเดอร์หลักของ app
เพื่อให้ Django ค้นพบ admin, app configuration และ migrations ได้ตามปกติ
