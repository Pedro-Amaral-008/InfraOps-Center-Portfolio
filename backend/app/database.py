import asyncio
from functools import wraps

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# statement_timeout: nenhuma query pode segurar uma conexao do pool por mais
# de 10s. Se estourar, o Postgres mata a query e devolve erro (que o endpoint
# trata como falha), mas a conexao volta pro pool na hora — evita que uma
# consulta pesada no HD externo lento derrube o resto do painel junto.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_size=25,
    max_overflow=25,
    pool_timeout=30,
    pool_recycle=1800,
    connect_args={"server_settings": {"statement_timeout": "10000"}},
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
# e trava o sistema inteiro). Com os indices e cache adicionados, 4 rodam por
# vez agora, as demais esperam na fila em vez de brigar pelo disco em paralelo.
semaforo_consulta_pesada = asyncio.Semaphore(16)

# Semaforo separado e exclusivo pra sincronizacao em segundo plano (Suricata).
# Antes competia pela mesma vaga que as telas que o usuario esta vendo, o que
# podia deixar o painel esperando na fila atras de uma tarefa de fundo sem o
# usuario nem saber. Uma tarefa de sync por vez, nunca disputa com o painel.
semaforo_sync_fundo = asyncio.Semaphore(1)


def limitar_concorrencia_pesada(func):
    """Decorador: serializa (max 4 simultaneas) chamadas a agregacoes pesadas
    de banco vindas do painel, pra nao saturar o disco quando varios widgets
    pedem consultas historicas grandes ao mesmo tempo."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with semaforo_consulta_pesada:
            return await func(*args, **kwargs)
    return wrapper


def limitar_concorrencia_sync(func):
    """Decorador exclusivo pra tarefas de sincronizacao em segundo plano
    (ex: Suricata). Usa um semaforo proprio pra nunca competir com as
    consultas que o usuario esta esperando na tela."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with semaforo_sync_fundo:
            return await func(*args, **kwargs)
    return wrapper
