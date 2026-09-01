import logging
from app.utils.log_buffer import _LogBuffer, install, tail

def test_buffer_emit_and_tail():
    buf = _LogBuffer()
    log = logging.getLogger("test")
    log.addHandler(buf)
    log.setLevel(logging.INFO)
    log.info("hello"); log.warning("world")
    result = buf.tail(10)
    assert len(result) == 2
    assert result[0]["msg"] == "hello"
    assert result[1]["level"] == "WARNING"

def test_tail_respects_limit():
    buf = _LogBuffer()
    log = logging.getLogger("test2")
    log.addHandler(buf)
    log.setLevel(logging.DEBUG)
    for i in range(5):
        log.debug(f"line {i}")
    assert len(buf.tail(3)) == 3

def test_install_idempotent():
    install(); install()
    # just verify no crash
    tail()
