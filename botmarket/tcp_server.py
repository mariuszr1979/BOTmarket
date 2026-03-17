import asyncio
from wire import HEADER_SIZE, unpack_header, pack_message, MSG_ERROR
from db import init_db


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    try:
        while True:
            header = await reader.readexactly(HEADER_SIZE)
            msg_type, payload_len = unpack_header(header)
            payload = await reader.readexactly(payload_len)
            # Step 0: echo back an error — no handlers yet
            response = pack_message(MSG_ERROR, b"not implemented")
            writer.write(response)
            await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def start_tcp_server(host="0.0.0.0", port=9000):
    init_db()
    server = await asyncio.start_server(handle_client, host, port)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(start_tcp_server())
