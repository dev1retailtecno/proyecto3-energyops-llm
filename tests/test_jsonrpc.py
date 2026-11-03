import pytest

from energyops_mcp.protocol.jsonrpc import (
    INVALID_REQUEST,
    PARSE_ERROR,
    JsonRpcError,
    JsonRpcErrorResponse,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    parse_message,
    serialize,
)


def test_parse_request():
    msg = parse_message('{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}')
    assert isinstance(msg, JsonRpcRequest)
    assert msg.id == 1
    assert msg.method == "ping"


def test_parse_notification_has_no_id():
    msg = parse_message('{"jsonrpc":"2.0","method":"notifications/initialized"}')
    assert isinstance(msg, JsonRpcNotification)


def test_parse_success_response():
    msg = parse_message('{"jsonrpc":"2.0","id":7,"result":{"ok":true}}')
    assert isinstance(msg, JsonRpcResponse)
    assert msg.id == 7
    assert msg.result == {"ok": True}


def test_parse_error_response():
    msg = parse_message('{"jsonrpc":"2.0","id":7,"error":{"code":-32601,"message":"Method not found"}}')
    assert isinstance(msg, JsonRpcErrorResponse)
    assert msg.error.code == -32601


def test_malformed_json_raises_parse_error():
    with pytest.raises(JsonRpcError) as exc_info:
        parse_message("{not json")
    assert exc_info.value.code == PARSE_ERROR


@pytest.mark.parametrize(
    "raw",
    [
        "[]",  # not an object
        '{"id":1,"method":"x"}',  # missing jsonrpc version
        '{"jsonrpc":"1.0","id":1,"method":"x"}',  # wrong version
        '{"jsonrpc":"2.0","id":1,"method":""}',  # empty method
        '{"jsonrpc":"2.0","id":1,"method":"x","params":"not-object-or-array"}',
        '{"jsonrpc":"2.0","id":1}',  # neither method nor result/error
        '{"jsonrpc":"2.0","result":{}}',  # response without id
        '{"jsonrpc":"2.0","id":1,"error":{"message":"missing code"}}',
    ],
)
def test_invalid_request_shapes(raw):
    with pytest.raises(JsonRpcError) as exc_info:
        parse_message(raw)
    assert exc_info.value.code == INVALID_REQUEST


def test_serialize_request_round_trips():
    req = JsonRpcRequest(id=1, method="ping", params={})
    line = serialize(req)
    assert "\n" not in line
    parsed = parse_message(line)
    assert isinstance(parsed, JsonRpcRequest)
    assert parsed.id == 1 and parsed.method == "ping"


def test_notification_omits_id_field():
    note = JsonRpcNotification(method="notifications/initialized")
    wire = note.to_wire()
    assert "id" not in wire
