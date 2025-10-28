import socket

from cli import utils


def test_generate_run_id_unique() -> None:
    run_id_1 = utils.generate_run_id()
    run_id_2 = utils.generate_run_id()
    assert run_id_1 != run_id_2
    assert run_id_1.startswith("odoo-")


def test_ensure_available_port_skips_bound_port() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    bound_port = sock.getsockname()[1]
    try:
        chosen_port = utils.ensure_available_port(bound_port)
        assert chosen_port != bound_port
    finally:
        sock.close()
