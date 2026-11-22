import os
import sqlite3

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash

from models.base import Base

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")
DATABASE_URL = "sqlite:///" + DATABASE.replace("\\", "/")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session():
    """SQLAlchemy сессиясын беретін FastAPI тәуелділігі (Depends)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db():
    """Ескі sqlite3 қосылымы. 2-этапта жойылады."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_missing_columns():
    """Бұрыңғы базаға жаңа бағандарды қосады. Деректер сақталады."""
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(tests)"))]
        if "category_id" not in cols:
            conn.execute(text(
                "ALTER TABLE tests ADD COLUMN category_id INTEGER "
                "REFERENCES categories (id) ON DELETE SET NULL"))


def _seed():
    """Бастапқы админ, санаттар және үлгі тест (егер жоқ болса)."""
    from models import Category, Question, Test, User

    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.role == "admin")) is None:
            db.add(User(full_name="Администратор", email="admin@test.kz",
                        password_hash=generate_password_hash("admin123"),
                        role="admin"))

        if db.scalar(select(Category.id).limit(1)) is None:
            for name in ("Python", "Математика", "Тарих"):
                db.add(Category(name=name))
            db.flush()

        if db.scalar(select(Test.id).limit(1)) is None:
            python_cat = db.scalar(select(Category).where(Category.name == "Python"))
            test = Test(title="Python негіздері",
                        description="Python тілінің базалық білімін тексеретін тест",
                        max_score=100, duration_minutes=15, category=python_cat)
            test.questions = [
                Question(question_text="Python-да экранға мәтін шығаратын функция қайсы?",
                         option_a="echo()", option_b="print()",
                         option_c="write()", option_d="show()", correct_option="B"),
                Question(question_text="Тізім (list) қай жақшамен жазылады?",
                         option_a="( )", option_b="{ }",
                         option_c="[ ]", option_d="< >", correct_option="C"),
                Question(question_text="Python қай тіл түріне жатады?",
                         option_a="Интерпretацияланатын", option_b="Тек компиляцияланатын",
                         option_c="Ассемблер", option_d="Белгілеу тілі", correct_option="A"),
            ]
            db.add(test)

        db.commit()


def init_db():
    import models  # noqa: F401  (барлық кестелерді тіркеу үшін)

    Base.metadata.create_all(bind=engine)  # жоқ кестелерді жасайды
    _add_missing_columns()                 # бар кестеге жаңа бағандарды қосады
    _seed()