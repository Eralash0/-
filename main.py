import sqlite3
from urllib.parse import urlencode, urlparse

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import NoMatchFound
from jinja2 import pass_context
from werkzeug.security import generate_password_hash, check_password_hash

from database import init_db, get_db
from i18n import translate_html
from routers.auth import router as auth_router
from security import create_access_token, COOKIE_NAME, ACCESS_TOKEN_MINUTES
from routers.catalog import router as catalog_router
from routers.admin import router as admin_router
from routers.cart import router as cart_router
from routers.orders import router as orders_router, attach_result

app = FastAPI(title="Онлайн тестілеу жүйесі")
app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key-123")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

init_db()


# ---------- Шаблондарға көмекші функциялар ----------

@pass_context
def url_for(context, name, **params):
    """Flask-тағы url_for сияқты жұмыс істейді."""
    request = context["request"]
    if name == "static":
        return "/static/" + params.get("filename", "")

    path_names = set()
    for route in request.app.routes:
        if getattr(route, "name", None) == name:
            path_names = set(getattr(route, "param_convertors", {}).keys())
            break

    path_params = {k: v for k, v in params.items() if k in path_names}
    query = {k: v for k, v in params.items() if k not in path_names}

    try:
        url = str(request.app.url_path_for(name, **path_params))
    except NoMatchFound:
        return "#"  # бет әлі жасалмаған
    if query:
        url += "?" + urlencode(query)
    return url


templates.env.globals["url_for"] = url_for


def flash(request: Request, message: str, category: str = "success"):
    flashes = request.session.get("_flashes", [])
    flashes.append([category, message])
    request.session["_flashes"] = flashes


def render(request: Request, name: str, **context):
    def get_flashed_messages(with_categories=False):
        flashes = request.session.pop("_flashes", [])
        return [tuple(f) for f in flashes]

    lang = request.session.get("lang", "kz")
    context["request"] = request
    context["session"] = request.session
    context["get_flashed_messages"] = get_flashed_messages
    context["lang"] = lang

    html = templates.get_template(name).render(context)
    if lang == "ru":
        html = translate_html(html)
    return HTMLResponse(html)


# ---------- Қорғау (кейінгі этаптарда керек) ----------

class RedirectTo(Exception):
    def __init__(self, url: str):
        self.url = url


@app.exception_handler(RedirectTo)
async def redirect_handler(request: Request, exc: RedirectTo):
    return RedirectResponse(exc.url, status_code=303)


def login_required(request: Request):
    if "user_id" not in request.session:
        flash(request, "Алдымен жүйеге кіріңіз", "error")
        raise RedirectTo("/login")


def admin_required(request: Request):
    if request.session.get("role") != "admin":
        flash(request, "Бұл бетке тек админ кіре алады", "error")
        raise RedirectTo("/")


# ---------- Беттер ----------

@app.get("/", name="index")
def index(request: Request):
    return render(request, "index.html")


@app.get("/register", name="register")
def register_page(request: Request):
    return render(request, "register.html")


@app.post("/register", name="register")
def register_post(request: Request,
                  full_name: str = Form(""),
                  email: str = Form(""),
                  password: str = Form(""),
                  confirm: str = Form("")):
    full_name = full_name.strip()
    email = email.strip().lower()

    if not full_name or not email or not password:
        flash(request, "Барлық өрісті толтырыңыз", "error")
    elif len(password) < 6:
        flash(request, "Құпиясөз кемінде 6 таңба болсын", "error")
    elif password != confirm:
        flash(request, "Құпиясөздер сәйкес емес", "error")
    else:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (full_name, email, password_hash, role) "
                "VALUES (?, ?, ?, 'student')",
                (full_name, email, generate_password_hash(password)),
            )
            conn.commit()
            flash(request, "Тіркелу сәтті! Енді кіріңіз", "success")
            return RedirectResponse("/login", status_code=303)
        except sqlite3.IntegrityError:
            flash(request, "Бұл email бұрын тіркелген", "error")
        finally:
            conn.close()

    return render(request, "register.html")


