import logging
import textwrap
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from aiosmtplib import SMTP

from .exceptions import SendEmailError


@dataclass
class SMTPClient:
    """
    Клиент SMTP для отправки e-mail.

    :param host: Хост SMTP-сервера
    :type host: str
    :param port: Порт SMTP-сервера
    :type port: int
    :param username: Имя пользователя
    :type username: str
    :param password: Пароль пользователя
    :type password: str
    :param ssl: Использовать SSL
    :type ssl: bool, optional
    """
    host: str
    port: str
    username: str
    password: str
    ssl: bool = True

    async def send_email(
            self,
            recipient: str,
            subject: str,
            message: str,
            sender: str
    ) -> None:
        """
        Отправляет e-mail.

        :param recipient: E-mail получателя
        :type recipient: str
        :param subject: Тема e-mail
        :type subject: str
        :param message: Текст e-mail
        :type message: str
        :param sender: E-mail отправителя
        :type sender: str

        :raises SendEmailError: Ошибка при отправке e-mail
        """
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        try:
            async with SMTP(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    use_tls=self.ssl
            ) as smtp:
                return await smtp.send_message(msg)
        except Exception as e:
            logging.error(f'failed to send e-mail to {recipient} {e}')
            raise SendEmailError(f'SendEmailError: {e}')

    async def send_html_email(
            self,
            recipient: str,
            subject: str,
            message: str,
            sender: str,
    ) -> None:
        """
        Отправляет HTML-письмо.
        `message` должен быть валидным HTML-фрагментом.
        """
        html_body = f"""\
        <html>
          <head>
            <meta charset="utf-8">
            <style>
              body   {{ font-family: monospace; font-size: 14px; }}
              pre    {{ background:#f4f4f4; padding:8px; border-left:3px solid #ccc; }}
              code   {{ background:#f4f4f4; padding:2px 4px; border-radius:3px; }}
              b      {{ color:#d32f2f; }}
            </style>
          </head>
          <body>
            {message.replace(chr(10), '<br>')}
          </body>
        </html>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient

        # plain-text fallback (без тегов)
        plain = (
            message.replace('<b>', '')
            .replace('</b>', '')
            .replace('<code>', '')
            .replace('</code>', '')
            .replace('<pre>', '\n')
            .replace('</pre>', '\n')
        )
        msg.attach(MIMEText(plain, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        try:
            async with SMTP(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    use_tls=self.ssl,
            ) as smtp:
                return await smtp.send_message(msg)
        except Exception as e:
            logging.error('failed to send e-mail to %s: %s', recipient, e)
            raise SendEmailError(f'SendEmailError: {e}')
