"""Send daily job report by email (HTML-formatted)."""
from __future__ import annotations

import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.log import get_logger
from src.retry import retry

log = get_logger(__name__)


def _md_to_html(md: str) -> str:
    """Lightweight markdown-to-HTML for the report email."""
    lines = md.split("\n")
    html_parts: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_table:
                html_parts.append("</table>")
                in_table = False
            html_parts.append("<br>")
            continue

        if stripped.startswith("### "):
            html_parts.append(f'<h3 style="margin:12px 0 4px;color:#1a1a1a">{_inline(stripped[4:])}</h3>')
            continue
        if stripped.startswith("## "):
            html_parts.append(f'<h2 style="margin:18px 0 6px;color:#2c3e50;border-bottom:1px solid #ddd;padding-bottom:4px">{_inline(stripped[3:])}</h2>')
            continue
        if stripped.startswith("# "):
            html_parts.append(f'<h1 style="margin:0 0 8px;color:#2c3e50">{_inline(stripped[2:])}</h1>')
            continue

        if stripped == "---":
            html_parts.append('<hr style="border:none;border-top:1px solid #e0e0e0;margin:16px 0">')
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if all(set(c) <= {"-", " ", ":"} for c in cells):
                continue
            if not in_table:
                html_parts.append('<table style="border-collapse:collapse;width:100%;font-size:13px;margin:8px 0">')
                html_parts.append("<tr>" + "".join(
                    f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f7fa;text-align:left;white-space:nowrap">{_inline(c)}</th>' for c in cells
                ) + "</tr>")
                in_table = True
                continue
            color = "#fff"
            if any(c.strip() == "Applied" for c in cells):
                color = "#e8f5e9"
            html_parts.append("<tr>" + "".join(
                f'<td style="border:1px solid #ddd;padding:5px 8px;background:{color}">{_inline(c)}</td>' for c in cells
            ) + "</tr>")
            continue

        if stripped.startswith("- "):
            html_parts.append(f'<div style="margin:2px 0 2px 16px">\u2022 {_inline(stripped[2:])}</div>')
            continue

        if stripped.startswith("```"):
            continue

        html_parts.append(f"<p style='margin:4px 0'>{_inline(stripped)}</p>")

    if in_table:
        html_parts.append("</table>")

    return "\n".join(html_parts)


def _inline(text: str) -> str:
    """Convert inline markdown (bold, italic, links, code) to HTML."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    text = re.sub(
        r'`(.+?)`',
        r'<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;font-size:12px">\1</code>',
        text,
    )
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#1a73e8">\1</a>', text)
    return text


@retry(max_attempts=3, base_delay=3.0, retryable=(smtplib.SMTPException, OSError))
def _smtp_send(
    host: str, port: int, user: str, password: str,
    from_addr: str, to_addr: str, msg: MIMEMultipart,
) -> None:
    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())


def send_report_email(
    body: str,
    subject: str | None = None,
    to_email: str | None = None,
) -> tuple[bool, str]:
    host = os.environ.get("SMTP_HOST", "").strip()
    port_str = os.environ.get("SMTP_PORT", "587").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get("FROM_EMAIL", user).strip()
    to_addr = (to_email or os.environ.get("TO_EMAIL", "")).strip()

    if not all([host, user, password, to_addr]):
        return False, "SMTP not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, TO_EMAIL in .env)"

    try:
        port = int(port_str)
    except ValueError:
        port = 587

    if not subject:
        subject = f"Daily Job Report \u2013 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    html_body = f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:900px;margin:0 auto;padding:16px;color:#333">
{_md_to_html(body)}
<hr style="border:none;border-top:1px solid #e0e0e0;margin:20px 0 8px">
<p style="font-size:11px;color:#999">Sent by your Autonomous Job Search Agent</p>
</div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        _smtp_send(host, port, user, password, from_addr, to_addr, msg)
        log.info("Email sent to %s", to_addr)
        return True, "Email sent"
    except Exception as e:
        log.error("Email failed: %s", e)
        return False, str(e)[:150]