@app.get("/login", name="login")
def login_page(request: Request):
    return render(request, "login.html")


@app.post("/login", name="login")
def login_post(request: Request,
               email: str = Form(""),
               password: str = Form("")):
    email = email.strip().lower()

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
#ә) login_post функциясы. Ctrl+F арқылы def login_post тап. Ішінде if user and check_password_hash(...) блогын тап және соңғы return RedirectResponse("/", status_code=303) жолын мына кодпен ауыстыр (блоктың басындағы request.session[...] жолдары өзгермейді):

    if user and check_password_hash(user["password_hash"], password):
        request.session["user_id"] = user["id"]
        request.session["full_name"] = user["full_name"]
        request.session["role"] = user["role"]
        flash(request, f"Қош келдіңіз, {user['full_name']}!", "success")
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(COOKIE_NAME,
                            create_access_token(user["id"], user["role"]),
                            httponly=True, samesite="lax",
                            max_age=ACCESS_TOKEN_MINUTES * 60)
        return response

    flash(request, "Email немесе құпиясөз қате", "error")
    return render(request, "login.html")


@app.get("/logout", name="logout")
def logout(request: Request):
    request.session.clear()
    flash(request, "Сіз жүйеден шықтыңыз", "success")
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


def get_grade(percent):
    if percent >= 90:
        return "5 (Өте жақсы)"
    if percent >= 75:
        return "4 (Жақсы)"
    if percent >= 50:
        return "3 (Қанағаттанарлық)"
    return "2 (Қанағаттанарлықсыз)"


@app.get("/tests", name="tests", dependencies=[Depends(login_required)])
def tests_page(request: Request):
    conn = get_db()
    rows = conn.execute("""
        SELECT t.*, COUNT(q.id) AS q_count, u.full_name AS author
        FROM tests t
        LEFT JOIN questions q ON q.test_id = t.id
        LEFT JOIN users u ON u.id = t.created_by
        GROUP BY t.id
        HAVING COUNT(q.id) > 0
        ORDER BY t.id DESC
    """).fetchall()
    my_results = conn.execute("""
        SELECT r.*, t.title
        FROM results r
        JOIN tests t ON t.id = r.test_id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
    """, (request.session["user_id"],)).fetchall()
    conn.close()
    return render(request, "tests.html", tests=rows, my_results=my_results)


@app.get("/test/{test_id}", name="take_test",
         dependencies=[Depends(login_required)])
def take_test_page(request: Request, test_id: int):
    conn = get_db()
    test = conn.execute(
        "SELECT * FROM tests WHERE id = ?", (test_id,)
    ).fetchone()
    if test is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Тест табылмады")
    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY id", (test_id,)
    ).fetchall()
    conn.close()
    return render(request, "take_test.html", test=test, questions=questions)


@app.post("/test/{test_id}/submit", name="submit_test",
          dependencies=[Depends(login_required)])
