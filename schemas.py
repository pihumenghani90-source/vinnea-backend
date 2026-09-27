from pydantic import BaseModel
from typing import Optional
class User_create(BaseModel):
    username:str
    email:str
    password:str

class User_out(BaseModel):
    id:int
    username:str
    email:str

class config:
    from_attributes=True
#the "delivery form" for what a post looks like when sent back to the client:
class PostOut(BaseModel):
    id: int
    file_path: str
    media_type: str
    ccaption: Optional[str] = None 
    owner_id: int

    class Config:
        from_attributes = True

    