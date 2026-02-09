from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from datetime import datetime
import smtplib
from email.message import EmailMessage


def get_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "karaoke.db"


def q_one(conn: sqlite3.Connection, sql: str, params=()):
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else 0


def q_all(conn: sqlite3.Connection, sql: str, params=()):
    cur = conn.execute(sql, params)
    return cur.fetchall()


def build_report(conn: sqlite3.Connection):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    total_favs = q_one(conn, "SELECT COUNT(*) FROM favorites")
    users = q_one(conn, "SELECT COUNT(DISTINCT user_id) FROM favorites")

    top = q_all(
        conn,
        """
        SELECT code, COUNT(*) as c
        FROM favorites
        GROUP BY code
        ORDER BY c DESC
        LIMIT 30
        """
    )

    lines = []
    for code, c in top:
        lines.append(f"<tr><td>{code}</td><td style='text-align:right'>{c}</td></tr>")

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color:#111;">
        <h2>Relatório de Favoritos — Karaokê RJ</h2>
        <p><b>Gerado em:</b> {now}</p>

        <ul>
          <li><b>Total de favoritos:</b> {total_favs}</li>
          <li><b>Usuários distintos:</b> {users}</li>
        </ul>

        <h3>Top 30 (Geral)</h3>
        <table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;">
          <thead>
            <tr><th>Código</th><th>Qtd</th></tr>
          </thead>
          <tbody>
            {''.join(lines) if lines else '<tr><td colspan="2">Sem dados</td></tr>'}
          </tbody>
        </table>
      </body>
    </html>
    """.strip()

    subject = f"Relatório de Favoritos — Karaokê RJ — {datetime.now().strftime('%Y-%m-%d')}"
    return subject, html


def send_email_gmail(subject: str, html_body: str):
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    report_to = os.getenv("REPORT_TO", "").strip()

    if not gmail_user or not gmail_app_password or not report_to:
        raise RuntimeError(
            "Defina as variáveis de ambiente: GMAIL_USER, GMAIL_APP_PASSWORD, REPORT_TO"
        )

    msg = EmailMessage()
    msg["From"] = gmail_user
    msg["To"] = report_to
    msg["Subject"] = subject
    msg.set_content("Seu cliente de e-mail não suporta HTML.")
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(gmail_user, gmail_app_password)
        smtp.send_message(msg)


def main():
    db_path = get_db_path()

    conn = sqlite3.connect(str(db_path))
    try:
        subject, html = build_report(conn)
    finally:
        conn.close()

    send_email_gmail(subject, html)
    print("OK: relatório enviado.")


if __name__ == "__main__":
    main()
