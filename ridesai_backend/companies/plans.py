from .models import Plan


def get_default_plan():
    """Return an active plan for legacy billing screens without creating records."""
    return Plan.objects.filter(is_active=True).order_by("price", "id").first()
