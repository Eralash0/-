from werkzeug.security import generate_password_hash
from database import get_db

NEW_EMAIL = "admin@test.kz"
NEW_PASSWORD = "Өз-күшті-құпиясөзің"

conn = get_db()
conn.execute(
    "UPDATE users SET email = ?, password_hash = ? WHERE role = 'admin'",
    (NEW_EMAIL, generate_password_hash(NEW_PASSWORD)),
)
conn.commit()
conn.close()
print("Админ деректері жаңартылды")