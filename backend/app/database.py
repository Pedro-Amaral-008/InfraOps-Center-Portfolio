import asyncio
from functools import wraps

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Limite de concorrencia pra consultas pesadas de agregacao historica
# (unifi_consumo_amostras e acesso_dominio sao tabelas grandes no HD externo,
# que e lento; rodar muitas agregacoes pesadas ao mesmo tempo satura o disco
# e trava o sistema inteiro). So 2 rodam por vez, as demais esperam na fila
# em vez de brigar pelo disco em paralelo.
semaforo_consulta_pesada = asyncio.Semaphore(2)


def limitar_concorrencia_pesada(func):
    """Decorador: serializa (max 2 simultaneas) chamadas a agregacoes pesadas
    de banco, pra nao saturar o disco quando varios widgets do painel pedem
    consultas historicas grandes ao mesmo tempo."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with semaforo_consulta_pesada:
            return await func(*args, **kwargs)
    return wrapper
