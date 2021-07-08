class Error(Exception):
    error_type = "error"

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class VerificationError(Error):
    error_type = "verification"


class FetchError(Error):
    error_type = "fetch"


class StarTypeError(Error):
    error_type = 'type'


class StarGetValueError(Error):
    error_type = 'get value'
