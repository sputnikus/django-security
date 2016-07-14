from six.moves.urllib.parse import urlparse, parse_qs

from django.utils import timezone
from django.template.defaultfilters import truncatechars
from django.utils.encoding import force_text

from requests import *

from security.config import LOG_REQUEST_BODY_LENGTH, LOG_RESPONSE_BODY_LENGTH
from security.models import LoggedRequest, OutputLoggedRequest


def request(method, url, params=None, data=None, headers=None, cookies=None, files=None, auth=None, timeout=None,
            allow_redirects=True, proxies=None, hooks=None, stream=None, verify=None, cert=None, json=None, slug=None,
            related_objects=None):
    """Constructs and sends a :class:`Request <Request>`.
    :param method: method for the new :class:`Request` object.
    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query string for the :class:`Request`.
    :param data: (optional) Dictionary, bytes, or file-like object to send in the body of the :class:`Request`.
    :param json: (optional) json data to send in the body of the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the :class:`Request`.
    :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': ('filename', fileobj)}``)
                  for multipart encoding upload.
    :param auth: (optional) Auth tuple to enable Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send data
        before giving up, as a float, or a :ref:`(connect timeout, read
        timeout) <timeouts>` tuple.
    :type timeout: float or tuple
    :param allow_redirects: (optional) Boolean. Set to True if POST/PUT/DELETE redirect following is allowed.
    :type allow_redirects: bool
    :param proxies: (optional) Dictionary mapping protocol to the URL of the proxy.
    :param verify: (optional) whether the SSL cert will be verified. A CA_BUNDLE path can also be provided. Defaults to
                   ``True``.
    :param stream: (optional) if ``False``, the response content will be immediately downloaded.
    :param cert: (optional) if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    Usage::
      >>> import requests
      >>> req = requests.request('GET', 'http://httpbin.org/get')
      <Response [200]>
    """

    parsed_url = urlparse(url)
    logged_kwargs = {
        'is_secure': parsed_url.scheme == 'https',
        'host': parsed_url.netloc,
        'path': parsed_url.path,
        'method': method.upper(),
        'queries': params or parse_qs(parsed_url.query),
        'slug': slug
    }

    # By using the 'with' statement we are sure the session is closed, thus we
    # avoid leaving sockets open which can trigger a ResourceWarning in some
    # cases, and look like a memory leak in others.
    with Session() as session:
        try:
            req = Request(
                method=method.upper(), url=url, headers=headers, files=files, data=data or {}, json=json,
                params=params or {}, auth=auth, cookies=cookies, hooks=hooks,
            )
            prep = session.prepare_request(req)

            proxies = proxies or {}

            settings = session.merge_environment_settings(
                prep.url, proxies, stream, verify, cert
            )
            # Send the request.
            send_kwargs = {
                'timeout': timeout,
                'allow_redirects': allow_redirects,
            }
            send_kwargs.update(settings)

            def prepare_request_body(prep):
                return (truncatechars(force_text(prep.body[:LOG_REQUEST_BODY_LENGTH + 1], errors='replace'),
                                      LOG_REQUEST_BODY_LENGTH) if prep.body else '')

            logged_kwargs.update({
                'request_timestamp': timezone.now(),
                'request_headers': dict(prep.headers.items()),
                'request_body': prepare_request_body(prep),
            })
            resp = session.send(prep, **send_kwargs)
            logged_kwargs.update({
                'response_timestamp': timezone.now(),
                'response_code': resp.status_code,
                'response_headers': dict(resp.headers.items()),
                'request_body': prepare_request_body(prep),
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
            output_logged_request = OutputLoggedRequest.objects.create(**logged_kwargs)
            for obj in related_objects or ():
                output_logged_request.related_objects.create(content_object=obj)


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
