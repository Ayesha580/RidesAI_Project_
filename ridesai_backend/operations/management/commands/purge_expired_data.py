"""
Management command: python manage.py purge_expired_data [--dry-run] [--company-id=<id>]
Runs company-scoped data retention purges across companies with auto_purge_enabled=True
(or a specific company when --company-id is provided).
"""

from django.core.management.base import BaseCommand

from companies.models import Company
from operations.models import DataRetentionPolicy
from operations.privacy_service import run_company_data_purge


class Command(BaseCommand):
    help = "Purge expired AI chat messages and anonymize expired order PII according to per-company DataRetentionPolicy."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would be purged without modifying data.")
        parser.add_argument("--company-id", type=int, default=None, help="Target a specific company ID.")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        company_id = options.get("company_id")

        if company_id is not None:
            companies = list(Company.objects.filter(pk=company_id))
        else:
            enabled_ids = DataRetentionPolicy.objects.filter(auto_purge_enabled=True).values_list("company_id", flat=True)
            companies = list(Company.objects.filter(pk__in=enabled_ids))

        if not companies:
            self.stdout.write("No eligible companies found for data retention purge.")
            return

        total_msgs = 0
        total_orders = 0
        for comp in companies:
            res = run_company_data_purge(comp, dry_run=dry_run)
            total_msgs += res["purged_messages"]
            total_orders += res["anonymized_orders"]
            prefix = "[DRY-RUN] " if dry_run else ""
            self.stdout.write(
                f"{prefix}{comp.name} (ID {comp.id}): purged_messages={res['purged_messages']}, "
                f"anonymized_orders={res['anonymized_orders']}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed retention purge for {len(companies)} company(s): "
                f"{total_msgs} message(s), {total_orders} order(s)."
            )
        )