async def submit_test(request: Request, test_id: int):
    form = await request.form()

    conn = get_db()
    test = conn.execute(
        "SELECT * FROM tests WHERE id = ?", (test_id,)
    ).fetchone()
    if test is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Тест табылмады")

    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY id", (test_id,)
    ).fetchall()
    total = len(questions)
    if total == 0:
        conn.close()
        flash(request, "Бұл тестте сұрақ жоқ", "error")
        return RedirectResponse("/tests", status_code=303)

    correct = 0
    answers = []
    for pos, q in enumerate(questions, start=1):
        chosen = form.get(f"q{q['id']}")
        if chosen not in ("A", "B", "C", "D"):
            chosen = None
        if chosen == q["correct_option"]:
            correct += 1
        answers.append((pos, q["question_text"], q["option_a"], q["option_b"],
                        q["option_c"], q["option_d"], q["correct_option"], chosen))

    percent = round(correct / total * 100, 1)
    score = round(correct / total * test["max_score"])

    cur = conn.execute(
        "INSERT INTO results (user_id, test_id, score, max_score, percent) "
        "VALUES (?, ?, ?, ?, ?)",
        (request.session["user_id"], test_id, score,
         test["max_score"], percent),
    )
    result_id = cur.lastrowid

    conn.executemany(
        """INSERT INTO result_answers
           (result_id, position, question_text, option_a, option_b, option_c,
            option_d, correct_option, chosen_option)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(result_id, *a) for a in answers],
    )
    conn.commit()
    conn.close()
    attach_result(request.session["user_id"], test_id, result_id)
    return RedirectResponse(f"/result/{result_id}", status_code=303)


@app.get("/result/{result_id}", name="result",
         dependencies=[Depends(login_required)])
@app.get("/result/{result_id}", name="result",
         dependencies=[Depends(login_required)])
def result_page(request: Request, result_id: int):
    conn = get_db()
    r = conn.execute("""
        SELECT r.*, t.title, u.full_name
        FROM results r
        JOIN tests t ON t.id = r.test_id
        JOIN users u ON u.id = r.user_id
        WHERE r.id = ?
    """, (result_id,)).fetchone()

    if r is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Нәтиже табылмады")
    if (r["user_id"] != request.session["user_id"]
            and request.session.get("role") != "admin"):
        conn.close()
        raise HTTPException(status_code=403, detail="Рұқсат жоқ")

    rows = conn.execute(
        "SELECT * FROM result_answers WHERE result_id = ? ORDER BY position",
        (result_id,),
    ).fetchall()
    conn.close()

    stats = {"correct": 0, "wrong": 0, "skipped": 0}
    review = []
    for a in rows:
        chosen = a["chosen_option"]
        if chosen is None:
            status = "skipped"
        elif chosen == a["correct_option"]:
            status = "correct"
        else:
            status = "wrong"
        stats[status] += 1
        review.append({
            "position": a["position"],
            "text": a["question_text"],
            "status": status,
            "chosen": chosen,
            "correct": a["correct_option"],
            "options": [("A", a["option_a"]), ("B", a["option_b"]),
                        ("C", a["option_c"]), ("D", a["option_d"])],
        })

    return render(request, "result.html", r=r, grade=get_grade(r["percent"]),
                  review=review, stats=stats)
# ===================== 4-ЭТАП: АДМИН-ПАНЕЛЬ =====================

admin_deps = [Depends(login_required), Depends(admin_required)]


@app.get("/admin", name="admin", dependencies=admin_deps)
def admin_page(request: Request):
    conn = get_db()

    stats = {
        "students": conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0],
        "tests": conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0],
        "results": conn.execute("SELECT COUNT(*) FROM results").fetchone()[0],
        "avg": conn.execute(
            "SELECT ROUND(AVG(percent), 1) FROM results").fetchone()[0] or 0,
    }

    tests = conn.execute("""
        SELECT t.*, COUNT(q.id) AS q_count
        FROM tests t
        LEFT JOIN questions q ON q.test_id = t.id
        GROUP BY t.id
        ORDER BY t.id DESC
    """).fetchall()

    questions_by_test = {}
    for q in conn.execute("SELECT * FROM questions ORDER BY id").fetchall():
        questions_by_test.setdefault(q["test_id"], []).append(q)

    results = []
    rows = conn.execute("""
        SELECT r.*, u.full_name, u.email, t.title
        FROM results r
        JOIN users u ON u.id = r.user_id
        JOIN tests t ON t.id = r.test_id
        ORDER BY r.id DESC
    """).fetchall()
    for r in rows:
        item = dict(r)
        item["grade"] = get_grade(r["percent"])
        results.append(item)

    users = conn.execute("""
        SELECT u.*, COUNT(r.id) AS r_count
        FROM users u
        LEFT JOIN results r ON r.user_id = u.id
        GROUP BY u.id
        ORDER BY u.id
    """).fetchall()

    conn.close()
    return render(request, "admin.html", stats=stats, tests=tests,
                  questions_by_test=questions_by_test,
                  results=results, users=users)


@app.post("/admin/test/add", name="admin_add_test", dependencies=admin_deps)
def admin_add_test(request: Request,
                   title: str = Form(""),
                   description: str = Form(""),
                   max_score: str = Form("100"),
                   duration: str = Form("15")):
    title = title.strip()
    description = description.strip()
    try:
        max_score_i = int(max_score)
        duration_i = int(duration)
    except ValueError:
        flash(request, "Балл және уақыт сан болуы керек", "error")
        return RedirectResponse("/admin", status_code=303)

    if not title or max_score_i <= 0 or duration_i <= 0:
        flash(request, "Деректерді дұрыс толтырыңыз", "error")
        return RedirectResponse("/admin", status_code=303)

    conn = get_db()
    conn.execute(
        "INSERT INTO tests (title, description, max_score, duration_minutes) "
        "VALUES (?, ?, ?, ?)",
        (title, description, max_score_i, duration_i),
    )
    conn.commit()
    conn.close()
    flash(request, "Тест қосылды. Енді оған сұрақ қосыңыз", "success")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/test/{test_id}/delete", name="admin_delete_test",
          dependencies=admin_deps)
def admin_delete_test(request: Request, test_id: int):
    conn = get_db()
    conn.execute("DELETE FROM tests WHERE id = ?", (test_id,))
    conn.commit()
    conn.close()
    flash(request, "Тест және оның сұрақтары, нәтижелері өшірілді", "success")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/question/add", name="admin_add_question",
          dependencies=admin_deps)
def admin_add_question(request: Request,
                       test_id: str = Form(""),
                       question_text: str = Form(""),
                       option_a: str = Form(""),
                       option_b: str = Form(""),
                       option_c: str = Form(""),
                       option_d: str = Form(""),
                       correct_option: str = Form("")):
    fields = [question_text.strip(), option_a.strip(), option_b.strip(),
              option_c.strip(), option_d.strip()]

    if not all(fields) or correct_option not in ("A", "B", "C", "D"):
        flash(request, "Сұрақ пен 4 жауапты толық толтырыңыз", "error")
        return RedirectResponse("/admin", status_code=303)

    try:
        test_id_i = int(test_id)
    except ValueError:
        flash(request, "Тестті таңдаңыз", "error")
        return RedirectResponse("/admin", status_code=303)

    conn = get_db()
    conn.execute(
        """INSERT INTO questions
           (test_id, question_text, option_a, option_b, option_c, option_d, correct_option)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (test_id_i, *fields, correct_option),
    )
    conn.commit()
    conn.close()
    flash(request, "Сұрақ қосылды", "success")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/question/{question_id}/delete",
          name="admin_delete_question", dependencies=admin_deps)
