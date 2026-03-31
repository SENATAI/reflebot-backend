import granian
from .bootstrap import create_app

app = create_app()

if __name__ == "__main__":
    granian.Granian(
        "auth_app.main:app",  # путь к приложению в формате module:variable
        host="0.0.0.0",
        port=8080,
        reload=True,
        interface="asgi"  # или "wsgi", если вы используете WSGI
    ).serve()