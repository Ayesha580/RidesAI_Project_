from django.conf import settings
from django.core.management.base import BaseCommand

from companies.models import Company
from operations import evolution_client


class Command(BaseCommand):
    help = "Re-syncs the Evolution API webhook URL (host.docker.internal) for all or a specific company instance."

    def add_arguments(self, parser):
        parser.add_argument("--instance", type=str, default="", help="Optional specific instance name (e.g., company_10)")
        parser.add_argument(
            "--url",
            type=str,
            default="",
            help="Optional override webhook URL (defaults to settings.EVOLUTION_WEBHOOK_URL)",
        )

    def handle(self, *args, **options):
        target_instance = (options.get("instance") or "").strip()
        webhook_url = evolution_client._normalize_webhook_url(
            options.get("url")
            or getattr(settings, "EVOLUTION_WEBHOOK_URL", None)
            or evolution_client.DEFAULT_DOCKER_WEBHOOK_URL
        )

        if target_instance:
            instances = [target_instance]
        else:
            instances = list(
                Company.objects.exclude(whatsapp_instance_name__isnull=True)
                .exclude(whatsapp_instance_name="")
                .values_list("whatsapp_instance_name", flat=True)
            )

        if not instances:
            self.stdout.write(self.style.WARNING("No Evolution instances found to sync."))
            return

        for inst in instances:
            res = evolution_client.set_instance_webhook(inst, webhook_url=webhook_url)
            if res.get("success"):
                self.stdout.write(self.style.SUCCESS(f"Synced '{inst}' -> {res.get('webhook_url')}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed '{inst}': {res.get('error') or res.get('data')}"))
