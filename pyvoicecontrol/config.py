import configparser
from .config_exceptions import *   # noqa


def validate_and_convert_types(scheme, value, section, field, output_dict):
    """The `scheme` is a dictionary indicating the object structure and types.  We operate
       on a specific field (leaf dict key) and section (dict key) at a time, validate
       the data type and convert it from a string into a native python type.
    """
    if 'default' not in scheme[section][field] and field not in value[section]:
        raise ConfigExceptionMandatoryParameterMissing('Mandatory parameter {} missing from {}'.format(field, section))
    elif field not in value[section]:
        output_dict[section][field] = scheme[section][field]['default']
    else:
        if scheme[section][field]['type'] == bool:
            allowed_true_values = ['yes', 'true', 'high', 'on']
            allowed_false_values = ['no', 'false', 'low', 'off']
            if value[section][field].lower() in allowed_true_values:
                output_dict[section][field] = True
            elif value[section][field].lower() in allowed_false_values:
                output_dict[section][field] = False
            else:
                raise ConfigExceptionValueIsNotABoolean('Parameter {} from {} must be boolean (yes, no, true, false)'.format(
                    field, section))
        elif scheme[section][field]['type'] == str:
            if 'allowed_values' in scheme[section][field] and \
            value[section][field].lower() not in scheme[section][field]['allowed_values']:
                raise ConfigExceptionValueIsNotInAllowedValues('Parameter {} from {} must be one of {}'.format(
                    field, section, scheme[section][field]['allowed_values']))
            output_dict[section][field] = value[section][field].lower() if 'allowed_values' in scheme[section][field] else value[section][field]
        elif scheme[section][field]['type'] == int:
            base = 16 if value[section][field].startswith('0x') else 10
            x = int(value[section][field], base)
            if 'min' in scheme[section][field] and x < scheme[section][field]['min']:
                raise ConfigExceptionValueTooLow('Parameter {} from {} must be >= {}'.format(
                    field, section, scheme[section][field]['min']))
            if 'max' in scheme[section][field] and x > scheme[section][field]['max']:
                raise ConfigExceptionValueTooHigh('Parameter {} from {} must be <= {}'.format(
                    field, section, scheme[section][field]['max']))
            output_dict[section][field] = x
        elif scheme[section][field]['type'] == float:
            x = float(value[section][field])
            if 'min' in scheme[section][field] and x < scheme[section][field]['min']:
                raise ConfigExceptionValueTooLow('Parameter {} from {} must be >= {}'.format(
                    field, section, scheme[section][field]['min']))
            if 'max' in scheme[section][field] and x > scheme[section][field]['max']:
                raise ConfigExceptionValueTooHigh('Parameter {} from {} must be <= {}'.format(
                    field, section, scheme[section][field]['max']))
            output_dict[section][field] = x
        elif scheme[section][field]['type'] == list:
            input_values = [k.strip() for k in value[section][field].strip().split(',')]
            output_values = []
            for i in input_values:
                if scheme[section][field]['subtype'] == bool:
                    allowed_true_values = ['yes', 'true']
                    allowed_false_values = ['no', 'false']
                    if i.lower() in allowed_true_values:
                        output_values.append(True)
                    elif i.lower() in allowed_false_values:
                        output_values.append(False)
                    else:
                        raise ConfigExceptionValueIsNotABoolean('Parameter {} from {} must contain boolean (yes, no, true, false)'.format(
                            field, section))
                elif scheme[section][field]['subtype'] == str:
                    if 'allowed_values' in scheme[section][field] and \
                    i.lower() not in scheme[section][field]['allowed_values']:
                        raise ConfigExceptionValueIsNotInAllowedValues('Parameter {} from {} must contain one of {}'.format(
                            field, section, scheme[section][field]['allowed_values']))
                    output_values.append(i.lower() if 'allowed_values' in scheme[section][field] else i)
                elif scheme[section][field]['subtype'] == int:
                    base = 16 if i.startswith('0x') else 10
                    x = int(i, base)
                    if 'min' in scheme[section][field] and x < scheme[section][field]['min']:
                        raise ConfigExceptionValueTooLow('Parameter {} from {} must be >= {}'.format(
                            field, section, scheme[section][field]['min']))
                    if 'max' in scheme[section][field] and x > scheme[section][field]['max']:
                        raise ConfigExceptionValueTooHigh('Parameter {} from {} must be <= {}'.format(
                            field, section, scheme[section][field]['max']))
                    output_values.append(x)
                elif scheme[section][field]['subtype'] == float:
                    x = float(i)
                    if 'min' in scheme[section][field] and x < scheme[section][field]['min']:
                        raise ConfigExceptionValueTooLow('Parameter {} from {} must be >= {}'.format(
                            field, section, scheme[section][field]['min']))
                    if 'max' in scheme[section][field] and x > scheme[section][field]['max']:
                        raise ConfigExceptionValueTooHigh('Parameter {} from {} must be <= {}'.format(
                            field, section, scheme[section][field]['max']))
                    output_values.append(x)
            output_dict[section][field] = output_values
        else:
            raise ConfigExceptionInvalidSchemaType('Unrecognised type for validation {}', scheme[section][field])


def parse_config(file, schema_dict):
    """ConfigParser will convert a text file with section headings and field=value entries
       into a nested dictionary.  We take that data and apply a schema dict which is used
       to validate the file and convert types into native python types eg bool, string, integer.
    """
    cfg = configparser.ConfigParser()
    cfg.read_file(file)

    output_dict = {}

    for section in schema_dict:
        output_dict[section] = {}
        for field in schema_dict[section]:
            validate_and_convert_types(schema_dict, cfg, section, field, output_dict)
    return output_dict
