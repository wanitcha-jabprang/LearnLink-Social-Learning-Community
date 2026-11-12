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

Application services แยกตามความรับผิดชอบและ use case เช่น บัญชี โปรไฟล์
การติดตาม การลบบัญชี โพสต์ ความคิดเห็น และปฏิสัมพันธ์กับโพสต์
`PostAccessService` รวมกฎตรวจสิทธิ์ที่ใช้ร่วมกัน ส่วน container ใน
`infrastructure` เป็น composition root ที่สร้างและส่ง dependencies ให้ services
แทนการสร้าง repository ภายใน business logic

กฎใน `domain` ใช้ pure functions เมื่อไม่มี state หรือ dependency ที่ต้องเก็บไว้;
ไม่จำเป็นต้องห่อทุกฟังก์ชันเป็น class เพื่อให้เป็น OOP
เช่นเดียวกัน Django function-based views ยังคงเป็น HTTP adapters ที่เหมาะกับ
แต่ละ endpoint ฝั่ง Python เป็นแหล่งตรวจสอบกฎธุรกิจและไฟล์อัปโหลด
ส่วน JavaScript ใช้เฉพาะพฤติกรรมที่ต้องทำงานใน browser เช่น preview และคร็อปรูป
templates และ CSS คงเป็นรูปแบบ declarative ของชั้นนำเสนอ

App configuration ของ Django โหลด models จาก
`infrastructure.persistence.models` โดยตรง ขณะที่ URL หลักของโปรเจกต์ include
`presentation.urls` ของแต่ละฟีเจอร์ ไฟล์ `admin.py`, `apps.py`
และโฟลเดอร์ `migrations/` ยังคงอยู่ที่โฟลเดอร์หลักของ app
เพื่อให้ Django ค้นพบ admin, app configuration และ migrations ได้ตามปกติ
