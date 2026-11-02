import hashlib
import hmac

from slidecold import verify_webhook_signature

SECRET = "whsec_test123"
BODY = '{"event":"lead.imported","data":{"recipientUsername":"alice"},"timestamp":1700000000000}'
SIG = hmac.new(SECRET.encode(), BODY.encode(), hashlib.sha256).hexdigest()


def test_valid_signature():
    assert verify_webhook_signature(BODY, SIG, SECRET)
    assert verify_webhook_signature(BODY.encode(), SIG.upper(), SECRET)


def test_invalid_signature():
    assert not verify_webhook_signature(BODY, SIG, "whsec_other")
    assert not verify_webhook_signature(BODY + " ", SIG, SECRET)
    assert not verify_webhook_signature(BODY, "", SECRET)
    assert not verify_webhook_signature(BODY, "zz" + SIG[2:], SECRET)
