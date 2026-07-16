import asyncio
from app.database import engine, Base, AsyncSessionLocal
from app.models import User
from app.auth import hash_senha

usuarios = [
    {"username": "pedro", "nome_completo": "Pedro", "senha": "TROCAR_SENHA_1", "role": "super_admin"},
    {"username": "andre", "nome_completo": "Andre", "senha": "TROCAR_SENHA_2", "role": "admin"},
    {"username": "eduardo", "nome_completo": "Eduardo", "senha": "TROCAR_SENHA_3", "role": "admin"},
    {"username": "daniel", "nome_completo": "Daniel", "senha": "TROCAR_SENHA_4", "role": "operador"},
    {"username": "joao", "nome_completo": "Joao", "senha": "TROCAR_SENHA_5", "role": "operador"},
]


async def criar_tabelas_e_usuarios():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for u in usuarios:
            novo_usuario = User(
                username=u["username"],
                nome_completo=u["nome_completo"],
                password_hash=hash_senha(u["senha"]),
                role=u["role"],
                deve_trocar_senha=True,
            )
            session.add(novo_usuario)
        await session.commit()

    print("Tabelas criadas e usuarios inseridos com sucesso.")
    print("")
    print("SENHAS TEMPORARIAS (repassar com seguranca, cada usuario deve trocar no 1o login):")
    for u in usuarios:
        print(f"  {u['username']:10s} -> {u['senha']}")


if __name__ == "__main__":
    asyncio.run(criar_tabelas_e_usuarios())
