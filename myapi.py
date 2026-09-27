from fastapi import FastAPI,Depends,HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from schemas import User_create , User_out
from security import hash_password

app=FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
   )
from fastapi.staticfiles import StaticFiles
import os
os.makedirs("uploads", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


def get_db():
    db =SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/signup",response_model=User_out)
def sign_up(user: User_create,db: Session=Depends(get_db)):
    existing =db.query(User).filter(User.username==user.username).first()
    if existing:
        raise HTTPException(status_code=400,detail="username already talken")
    new_user=User(
        username=user.username,
        email=user.email,
        hashpassword=hash_password(user.password),

    )



    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
from fastapi.security import OAuth2PasswordRequestForm
from security import verify_password, create_access_token

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashpassword):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

from security import decode_token

@app.get("/me")
def read_current_user(current_user: str = Depends(decode_token)):
    return {"username": current_user}

import os
import shutil
import uuid
from fastapi import UploadFile, File, Form
from models import Post
from schemas import PostOut

UPLOAD_DIR = "uploads"

@app.post("/upload", response_model=PostOut)
def upload_post(
    file: UploadFile = File(...),
    caption: str = Form(None),
    current_user: str = Depends(decode_token),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == current_user).first()

    file_ext = file.filename.split(".")[-1]
    unique_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    media_type = "video" if file.content_type.startswith("video") else "image"

    new_post = Post(
        file_path=file_path,
        media_type=media_type,
        caption=caption,
        owner_id=user.id,
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post

from typing import List

@app.get("/posts", response_model=List[PostOut])
def get_all_posts(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return (
        db.query(Post)
        .order_by(Post.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

@app.get("/posts/me", response_model=List[PostOut])
def get_my_posts(
    current_user: str = Depends(decode_token),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == current_user).first()
    return db.query(Post).filter(Post.owner_id == user.id).order_by(Post.created_at.desc()).all()


@app.get("/posts/user/{username}", response_model=List[PostOut])
def get_posts_by_user(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return db.query(Post).filter(Post.owner_id == user.id).order_by(Post.created_at.desc()).all()
@app.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    current_user: str = Depends(decode_token),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user = db.query(User).filter(User.username == current_user).first()

    if post.owner_id != user.id:
        raise HTTPException(status_code=403, detail="You don't own this post")

    if os.path.exists(post.file_path):
        os.remove(post.file_path)

    db.delete(post)
    db.commit()

    return {"detail": "Post deleted successfully"}
