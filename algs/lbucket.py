"""Possible leaky bucket implementation for per flow and per item scenarios."""


import time
import logging


def lbucket_alg(pos_xmit, prev_time, curr_time, xmit_unit, burst):
    """Leaky bucket algorithm.
    Args:

        pos_xmit (int): Possible xmit variable
        prev_time (int): Last time request arriving
        curr_time (int): Current time request arriving
        xmit_unit (int): Time for xmit 1 item
        burst (int): Additional burts for smoothing xmits

    Returns:
        tuple: from new pos_xmit, time. If request can be xmited then,
            tuple contains sum of `delta_pos_xmit, `xmit_unit` and `curr_time`,
            otherwise `pos_xmit`, `prev_time` are returned

    Based on algorithm from Harry G. Perros "Connection-oriented Networks:
        SONET/SDH, ATM, MPLS and OPTICAL NETWORKS", p.4.7.1, see details there.
    """

    delta_pos_xmit = pos_xmit - (curr_time - prev_time)

    if delta_pos_xmit <= 0:
        delta_pos_xmit = 0

    elif delta_pos_xmit > burst:
        return pos_xmit, prev_time

    return delta_pos_xmit + xmit_unit, curr_time


class Halt(object):
    """Halt helper class provides simple managed bool obj.

    One serves `*_lbucket()` functions as their halt obj with managed state,
    so that if `obj.set()` is performed this allows to stop these functions execution,
    due stopping the main `while` cycle.
    """

    def __init__(self):
        self._flag = False

    def __bool__(self):
        return self._flag

    def set(self):
        self._flag = True

    def clear(self):
        self._flag = False


def cast_time(time_value, offset):
    """Time value represented as number of ms, us, etc

     Args:
        time_value (float): Time value.
        offset (int): Offset serves to purpose of changing time interval rate.

    Returns:
        int: Time value represented as number of ms, us, etc

    For representing different time ranges use `offset` value as:
        for ms use `offset` equals 1000
        for us use `offset` equals 1000000
    """

    return int(round(time_value * offset, 2))


def get_req_deque(in_queue):
    """Getting request from input queue.

    Args:
        in_queue (collections.deque): Input queue, for getting requests

    Returns:
        req or None: req if request was got, otherwise None
    """

    try:
        # getting request, operation is atomic
        return in_queue.popleft()

    # another consumer may empty input queue during checking and getting data
    except IndexError:
        logging.debug("Empty input queue <{}>".format(in_queue))


def send_req_deque(out_queue, req, overwrite):
    """Sending request to output queue.

    Args:
        out_queue (collections.deque): Output queue, for setting request for execution
        req (req): Request obj
        overwrite (bool): If `out_queue` is full the option allows to rewrite latest item of the queue

    Returns:
        bool: True if request was added, otherwise False
    """

    # cheking if output queue has enough space for request
    if out_queue.maxlen and len(out_queue) == out_queue.maxlen and not overwrite:
        logging.debug("Overloaded output queue <{}>".format(out_queue))

        return False

    # appeding request, operation is atomic
    out_queue.append(req)

    return True


def flow_lbucket(in_queue, out_queue, max_xmit, burst,
                    halt=False, overwrite=False, wait_time=0.01,
                    offset=1000000, lbucket=lbucket_alg,
                    get_time=cast_time, get_req=get_req_deque,
                    send_req=send_req_deque):
    """Per flow leaky bucket.

    Args:
        in_queue (): Input queue, for getting requests, might me any obj defined by get_req()/send_req() methods,
            must have redefined `__bool__()`
        out_queue (): Output queue, for sending request to execution, might me any obj
            defined by get_req()/send_req() methods, must have redefined `__bool__()`
        max_xmit (int): Max number of xmits per sec
        burst (int): Additional burts for smoothing transmission
        halt (Halt): Halt allows to interrupt execution and function returns value. Default is False.
        overwrite (bool): If `out_queue` is full the option allows to rewrite latest item of the queue
            on current request, otherwise just ignore the one. Default is False (no rewriting).
        wait_time (float): Waiting timeout for preventing CPU load if `in_queue` is empty. Default is 0.01 (10 ms).
        offset (int): Offset serves to purpose of changing time interval rate. Default is 1000000.
        lbucket (function): Leaky bucket algorithm. Default is `lbucket_alg()`
        get_time (function): Function for getting time value. Default is `cast_time()`
        get_req (function): Function for getting request. Default is `get_req_deque()`
        send_req (function): Function for sending request. Default is `send_req_deque()`

    Returns:
        None

    A function handles requests from given `in_queue` checks if there is possibility to transmit request
    per certain time. If yes, it sends rqeuest into `out_queue`, otherwise request is ignored.
    """

    prev_time = 0
    curr_time = 0
    # possible retransmission value
    pos_xmit = 0
    # time for xmit 1 item
    xmit_unit = offset / max_xmit
    burst = xmit_unit * burst

    while not halt:

        # empty queue, just waiting for data
        if not in_queue:
            # sleep if nothing in input queue, in order to prevent CPU load
            if wait_time:
                time.sleep(wait_time)
            continue

        # getting request, operation is atomic
        req = get_req(in_queue)
        # if no req, just continue
        if req is None:
            continue

        curr_time = get_time(time.time())

        pos_xmit, prev_time = lbucket(pos_xmit, prev_time, curr_time, xmit_unit, burst)

        # if no free attempts request just ignored
        if prev_time != curr_time:
            continue

        # if sending was not successfully performed, decrease attempt
        if not send_req(out_queue, req, overwrite):
            pos_xmit -= xmit_unit


