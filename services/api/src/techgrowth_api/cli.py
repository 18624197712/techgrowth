import getpass

import typer
from argon2 import PasswordHasher
from sqlalchemy import select

from .config import get_settings
from .db import Database
from .models import User
from .services.auth import AuthService

app = typer.Typer(help="TechGrowth administration commands", no_args_is_help=True)


def services() -> tuple[Database, AuthService]:
    settings = get_settings()
    database = Database(settings.database_url)
    database.create_all()
    return database, AuthService(database.session_factory, settings)


@app.command("create-admin")
def create_admin(email: str = typer.Option(..., prompt=True)) -> None:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise typer.BadParameter("Passwords do not match")
    _, auth = services()
    auth.create_admin(email, password)
    typer.echo("Administrator created. Sign in to enroll TOTP.")


@app.command("reset-password")
def reset_password(email: str = typer.Option(..., prompt=True)) -> None:
    password = getpass.getpass("New password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation or len(password) < 12:
        raise typer.BadParameter("Passwords must match and contain at least 12 characters")
    database, _ = services()
    with database.session_factory() as db:
        user = db.scalar(select(User).where(User.email == email.casefold().strip()))
        if not user:
            raise typer.BadParameter("Administrator not found")
        user.password_hash = PasswordHasher().hash(password)
        db.commit()
    typer.echo("Password updated.")


if __name__ == "__main__":
    app()
