import uuid
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from platform_core.tenancy import tenant_scope


class Command(BaseCommand):
    help = "Create synthetic records only in explicitly enabled demo mode"

    def handle(self, *args, **options):
        if not settings.DEMO:
            raise CommandError("Demo seeding requires UNUM_DEMO=1")
        with tenant_scope("demo"):
            self.seed()

    @transaction.atomic
    def seed(self):
        if settings.SERVICE == "inventory":
            from services.inventory.models import Asset
            for r in range(32):
                for n in range(4):
                    i = r * 4 + n
                    Asset.objects.get_or_create(id=f"asset-{i:03}", defaults={
                        "tenant": "demo", "site": "ashburn" if r < 24 else "dallas", "name": f"{['app', 'db', 'compute', 'storage'][n]}-{r + 1:02}-{n + 1:02}",
                        "manufacturer": ["Dell", "HPE", "Dell", "NetApp"][n],
                        "model": ["PowerEdge R750", "ProLiant DL380", "PowerEdge R760", "AFF A400"][n],
                        "serial": f"DEMO{i:06}", "asset_tag": f"UD-{10000 + i}",
                        "height_u": [2, 2, 2, 4][n], "watts": [480, 620, 740, 880][n]})
        elif settings.SERVICE == "placement":
            from services.placement.models import Authority, Placement, Rack, Room
            for room_id, name in (("hall-a", "Data Hall A"), ("hall-b", "Data Hall B")):
                Room.objects.get_or_create(id=room_id, defaults={"tenant": "demo", "site": "ashburn", "site_name": "Ashburn, VA", "name": name})
            Authority.objects.get_or_create(site="ashburn", defaults={"tenant": "demo"})
            Room.objects.get_or_create(id="dallas-hall-a", defaults={"tenant": "demo", "site": "dallas", "site_name": "Dallas, TX", "name": "Data Hall A"})
            Authority.objects.get_or_create(site="dallas", defaults={"tenant": "demo"})
            for site, state, city in (("ashburn", "Virginia", "Ashburn"), ("dallas", "Texas", "Dallas")):
                Room.objects.filter(tenant="demo", site=site, region="").update(region="AMER", country="United States", state=state, city=city, room_type="data_hall")
            for room_id, name, kind in (("dallas-office-mdf", "Office MDF", "mdf"), ("dallas-office-idf", "Floor 2 IDF", "idf")):
                Room.objects.get_or_create(id=room_id, defaults={"tenant": "demo", "site": "dallas", "site_name": "Dallas, TX", "name": name, "region": "AMER", "country": "United States", "state": "Texas", "city": "Dallas", "room_type": kind})
                Rack.objects.get_or_create(id=room_id + "-cabinet", defaults={"tenant": "demo", "room_id": room_id, "label": kind.upper() + "-01", "x": 0, "y": 0})
            for r in range(32):
                rack, _ = Rack.objects.get_or_create(id=f"rack-{r:02}", defaults={
                    "tenant": "demo", "room_id": "hall-a" if r < 16 else "hall-b" if r < 24 else "dallas-hall-a",
                    "label": f"{chr(65 + r // 8)}{r % 8 + 1:02}", "x": r % 8, "y": (r // 8) % 2})
                for n in range(4):
                    Placement.objects.get_or_create(asset_id=f"asset-{r * 4 + n:03}", defaults={
                        "tenant": "demo", "rack": rack, "u": [3, 9, 17, 29][n],
                        "height_u": [2, 2, 2, 4][n], "owner": "unum" if r % 3 == 0 or r >= 24 else "nlyte-lab"})
        elif settings.SERVICE == "synchronization":
            from services.synchronization.models import Conflict, Connection
            Connection.objects.get_or_create(id="nlyte-lab", defaults={"tenant": "demo", "site": "ashburn",
                "label": "Nlyte • awaiting configuration", "state": "unconfigured", "capabilities": {"read": False, "write": False}})
            Conflict.objects.get_or_create(id=uuid.UUID("a0000000-0000-4000-8000-000000000001"), defaults={
                "tenant": "demo", "site": "ashburn", "entity": "asset-004", "field": "asset_tag",
                "owner": "nlyte-lab", "baseline": "UD-10004",
                "candidates": {"nlyte-lab": "NL-10004", "unum": "UD-20004"}})
        self.stdout.write("Synthetic " + settings.SERVICE + " records ready")