class ReqInfo(object):
    """ReqInfo is representation request information.

    This is possible implementation for example purpose.
    """

    def __init__(self, max_xmit, timestamp, lock=None):
        """__init__

        Args:
            max_xmit (int): Max number of attemps per sec
            timestamp (int): Last time request arriving
            lock (threading.Lock or None): A lock for performing save operation on obj
        """
        self.max_xmit = max_xmit
        self.timestamp = timestamp
        self.lock = lock
        self.pos_xmit = 0


def req_info_extract(data, req):
    """Request info represented as namedtuple.

    Args:
        data (dict-like obj): Data for requests, contains: maximum and free number of attemps, timestamp
        req (req): Request obj

    Returns:
        ReqInfo or None: if request item is present in data then ReqInfo obj contains:
            maximum and free number of attemps, timestamp, lock, otherwise None
    """

    # assuming req has `id` attribute
    # getting request info, operation is atomic
    try:
        req_info = data.get(req.id)

    # None for unknown for getting data
    except AttributeError as err:
        logging.error("Do not know how to handle <{}>".format(req))
        logging.exception(err)

        return

    # None for unknown
    if req_info is None:
        logging.debug("Unknown request <{}>".format(req))

        return

    return req_info


def per_item_lbucket(in_queue, out_queue, max_xmit, burst,
                        data, shared=False, global_lock=None,
                        halt=False, overwrite=False, wait_time=0.01,
                        offset=1000000, lbucket=lbucket_alg,
                        get_time=cast_time, get_req_info=req_info_extract,
                        get_req=get_req_deque, send_req=send_req_deque):
    """Per item leaky bucket.

    Args:
        in_queue (): Input queue, for getting requests, might me any obj defined by get_req()/send_req() methods,
            must have redefined `__bool__()`
        out_queue (): Output queue, for sending request to execution, might me any obj
            defined by get_req()/send_req() methods, must have redefined `__bool__()`
        max_xmit (int): Max number of xmits per sec
        burst (int): Additional burts for smoothing transmission.
        data (dict-like obj): Data for requests, contains: max_xmit, timestamp and pos_xmit,
            see `lbucket` implementation for details
        shared (bool): Indicator data is shared and lock has to be used. Default is False.
        global_lock (threading.Lock() or None): Lock is useful if data is shared between threads. Default is None.
        halt (Halt): Halt allows to interrupt execution and function returns value. Default is False.
        overwrite (bool): If `out_queue` is full the option allows to rewrite latest item of the queue
            on current request, otherwise just ignore the one. Default is False (no rewriting).
        wait_time (float): Waiting timeout for preventing CPU load if `in_queue` is empty. Default is 0.01 (10 ms).
        offset (int): Offset serves to purpose of changing time interval rate. Default is 1000000.
        lbucket (function): Leaky bucket algorithm. Default is `lbucket_alg()`
        get_time (function): Function for getting time value. Default is `cast_time()`
        get_req_info (function): Function for getting request info. Default is `req_info_extract()`
        get_req (function): Function for getting request. Default is `get_req_deque()`
        send_req (function): Function for sending request. Default is `send_req_deque()`

    Returns:
        dict-like obj or None: `dict-like obj` is returned if no shared data is used,
        provided info might be useful for certain cases, otherwise `None`.

    A function handles requests from given `in_queue` checks if there is possibility to transmit request
    per certain time. If yes, it sends rqeuest into `out_queue`, otherwise request is ignored.
    The function is able to work on local and on shared data. An individual lock provided ReqInfo obj is used
    for performing safe data operations. If no individual lock provided then global lock is used.
    """

    while not halt:

        # empty queue, just waiting for data
        if not in_queue:
            # sleep if nothing in input queue, in order to prevent CPU load
            if wait_time:
                time.sleep(wait_time)
            continue

        # getting request, operation is atomic
        req = get_req(in_queue)
        # if no req, just continue
        if req is None:
            continue

        # getting request info, operation is atomic
        req_info = req_info_extract(data, req)

        # dropping unknown request
        if req_info is None:
            continue

        # on shared data lock has to be performed
        # getting lock for checking if request info can be handled
        if shared and getattr(req_info.lock or global_lock, "aquire", lambda: False)() is False:
            logging.error("Can not aquire lock neither via request info obj <{}> nor via global lock <{}>".format(req_info, global_lock))

        # set detail for each item individually
        curr_time = get_time(time.time())
        # time for xmit 1 item
        xmit_unit = offset / req_info.max_xmit
        burst = xmit_unit * burst

        pos_xmit, prev_time = lbucket(req_info.pos_xmit, req_info.timestamp, curr_time, xmit_unit, burst)

        # if no free attempts request just ignored
        if prev_time != curr_time:
            continue

        # if sending was not successfully performed, decrease attempt
        if not send_req(out_queue, req, overwrite):
            pos_xmit -= xmit_unit

        # updating request info details
        req_info.pos_xmit, req_info.timestamp = pos_xmit, prev_time

        # on shared data lock has to be performed
        # releasing lock after end of unsfe uperation
        if shared and getattr(req_info.lock or global_lock, "release", lambda: False)()is False:
            logging.error("Can not release lock neither via request info obj <{}> nor via global lock <{}>".format(req_info, global_lock))

    # returning current data, might be useful for syncronization purpose
    if not shared:
        return data
