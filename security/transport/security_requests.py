import itertools
from urllib.parse import parse_qs, urlparse

from requests import *

from django.utils import timezone
from django.utils.encoding import force_text

from security.config import settings
from security.models import LoggedRequest, LoggedRequestStatus, clean_body, clean_headers, clean_queries
from security.utils import is_base_collection, log_output_request, log_context_manager


def stringify_dict(d):
    def stringify(value):
        if isinstance(value, bytes):
            return force_text(value)
        elif isinstance(value, dict):
            return stringify_dict(value)
        else:
            return value

    return {k: stringify(v) for k, v in d.items()}


def prepare_body(body):
    return force_text(body, errors='replace')


def flat_params(params):
    return {
        k: v[0] if is_base_collection(v) and len(v) == 1 else v
        for k, v in params.items()
    }


def list_params(params):
    return {
        k: list(v) if is_base_collection(v) else [v]
        for k, v in params.items()
    }


def get_logged_params(url, params):
    params = list_params(params or {})
    parsed_params = parse_qs(urlparse(url).query)

    for k, v in parsed_params.items():
        if k not in params:
            params[k] = v
        else:
            params[k] += v

    return flat_params(params)


class SecuritySession(Session):

    def __init__(self, slug=None, related_objects=None):
        super().__init__()
        self.slug = slug
        self.related_objects = [] if related_objects is None else related_objects

    def request(self, method, url, params=None, data=None, headers=None, cookies=None, files=None, auth=None,
                timeout=None, allow_redirects=True, proxies=None, hooks=None, stream=None, verify=None, cert=None,
                json=None, slug=None, related_objects=None):

        related_objects = [] if related_objects is None else related_objects

        parsed_url = urlparse(url)
        request_timestamp = timezone.now()
        logged_kwargs = {
            'is_secure': parsed_url.scheme == 'https',
            'host': parsed_url.netloc,
            'path': parsed_url.path,
            'method': method.upper(),
            'queries': clean_queries(get_logged_params(url, params)),
            'slug': slug or self.slug or log_context_manager.get_output_request_slug(),
            'request_timestamp': request_timestamp,
        }

        try:
            # Create the Request.
            req = Request(
                method=method.upper(), url=url, headers=headers, files=files, data=data or {}, json=json,
                params=params or {}, auth=auth, cookies=cookies, hooks=hooks,
            )
            prep = self.prepare_request(req)
            proxies = proxies or {}
            request_settings = self.merge_environment_settings(
                prep.url, proxies, stream, verify, cert
            )
            # Send the request.
            send_kwargs = {
                'timeout': timeout,
                'allow_redirects': allow_redirects,
            }
            send_kwargs.update(request_settings)
            logged_kwargs.update({
                'request_headers': clean_headers(dict(prep.headers.items())),
                'request_body': clean_body(prepare_body(prep.body), settings.LOG_REQUEST_BODY_LENGTH),
            })
            resp = self.send(prep, **send_kwargs)

            response_timestamp = timezone.now()
            logged_kwargs.update({
                'response_timestamp': response_timestamp,
                'response_time': (response_timestamp - request_timestamp).total_seconds(),
                'response_code': resp.status_code,
                'response_headers': clean_headers(dict(resp.headers.items())),
                'response_body': clean_body(prepare_body(resp.content), settings.LOG_RESPONSE_BODY_LENGTH),
                'status': LoggedRequest.get_status(resp.status_code)
            })
            return resp
        except Exception as ex:
            logged_kwargs.update({
                'error_description': force_text(ex),
                'status': LoggedRequestStatus.CRITICAL,
                'exception_name': ex.__class__.__name__
            })
            raise
        finally:
            log_output_request(
                stringify_dict(logged_kwargs),
                list(itertools.chain(
                    related_objects, self.related_objects, log_context_manager.get_output_request_related_objects()
                ))
            )


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
