from security.backends.sql.throttling import PerRequestThrottlingValidator


default_validators = (
    PerRequestThrottlingValidator(60, 2),
)
