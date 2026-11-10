from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import StaffRole, User
from companies.models import Company
from .models import Order, DeliveryAssignment, OrderEvent


class BusinessOrderIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(name="Tenant A", business_type="restaurant", is_approved=True, polar_subscription_id="sub_tenant_a")
        self.company_b = Company.objects.create(name="Tenant B", business_type="restaurant", is_approved=True, polar_subscription_id="sub_tenant_b")
        self.owner_a = User.objects.create_user(username="owner_a", password="Pass12345!",
            email="owner-a@example.com", company=self.company_a, role=User.ROLE_OWNER)
        self.owner_b = User.objects.create_user(username="owner_b", password="Pass12345!",
            email="owner-b@example.com", company=self.company_b, role=User.ROLE_OWNER)

    def test_orders_are_isolated_by_company(self):
        Order.objects.create(company=self.company_a, customer_name="A customer")
        Order.objects.create(company=self.company_b, customer_name="B customer")
        self.client.force_authenticate(self.owner_a)
        response = self.client.get("/api/operations/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["customer_name"], "A customer")

    def test_rider_only_sees_assigned_orders_and_can_advance_delivery(self):
        role = StaffRole.objects.create(company=self.company_a, name="Rider", modules=["my_deliveries"],
            permissions=["deliveries.view_assigned", "deliveries.update_status"])
        rider = User.objects.create_user(username="rider_a", password="Pass12345!",
            company=self.company_a, role=User.ROLE_STAFF, staff_role=role)
        assigned = Order.objects.create(company=self.company_a, customer_name="Assigned", status=Order.STATUS_ASSIGNED)
        other = Order.objects.create(company=self.company_a, customer_name="Not assigned")
        DeliveryAssignment.objects.create(company=self.company_a, order=assigned, rider=rider)
        self.client.force_authenticate(rider)
        response = self.client.get("/api/operations/deliveries/my/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data], [assigned.id])
        response = self.client.patch(f"/api/operations/orders/{assigned.id}/status/",
            {"status": "picked_up"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "picked_up")
        response = self.client.patch(f"/api/operations/orders/{other.id}/status/",
            {"status": "picked_up"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(OrderEvent.objects.filter(order=assigned, to_status="picked_up").exists())

    def test_rider_cannot_change_business_order_to_cancelled(self):
        role = StaffRole.objects.create(company=self.company_a, name="Rider 2", modules=["my_deliveries"],
            permissions=["deliveries.view_assigned", "deliveries.update_status"])
        rider = User.objects.create_user(username="rider_b", password="Pass12345!",
            company=self.company_a, role=User.ROLE_STAFF, staff_role=role)
        order = Order.objects.create(company=self.company_a, customer_name="Assigned", status=Order.STATUS_ASSIGNED)
        DeliveryAssignment.objects.create(company=self.company_a, order=order, rider=rider)
        self.client.force_authenticate(rider)
        response = self.client.patch(f"/api/operations/orders/{order.id}/status/",
            {"status": "cancelled"}, format="json")
        self.assertEqual(response.status_code, 403)

from companies.models import ServiceArea, CatalogItem
from .views import _create_order
from decimal import Decimal

class DeliveryAreaEnforcementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Zone business', is_approved=True, polar_subscription_id='zone-sub')
        self.item = CatalogItem.objects.create(company=self.company, name='Test item', price=Decimal('100'), is_available=True)
        ServiceArea.objects.create(company=self.company, name='Wah delivery', area_type='city', city='Wah Cantt', country='Pakistan', delivery_fee=Decimal('20'))

    def test_delivery_is_rejected_outside_configured_zone(self):
        with self.assertRaisesMessage(ValueError, 'Delivery is unavailable'):
            _create_order(self.company, {'customer_name':'Test','delivery_address':'Somewhere','fulfillment_type':'delivery','city':'London','country':'UK','items':[{'item_id':self.item.id,'quantity':1}]})

    def test_delivery_fee_comes_from_matched_business_zone(self):
        order = _create_order(self.company, {'customer_name':'Test','delivery_address':'Main street','fulfillment_type':'delivery','city':'Wah Cantt','country':'Pakistan','delivery_fee':'0','items':[{'item_id':self.item.id,'quantity':1}]})
        self.assertEqual(order.delivery_fee, Decimal('20'))

    def test_collection_does_not_require_delivery_zone(self):
        self.company.service_areas.all().delete()
        order = _create_order(self.company, {'customer_name':'Test','fulfillment_type':'collection','items':[{'item_id':self.item.id,'quantity':1}]})
        self.assertEqual(order.delivery_fee, Decimal('0'))


    def test_collection_order_ignores_customer_supplied_delivery_fee(self):
        self.company.service_areas.all().delete()
        order = _create_order(self.company, {
            "customer_name": "Test",
            "fulfillment_type": "collection",
            "delivery_fee": "9999",
            "items": [{"item_id": self.item.id, "quantity": 1}],
        })
        self.assertEqual(order.delivery_fee, Decimal("0"))


class OrderLifecycleValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Lifecycle business", is_approved=True, polar_subscription_id="lifecycle-sub"
        )
        self.owner = User.objects.create_user(
            username="lifecycle-owner", password="Pass12345!",
            company=self.company, role=User.ROLE_OWNER,
        )
        self.order = Order.objects.create(company=self.company, customer_name="Test customer")
        self.client.force_authenticate(self.owner)

    def test_order_cannot_skip_lifecycle_states(self):
        response = self.client.patch(
            f"/api/operations/orders/{self.order.id}/status/",
            {"status": "delivered"}, format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_NEW)
