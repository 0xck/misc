# JSON formatter for logging.Logger
Allows format standard logging messasges to JSON

## Usage
import `JSONMapFormatter` and use one for `logging.Handler` obj.

### Example:

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

```json
{"time": "2018-02-05 21:06:25,618", "levelname": "INFO", "name": "root", "msg": "MESSAGE", "extra": {"funcName": "<module>", "lineno": 18, "pathname": "./test.py", "exception": {"type": "", "value": 1}, "data": {"1st": {"2nd": {"3rd": {"value": 3}}, "value": 2}, "4th": 4, "args": ["more value", "one more value"]}}}

```

Changing `JSONMapFormatter()` to `JSONMapFormatter(fmt='%(name)s / %(asctime)s / %(message)s')` gives:

```json
root / 2018-02-05 21:08:20,876 / {"time": "2018-02-05 21:08:20,876", "levelname": "INFO", "name": "root", "msg": "MESSAGE", "extra": {"funcName": "<module>", "lineno": 18, "pathname": "./test.py", "exception": {"type": "", "value": 1}, "data": {"1st": {"2nd": {"3rd": {"value": 3}}, "value": 2}, "4th": 4, "args": ["more value", "one more value"]}}}

```