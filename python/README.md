# JSON formatter for logging.Logger
Allows format standard logging messasges to JSON

## Usage
import `JSONMapFormatter` and use one for `logging.Handler` obj.

### Terms
Look at logger argumets for `logger.info('MESSAGE', {'1st': {'2nd': {'3rd': {'value': 3}}, 'value': 2}, 'value': 1}, 'more value', 'one more value', {'4th': 4})`:
* 1st is always message obj, in this example: _'MESSAGE'_
* dict-like objs that may be described by JSONMap or just stored in one of JSON path, in this example: _{'1st': {'2nd': {'3rd': {'value': 3}}, 'value': 2}, 'value': 1}_ and _{'4th': 4}_
*  non dict-like objs or **args** that just stored in one of JSON path, in this example: _'more value'_ and _'one more value'_

### Simple example:

_test.py:_

```python
import logging
from jsonlogfmt import JSONMapFormatter

fmt = JSONMapFormatter()

console = logging.StreamHandler()
console.setFormatter(fmt)
console.setLevel(logging.INFO)

logger = logging.getLogger()
logger.addHandler(console)
logger.setLevel(logging.INFO)


if __name__ == '__main__':

    logger.info('MESSAGE', {'1st': {'2nd': {'3rd': {'value': 3}}, 'value': 2}, 'value': 1}, 'more value', 'one more value', {'4th': 4})
```

_Output:_

_(output was formatted, original is ordinary flat string)_

```json
{'extra': {'data': {'1st': {'2nd': {'3rd': {'value': 3}}, 'value': 2},
                    '4th': 4,
                    'args': ['more value', 'one more value']},
           'exception': {'type': '', 'value': 1},
           'funcName': '<module>',
           'lineno': 18,
           'pathname': './test.py'},
 'levelname': 'INFO',
 'msg': 'MESSAGE',
 'name': 'root',
 'time': '2018-02-05 21:06:25,618'}

```

### Default logging format example:
Default logging formatting is also supported. That may be useful for some purposes e.g. for creating standard syslog entry with extra JSON message. Changing `JSONMapFormatter()` to `JSONMapFormatter(fmt='%(name)s / %(asctime)s / %(message)s')` gives:

_Output:_

_(output was formatted, original is ordinary flat string)_

```json
root / 2018-02-05 21:08:20,876 / 
{'extra': {'data': {'1st': {'2nd': {'3rd': {'value': 3}}, 'value': 2},
                    '4th': 4,
                    'args': ['more value', 'one more value']},
           'exception': {'type': '', 'value': 1},
           'funcName': '<module>',
           'lineno': 18,
           'pathname': './test.py'},
 'levelname': 'INFO',
 'msg': 'MESSAGE',
 'name': 'root',
 'time': '2018-02-05 21:08:20,876'}

```

### Custom JSONMap
By default `JSONMapFormatter` uses JSONMAP dict-like obj, one can be changed.

```python
newJSONMap = {'created': None,
    'extra': OrderedDict([('funcName', '')]),
    'levelname': '',
    'msg': '',
    'time': ''}

fmt = JSONMapFormatter(jsonmap=newJSONMap)

```

_Output:_

_(output was formatted, original is ordinary flat string)_

```json
{'created': 1517855408.837364,
 'extra': {'data': {'1st': {'2nd': {'3rd': {'value': 3}}, 'value': 2},
                    '4th': 4,
                    'args': ['more value', 'one more value'],
                    'value': 1},
           'funcName': '<module>'},
 'levelname': 'INFO',
 'msg': 'MESSAGE',
 'time': '2018-02-05 21:30:08,837'}
```

**Note.**

Be careful, entry values of dict-like obj if they have similar keys on one level **will be rewritten** on value of latest obj.

### Custom extrakeys and argskey
By default for storing extra data _extra: {data: {}}_ path is used (_extra: {data: {args: {}}}_ for non dict-like args) that behavior can be changed. Use `extrakeys` for dict-like obj and `argskey` for non dict-like args). E.g. `fmt = JSONMapFormatter(jsonmap=newJSONMap, extrakeys=['newExtrapath', 'subpath'], argskey=['newArgspath'])` gives:

_Output:_

_(output was formatted, original is ordinary flat string)_

```json
{'created': 1517856642.977184,
 'extra': {'funcName': '<module>'},
 'levelname': 'INFO',
 'msg': 'MESSAGE',
 'newExtrapath': {'subpath': {'1st': {'2nd': {'3rd': {'value': 3}}, 'value': 2},
                              '4th': 4,
                              'newArgspath': ['more value', 'one more value'],
                              'value': 1}},
 'time': '2018-02-05 21:50:42,977'}
 ```

**Note.**

`extrakeys` is parent path for `argskey` that means non dict-like args stores in common extra path.