def admin_delete_question(request: Request, question_id: int):
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()
    flash(request, "Сұрақ өшірілді", "success")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/user/{user_id}/delete", name="admin_delete_user",
          dependencies=admin_deps)
def admin_delete_user(request: Request, user_id: int):
    conn = get_db()
    user = conn.execute(
        "SELECT role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        flash(request, "Қолданушы табылмады", "error")
    elif user["role"] == "admin":
        flash(request, "Админді өшіруге болмайды", "error")
    else:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        flash(request, "Студент өшірілді", "success")
    conn.close()
    return RedirectResponse("/admin", status_code=303)


# ================ 5-ЭТАП: ПРОФИЛЬ ЖӘНЕ БАПТАУЛАР ================

@app.get("/profile", name="profile", dependencies=[Depends(login_required)])
def profile_page(request: Request, tab: str = "profile"):
    if tab not in ("profile", "settings"):
        tab = "profile"

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (request.session["user_id"],)
    ).fetchone()
    if user is None:
        conn.close()
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    my = conn.execute(
        "SELECT COUNT(*) AS cnt, ROUND(AVG(percent), 1) AS avg, "
        "MAX(percent) AS best FROM results WHERE user_id = ?",
        (user["id"],),
    ).fetchone()

    recent = conn.execute("""
        SELECT r.*, t.title
        FROM results r
        JOIN tests t ON t.id = r.test_id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
        LIMIT 5
    """, (user["id"],)).fetchall()

    admin_stats = None
    if user["role"] == "admin":
        admin_stats = {
            "students": conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'student'"
            ).fetchone()[0],
            "tests": conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0],
            "results": conn.execute(
                "SELECT COUNT(*) FROM results").fetchone()[0],
        }
    conn.close()

    return render(request, "profile.html", user=user, my=my, recent=recent,
                  admin_stats=admin_stats, tab=tab)


