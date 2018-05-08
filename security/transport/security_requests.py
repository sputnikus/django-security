from requests import *
from urllib.parse import parse_qs, urlparse

from django.template.defaultfilters import truncatechars
from django.utils import timezone
from django.utils.encoding import force_text

from security.config import settings
from security.models import LoggedRequest, OutputLoggedRequest

from .transaction import log_output_request


def stringify_dict(d):
    def stringify(value):
        if isinstance(value, bytes):
            return force_text(value)
        elif isinstance(value, dict):
            return stringify_dict(value)
        else:
            return value

    return {k: stringify(v) for k, v in d.items()}


def prepare_request_body(prep):
    return (truncatechars(force_text(prep.body, errors='replace'),
                          settings.LOG_REQUEST_BODY_LENGTH) if prep.body else '')


def prepare_response_body(resp):
    return (truncatechars(force_text(resp.content[:settings.LOG_RESPONSE_BODY_LENGTH + 1], errors='replace'),
                          settings.LOG_RESPONSE_BODY_LENGTH) if resp.content else '')


class SecuritySession(Session):

    def __init__(self, *args, **kwargs):
        super(SecuritySession, self).__init__(*args, **kwargs)
        self.slug = None

    def request(self, method, url, params=None, data=None, headers=None, cookies=None, files=None, auth=None,
                timeout=None, allow_redirects=True, proxies=None, hooks=None, stream=None, verify=None, cert=None,
                json=None, slug=None, related_objects=()):

        parsed_url = urlparse(url)
        logged_kwargs = {
            'is_secure': parsed_url.scheme == 'https',
            'host': parsed_url.netloc,
            'path': parsed_url.path,
            'method': method.upper(),
            'queries': params or parse_qs(parsed_url.query),
            'slug': slug or self.slug,
            'request_timestamp': timezone.now(),
        }

        try:
            # Create the Request.
            req = Request(
                method=method.upper(), url=url, headers=headers, files=files, data=data or {}, json=json,
                params=params or {}, auth=auth, cookies=cookies, hooks=hooks,
            )
            prep = self.prepare_request(req)
            proxies = proxies or {}
            settings = self.merge_environment_settings(
                prep.url, proxies, stream, verify, cert
            )
            # Send the request.
            send_kwargs = {
                'timeout': timeout,
                'allow_redirects': allow_redirects,
            }
            send_kwargs.update(settings)
            logged_kwargs.update({
                'request_headers': dict(prep.headers.items()),
                'request_body': prepare_request_body(prep),
            })
            resp = self.send(prep, **send_kwargs)

            logged_kwargs.update({
                'response_timestamp': timezone.now(),
                'response_code': resp.status_code,
                'response_headers': dict(resp.headers.items()),
                'response_body': prepare_response_body(resp),
                'status': LoggedRequest.get_status(resp.status_code)
            })
            return resp
        except Exception as ex:
            logged_kwargs.update({
                'error_description': force_text(ex),
                'status': LoggedRequest.CRITICAL,
                'exception_name': ex.__class__.__name__
            })
            raise
        finally:
            log_output_request(stringify_dict(logged_kwargs), related_objects)


def request(method, url, **kwargs):
    with SecuritySession() as session:
        return session.request(method=method, url=url, **kwargs)


def get(url, params=None, **kwargs):
    """Sends a GET request.
    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query string for the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    kwargs.setdefault('allow_redirects', True)
    return request('get', url, params=params, **kwargs)


def options(url, **kwargs):
    """Sends a OPTIONS request.
    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    kwargs.setdefault('allow_redirects', True)
    return request('options', url, **kwargs)


def head(url, **kwargs):
    """Sends a HEAD request.
    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    kwargs.setdefault('allow_redirects', False)
    return request('head', url, **kwargs)


def post(url, data=None, json=None, **kwargs):
    """Sends a POST request.
    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, bytes, or file-like object to send in the body of the :class:`Request`.
    :param json: (optional) json data to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request('post', url, data=data, json=json, **kwargs)


def put(url, data=None, **kwargs):
    """Sends a PUT request.
    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, bytes, or file-like object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request('put', url, data=data, **kwargs)


def patch(url, data=None, **kwargs):
    """Sends a PATCH request.
    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, bytes, or file-like object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request('patch', url, data=data, **kwargs)


def delete(url, **kwargs):
    """Sends a DELETE request.
    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request('delete', url, **kwargs)
