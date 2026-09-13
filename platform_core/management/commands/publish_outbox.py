import asyncio
import json
import nats
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from platform_core.models import Outbox
from platform_core.events import validate_event
from platform_core.tenancy import tenant_scope


class Command(BaseCommand):
    help = "Publish one durable outbox batch; schedule repeatedly or via a worker"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Authorized tenant to publish")

    def handle(self, *args, **options):
        if not settings.NATS_URL:
            raise CommandError("UNUM_NATS_URL is required; no in-memory fallback")
        tenant = options["tenant"]
        with tenant_scope(tenant):
            rows = list(Outbox.objects.filter(tenant=tenant, published_at=None).order_by("created_at")[:100])
        for row in rows:
            validate_event(row.payload, trusted_tenant=tenant)
            if row.payload["event_id"] != str(row.id):
                raise CommandError("Outbox event identifier does not match its stored record")

        def mark_published(row):
            # Async ORM operations use a different thread/connection. Establish
            # its scope explicitly, and keep database transactions off the wire.
            with tenant_scope(tenant):
                Outbox.objects.filter(pk=row.id, tenant=tenant, published_at=None).update(published_at=timezone.now())

        async def publish():
            nc = await asyncio.wait_for(nats.connect(
                settings.NATS_URL, connect_timeout=2, max_reconnect_attempts=1,
                reconnect_time_wait=0, allow_reconnect=False, drain_timeout=2), timeout=3)
            try:
                js = nc.jetstream()
                for row in rows:
                    await js.publish(row.subject, json.dumps(row.payload).encode(), timeout=5,
                                     headers={"Nats-Msg-Id": str(row.id)})
                    # A crash after publish but before this update repeats delivery.
                    # Consumers must deduplicate transactionally using event_id.
                    await sync_to_async(mark_published, thread_sensitive=True)(row)
            finally:
                await nc.drain()
        asyncio.run(publish())