@app.post("/profile/name", name="profile_name",
          dependencies=[Depends(login_required)])
def profile_name(request: Request, full_name: str = Form("")):
    name = full_name.strip()
    if len(name) < 2:
        flash(request, "Аты-жөні кемінде 2 таңба болсын", "error")
    else:
        conn = get_db()
        conn.execute("UPDATE users SET full_name = ? WHERE id = ?",
                     (name, request.session["user_id"]))
        conn.commit()
        conn.close()
        request.session["full_name"] = name
        flash(request, "Аты-жөні жаңартылды", "success")
    return RedirectResponse("/profile?tab=settings", status_code=303)


@app.post("/profile/email", name="profile_email",
          dependencies=[Depends(login_required)])
def profile_email(request: Request,
                  email: str = Form(""),
                  password: str = Form("")):
    email = email.strip().lower()

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?",
                        (request.session["user_id"],)).fetchone()

    if "@" not in email or "." not in email:
        flash(request, "Email дұрыс емес", "error")
    elif not check_password_hash(user["password_hash"], password):
        flash(request, "Құпиясөз қате", "error")
    else:
        try:
            conn.execute("UPDATE users SET email = ? WHERE id = ?",
                         (email, user["id"]))
            conn.commit()
            flash(request, "Email жаңартылды", "success")
        except sqlite3.IntegrityError:
            flash(request, "Бұл email басқа қолданушыда бар", "error")
    conn.close()
    return RedirectResponse("/profile?tab=settings", status_code=303)


@app.post("/profile/password", name="profile_password",
          dependencies=[Depends(login_required)])
def profile_password(request: Request,
                     old_password: str = Form(""),
                     new_password: str = Form(""),
                     confirm: str = Form("")):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?",
                        (request.session["user_id"],)).fetchone()

    if not check_password_hash(user["password_hash"], old_password):
        flash(request, "Ескі құпиясөз қате", "error")
    elif len(new_password) < 6:
        flash(request, "Жаңа құпиясөз кемінде 6 таңба болсын", "error")
    elif new_password != confirm:
        flash(request, "Жаңа құпиясөздер сәйкес емес", "error")
    else:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (generate_password_hash(new_password), user["id"]))
        conn.commit()
        flash(request, "Құпиясөз өзгертілді", "success")
    conn.close()
    return RedirectResponse("/profile?tab=settings", status_code=303)


@app.post("/profile/delete", name="profile_delete",
          dependencies=[Depends(login_required)])
def profile_delete(request: Request, password: str = Form("")):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?",
                        (request.session["user_id"],)).fetchone()

    if user["role"] == "admin":
        conn.close()
        flash(request, "Админ аккаунтын өшіруге болмайды", "error")
        return RedirectResponse("/profile?tab=settings", status_code=303)

    if not check_password_hash(user["password_hash"], password):
        conn.close()
        flash(request, "Құпиясөз қате, аккаунт өшірілмеді", "error")
        return RedirectResponse("/profile?tab=settings", status_code=303)

    conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    conn.commit()
    conn.close()
    request.session.clear()
    flash(request, "Аккаунтыңыз өшірілді", "success")
    return RedirectResponse("/", status_code=303)
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_TEXTS = {
    403: ("Рұқсат жоқ", "Бұл бетке кіруге құқығыңыз жоқ."),
    404: ("Бет табылмады", "Іздеген бетіңіз жоқ немесе өшірілген."),
}


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    title, text = ERROR_TEXTS.get(
        exc.status_code, ("Қате пайда болды", "Бірдеңе дұрыс болмады.")
    )
    response = render(request, "error.html",
                      code=exc.status_code, title=title, text=text)
    response.status_code = exc.status_code
    return response
