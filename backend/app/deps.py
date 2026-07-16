from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.auth import decodificar_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais invalidas ou expiradas",
    )

    payload = decodificar_token(token)
    if payload is None:
        raise credenciais_invalidas

    username = payload.get("sub")
    if username is None:
        raise credenciais_invalidas

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not user.ativo:
        raise credenciais_invalidas

    return user


def exigir_papel(*papeis_permitidos: str):
    async def verificador(usuario: User = Depends(get_current_user)) -> User:
        if usuario.role not in papeis_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voce nao tem permissao para executar esta acao",
            )
        return usuario
    return verificador
