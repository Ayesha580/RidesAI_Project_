import base64
import logging
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from standardwebhooks.webhooks import Webhook, WebhookVerificationError

from accounts.permissions import IsOwner, IsSuperAdmin
from companies.models import Company, Plan
from companies.plans import get_default_plan
from .models import CheckoutSession, PaymentTransaction, WebhookEvent, ManualPayment
from .services import refresh_grace_state, sync_company_from_subscription, approve_manual_payment, consume_company_message, refresh_message_period, get_access_state

logger = logging.getLogger(__name__)

POLAR_API_URL = settings.POLAR_API_URL
DEAD_STATUSES = ("canceled", "cancelled", "revoked", "incomplete_expired")

BILLING_PERMS = [IsAuthenticated, IsOwner]


def _headers(json_body=True):
    h = {
        "Authorization": f"Bearer {settings.POLAR_ACCESS_TOKEN}",
        "Polar-Version": "2026-04",
    }
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _polar_error(message, e):
    resp = getattr(e, "response", None)
    logger.error("POLAR ERROR: %s | %s | %s", message, e, resp.text if resp is not None else None)
    return Response(
        {"error": message, "detail": "The payment provider request failed. Please try again later."},
        status=status.HTTP_502_BAD_GATEWAY,
    )


def _get_subscription(company):
    r = requests.get(
        f"{POLAR_API_URL}/v1/subscriptions/{company.polar_subscription_id}",
        headers=_headers(False),
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


class PublicPlansAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        if getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
            return Response([])
        plans = Plan.objects.filter(is_active=True, polar_product_id__gt="").order_by("price", "name", "billing_cycle")
        return Response([{
            "id": plan.pk,
            "name": plan.name,
            "billing_cycle": plan.billing_cycle,
            "price": str(plan.price),
            "currency": plan.currency,
        } for plan in plans])


# ------------------------------------------------------------
# OVERVIEW (trial + subscription dono)
# ------------------------------------------------------------
class BillingOverviewAPIView(APIView):
    permission_classes = BILLING_PERMS

    def get(self, request):
        company = request.user.company
        if not company:
            return Response({"error": "Company not found."}, status=404)

        refresh_grace_state(company)
        if getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
            company.refresh_from_db()
            refresh_message_period(company)
            now = timezone.now()
            expiry = company.access_expires_at or company.trial_ends_at
            days_left = max((expiry - now).days, 0) if expiry else None
            latest_payment = company.manual_payments.first()
            return Response({
                "mode": "manual",
                "payment_instructions": getattr(settings, "MANUAL_PAYMENT_INSTRUCTIONS", "Please contact the administrator for payment details."),
                "status": ("pending_approval" if not company.is_approved else "suspended" if company.payment_status == Company.PAYMENT_SUSPENDED else "past_due" if company.payment_status == Company.PAYMENT_PAST_DUE else "payment_pending" if latest_payment and latest_payment.status == "pending" else "payment_rejected" if latest_payment and latest_payment.status == "rejected" else "initial_access" if not latest_payment else "active"),
                "payment_status": company.payment_status,
                "access_expires_at": company.access_expires_at,
                "next_due_date": company.renewal_due_at or expiry,
                "grace_ends_at": company.grace_ends_at,
                "days_left": days_left,
                "message_limit": company.message_limit,
                "messages_used": company.messages_used,
                "messages_remaining": max(company.message_limit - company.messages_used, 0),
                "latest_payment": ({"status": latest_payment.status, "created_at": latest_payment.created_at, "amount": str(latest_payment.amount) if latest_payment.amount is not None else None, "currency": latest_payment.currency} if latest_payment else None),
                "business_email_address": company.business_email_address,
                "business_email_domain": company.business_email_domain,
                "business_email_setup_status": company.business_email_setup_status,
            })
        plan = company.plan or get_default_plan()
        if not company.polar_subscription_id:
            if not company.trial_ends_at:
                return Response({
                    "status": "payment_required",
                    "plan": plan.name if plan else None,
                    "can_subscribe": True,
                })
            now = timezone.now()
            expired = now >= company.trial_ends_at
            return Response({
                "status": "trial_expired" if expired else "trialing",
                "payment_status": company.payment_status,
                "plan": plan.name if plan else None,
                "billing_cycle": plan.billing_cycle if plan else None,
                "amount_due": plan.price if plan else None,
                "next_due_date": company.trial_ends_at,
                "days_left": max((company.trial_ends_at - now).days, 0),
                "cancel_at_period_end": False,
                "can_pay_early": False,
                "can_subscribe": True,
                "polar_subscription_id": company.polar_subscription_id,
            })

        try:
            sub = _get_subscription(company)
        except requests.exceptions.RequestException as e:
            return _polar_error("Failed to fetch subscription.", e)

        period_end = sub.get("current_period_end")
        days_left = None
        if period_end:
            end_dt = parse_datetime(period_end)
            if end_dt:
                days_left = (end_dt - timezone.now()).days

        cancel_at_period_end = sub.get("cancel_at_period_end", False)

        return Response({
            "status": "canceling" if cancel_at_period_end else sub.get("status"),
            "payment_status": company.payment_status,
            "plan": plan.name if plan else None,
            "billing_cycle": plan.billing_cycle if plan else None,
            "amount_due": plan.price if plan else None,
            "next_due_date": period_end,
            "days_left": days_left,
            "cancel_at_period_end": cancel_at_period_end,
            "can_subscribe": sub.get("status") in DEAD_STATUSES,
            "grace_ends_at": company.grace_ends_at,
            "payment_failed_at": company.payment_failed_at,
            "polar_subscription_id": None,
        })

class SelectPlanAPIView(APIView):
    """Shown after OTP verification. GET = registration payload + plans, POST = choose plan."""
    permission_classes = BILLING_PERMS

    def get(self, request):
        company = request.user.company
        if not company:
            return Response({"error": "Company not found."}, status=404)
        if get_access_state(company) == "ok":
            return Response({"redirect": "/owner/dashboard", "already_active": True})
        plans = Plan.objects.filter(is_active=True, polar_product_id__gt="").order_by("price", "name", "billing_cycle")
        u = request.user
        return Response({
            "registration": {
                "business_name": company.name,
                "business_type": company.business_type,
                "owner_name": u.first_name,
                "username": u.username,
                "email": u.email,
                "phone": company.phone,
            },
            "selected_plan_id": company.plan_id,
            "plans": [{
                "id": p.pk, "name": p.name, "billing_cycle": p.billing_cycle,
                "price": str(p.price), "currency": p.currency,
            } for p in plans],
        })

    def post(self, request):
        company = request.user.company
        if not company:
            return Response({"error": "Company not found."}, status=404)
        if company.polar_subscription_id:
            return Response({"error": "A subscription already exists."}, status=400)
        plan = Plan.objects.filter(
            pk=request.data.get("plan_id"), is_active=True, polar_product_id__gt=""
        ).first()
        if not plan:
            return Response({"error": "Please select a valid plan."}, status=400)
        company.plan = plan
        company.save(update_fields=["plan"])
        return Response({"success": True, "plan": plan.name, "next": "checkout"})


class CustomerSessionAPIView(APIView):
    permission_classes = BILLING_PERMS

    def post(self, request):
        if getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
            return Response({"error": "Online subscription checkout is disabled for this client."}, status=404)
        company = request.user.company
        if not company:
            return Response({"error": "Company not found."}, status=404)
        if not request.user.email_verified:
            return Response({"error": "Please verify your email address before starting checkout."}, status=403)
        if not settings.POLAR_ACCESS_TOKEN:
            return Response({"error": "Online payments are not configured. Please contact support."}, status=503)

        portal_only = bool(request.data.get("portal"))

        subscription = None
        if company.polar_subscription_id:
            try:
                r = requests.get(
                    f"{POLAR_API_URL}/v1/subscriptions/{company.polar_subscription_id}",
                    headers=_headers(),
                    timeout=20,
                )
                if r.status_code == 200:
                    subscription = r.json()
                elif r.status_code != 404:
                    r.raise_for_status()
                else:
                    logger.warning(
                        "Polar subscription %s not found (404) for company %s. "
                        "Check sandbox/production token mismatch.",
                        company.polar_subscription_id, company.pk,
                    )
            except requests.exceptions.RequestException as e:
                return _polar_error("Failed to fetch subscription.", e)

        no_active_sub = not subscription or subscription.get("status") in DEAD_STATUSES

        if no_active_sub and portal_only:
            return Response(
                {"error": "No active subscription found. Please complete a payment first."},
                status=400,
            )
        if no_active_sub:
            if not company.plan:
                return Response({"error": "Company plan not found."}, status=400)

            plan_name = company.plan.name
            billing = company.plan.billing_cycle
            product_id = company.plan.polar_product_id

            if not product_id:
                return Response(
                    {"error": "Configured Polar product not found.", "plan": plan_name, "billing": billing},
                    status=400,
                )

            recent_checkout = CheckoutSession.objects.filter(
                company=company,
                user=request.user,
                plan=company.plan,
                status="created",
                created_at__gte=timezone.now() - timedelta(minutes=20),
            ).order_by("-created_at").first()
            if recent_checkout:
                return Response({
                    "success": True,
                    "action": "new_subscription",
                    "checkout_id": recent_checkout.polar_checkout_id,
                    "checkout_url": recent_checkout.checkout_url,
                    "reused": True,
                })

            frontend_url = settings.SITE_URL.rstrip("/")
            payload = {
                "products": [product_id],
                "success_url": f"{frontend_url}/payment-success?checkout_id={{CHECKOUT_ID}}",
                "customer_email": request.user.email,
                "metadata": {
                    "company_id": str(company.pk),
                    "plan": plan_name,
                    "billing": billing,
                },
            }

            try:
                r = requests.post(
                    f"{POLAR_API_URL}/v1/checkouts/",
                    headers=_headers(),
                    json=payload,
                    timeout=20,
                )
                r.raise_for_status()
                checkout = r.json()
            except requests.exceptions.RequestException as e:
                return _polar_error("Failed to create checkout.", e)

            if not checkout.get("url") or not checkout.get("id"):
                return Response(
                    {"error": "Polar did not return checkout details.", "polar_response": checkout},
                    status=502,
                )

            CheckoutSession.objects.update_or_create(
                polar_checkout_id=checkout["id"],
                defaults={
                    "company": company,
                    "plan": company.plan,
                    "user": request.user,
                    "checkout_url": checkout["url"],
                    "customer_email": request.user.email,
                    "status": "created",
                    "metadata": payload["metadata"],
                },
            )
            return Response({
                "success": True,
                "action": "new_subscription",
                "checkout_id": checkout["id"],
                "checkout_url": checkout["url"],
            })

        # ---- Customer portal ----
        customer_id = subscription.get("customer_id")
        if not customer_id:
            return Response({"error": "Customer ID not found."}, status=400)

        try:
            r = requests.get(
                f"{POLAR_API_URL}/v1/members/",
                headers=_headers(),
                params={"customer_id": customer_id},
                timeout=20,
            )
            r.raise_for_status()
            members = r.json().get("items", [])
        except requests.exceptions.RequestException as e:
            return _polar_error("Failed to fetch customer members.", e)

        member_id = next(
            (m.get("id") for m in members if m.get("role") == "owner"),
            members[0].get("id") if members else None,
        )

        session_payload = {"customer_id": customer_id}
        if member_id:
            session_payload["member_id"] = member_id

        try:
            r = requests.post(
                f"{POLAR_API_URL}/v1/customer-sessions",
                headers=_headers(),
                json=session_payload,
                timeout=20,
            )
            r.raise_for_status()
            session_data = r.json()
        except requests.exceptions.RequestException as e:
            return _polar_error("Failed to create customer session.", e)

        return Response({
            "success": True,
            "action": "customer_portal",
            "customer_id": customer_id,
            "member_id": member_id,
            "session": session_data,
        })


class CompleteRenewalAPIView(APIView):
    permission_classes = BILLING_PERMS

    def post(self, request):
        if getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
            return Response({"error": "Automated subscription management is disabled for this client."}, status=404)
        company = request.user.company
        checkout_id = request.data.get("checkout_id")

        if not company or not checkout_id:
            return Response({"error": "Company and checkout_id are required."}, status=400)

        try:
            r = requests.get(
                f"{POLAR_API_URL}/v1/checkouts/{checkout_id}",
                headers=_headers(False),
                timeout=20,
            )
            r.raise_for_status()
            checkout = r.json()

            metadata = checkout.get("metadata") or {}
            local_checkout = CheckoutSession.objects.filter(
                polar_checkout_id=checkout_id, company=company, user=request.user
            ).first()
            if str(metadata.get("company_id")) != str(company.pk):
                return Response({"error": "Checkout does not belong to this account."}, status=403)
            if local_checkout and local_checkout.user_id != request.user.id:
                return Response({"error": "Checkout does not belong to this account."}, status=403)

            if checkout.get("status") != "succeeded":
                return Response({"error": "Payment has not been completed."}, status=400)

            subscription_id = checkout.get("subscription_id")
            if not subscription_id:
                customer_id = checkout.get("customer_id")
                product_id = checkout.get("product_id")

                for attempt in range(3):
                    lr = requests.get(
                        f"{POLAR_API_URL}/v1/subscriptions/",
                        headers=_headers(False),
                        params={"customer_id": customer_id, "product_id": product_id, "limit": 100},
                        timeout=20,
                    )
                    lr.raise_for_status()
                    matched = next(
                        (
                            s for s in lr.json().get("items", [])
                            if str(s.get("checkout_id")) == str(checkout_id)
                            and s.get("status") in ("active", "trialing")
                        ),
                        None,
                    )
                    if matched:
                        subscription_id = matched["id"]
                        break
                    if attempt < 2:
                        time.sleep(2)

            if not subscription_id:
                return Response(
                    {
                        "success": False,
                        "pending": True,
                        "error": "Payment succeeded but subscription not found yet. "
                                 "Do not pay again; try again in a moment.",
                        "checkout_id": checkout_id,
                    },
                    status=202,
                )

            sr = requests.get(
                f"{POLAR_API_URL}/v1/subscriptions/{subscription_id}",
                headers=_headers(False),
                timeout=20,
            )
            sr.raise_for_status()
            subscription = sr.json()

        except requests.exceptions.RequestException as e:
            return _polar_error("Failed to verify payment.", e)

        if str(subscription.get("checkout_id")) != str(checkout_id):
            return Response({"error": "Subscription does not match this checkout."}, status=409)

        if subscription.get("status") not in ("active", "trialing"):
            return Response(
                {"error": "The subscription is not active.", "subscription_status": subscription.get("status")},
                status=409,
            )
        if Company.objects.filter(polar_subscription_id=subscription_id).exclude(pk=company.pk).exists():
            return Response(
                {"error": "This subscription is already linked to another company."},
                status=409,
            )
        selected_plan = local_checkout.plan if local_checkout else company.plan
        company.polar_subscription_id = subscription_id
        if selected_plan:
            company.plan = selected_plan
        company.save(update_fields=["polar_subscription_id", "plan"])
        if local_checkout:
            local_checkout.status = "succeeded"
            local_checkout.save(update_fields=["status", "updated_at"])

        sync_company_from_subscription(company, subscription)
        company.refresh_from_db()

        return Response({
            "success": True,
            "message": "Payment verified. Your business access is subject to the separate admin approval status.",
            "payment_status": company.payment_status,
            "subscription_id": company.polar_subscription_id,
            "redirect": "/owner/dashboard",
        })


# ------------------------------------------------------------
# CANCEL / RESUME
# ------------------------------------------------------------
class CancelSubscriptionAPIView(APIView):
    permission_classes = BILLING_PERMS

    def post(self, request):
        if getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
            return Response({"error": "Automated subscription management is disabled for this client."}, status=404)
        company = request.user.company
        if not company or not company.polar_subscription_id:
            return Response({"error": "No subscription found."}, status=400)

        url = f"{POLAR_API_URL}/v1/subscriptions/{company.polar_subscription_id}"

        try:
            cur = requests.get(url, headers=_headers(), timeout=20)
            cur.raise_for_status()
            current = cur.json()

            if current.get("status") in DEAD_STATUSES:
                sync_company_from_subscription(company, current)
                return Response({"success": True, "message": "Subscription is already canceled."})

            if current.get("cancel_at_period_end"):
                return Response({"success": True, "message": "Already scheduled for cancellation."})

            r = requests.patch(url, headers=_headers(), json={"cancel_at_period_end": True}, timeout=20)
            r.raise_for_status()
            sub = r.json()
        except requests.exceptions.RequestException as e:
            return _polar_error("Subscription cancellation failed.", e)

        sync_company_from_subscription(company, sub)
        return Response({"success": True, "message": "Cancellation scheduled.", "subscription": sub})


class ResumeSubscriptionAPIView(APIView):
    permission_classes = BILLING_PERMS

    def post(self, request):
        if getattr(settings, "RIDESAI_SINGLE_CLIENT_MODE", False):
            return Response({"error": "Automated subscription management is disabled for this client."}, status=404)
        company = request.user.company
        if not company or not company.polar_subscription_id:
            return Response({"error": "No subscription found."}, status=400)

        url = f"{POLAR_API_URL}/v1/subscriptions/{company.polar_subscription_id}"

        try:
            cur = requests.get(url, headers=_headers(), timeout=20)
            cur.raise_for_status()
            if cur.json().get("status") in DEAD_STATUSES:
                return Response(
                    {"error": "Subscription has already ended. Please subscribe again."},
                    status=400,
                )

            r = requests.patch(url, headers=_headers(), json={"cancel_at_period_end": False}, timeout=20)
            r.raise_for_status()
            sub = r.json()
        except requests.exceptions.RequestException as e:
            return _polar_error("Failed to resume subscription.", e)

        sync_company_from_subscription(company, sub)
        return Response({"success": True, "message": "Subscription resumed.", "subscription": sub})


class PolarWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not settings.POLAR_WEBHOOK_SECRET:
            logger.error("Polar webhook rejected because POLAR_WEBHOOK_SECRET is not configured.")
            return Response({"error": "Webhook is not configured."}, status=503)

        secret = base64.b64encode(settings.POLAR_WEBHOOK_SECRET.encode()).decode()
        headers = {
            "webhook-id": request.headers.get("webhook-id", ""),
            "webhook-timestamp": request.headers.get("webhook-timestamp", ""),
            "webhook-signature": request.headers.get("webhook-signature", ""),
        }
        try:
            Webhook(secret).verify(request.body, headers)
        except WebhookVerificationError:
            return Response({"error": "Invalid signature"}, status=400)

        event_id = headers["webhook-id"]
        event_type = request.data.get("type", "")
        data = request.data.get("data", {})
        if not event_id or not event_type:
            return Response({"error": "Missing webhook event identifiers."}, status=400)

        event, created = WebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={"event_type": event_type, "payload": request.data},
        )
        if not created and event.processed:
            return Response({"ok": True, "duplicate": True})

        try:
            if event_type.startswith("subscription."):
                sub_id = data.get("id")
                company = Company.objects.filter(polar_subscription_id=sub_id).first()
                if not company:
                    company_id = (data.get("metadata") or {}).get("company_id")
                    if company_id and str(company_id).isdigit():
                        candidate = Company.objects.filter(pk=int(company_id)).first()
                        if candidate and (not candidate.polar_subscription_id or candidate.polar_subscription_id == sub_id):
                            candidate.polar_subscription_id = sub_id
                            candidate.save(update_fields=["polar_subscription_id"])
                            company = candidate
                if company:
                    sync_company_from_subscription(company, data)
                    CheckoutSession.objects.filter(
                        company=company,
                        polar_checkout_id=data.get("checkout_id", ""),
                    ).update(status="succeeded")

            elif event_type.startswith("checkout."):
                metadata = data.get("metadata") or {}
                company_id = metadata.get("company_id")
                company = Company.objects.filter(pk=company_id).first() if str(company_id or "").isdigit() else None
                subscription_id = data.get("subscription_id")
                if company and subscription_id and not company.polar_subscription_id:
                    company.polar_subscription_id = subscription_id
                    company.save(update_fields=["polar_subscription_id"])
                if company and data.get("status") in ("succeeded", "confirmed"):
                    CheckoutSession.objects.filter(
                        company=company, polar_checkout_id=data.get("id", "")
                    ).update(status="succeeded")

            elif event_type.startswith("order."):
                metadata = data.get("metadata") or {}
                checkout_id = data.get("checkout_id", "")
                local_checkout = CheckoutSession.objects.filter(polar_checkout_id=checkout_id).select_related("company", "plan").first()
                company_id = metadata.get("company_id")
                company = (
                    Company.objects.filter(pk=company_id).first()
                    if str(company_id or "").isdigit()
                    else (local_checkout.company if local_checkout else None)
                )
                if company and (company.plan or local_checkout):
                    plan = local_checkout.plan if local_checkout else company.plan
                    order_id = data.get("id")
                    if order_id:
                        PaymentTransaction.objects.update_or_create(
                            polar_order_id=order_id,
                            defaults={
                                "company": company,
                                "plan": plan,
                                "polar_checkout_id": checkout_id,
                                "polar_subscription_id": data.get("subscription_id", ""),
                                "amount": data.get("total_amount") or data.get("amount"),
                                "currency": data.get("currency", ""),
                                "status": data.get("status", "paid"),
                                "raw_payload": data,
                            },
                        )

            event.processed = True
            event.processed_at = timezone.now()
            event.processing_error = ""
            event.save(update_fields=["processed", "processed_at", "processing_error"])
        except Exception as exc:
            logger.exception("Polar webhook processing failed for event %s", event_id)
            event.processing_error = str(exc)[:4000]
            event.save(update_fields=["processing_error"])
            return Response({"error": "Webhook processing failed; provider may retry."}, status=500)

        return Response({"ok": True})