# ===================== РЕЙТИНГ =====================

@app.get("/rating", name="rating", dependencies=[Depends(login_required)])
def rating_page(request: Request):
    conn = get_db()
    rows = conn.execute("""
        SELECT u.id, u.full_name,
               COUNT(r.id) AS cnt,
               ROUND(AVG(r.percent), 1) AS avg,
               MAX(r.percent) AS best
        FROM users u
        JOIN results r ON r.user_id = u.id
        WHERE u.role = 'student'
        GROUP BY u.id
        ORDER BY avg DESC, cnt DESC, u.full_name
        LIMIT 50
    """).fetchall()
    conn.close()

    ranking = []
    for i, r in enumerate(rows, start=1):
        item = dict(r)
        item["place"] = i
        ranking.append(item)

    my_id = request.session["user_id"]
    my_place = next((x for x in ranking if x["id"] == my_id), None)

    return render(request, "rating.html", ranking=ranking, my_place=my_place)
# ===================== ӨЗ ТЕСТІМДІ ЖАСАУ =====================

def get_owned_test(conn, test_id: int, request: Request):
    """Тест осы қолданушыныкі (немесе админ) екенін тексереді."""
    test = conn.execute(
        "SELECT * FROM tests WHERE id = ?", (test_id,)
    ).fetchone()
    if test is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Тест табылмады")
    is_admin = request.session.get("role") == "admin"
    if test["created_by"] != request.session["user_id"] and not is_admin:
        conn.close()
        raise HTTPException(status_code=403, detail="Рұқсат жоқ")
    return test


@app.get("/my-tests", name="my_tests", dependencies=[Depends(login_required)])
def my_tests_page(request: Request, open_id: int = 0):
    conn = get_db()
    tests = conn.execute("""
        SELECT t.*, COUNT(q.id) AS q_count
        FROM tests t
        LEFT JOIN questions q ON q.test_id = t.id
        WHERE t.created_by = ?
        GROUP BY t.id
        ORDER BY t.id DESC
    """, (request.session["user_id"],)).fetchall()

    questions_by_test = {}
    ids = [t["id"] for t in tests]
    if ids:
        marks = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM questions WHERE test_id IN ({marks}) ORDER BY id",
            ids,
        ).fetchall()
        for q in rows:
            questions_by_test.setdefault(q["test_id"], []).append(q)
    conn.close()

    return render(request, "my_tests.html", tests=tests,
                  questions_by_test=questions_by_test, open_id=open_id)


@app.post("/my-tests/add", name="my_test_add",
          dependencies=[Depends(login_required)])
