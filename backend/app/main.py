
from fastapi import FastAPI

app = FastAPI()

@app.get("/tt/{q}")
def tt(q: int): 
    return(q) 