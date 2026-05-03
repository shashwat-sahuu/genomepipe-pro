"""Test handler for Vercel"""
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def test():
    return {"message": "test ok", "source": "test handler"}

# Vercel expects 'application'
application = app
