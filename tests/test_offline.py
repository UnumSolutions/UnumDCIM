import pytest
from platform_core.offline import issue_grant, verify_grant, operation_state, MAX_OFFLINE_SECONDS

KEY=b"synthetic-test-key-not-a-secret-123456"


def grant():
    return issue_grant(actor="operator", tenant="org", site="site-a", permissions=["placement.propose"],
                       authority_epoch=7, now=1000, key=KEY, mfa_verified=True)


def verify(token, **overrides):
    options=dict(tenant="org", site="site-a", permission="placement.propose", authority_epoch=7,
                 now=1001, key=KEY, revoked_ids=set()) | overrides
    return verify_grant(token, **options)


def test_grant_expires_at_72_hour_boundary():
    token=grant()
    assert verify(token, now=1000+MAX_OFFLINE_SECONDS-1)["actor"]=="operator"
    with pytest.raises(ValueError):verify(token, now=1000+MAX_OFFLINE_SECONDS)


def test_offline_grant_scope_epoch_and_permissions():
    token=grant()
    for override in ({"tenant":"other"},{"site":"other"},{"authority_epoch":8},{"permission":"plugin.install"},{"now":999}):
        with pytest.raises(ValueError):verify(token,**override)


def test_revocation_and_tampering():
    token=grant()
    with pytest.raises(ValueError):verify(token, revoked_ids={verify(token)["id"]})
    with pytest.raises(ValueError):verify(token[:-1]+('0' if token[-1]!='0' else '1'))


def test_no_mfa_no_offline_grant():
    with pytest.raises(ValueError):issue_grant(actor="a",tenant="t",site="s",permissions=[],authority_epoch=1,now=0,key=KEY,mfa_verified=False)


def test_nlyte_owned_operations_never_become_locally_authoritative():
    assert operation_state(local_authority=True,epoch=1,expected_epoch=1,connected=False,owner="nlyte")=="pending_owner_confirmation"
    assert operation_state(local_authority=True,epoch=1,expected_epoch=1,connected=False,owner="unum")=="eligible_for_local_workflow"
    assert operation_state(local_authority=True,epoch=2,expected_epoch=1,connected=False,owner="unum")=="pending_site_authority"
