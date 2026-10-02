import os, time, json, hmac, hashlib, base64, sqlite3, uuid, secrets, shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

SECRET = os.getenv("SECRET_KEY", "change-this-secret")
DB_FILE = "vinnea.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

# lets the browser frontend talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
oauth2 = OAuth2PasswordBearer(tokenUrl="login")


# ---------- database ----------
def db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


with db() as con:
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE, email TEXT UNIQUE, password TEXT);
    CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, caption TEXT, filename TEXT,
        media_type TEXT, created_at REAL);
    """)


# ---------- passwords + tokens ----------
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${h}"


def check_pw(pw, stored):
    salt, h = stored.split("$")
    return hmac.compare_digest(hash_pw(pw, salt).split("$")[1], h)


def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(text):
    return b64(hmac.new(SECRET.encode(), text.encode(), hashlib.sha256).digest())


def make_token(username):
    head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps({"sub": username, "exp": int(time.time()) + 7 * 86400}).encode())
    return f"{head}.{body}.{sign(head + '.' + body)}"


def read_token(token):
    try:
        head, body, sig = token.split(".")
        if not hmac.compare_digest(sig, sign(head + "." + body)):
            return None
        data = json.loads(unb64(body))
        return data["sub"] if data["exp"] > time.time() else None
    except Exception:
        return None


def current_user(token: str = Depends(oauth2)):
    username = read_token(token)
    if not username:
        raise HTTPException(401, "Invalid or expired token")
    row = db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        raise HTTPException(401, "User not found")
    return row


# ---------- schemas ----------
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


def post_out(r):
    return {
        "id": r["id"],
        "caption": r["caption"],
        "url": "/uploads/" + r["filename"],
        "media_type": r["media_type"],
        "username": r["username"],
        "created_at": r["created_at"],
    }


POST_SELECT = "SELECT p.*, u.username FROM posts p JOIN users u ON u.id = p.user_id"


# ---------- auth routes ----------
@app.post("/signup")
def sign_up(user: UserCreate):
    if len(user.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    try:
        with db() as con:
            cur = con.execute(
                "INSERT INTO users(username,email,password) VALUES(?,?,?)",
                (user.username.strip(), user.email.strip(), hash_pw(user.password)),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Username or email already taken")
    return {"id": cur.lastrowid, "username": user.username, "email": user.email}


@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    row = db().execute("SELECT * FROM users WHERE username=?", (form.username,)).fetchone()
    if not row or not check_pw(form.password, row["password"]):
        raise HTTPException(401, "Wrong username or password")
    return {"access_token": make_token(row["username"]), "token_type": "bearer"}


@app.get("/me")
def read_current_user(user=Depends(current_user)):
    return {"id": user["id"], "username": user["username"], "email": user["email"]}


# ---------- post routes ----------
@app.post("/upload")
def upload_post(
    file: UploadFile = File(...),
    caption: str = Form(""),
    user=Depends(current_user),
):
    ctype = file.content_type or ""
    if not (ctype.startswith("image/") or ctype.startswith("video/")):
        raise HTTPException(400, "Only images and videos are allowed")
    ext = os.path.splitext(file.filename or "")[1].lower()
    name = uuid.uuid4().hex + ext
    with open(os.path.join(UPLOAD_DIR, name), "wb") as out:
        shutil.copyfileobj(file.file, out)
    with db() as con:
        cur = con.execute(
            "INSERT INTO posts(user_id,caption,filename,media_type,created_at) VALUES(?,?,?,?,?)",
            (user["id"], caption, name, ctype, time.time()),
        )
    row = db().execute(POST_SELECT + " WHERE p.id=?", (cur.lastrowid,)).fetchone()
    return post_out(row)


@app.get("/posts")
def get_all_posts(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    rows = db().execute(POST_SELECT + " ORDER BY p.id DESC LIMIT ? OFFSET ?", (limit, skip)).fetchall()
    return [post_out(r) for r in rows]


@app.get("/posts/me")
def get_my_posts(user=Depends(current_user), skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    rows = db().execute(
        POST_SELECT + " WHERE p.user_id=? ORDER BY p.id DESC LIMIT ? OFFSET ?",
        (user["id"], limit, skip),
    ).fetchall()
    return [post_out(r) for r in rows]


@app.get("/posts/user/{username}")
def get_posts_by_user(username: str, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    rows = db().execute(
        POST_SELECT + " WHERE u.username=? ORDER BY p.id DESC LIMIT ? OFFSET ?",
        (username, limit, skip),
    ).fetchall()
    return [post_out(r) for r in rows]


@app.delete("/posts/{post_id}")
def delete_post(post_id: int, user=Depends(current_user)):
    row = db().execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Post not found")
    if row["user_id"] != user["id"]:
        raise HTTPException(403, "You can only delete your own posts")
    with db() as con:
        con.execute("DELETE FROM posts WHERE id=?", (post_id,))
    path = os.path.join(UPLOAD_DIR, row["filename"])
    if os.path.exists(path):
        os.remove(path)
    return {"deleted": post_id}
