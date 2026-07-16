from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditLog


async def registrar_log(
    db: AsyncSession,
    username: str,
    acao: str,
    resultado: str,
    detalhes: str | None = None,
    ip_origem: str | None = None,
):
    log = AuditLog(
        username=username,
        acao=acao,
        resultado=resultado,
        detalhes=detalhes,
        ip_origem=ip_origem,
    )
    db.add(log)
    await db.commit()