class ManualPaymentSubmitAPIView(APIView):
    # Keep this endpoint available while an account is past due or suspended.
    permission_classes = [IsAuthenticated, IsOwner]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        company = request.user.company
        if not company:
            return Response({"error": "Company not found."}, status=404)
        if company.manual_payments.filter(status="pending").exists():
            return Response({"error": "A payment is already awaiting review."}, status=400)
        amount_value = request.data.get("amount") or None
        if amount_value is not None:
            from decimal import Decimal, InvalidOperation
            try:
                amount_value = Decimal(str(amount_value))
                if amount_value < 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                return Response({"error": "Enter a valid non-negative payment amount."}, status=400)
        payment = ManualPayment.objects.create(
            company=company, submitted_by=request.user,
            amount=amount_value,
            currency=(request.data.get("currency") or "USD").upper(),
            payment_reference=str(request.data.get("payment_reference", ""))[:120],
            proof=request.FILES.get("proof"), notes=str(request.data.get("notes", "")),
        )
        return Response({"message": "Payment submitted for admin review.", "payment_id": payment.pk, "status": payment.status}, status=201)


class BusinessEmailSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request):
        c = request.user.company
        if not c:
            return Response({"error": "Company not found."}, status=404)
        return Response({"email_address": c.business_email_address, "domain": c.business_email_domain, "status": c.business_email_setup_status})

    def put(self, request):
        c = request.user.company
        if not c:
            return Response({"error": "Company not found."}, status=404)
        email_address = str(request.data.get("email_address", "")).strip().lower()
        domain = str(request.data.get("domain", "")).strip().lower()
        setup_status = request.data.get("status", "in_progress")
        if setup_status not in ("not_started", "in_progress", "completed"):
            return Response({"error": "Invalid setup status."}, status=400)
        if email_address and "@" not in email_address:
            return Response({"error": "Enter a valid business email address."}, status=400)
        c.business_email_address = email_address
        c.business_email_domain = domain
        c.business_email_setup_status = setup_status
        c.save(update_fields=["business_email_address", "business_email_domain", "business_email_setup_status"])
        return Response({"message": "Business email setup details saved."})


class ManualPaymentAdminAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        payments = ManualPayment.objects.select_related("company", "submitted_by").order_by("-created_at")
        return Response([{
            "id": p.pk, "company_id": p.company_id, "company": p.company.name,
            "submitted_by": p.submitted_by.email, "amount": str(p.amount) if p.amount is not None else None,
            "currency": p.currency, "reference": p.payment_reference, "status": p.status,
            "proof_url": request.build_absolute_uri(p.proof.url) if p.proof else None,
            "created_at": p.created_at, "notes": p.notes,
        } for p in payments])

    def post(self, request, payment_id):
        payment = ManualPayment.objects.select_related("company").filter(pk=payment_id).first()
        if not payment:
            return Response({"error": "Payment not found."}, status=404)
        if payment.status != "pending":
            return Response({"error": "This payment has already been reviewed."}, status=409)
        action = request.data.get("action")
        if action == "approve":
            approve_manual_payment(payment, request.user)
        elif action == "reject":
            payment.status = "rejected"
            payment.reviewed_by = request.user
            payment.reviewed_at = timezone.now()
            payment.admin_note = str(request.data.get("admin_note", ""))
            payment.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])
        else:
            return Response({"error": "Action must be approve or reject."}, status=400)
        return Response({"message": f"Payment {payment.status}.", "status": payment.status})


class ConsumeMessageAPIView(APIView):
    """Quota hook for the AI agent; call once for each accepted customer message."""
    permission_classes = [IsAuthenticated, IsOwner]

    def post(self, request):
        company = request.user.company
        if not company:
            return Response({"error": "Company not found."}, status=404)
        if get_access_state(company) != "ok":
            return Response({"error": "Account access is not active.", "code": "access_inactive"}, status=403)
        try:
            company = consume_company_message(company)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError
            if isinstance(exc, ValidationError):
                return Response(exc.detail, status=429)
            raise
        return Response({"messages_used": company.messages_used, "message_limit": company.message_limit, "messages_remaining": max(company.message_limit-company.messages_used, 0)})
