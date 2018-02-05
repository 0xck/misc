# Formatting class for logging.Logger, composes JSON message from logging.Logger message.
# Using is pretty simple, just use JSONMapFormatter obj in `setFormatter` of logging.Handler obj

from logging import Formatter
from collections import Mapping, OrderedDict
from functools import reduce
from json import dumps

# default JSON map
JSONMAP = OrderedDict({
    'time': '',
    'levelname': '',
    'name': '',
    'msg': '',
    'extra': OrderedDict({
            'funcName': '',
            'lineno': '',
            'pathname': '',
            'exception': OrderedDict({
                'type': '',
                'value': ''
            })
    })
})


class JSONMapFormatter(Formatter):
    """ JSONMapFormatter allows format standard logging messasges to JSON

    One uses dict-like map which describes keys are included in new formatted message.
    Moreover standard logging fuction partially saved, default formatting style is still supported,
    e.g. define format as '%(asctime)s %(name)s' and logger returns those values in log message.
    That may be useful for some purposes e.g. for creating standard syslog entry with extra JSON message.
    """

    def __init__(self, jsonmap=JSONMAP, extrakeys=['extra', 'data'], argskey=['args'], fmt='%(message)s', datefmt=None, style='%'):
        """ init function

        parameters:
            kwargs:
                jsonmap (Mapping): dict-like obj describes JSON message default: JSONMAP
                extrakeys (list): sequence contains path to extra key,
                    which serves for additional values created from dict-like message entries; default: ['extra', 'data']
                argskey (list): sequence contains path to args key,
                    which serves for additional values from nondict-like enties; default: ['args']; this value will be added to `extrakeys` path
                fmt (str): logging message format; default: '%(message)s'
                datefmt (str): logging date format; default: None
                style (str): logging type of format; default: '%'
        """

        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
        self.jsonmap = jsonmap
        self.msg = OrderedDict()
        self.extrakeys = extrakeys
        self.argskey = argskey

    def _set_extra(self, data, keys, value):
        """ sets values to nested dict from keys path

        parameters:
            args:
                data (Mapping): dict-like obj for adding
                keys (list): sequence contains path
                value (any): value for adding to `data`
        """

        # set extra path
        reduce(lambda x, key: x.setdefault(key, type(data)()), keys[:-1], data)  # type(a)() is more universal than just {}
        # set value
        reduce(lambda x, key: x.setdefault(key, value), keys, data)

    def _msg_filler(self, jsonmap, data, msg=None):
        """ fills msg from given data recursively bypassing jsonmap

        parameters:
            args:
                jsonmap (Mapping): dict-like obj describes JSON message
                data (Mapping): dict-like obj contains values for adding
            kwargs:
                msg (Mapping): dict-like obj for adding; default: None
        """

        # defines msg from self, that means 1st enter to recursively bypassing
        msg = self.msg if msg is None else msg

        # recursively bypassing each jsonmap entry
        for i in jsonmap:
            # if value is dict-like obj than recursively bypassing one
            if isinstance(jsonmap[i], Mapping):
                # creates a new dict value which will be used for filling
                msg[i] = OrderedDict()
                self._msg_filler(jsonmap[i], data, msg=msg[i])
            # adding value in case one does not exist
            else:
                item = data.pop(i, '')
                if msg.get(i, None) is None:
                    msg[i] = item

    def _set_msg(self, record):
        """ set msg data from given log messages and args

        parameters:
            args:
                record (LogRecord): logger obj contains logging info
        """

        # getting data from args
        # !!! be careful
        # values of dict-like obj if they have similar values on one level will be rewritten on value of latest obj
        # as  dict.update() does it
        emsglist = [record.args] if isinstance(record.args, Mapping) else [i for i in record.args if isinstance(i, Mapping)]
        # update record mehods dict with args dicts
        extramsg = record.__dict__.copy()
        for i in emsglist:
            extramsg.update(i)

        # filling from args, set new keys and values from given in log message args
        self._msg_filler(self.jsonmap, extramsg)

        # getting rest values, excludes native log items
        extramsg = {k: v for k, v in extramsg.items() if k not in set(extramsg).intersection(set(record.__dict__))}
        # set rest args dict as extra value
        if extramsg:
            self._set_extra(self.msg, self.extrakeys, extramsg)

        # if no more args
        if isinstance(record.args, Mapping):
            return

        # set rest args (nondict)
        eargs = [i for i in record.args if not isinstance(i, Mapping)]
        if eargs:
            self._set_extra(self.msg, self.extrakeys + self.argskey, eargs)

    def format(self, record):
        """ rewriting Formatter().format method

        Making new JSON message from given logger obj,
        changing record.msg attribute to new message,
        returning Formatter().format method.

        parameters:
            args:
                record (LogRecord): logger obj contains logging info
        returns (str): log string created by Formatter class
        """

        # adding time to record
        record.time = super().formatTime(record)

        # only one passing is needed for first handler, other handlers can use earlier msg
        if not self.msg:
            # filling data from record
            self._set_msg(record)

        # set record message
        record.msg = dumps(self.msg)
        # deleting args, needs for Formatter().format
        record.args = ()

        return super().format(record)
