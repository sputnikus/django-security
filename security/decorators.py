from functools import wraps

from django.utils.decorators import available_attrs


def throttling(validator):
    """
    Adds throttling validator to a function.
    """
    def decorator(view_func):
        def _throttling(self, request, *args, **kwargs):
            validator.validate(request)
            return view_func(self, request, *args, **kwargs)
        return wraps(view_func, assigned=available_attrs(view_func))(_throttling)

    return decorator


def throttling_all(klass):
    """
    Adds throttling validator to a class.
    """
    dispatch = getattr(klass, 'dispatch')
    setattr(klass, 'dispatch', throttling()(dispatch))
    return klass


def throttling_exempt():
    """
    Marks a function as being exempt from the throttling protection.
    """
    def decorator(view_func):
        def _throttling_exempt(*args, **kwargs):
            return view_func(*args, **kwargs)
        _throttling_exempt.throttling_exempt = True
        return wraps(view_func, assigned=available_attrs(view_func))(_throttling_exempt)

    return decorator


def throttling_exempt_all(klass):
    """
    Marks a class as being exempt from the throttling protection.
    """
    dispatch = getattr(klass, 'dispatch')
    setattr(klass, 'dispatch', throttling_exempt()(dispatch))
    return klass


def hide_request_body():
    """
    Marks a function as being exempt from storing request base to DB.
    """
    def decorator(view_func):
        def _hide_base(*args, **kwargs):
            return view_func(*args, **kwargs)
        _hide_base.hide_request_body = True
        return wraps(view_func, assigned=available_attrs(view_func))(_hide_base)

    return decorator


def hide_request_body_all(klass):
    """
    Marks a class as being exempt from storing request base to DB.
    """
    dispatch = getattr(klass, 'dispatch')
    setattr(klass, 'dispatch', hide_request_body()(dispatch))
    return klass