def my_test_add(request: Request,
                title: str = Form(""),
                description: str = Form(""),
                max_score: str = Form("100"),
                duration: str = Form("15")):
    title = title.strip()[:100]
    description = description.strip()[:300]
    try:
        ms = int(max_score)
        du = int(duration)
    except ValueError:
        flash(request, "Балл және уақыт сан болуы керек", "error")
        return RedirectResponse("/my-tests", status_code=303)

    if not title or not (1 <= ms <= 1000) or not (1 <= du <= 180):
        flash(request, "Деректерді дұрыс толтырыңыз", "error")
        return RedirectResponse("/my-tests", status_code=303)

    uid = request.session["user_id"]
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM tests WHERE created_by = ?", (uid,)
    ).fetchone()[0]
    if count >= 20 and request.session.get("role") != "admin":
        conn.close()
        flash(request, "Тест саны шегіне жеттіңіз (20)", "error")
        return RedirectResponse("/my-tests", status_code=303)

    cur = conn.execute(
        "INSERT INTO tests (title, description, max_score, duration_minutes, created_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (title, description, ms, du, uid),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    flash(request, "Тест жасалды. Енді оған сұрақ қосыңыз", "success")
    return RedirectResponse(f"/my-tests?open_id={new_id}", status_code=303)


@app.post("/my-tests/{test_id}/delete", name="my_test_delete",
          dependencies=[Depends(login_required)])
def my_test_delete(request: Request, test_id: int):
    conn = get_db()
    get_owned_test(conn, test_id, request)
    conn.execute("DELETE FROM tests WHERE id = ?", (test_id,))
    conn.commit()
    conn.close()
    flash(request, "Тест өшірілді", "success")
    return RedirectResponse("/my-tests", status_code=303)


@app.post("/my-tests/{test_id}/question/add", name="my_question_add",
          dependencies=[Depends(login_required)])
def my_question_add(request: Request, test_id: int,
                    question_text: str = Form(""),
                    option_a: str = Form(""),
                    option_b: str = Form(""),
                    option_c: str = Form(""),
                    option_d: str = Form(""),
                    correct_option: str = Form("")):
    fields = [x.strip()[:300] for x in
              (question_text, option_a, option_b, option_c, option_d)]
    back = f"/my-tests?open_id={test_id}"

    conn = get_db()
    get_owned_test(conn, test_id, request)

    if not all(fields) or correct_option not in ("A", "B", "C", "D"):
        conn.close()
        flash(request, "Сұрақ пен 4 жауапты толық толтырыңыз", "error")
        return RedirectResponse(back, status_code=303)

    count = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE test_id = ?", (test_id,)
    ).fetchone()[0]
    if count >= 50:
        conn.close()
        flash(request, "Бір тестте ең көбі 50 сұрақ болады", "error")
        return RedirectResponse(back, status_code=303)

    conn.execute(
        """INSERT INTO questions
           (test_id, question_text, option_a, option_b, option_c, option_d, correct_option)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (test_id, *fields, correct_option),
    )
    conn.commit()
    conn.close()
    flash(request, "Сұрақ қосылды", "success")
    return RedirectResponse(back, status_code=303)


@app.post("/my-tests/question/{question_id}/delete",
          name="my_question_delete", dependencies=[Depends(login_required)])
def my_question_delete(request: Request, question_id: int):
    conn = get_db()
    q = conn.execute(
        "SELECT test_id FROM questions WHERE id = ?", (question_id,)
    ).fetchone()
    if q is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Сұрақ табылмады")

    get_owned_test(conn, q["test_id"], request)
    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()
    flash(request, "Сұрақ өшірілді", "success")
    return RedirectResponse(f"/my-tests?open_id={q['test_id']}", status_code=303)
# ===================== ТІЛ АУЫСТЫРУ =====================

@app.get("/lang/{code}", name="set_lang")
def set_lang(request: Request, code: str):
    if code in ("kz", "ru"):
        request.session["lang"] = code

    ref = urlparse(request.headers.get("referer", ""))
    back = "/"
    if ref.netloc == request.url.netloc and ref.path:
        back = ref.path + (("?" + ref.query) if ref.query else "")
    return RedirectResponse(back, status_code=303)
# ===================== 2-ЭТАП: API АУТЕНТИФИКАЦИЯСЫ =====================

app.include_router(auth_router)
# ===================== 3-ЭТАП: КАТАЛОГ ЖӘНЕ ӘКІМШІ API =====================

app.include_router(catalog_router)
app.include_router(admin_router)
# ===================== 4-ЭТАП: СЕБЕТ ЖӘНЕ ТАПСЫРЫС =====================

app.include_router(cart_router)
app.include_router(orders_router)