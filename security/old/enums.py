from django.utils.translation import ugettext_lazy as _

from enumfields import Choice, ChoiceEnum


class LoggedRequestStatus(ChoiceEnum):

    INCOMPLETE = Choice(0, _('Incomplete'))
    DEBUG = Choice(10, _('Debug'))
    INFO = Choice(20, _('Info'))
    WARNING = Choice(30, _('Warning'))
    ERROR = Choice(40, _('Error'))
    CRITICAL = Choice(50, _('Critical'))


class InputLoggedRequestType(ChoiceEnum):

    COMMON_REQUEST = Choice(1, _('Common request'))
    THROTTLED_REQUEST = Choice(2, _('Throttled request'))
    SUCCESSFUL_LOGIN_REQUEST = Choice(3, _('Successful login request'))
    UNSUCCESSFUL_LOGIN_REQUEST = Choice(4, _('Unsuccessful login request'))
    SUCCESSFUL_2FA_CODE_VERIFICATION_REQUEST = Choice(5, _('Successful two factor code verification request'))
    UNSUCCESSFUL_2FA_CODE_VERIFICATION_REQUEST = Choice(6, _('Unsuccessful two factor code verification request'))


class CeleryTaskInvocationLogState(ChoiceEnum):

    WAITING = Choice(1, _('Waiting'))
    TRIGGERED = Choice(7, _('Triggered'))
    ACTIVE = Choice(2, _('Active'))
    SUCCEEDED = Choice(3, _('Succeeded'))
    FAILED = Choice(4, _('Failed'))
    EXPIRED = Choice(6, _('Expired'))
    TIMEOUT = Choice(8, _('Timeout'))
    IGNORED = Choice(9, _('Ignored'))


class CeleryTaskRunLogState(ChoiceEnum):

    ACTIVE = Choice(1, _('Active'))
    SUCCEEDED = Choice(2, _('Succeeded'))
    FAILED = Choice(3, _('Failed'))
    RETRIED = Choice(4, _('Retried'))
    EXPIRED = Choice(5, _('Expired'))
