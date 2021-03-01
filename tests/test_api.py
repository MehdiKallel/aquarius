#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0
import json
import lzma

from eth_account.messages import defunct_hash_message
from web3 import Web3

from aquarius.app.util import validate_date_format
from aquarius.events.constants import EVENT_METADATA_CREATED
from aquarius.run import get_status, get_version
from tests.ddo_samples_invalid import json_dict_no_valid_metadata
from tests.ddos.ddo_sample_updates import json_before, json_valid
from tests.helpers import (
    get_event,
    get_web3,
    new_ddo,
    send_create_update_tx,
    test_account1,
)


def sign_message(account, message_str):
    msg_hash = defunct_hash_message(text=message_str)
    full_signature = account.sign_message(msg_hash)
    return full_signature.signature.hex()


def get_ddo(client, base_ddo_url, did):
    rv = client.get(base_ddo_url + f"/{did}", content_type="application/json")
    fetched_ddo = json.loads(rv.data.decode("utf-8"))
    return fetched_ddo


def run_request_get_data(client_method, url, data=None):
    _response = run_request(client_method, url, data)
    print(f"response: {_response}")
    if _response and _response.data:
        return json.loads(_response.data.decode("utf-8"))

    return None


def run_request(client_method, url, data=None):
    if data is None:
        _response = client_method(url, content_type="application/json")
    else:
        _response = client_method(
            url, data=json.dumps(data), content_type="application/json"
        )

    return _response


def test_version(client):
    """Test version in root endpoint"""
    rv = client.get("/")
    assert json.loads(rv.data.decode("utf-8"))["software"] == "Aquarius"
    assert json.loads(rv.data.decode("utf-8"))["version"] == get_version()


def test_health(client):
    """Test health check endpoint"""
    rv = client.get("/health")
    assert rv.data.decode("utf-8") == get_status()[0]


def test_post_with_no_valid_ddo(client, base_ddo_url, events_object):
    block = get_web3().eth.blockNumber
    ddo = new_ddo(test_account1, get_web3(), f"dt.{block}", json_dict_no_valid_metadata)
    ddo_string = json.dumps(dict(ddo.items()))
    _ = send_create_update_tx(
        "create",
        ddo.id,
        bytes([1]),
        lzma.compress(Web3.toBytes(text=ddo_string)),
        test_account1,
    )
    get_event(EVENT_METADATA_CREATED, block, ddo.id)
    events_object.process_current_blocks()
    try:
        published_ddo = get_ddo(client, base_ddo_url, ddo.id)
        assert not published_ddo, (
            "publish should fail, Aquarius validation "
            "should have failed and skipped the "
            f"{EVENT_METADATA_CREATED} event."
        )
    except Exception:
        pass


def test_validate(client_with_no_data, base_ddo_url):
    post = run_request(client_with_no_data.post, base_ddo_url + "/validate", data={})
    assert post.status_code == 200
    assert (
        post.data == b'[{"message":"\'main\' is a required property","path":""}]\n'
    )  # noqa
    post = run_request(
        client_with_no_data.post, base_ddo_url + "/validate", data=json_valid
    )
    assert post.data == b"true\n"


def test_validate_remote(client_with_no_data, base_ddo_url):
    post = run_request(
        client_with_no_data.post, base_ddo_url + "/validate-remote", data={}
    )
    assert post.status_code == 400
    assert post.data == b'{"message":"Invalid DDO format."}\n'
    post = run_request(
        client_with_no_data.post, base_ddo_url + "/validate-remote", data=json_before
    )

    assert post.data == b"true\n"


def test_date_format_validator():
    date = "2016-02-08T16:02:20Z"
    assert validate_date_format(date) == (None, None)


def test_invalid_date():
    date = "XXXX"
    assert validate_date_format(date) == (
        "Incorrect data format, should be '%Y-%m-%dT%H:%M:%SZ'",
        400,
    )


def test_resolveByDtAddress(client_with_no_data, base_ddo_url, events_object):
    client = client_with_no_data
    block = get_web3().eth.blockNumber
    _ddo = json_before.copy()
    ddo = new_ddo(test_account1, get_web3(), f"dt.{block}", _ddo)
    send_create_update_tx(
        "create",
        ddo["id"],
        bytes([1]),
        lzma.compress(Web3.toBytes(text=json.dumps(dict(ddo)))),
        test_account1,
    )
    get_event(EVENT_METADATA_CREATED, block, ddo["id"])
    events_object.process_current_blocks()
    assert (
        len(
            run_request_get_data(
                client.post,
                base_ddo_url + "/query",
                {
                    "query": {
                        "query_string": {
                            "query": _ddo["dataToken"],
                            "default_field": "dataToken",
                        }
                    }
                },
            )["results"]
        )
        > 0
    )
