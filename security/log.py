from __future__ import unicode_literals

from logging import Handler

from six.moves.urllib.parse import urlparse


class OutputRequestLogHandler(Handler):

    def emit(self, record):
        from security.models import OutputLoggedRequest

        OutputLoggedRequest(status=self.levelno)
        if hasattr(record, 'requests_resp'):
            resp = record.requests_resp
            status_code = resp.status_code
            parsed_url = urlparse(resp.url)
            is_secure = parsed_url.scheme == 'https'
            host = parsed_url.netloc
            path = parsed_url.path
            
        from django.conf import settings
        from django.utils.encoding import force_text

        email_template = self._get_email_template(record)
        context_data = getattr(record, 'context_data', {})
        record.msg = force_text(record.msg)
        context_data['message'] = self.format(record)
        for recipient in self._get_recipients(record):
            plain_notification_sender.send_html_mail_from_email_template(
                template_name=email_template,
                from_email=settings.EMAIL_DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                context_data=context_data,
            )
