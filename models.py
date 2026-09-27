from sqlalchemy import String,Integer,Column,ForeignKey,DateTime
from sqlalchemy.orm import relationship , declarative_base
from datetime import datetime
Base=declarative_base()
#user model
class User(Base):
    __tablename__="Users"
    id=Column(Integer,primary_key=True,index=True)
    username=Column(String,unique=True,index=True)
    email=Column(String,unique=True,index=True)
    hashpassword=Column(String)
    post=relationship("Post",back_populates="owner")
#post model
class Post(Base):
    __tablename__="Posts"
    id=Column(Integer,primary_key=True,index=True)
    file_path=Column(String)
    media_type=Column(String) #photos and videos
    caption=Column(String,nullable=True)
    created_at=Column(DateTime,default=datetime.utcnow)
    owner_id=Column(Integer,ForeignKey("Users.id"))
    owner= relationship("User",back_populates="post")

