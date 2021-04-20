class ConfigException(Exception):
    pass


class ConfigExceptionMandatoryParameterMissing(ConfigException):
    pass


class ConfigExceptionValueTooLow(ConfigException):
    pass


class ConfigExceptionValueTooHigh(ConfigException):
    pass


class ConfigExceptionValueIsNotABoolean(ConfigException):
    pass


class ConfigExceptionValueIsNotInAllowedValues(ConfigException):
    pass


class ConfigExceptionInvalidSchemaType(ConfigException):
    pass
