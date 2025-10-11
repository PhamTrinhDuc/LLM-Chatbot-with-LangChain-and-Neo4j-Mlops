## TUTORIAL 

---

## 🌐 Tổng quan: SQL vs Neo4j

| Khái niệm        | SQL (Quan hệ)            | Neo4j (Đồ thị - Cypher)        |
|------------------|--------------------------|-------------------------------|
| Dữ liệu lưu ở   | Bảng (Tables)            | **Node** và **Relationship**  |
| Dòng dữ liệu     | Row                      | **Node** (ví dụ: `(:User)`)   |
| Liên kết bảng    | JOIN qua khóa ngoại      | **Relationship** (mũi tên: `-->`) |
| Ngôn ngữ truy vấn| SQL                      | **Cypher**                    |

---

## 🔑 Các lệnh Cypher cơ bản (so với SQL)
### 1. Tạo dữ liệu 
#### SQL: 
```bash
INSERT INTO users (id, name, email) VALUES (1, 'A', 'abc.@gmail.com');
```
#### Cypher: 
```bash
CREATE (:User {user_id: 1, name: 'A', email: 'abc.@gmail.com'});
```
- `(:User {...})` = một node có nhãn User và thuộc tính bên trong `{}`.

### 2. Truy vấn dữ liệu
#### SQL: 
```bash
SELECT name, email FROM users WHERE id = 1;
```
#### Cypher: 
```bash
MATCH (u: User {user_id: 1})
RETURN u.name, u.email
```
- `MATCH =` tìm node/relationship (giống `FROM` + `WHERE` trong SQL).
- `u` là biến (giống alias trong SQL).
- `RETURN =` chọn cột để hiển thị (giống `SELECT`).

### 3. Liên kết dữ liệu (JOIN trong SQL → Relationship trong Neo4j)
#### SQL: 
```bash
SELET u.name, o.product FROM users u 
JOIN orders o ON u.id = o.user_id;
```
#### Neo4j (dùng relationship):: 
```bash
MATCH (u:User)-[:PLACED]->(o:Order)
RETURN u.name, o.product;
```
- `(u:User)-[:PLACED]->(o:Order) =` tìm user có mối quan hệ `PLACED` đến order.
- Mũi tên `-->` thể hiện hướng của mối quan hệ.
- Không cần `JOIN —` mối quan hệ đã được lưu sẵn như một thực thể
### 4. Cập nhật dữ liệu 
#### SQL: 
```bash
UPDATE users SET email = 'def.@gmail.com' WHERE id=1;
```
#### Cypher: 
```bash
MATCH (u:User {u.user_id:1})
SET u.email='def.@gmail.com';
```
### 5. Xóa dữ liệu 
#### SQL: 
```bash
DELETE FROm users WHERE id=1;
```
#### Cypher: 
```bash
MATCH (u:User {u.user_id=1})
DETACH DELETE u;
```
- `DELETE` chỉ xóa node nếu không có relationship.
- `DETACH DELETE =` xóa node và cả các mối quan hệ của nó.
### 6. Tạo ràng buộc (Constraint)
#### SQL: 
```bash
ALTER TABLE users ADD CONSTRAINT UNIQUE (email);
```
#### Cypher: 
```bash
CREATE CONSTRAINT user_email_unique
FOR (u:User) REQUIRE u.email IS UNIQUE;
```
- Đảm bảo không có 2 node `:User` nào có cùng email.
### 7. Tạo hoặc cập nhật (UPSERT)
```bash
MERGE (u:User {user_id: 1})
SET u.name = 'A', u.email = 'a@example.com';
```
- `MERGE =` nếu tồn tại → cập nhật, nếu chưa → tạo mới.

## 📚 Bảng tra cứu nhanh: SQL → Cypher

| SQL                     | Cypher                                  |
|-------------------------|------------------------------------------|
| `SELECT`                | `RETURN`                                 |
| `FROM table`            | `MATCH (n:Label)`                        |
| `WHERE`                 | trong `MATCH` hoặc sau `MATCH`           |
| `INSERT`                | `CREATE` hoặc `MERGE`                    |
| `UPDATE`                | `SET`                                    |
| `DELETE`                | `DELETE` / `DETACH DELETE`               |
| `JOIN`                  | `-[:REL]->` (mối quan hệ đã lưu sẵn!)    |
| `PRIMARY KEY`           | `CREATE CONSTRAINT ... IS UNIQUE`        |
| `UPSERT`                | `MERGE`                                  |
