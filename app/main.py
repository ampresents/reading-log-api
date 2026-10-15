from fastapi import FastAPI

from app.errors import register_error_handlers
from app.routers import books, notes

app = FastAPI(title="Reading Log API")

register_error_handlers(app)
app.include_router(books.router)
app.include_router(notes.router)
