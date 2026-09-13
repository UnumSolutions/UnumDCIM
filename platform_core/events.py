from django.db import transaction
from platform_core.models import Inbox
from platform_core.tenancy import tenant_scope
from uuid import UUID


def validate_event(event, *, trusted_tenant):
    """Match broker data to the tenant authorized by the consumer configuration."""
    required = {"event_id", "tenant", "site", "producer", "entity", "revision", "authority_epoch", "correlation_id", "data"}
    if not isinstance(event, dict) or event.get("contract") != "unum.event/1" or not required <= event.keys():
        raise ValueError("Unsupported or incomplete event")
    if not isinstance(trusted_tenant, str) or not trusted_tenant.strip() or event["tenant"] != trusted_tenant:
        raise ValueError("Event tenant does not match the authorized consumer tenant")
    if not all(isinstance(event[name], str) and event[name].strip()
               for name in ("site", "producer", "entity", "correlation_id")):
        raise ValueError("Invalid event scope or correlation identifier")
    if not all(type(event[name]) is int and event[name] >= 1 for name in ("revision", "authority_epoch")):
        raise ValueError("Invalid event revision or authority epoch")
    if not isinstance(event["data"], dict):
        raise ValueError("Event data must be an object")
    try:
        UUID(event["event_id"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid event identifier") from exc


def consume(event, apply_projection, *, trusted_tenant):
    """Deduplication and projection share one authorized tenant and transaction."""
    validate_event(event, trusted_tenant=trusted_tenant)
    with tenant_scope(trusted_tenant), transaction.atomic():
        _, created = Inbox.objects.get_or_create(event_id=event["event_id"], tenant=trusted_tenant)
        if not created:
            return False
        apply_projection(event)
        return True
