# encoding: utf-8

import json
import asyncio

from aiohttp import web
from concurrent.futures import ThreadPoolExecutor

import market
import analyze


NEW_DATA_AVAILABLE = True
SHARED_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def log_future_exception(future):
    exc = future.exception()
    if exc is not None:
        print("Critical exception occured: %r" % exc)


@asyncio.coroutine
def update_market(loop=None):
    global NEW_DATA_AVAILABLE

    if loop is None:
        loop = asyncio.get_event_loop()

    while True:
        trades = yield from loop.run_in_executor(SHARED_EXECUTOR, market.get_trades, True)
        if trades.write(latest=True):
            NEW_DATA_AVAILABLE = True

        yield from asyncio.sleep(120, loop=loop)


_dupes = []
@asyncio.coroutine
def dupe(request):
    global _dupes
    global NEW_DATA_AVAILABLE

    if NEW_DATA_AVAILABLE:
        _dupes = analyze.get_dupes()
        NEW_DATA_AVAILABLE = False

    body = json.dumps([d.to_dict() for d in _dupes]).encode()
    return web.Response(body=body)


if __name__ == '__main__':
    app = web.Application()
    app.router.add_route('GET', '/api/dupe', dupe)
    app.router.add_route('POST', '/api/dupe', dupe)

    loop = asyncio.get_event_loop()

    upd_task = asyncio.async(update_market())
    upd_task.add_done_callback(log_future_exception)

    f = loop.create_server(app.make_handler(), '0.0.0.0', 8080)
    srv = loop.run_until_complete(f)
    print('serving on', srv.sockets[0].getsockname())
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
