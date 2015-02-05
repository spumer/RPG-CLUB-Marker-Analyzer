# encoding: utf-8

import json
import asyncio

from aiohttp import web
from concurrent.futures import ThreadPoolExecutor

import market
import analyze


SHARED_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def log_future_exception(future):
    exc = future.exception()
    if exc is not None:
        print("Critical exception occured: %r" % exc)


@asyncio.coroutine
def update_market(loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    while True:
        try:
            trades = yield from asyncio.wait_for(
                loop.run_in_executor(SHARED_EXECUTOR, market.get_trades, True),
                timeout=120
            )
            trades.write(latest=True)

            yield from asyncio.sleep(120, loop=loop)
        except asyncio.TimeoutError:
            print("TimeoutError occured. Try again!")
        except Exception as exc:
            print("Unhandled exception occured: %r" % exc)
            print("Sleep...")
            asyncio.sleep(10, loop=loop)
            print("Wake up!")


@asyncio.coroutine
def dupe(request):
    dupes = analyze.get_dupes()
    body = json.dumps([d.to_dict() for d in dupes]).encode()
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
