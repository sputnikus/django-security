from security.backends.elasticsearch.throttling import PerRequestThrottlingValidator


default_validators = (
    PerRequestThrottlingValidator(60, 2),
)
