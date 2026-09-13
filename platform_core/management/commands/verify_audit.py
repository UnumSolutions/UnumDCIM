import hashlib
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from platform_core.models import AuditEntry, AuditHead
from platform_core.tenancy import tenant_scope


class Command(BaseCommand):
    help = "Verify a tenant's local chains and their stored heads"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Authorized tenant to verify")

    def handle(self, *args, **options):
        tenant = options["tenant"]
        with tenant_scope(tenant), transaction.atomic():
            heads = AuditHead.objects.filter(tenant=tenant).select_for_update()
            entries = AuditEntry.objects.filter(tenant=tenant)
            if entries.exclude(chain__in=heads.values("chain")).exists():
                raise CommandError("Audit entries exist without a stored head")
            for head in heads:
                previous, sequence = "0" * 64, 0
                for entry in entries.filter(chain=head.chain).order_by("sequence"):
                    expected = hashlib.sha256((previous + json.dumps(entry.payload, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()
                    sequence += 1
                    if (entry.payload.get("tenant") != tenant or entry.sequence != sequence
                            or entry.previous != previous or entry.digest != expected):
                        raise CommandError("Audit chain verification failed: " + head.chain)
                    previous = expected
                if previous != head.digest or sequence != head.sequence:
                    raise CommandError("Audit head mismatch: " + head.chain)
        self.stdout.write("Audit chains verified")
