from .throttling import PerRequestThrottlingValidator, UnsuccessfulLoginThrottlingValidator, SuccessfulLoginThrottlingValidator


validators = (
    PerRequestThrottlingValidator(3600, 150),  # 150 per an hour
    PerRequestThrottlingValidator(60, 20),  # 20 per an minute
    UnsuccessfulLoginThrottlingValidator(60, 2),
    UnsuccessfulLoginThrottlingValidator(10 * 60, 10),
    SuccessfulLoginThrottlingValidator(60, 2),
    SuccessfulLoginThrottlingValidator(10 * 60, 10),
)