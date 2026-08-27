import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


def _enviar_email(destinatario: str, assunto: str, corpo_html: str):
    if not settings.smtp_user or not settings.smtp_password:
        print(f"SMTP nao configurado, e-mail nao enviado para {destinatario}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = settings.smtp_from
        msg["To"] = destinatario
        msg.attach(MIMEText(corpo_html, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as servidor:
            servidor.starttls()
            servidor.login(settings.smtp_user, settings.smtp_password)
            servidor.sendmail(settings.smtp_from, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail para {destinatario}: {e}")
        return False


def enviar_email_confirmacao_solicitacao(destinatario: str, nome: str):
    corpo = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
        <h2 style="color: #1f1f1f;">E-Ops — Solicitação recebida</h2>
        <p>Olá, {nome}!</p>
        <p>Sua solicitação de acesso ao E-Ops foi recebida e está aguardando aprovação de um administrador.</p>
        <p>Você receberá um e-mail assim que sua conta for aprovada.</p>
    </div>
    """
    return _enviar_email(destinatario, "E-Ops — Solicitação de acesso recebida", corpo)


def enviar_email_acesso_aprovado(destinatario: str, nome: str, username: str):
    corpo = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
        <h2 style="color: #1f1f1f;">E-Ops — Acesso aprovado</h2>
        <p>Olá, {nome}!</p>
        <p>Sua solicitação de acesso ao E-Ops foi aprovada. Você já pode fazer login com o usuário
        <strong>{username}</strong> e a senha que você cadastrou.</p>
        <p><a href="{settings.frontend_url}" style="color: #2563EB;">Acessar o E-Ops</a></p>
    </div>
    """
    return _enviar_email(destinatario, "E-Ops — Seu acesso foi aprovado", corpo)


def enviar_email_recuperacao_senha(destinatario: str, nome: str, token: str):
    link = f"{settings.frontend_url}/redefinir-senha?token={token}"
    corpo = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
        <h2 style="color: #1f1f1f;">E-Ops — Redefinição de senha</h2>
        <p>Olá, {nome}!</p>
        <p>Recebemos uma solicitação para redefinir sua senha. Se foi você, clique no link abaixo:</p>
        <p><a href="{link}" style="color: #2563EB;">Redefinir minha senha</a></p>
        <p style="color: #6b6b70; font-size: 13px;">Este link expira em 1 hora. Se você não solicitou isso, ignore este e-mail.</p>
    </div>
    """
    return _enviar_email(destinatario, "E-Ops — Redefinição de senha", corpo)
