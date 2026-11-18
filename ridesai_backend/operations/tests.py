from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import StaffRole, User
from companies.models import Company
from .models import (
    Order, OrderItem, DeliveryAssignment, OrderEvent, AgentConversation, AgentMessage,
    VoiceCall, CallPermission, CallEvent, OrderPrintLog
)
from .calling import WhatsAppCallingClient, handle_calling_webhook_event


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


from .whatsapp_agent import (
    execute_get_catalog_items,
    execute_create_order,
    execute_check_order_status,
    process_incoming_whatsapp_message,
)
from companies.models import Inventory


class WhatsAppAgentToolCallingTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Burger Hub",
            business_type="restaurant",
            is_approved=True,
            status="active",
        )
        self.company_b = Company.objects.create(
            name="Pizza Palace",
            business_type="restaurant",
            is_approved=True,
            status="active",
        )

        self.item_a1 = CatalogItem.objects.create(
            company=self.company_a,
            name="Cheeseburger",
            price=Decimal("12.50"),
            description="Juicy beef patty with cheese",
            is_available=True,
        )
        self.item_a2 = CatalogItem.objects.create(
            company=self.company_a,
            name="French Fries",
            price=Decimal("4.00"),
            description="Crispy fries",
            is_available=True,
        )
        self.item_b1 = CatalogItem.objects.create(
            company=self.company_b,
            name="Pepperoni Pizza",
            price=Decimal("18.00"),
            description="Classic pepperoni pizza",
            is_available=True,
        )

    def test_execute_get_catalog_items_tenant_isolation(self):
        result_a = execute_get_catalog_items(self.company_a)
        self.assertTrue(result_a["success"])
        self.assertEqual(result_a["count"], 2)
        names_a = [item["name"] for item in result_a["items"]]
        self.assertIn("Cheeseburger", names_a)
        self.assertIn("French Fries", names_a)
        self.assertNotIn("Pepperoni Pizza", names_a)

        # Test search query filter
        filtered = execute_get_catalog_items(self.company_a, search_query="fries")
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["items"][0]["name"], "French Fries")

    def test_execute_create_order_atomic_success(self):
        items_payload = [
            {"item_name": "Cheeseburger", "quantity": 2},
            {"item_name": "French Fries", "quantity": 1},
        ]
        result = execute_create_order(
            company=self.company_a,
            customer_name="John Doe",
            customer_phone="+1234567890",
            items=items_payload,
            delivery_address="456 Elm Street, Apt 2B",
            notes="Please leave at the door",
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["order_number"].startswith("RA-"))
        self.assertEqual(result["total"], "$29.00")  # (2 * 12.50) + (1 * 4.00) = 29.00

        # Verify Database state
        order = Order.objects.get(order_number=result["order_number"])
        self.assertEqual(order.company, self.company_a)
        self.assertEqual(order.customer_name, "John Doe")
        self.assertEqual(order.customer_phone, "+1234567890")
        self.assertEqual(order.delivery_address, "456 Elm Street, Apt 2B")
        self.assertEqual(order.status, Order.STATUS_NEW)
        self.assertEqual(order.source, "agent")
        self.assertEqual(order.total, Decimal("29.00"))

        order_items = list(order.items.all().order_by("item_name"))
        self.assertEqual(len(order_items), 2)
        self.assertEqual(order_items[0].item_name, "Cheeseburger")
        self.assertEqual(order_items[0].quantity, Decimal("2"))
        self.assertEqual(order_items[0].unit_price, Decimal("12.50"))
        self.assertEqual(order_items[0].line_total, Decimal("25.00"))

        self.assertEqual(order_items[1].item_name, "French Fries")
        self.assertEqual(order_items[1].quantity, Decimal("1"))
        self.assertEqual(order_items[1].unit_price, Decimal("4.00"))
        self.assertEqual(order_items[1].line_total, Decimal("4.00"))

        # Verify audit trail OrderEvent
        event = OrderEvent.objects.filter(order=order).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "agent_order_created")

    def test_execute_create_order_multi_tenant_isolation(self):
        # Company A customer attempts to order an item only present in Company B
        items_payload = [{"item_name": "Pepperoni Pizza", "quantity": 1}]
        result = execute_create_order(
            company=self.company_a,
            customer_name="Sneaky Customer",
            customer_phone="+1112223333",
            items=items_payload,
            delivery_address="10 Downing St",
        )
        self.assertFalse(result["success"])
        self.assertIn("was not found in our catalog", result["error"])
        self.assertEqual(Order.objects.count(), 0)

    def test_execute_create_order_inventory_tracking(self):
        Inventory.objects.create(
            company=self.company_a,
            item=self.item_a1,
            is_unlimited=False,
            quantity=Decimal("3"),
        )

        # Order 2 units - should succeed
        res1 = execute_create_order(
            company=self.company_a,
            customer_name="Buyer 1",
            customer_phone="+1234",
            items=[{"item_name": "Cheeseburger", "quantity": 2}],
            delivery_address="Address 1",
        )
        self.assertTrue(res1["success"])

        inv = Inventory.objects.get(item=self.item_a1)
        self.assertEqual(inv.quantity, Decimal("1"))

        # Attempt to order 2 more units when only 1 is left - should fail
        res2 = execute_create_order(
            company=self.company_a,
            customer_name="Buyer 2",
            customer_phone="+5678",
            items=[{"item_name": "Cheeseburger", "quantity": 2}],
            delivery_address="Address 2",
        )
        self.assertFalse(res2["success"])
        self.assertIn("Insufficient stock", res2["error"])

    def test_execute_check_order_status(self):
        order = Order.objects.create(
            company=self.company_a,
            customer_name="Bob Smith",
            customer_phone="+1987654321",
            delivery_address="789 Pine Ave",
            status=Order.STATUS_CONFIRMED,
            total=Decimal("25.00"),
        )
        OrderItem.objects.create(
            order=order,
            item=self.item_a1,
            item_name="Cheeseburger",
            quantity=Decimal("2"),
            unit_price=Decimal("12.50"),
            line_total=Decimal("25.00"),
        )

        # Check by customer phone
        status_res = execute_check_order_status(
            company=self.company_a,
            customer_phone="+1987654321",
        )
        self.assertTrue(status_res["found"])
        self.assertEqual(status_res["latest_order"]["order_number"], order.order_number)
        self.assertEqual(status_res["latest_order"]["status"], "confirmed")

        # Company B cannot access Company A's order status
        status_res_b = execute_check_order_status(
            company=self.company_b,
            customer_phone="+1987654321",
        )
        self.assertFalse(status_res_b["found"])

    def test_unmapped_phone_number_fails_closed(self):
        # A message arrives at an unmapped / unknown phone_number_id
        res = process_incoming_whatsapp_message(
            sender_phone="+9999999999",
            message_text="Hello, I want to order 5 burgers",
            phone_number_id="unmapped_nonexistent_id_99999",
        )
        self.assertFalse(res["success"])
        self.assertIn("Unconfigured", res["error"])
        # No orders created
        self.assertEqual(Order.objects.count(), 0)

    @patch("operations.whatsapp_agent.OpenAI")
    def test_generate_agent_reply_executes_tool_call(self, mock_openai_cls):
        import json
        from operations.whatsapp_agent import _generate_agent_reply

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Tool call object
        tool_call = MagicMock()
        tool_call.id = "call_test123"
        tool_call.function.name = "create_order"
        tool_call.function.arguments = json.dumps({
            "items": [{"item_name": "Cheeseburger", "quantity": 1}],
            "delivery_address": "777 Market St",
            "customer_name": "Dave",
        })

        # First completion returns tool_calls
        first_resp = MagicMock()
        first_msg = MagicMock()
        first_msg.tool_calls = [tool_call]
        first_msg.content = None
        first_resp.choices = [MagicMock(message=first_msg)]

        # Second completion returns confirmation text
        second_resp = MagicMock()
        second_msg = MagicMock()
        second_msg.content = "Your order has been placed successfully for 1x Cheeseburger!"
        second_resp.choices = [MagicMock(message=second_msg)]

        mock_client.chat.completions.create.side_effect = [first_resp, second_resp]

        context = {
            "company": self.company_a,
            "business_name": "Burger Hub",
            "catalog": [{"name": "Cheeseburger", "price": "12.50"}],
            "knowledge": [],
            "hours": [],
        }

        with patch.object(settings, "OPENAI_API_KEY", "sk-mock-valid-key-for-test"):
            reply = _generate_agent_reply(
                message_text="I want to order 1 cheeseburger to 777 Market St",
                customer_name="Dave",
                context=context,
                sender_phone="+15551234567",
            )

        self.assertEqual(reply, "Your order has been placed successfully for 1x Cheeseburger!")
        # Verify order was created in DB
        self.assertEqual(Order.objects.filter(company=self.company_a, delivery_address="777 Market St").count(), 1)


class DashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Dashboard Foods",
            business_type="restaurant",
            status="active",
            is_approved=True,
        )
        self.conv = AgentConversation.objects.create(
            company=self.company,
            customer_name="Test Customer",
            customer_phone="+923009999999",
            status="bot",
        )
        from .models import AgentMessage
        AgentMessage.objects.create(
            conversation=self.conv,
            role="user",
            content="Hello from customer",
        )
        AgentMessage.objects.create(
            conversation=self.conv,
            role="assistant",
            content="Hello from agent",
        )

        self.item = CatalogItem.objects.create(
            company=self.company,
            name="Zinger Deluxe",
            price=Decimal("500.00"),
            is_available=True,
        )
        self.order = Order.objects.create(
            company=self.company,
            customer_name="Test Customer",
            customer_phone="+923009999999",
            delivery_address="Model Town, Lahore",
            status="new",
            subtotal=Decimal("500.00"),
            total=Decimal("500.00"),
            source="agent",
        )
        OrderItem.objects.create(
            order=self.order,
            item=self.item,
            item_name="Zinger Deluxe",
            quantity=Decimal("1"),
            unit_price=Decimal("500.00"),
            line_total=Decimal("500.00"),
        )

    def test_dashboard_conversations_endpoint(self):
        response = self.client.get(f"/api/dashboard/conversations/?company_id={self.company.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertGreaterEqual(response.data["count"], 1)

        first_conv = response.data["results"][0]
        self.assertEqual(first_conv["customer_phone"], "+923009999999")
        self.assertEqual(len(first_conv["messages"]), 2)
        self.assertEqual(first_conv["messages"][0]["role"], "user")
        self.assertEqual(first_conv["messages"][1]["role"], "assistant")

    def test_dashboard_orders_endpoint(self):
        response = self.client.get(f"/api/dashboard/orders/?company_id={self.company.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(response.data["count"], 1)

        first_order = response.data["results"][0]
        self.assertEqual(first_order["order_number"], self.order.order_number)
        self.assertEqual(first_order["total"], "500.00")
        self.assertEqual(len(first_order["items"]), 1)
        self.assertEqual(first_order["items"][0]["item_name"], "Zinger Deluxe")

    def test_dashboard_conversation_reply_endpoint(self):
        response = self.client.post(
            f"/api/dashboard/conversations/{self.conv.conversation_key}/reply/?company_id={self.company.id}",
            {"message": "Manager intervening: We are processing your request.", "status": "human"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))

        self.conv.refresh_from_db()
        self.assertEqual(self.conv.status, "human")
        self.assertEqual(self.conv.messages.count(), 3)
        self.assertEqual(self.conv.messages.last().role, "human")

    def test_dashboard_order_status_update(self):
        response = self.client.patch(
            f"/api/dashboard/orders/{self.order.id}/status/?company_id={self.company.id}",
            {"status": "confirmed", "note": "Confirmed by kitchen"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "confirmed")
        self.assertTrue(OrderEvent.objects.filter(order=self.order, to_status="confirmed").exists())


class WhatsAppVoiceAndWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("operations.whatsapp_service.requests.post")
    def test_send_audio_message_includes_voice_true(self, mock_post):
        from operations.whatsapp_service import WhatsAppService

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "messaging_product": "whatsapp",
            "messages": [{"id": "wamid.mock123"}]
        }
        mock_resp.text = '{"messages":[{"id":"wamid.mock123"}]}'
        mock_post.return_value = mock_resp

        service = WhatsAppService(phone_number_id="123456789", access_token="test_token_abc")
        result = service.send_audio_message(to="+923090139836", media_id="media_test_456")

        self.assertTrue(result["success"])
        self.assertEqual(result["message_id"], "wamid.mock123")

        # Verify requests.post was called with the correct payload
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs.get("json", {})

        self.assertEqual(payload.get("messaging_product"), "whatsapp")
        self.assertEqual(payload.get("type"), "audio")
        self.assertIn("audio", payload)
        self.assertEqual(payload["audio"].get("id"), "media_test_456")
        self.assertIs(payload["audio"].get("voice"), True)

    def test_webhook_parses_status_failed_event_without_crashing(self):
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "12345",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "1527102377143902",
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.HBgMOTIz...",
                                        "status": "failed",
                                        "timestamp": "1731910000",
                                        "recipient_id": "923090139836",
                                        "errors": [
                                            {
                                                "code": 131047,
                                                "title": "Re-engagement message",
                                                "message": "Message failed to send because more than 24 hours have passed.",
                                                "error_data": {"details": "Re-engagement message"},
                                            }
                                        ],
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        with self.assertLogs("operations.views", level="ERROR") as cm:
            response = self.client.post(
                "/api/operations/whatsapp/webhook/",
                webhook_payload,
                format="json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "success"})

        # Confirm the ERROR was logged with the error code and wamid
        error_logs = [log for log in cm.output if "Message delivery failed" in log]
        self.assertEqual(len(error_logs), 1)
        self.assertIn("131047", error_logs[0])
        self.assertIn("wamid.HBgMOTIz...", error_logs[0])
        self.assertIn("...9836", error_logs[0])

    def test_webhook_parses_status_delivered_event(self):
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "12345",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "1527102377143902",
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.HBgMOTIzDelivered...",
                                        "status": "delivered",
                                        "timestamp": "1731910000",
                                        "recipient_id": "923090139836",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        response = self.client.post(
            "/api/operations/whatsapp/webhook/",
            webhook_payload,
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})


class WhatsAppCallingFoundationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_calling = Company.objects.create(
            name="Alpha Burger Calling",
            business_type="restaurant",
            is_approved=True,
            is_calling_enabled=True,
        )
        self.company_disabled = Company.objects.create(
            name="Beta Pizza No Calling",
            business_type="restaurant",
            is_approved=True,
            is_calling_enabled=False,
        )

    def test_company_is_calling_enabled_defaults_to_false(self):
        comp = Company.objects.create(name="Default Feature Flag Co")
        self.assertFalse(comp.is_calling_enabled)

    def test_calling_models_tenant_isolation(self):
        call_a = VoiceCall.objects.create(
            company=self.company_calling,
            call_id="call_iso_001",
            customer_phone="+923001111111",
            direction="inbound",
            status="initiated",
            sdp_offer="v=0\r\no=mock_sdp",
        )
        perm_a = CallPermission.objects.create(
            company=self.company_calling,
            customer_phone="+923001111111",
            permission_type="inbound_call",
            is_granted=True,
        )
        event_a = CallEvent.objects.create(
            call=call_a,
            event_type="connect",
            raw_payload={"id": "call_iso_001", "event": "connect"},
        )

        self.assertEqual(self.company_calling.voice_calls.count(), 1)
        self.assertEqual(self.company_calling.call_permissions.count(), 1)
        self.assertEqual(call_a.events.count(), 1)

        # Company B has strict isolation
        self.assertEqual(self.company_disabled.voice_calls.count(), 0)
        self.assertEqual(self.company_disabled.call_permissions.count(), 0)

    @patch("operations.calling.meta_client.requests.post")
    def test_calling_client_endpoints_and_payloads(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"success": True, "call_id": "call_mock_123"}
        mock_resp.text = '{"success": true, "call_id": "call_mock_123"}'
        mock_post.return_value = mock_resp

        client = WhatsAppCallingClient(
            phone_number_id="1527102377143902",
            access_token="mock_calling_token_abc",
        )

        # 1. Initiate Call
        res_init = client.initiate_call("+923090139836", "v=0\r\no=offer_sdp")
        self.assertTrue(res_init["success"])
        mock_post.assert_called_with(
            "https://graph.facebook.com/v21.0/1527102377143902/calls",
            headers={
                "Authorization": "Bearer mock_calling_token_abc",
                "Content-Type": "application/json",
                "User-Agent": "RidesAI-WhatsApp-Calling/1.0",
            },
            json={
                "messaging_product": "whatsapp",
                "to": "923090139836",
                "action": "initiate",
                "session": {
                    "sdp": "v=0\r\no=offer_sdp",
                    "type": "offer",
                },
            },
            timeout=20,
        )

        # 2. Accept Call
        res_acc = client.accept_call("call_mock_123", "v=0\r\no=answer_sdp")
        self.assertTrue(res_acc["success"])
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["action"], "accept")
        self.assertEqual(kwargs["json"]["session"]["type"], "answer")

        # 3. Reject Call
        res_rej = client.reject_call("call_mock_123")
        self.assertTrue(res_rej["success"])
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["action"], "reject")

        # 4. Terminate Call
        res_term = client.terminate_call("call_mock_123")
        self.assertTrue(res_term["success"])
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["action"], "terminate")

    @patch("operations.views.get_config_by_phone_number_id")
    def test_calls_webhook_lifecycle_transitions(self, mock_get_cfg):
        mock_get_cfg.return_value = {
            "company_id": self.company_calling.id,
            "phone_number_id": "1527102377143902",
        }

        # Step 1: Connect / Offer
        connect_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "12345",
                    "changes": [
                        {
                            "field": "calls",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "1527102377143902",
                                },
                                "calls": [
                                    {
                                        "id": "call_life_001",
                                        "from": "+923090139836",
                                        "event": "connect",
                                        "direction": "inbound",
                                        "session": {
                                            "sdp": "v=0\r\no=initial_offer",
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

        resp1 = self.client.post("/api/operations/whatsapp/webhook/", connect_payload, format="json")
        self.assertEqual(resp1.status_code, 200)

        vcall = VoiceCall.objects.get(call_id="call_life_001")
        self.assertEqual(vcall.status, "initiated")
        self.assertEqual(vcall.customer_phone, "+923090139836")
        self.assertEqual(vcall.sdp_offer, "v=0\r\no=initial_offer")
        self.assertEqual(vcall.events.count(), 1)
        self.assertEqual(vcall.events.first().event_type, "connect")

        # Step 2: Ringing
        ringing_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "12345",
                    "changes": [
                        {
                            "field": "calls",
                            "value": {
                                "metadata": {"phone_number_id": "1527102377143902"},
                                "calls": [{"id": "call_life_001", "event": "ringing"}],
                            },
                        }
                    ],
                }
            ],
        }
        self.client.post("/api/operations/whatsapp/webhook/", ringing_payload, format="json")
        vcall.refresh_from_db()
        self.assertEqual(vcall.status, "ringing")
        self.assertEqual(vcall.events.count(), 2)

        # Step 3: Accepted
        accepted_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "12345",
                    "changes": [
                        {
                            "field": "calls",
                            "value": {
                                "metadata": {"phone_number_id": "1527102377143902"},
                                "calls": [{"id": "call_life_001", "event": "accepted"}],
                            },
                        }
                    ],
                }
            ],
        }
        self.client.post("/api/operations/whatsapp/webhook/", accepted_payload, format="json")
        vcall.refresh_from_db()
        self.assertEqual(vcall.status, "accepted")
        self.assertIsNotNone(vcall.started_at)
        self.assertEqual(vcall.events.count(), 3)

        # Step 4: Terminate
        terminate_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "12345",
                    "changes": [
                        {
                            "field": "calls",
                            "value": {
                                "metadata": {"phone_number_id": "1527102377143902"},
                                "calls": [{"id": "call_life_001", "event": "terminate"}],
                            },
                        }
                    ],
                }
            ],
        }
        self.client.post("/api/operations/whatsapp/webhook/", terminate_payload, format="json")
        vcall.refresh_from_db()
        self.assertEqual(vcall.status, "terminated")
        self.assertIsNotNone(vcall.ended_at)
        self.assertGreaterEqual(vcall.duration_seconds, 0)
        self.assertEqual(vcall.events.count(), 4)

    @patch("operations.views.get_config_by_phone_number_id")
    def test_calls_webhook_ignored_when_calling_disabled(self, mock_get_cfg):
        mock_get_cfg.return_value = {
            "company_id": self.company_disabled.id,
            "phone_number_id": "1527102377143902",
        }

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "12345",
                    "changes": [
                        {
                            "field": "calls",
                            "value": {
                                "metadata": {"phone_number_id": "1527102377143902"},
                                "calls": [{"id": "call_disabled_99", "event": "connect"}],
                            },
                        }
                    ],
                }
            ],
        }

        resp = self.client.post("/api/operations/whatsapp/webhook/", payload, format="json")
        self.assertEqual(resp.status_code, 200)
        # Verify no VoiceCall was created for the disabled company
        self.assertEqual(VoiceCall.objects.filter(call_id="call_disabled_99").count(), 0)


class DashboardCallsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Tenant Calls A",
            business_type="restaurant",
            is_approved=True,
            is_calling_enabled=True,
        )
        self.company_b = Company.objects.create(
            name="Tenant Calls B",
            business_type="restaurant",
            is_approved=True,
            is_calling_enabled=False,
        )
        self.owner_a = User.objects.create_user(
            username="owner_calls_a", password="Pass12345!",
            email="owner-calls-a@example.com", company=self.company_a, role=User.ROLE_OWNER
        )
        self.owner_b = User.objects.create_user(
            username="owner_calls_b", password="Pass12345!",
            email="owner-calls-b@example.com", company=self.company_b, role=User.ROLE_OWNER
        )

        # Create calls for Company A
        self.call_a1 = VoiceCall.objects.create(
            company=self.company_a,
            call_id="call_a_active",
            customer_phone="+923001112233",
            direction="inbound",
            status="accepted",
            duration_seconds=0,
        )
        self.call_a2 = VoiceCall.objects.create(
            company=self.company_a,
            call_id="call_a_term",
            customer_phone="+923004445566",
            direction="outbound",
            status="terminated",
            duration_seconds=120,
        )
        self.call_a3 = VoiceCall.objects.create(
            company=self.company_a,
            call_id="call_a_failed",
            customer_phone="+923007778899",
            direction="inbound",
            status="failed",
            error_code="131047",
            error_message="Window expired",
        )

        # Call Event for call_a1
        self.event_a1 = CallEvent.objects.create(
            call=self.call_a1,
            event_type="connect",
            raw_payload={"id": "call_a_active", "event": "connect"},
        )
        self.event_a2 = CallEvent.objects.create(
            call=self.call_a1,
            event_type="accepted",
            raw_payload={"id": "call_a_active", "event": "accepted"},
        )

        # Create calls for Company B
        self.call_b1 = VoiceCall.objects.create(
            company=self.company_b,
            call_id="call_b_isolated",
            customer_phone="+15559998888",
            direction="inbound",
            status="initiated",
        )

    def test_dashboard_calls_stats_and_tenant_isolation(self):
        # Authenticate as owner of Company A
        self.client.force_authenticate(self.owner_a)
        response = self.client.get("/api/dashboard/calls/")
        self.assertEqual(response.status_code, 200)

        data = response.data
        self.assertTrue(data["is_calling_enabled"])

        # Check KPI Stats
        stats = data["stats"]
        self.assertEqual(stats["total_calls"], 3)
        self.assertEqual(stats["active_calls"], 1)  # call_a1 is accepted
        self.assertEqual(stats["missed_or_failed"], 1)  # call_a3 is failed
        self.assertEqual(stats["avg_duration_seconds"], 120.0)  # only call_a2 is terminated with 120s

        # Check that only Company A's calls are returned
        call_ids = [c["call_id"] for c in data["calls"]]
        self.assertIn("call_a_active", call_ids)
        self.assertIn("call_a_term", call_ids)
        self.assertIn("call_a_failed", call_ids)
        self.assertNotIn("call_b_isolated", call_ids)

        # Authenticate as owner of Company B
        self.client.force_authenticate(self.owner_b)
        response_b = self.client.get("/api/dashboard/calls/")
        self.assertEqual(response_b.status_code, 200)
        self.assertFalse(response_b.data["is_calling_enabled"])
        self.assertEqual(response_b.data["stats"]["total_calls"], 1)
        self.assertEqual(len(response_b.data["calls"]), 1)
        self.assertEqual(response_b.data["calls"][0]["call_id"], "call_b_isolated")

    def test_dashboard_calls_filters(self):
        self.client.force_authenticate(self.owner_a)

        # Status filter
        res_status = self.client.get("/api/dashboard/calls/?status=accepted")
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(len(res_status.data["calls"]), 1)
        self.assertEqual(res_status.data["calls"][0]["call_id"], "call_a_active")

        # Direction filter
        res_dir = self.client.get("/api/dashboard/calls/?direction=outbound")
        self.assertEqual(res_dir.status_code, 200)
        self.assertEqual(len(res_dir.data["calls"]), 1)
        self.assertEqual(res_dir.data["calls"][0]["call_id"], "call_a_term")

        # Search filter by customer phone
        res_search = self.client.get("/api/dashboard/calls/?search=7778899")
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(len(res_search.data["calls"]), 1)
        self.assertEqual(res_search.data["calls"][0]["call_id"], "call_a_failed")

    def test_dashboard_call_events_endpoint_and_isolation(self):
        self.client.force_authenticate(self.owner_a)

        # Owner A fetches events for call_a1
        res = self.client.get(f"/api/dashboard/calls/{self.call_a1.id}/events/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["call"]["call_id"], "call_a_active")
        self.assertEqual(len(res.data["events"]), 2)
        self.assertEqual(res.data["events"][0]["event_type"], "connect")
        self.assertEqual(res.data["events"][1]["event_type"], "accepted")

        # Owner B tries to access call_a1 events -> Must return 404
        self.client.force_authenticate(self.owner_b)
        res_cross = self.client.get(f"/api/dashboard/calls/{self.call_a1.id}/events/")
        self.assertEqual(res_cross.status_code, 404)


class ThermalReceiptPrintingTests(TestCase):
    """
    Enterprise Thermal Receipt (Invoice + KOT) System Tests.
    Verifies ESC/POS binary generation, dashboard receipt API, print logging, and multi-tenant isolation.
    """

    def setUp(self):
        self.client = APIClient()

        # Company A (SpeedX SP-200U configured)
        self.company_a = Company.objects.create(
            name="Burger Hub",
            phone="+923001234567",
            address="Commercial Area, Block A",
            printer_name="SpeedX SP-200U",
            receipt_header="Best Burgers in Town",
            receipt_footer="Thanks for choosing Burger Hub!",
            currency_symbol="Rs.",
            auto_print_kot=False,
            auto_print_invoice=False,
        )
        self.owner_a = User.objects.create_user(
            username="owner_a_thermal",
            email="owner_a@burgerhub.com",
            password="testpassword123",
            company=self.company_a,
            role=User.ROLE_OWNER,
        )

        # Company B (Isolated tenant)
        self.company_b = Company.objects.create(
            name="Pizza King",
            phone="+923009876543",
            address="Main Boulevard, Sector C",
            printer_name="Epson TM-T88VI",
        )
        self.owner_b = User.objects.create_user(
            username="owner_b_thermal",
            email="owner_b@pizzaking.com",
            password="testpassword123",
            company=self.company_b,
            role=User.ROLE_OWNER,
        )

        # Order for Company A
        self.order_a = Order.objects.create(
            company=self.company_a,
            order_number="ORD-BH-1001",
            customer_name="John Doe",
            customer_phone="+923001112233",
            delivery_address="Street 12, House 4B",
            status="confirmed",
            subtotal=Decimal("25.00"),
            delivery_fee=Decimal("3.00"),
            total=Decimal("28.00"),
            notes="No onions, extra spicy sauce please!",
            source="agent",
        )
        self.item_a1 = OrderItem.objects.create(
            order=self.order_a,
            item_name="Double Cheeseburger",
            quantity=Decimal("2"),
            unit_price=Decimal("10.00"),
            line_total=Decimal("20.00"),
        )
        self.item_a2 = OrderItem.objects.create(
            order=self.order_a,
            item_name="Curly Fries",
            quantity=Decimal("1"),
            unit_price=Decimal("5.00"),
            line_total=Decimal("5.00"),
        )

    def test_escpos_invoice_builder(self):
        from operations.printing import build_invoice_escpos
        raw_bytes = build_invoice_escpos(self.order_a, company=self.company_a)
        self.assertIsInstance(raw_bytes, bytes)
        # Ends with cut paper command GS V 66 0
        self.assertTrue(raw_bytes.endswith(b"\x1dV\x42\x00"))

        decoded_text = raw_bytes.decode("ascii", errors="replace")
        self.assertIn("BURGER HUB", decoded_text)
        self.assertIn("ORD-BH-1001", decoded_text)
        self.assertIn("John Doe", decoded_text)
        self.assertIn("Double Cheeseburger", decoded_text)
        self.assertIn("Curly Fries", decoded_text)
        self.assertIn("Rs. 28.00", decoded_text)
        self.assertNotIn("$", decoded_text)
        self.assertIn("No onions, extra spicy", decoded_text)
        self.assertIn("Thanks for choosing Burger Hub!", decoded_text)

    def test_escpos_kot_builder(self):
        from operations.printing import build_kot_escpos
        raw_bytes = build_kot_escpos(self.order_a, company=self.company_a)
        self.assertIsInstance(raw_bytes, bytes)
        self.assertTrue(raw_bytes.endswith(b"\x1dV\x42\x00"))

        decoded_text = raw_bytes.decode("ascii", errors="replace")
        self.assertIn("KOT", decoded_text)
        self.assertIn("ORD-BH-1001", decoded_text)
        self.assertIn("2x", decoded_text)
        self.assertIn("Double Cheeseburger", decoded_text)
        self.assertIn("Curly Fries", decoded_text)
        self.assertIn("SPECIAL PREPARATION INSTRUCTIONS", decoded_text)
        self.assertIn("No onions, extra spicy", decoded_text)

    def test_order_receipt_api_invoice_and_kot(self):
        self.client.force_authenticate(self.owner_a)

        # GET invoice
        res_inv = self.client.get(f"/api/dashboard/orders/{self.order_a.id}/receipt/?type=invoice")
        self.assertEqual(res_inv.status_code, 200)
        self.assertEqual(res_inv.data["slip_type"], "invoice")
        self.assertEqual(res_inv.data["printer_name"], "SpeedX SP-200U")
        self.assertEqual(res_inv.data["currency_symbol"], "Rs.")
        self.assertFalse(res_inv.data["auto_print_kot"])
        self.assertIn("escpos_base64", res_inv.data)
        self.assertEqual(res_inv.data["receipt"]["order"]["order_number"], "ORD-BH-1001")
        self.assertEqual(res_inv.data["receipt"]["currency_symbol"], "Rs.")
        self.assertEqual(len(res_inv.data["receipt"]["items"]), 2)
        self.assertEqual(res_inv.data["receipt"]["totals"]["total"], 28.0)

        # GET KOT
        res_kot = self.client.get(f"/api/dashboard/orders/{self.order_a.id}/receipt/?type=kot")
        self.assertEqual(res_kot.status_code, 200)
        self.assertEqual(res_kot.data["slip_type"], "kot")
        self.assertIsNone(res_kot.data["receipt"]["totals"])
        self.assertTrue(res_kot.data["receipt"]["order"]["has_notes"])

    def test_order_print_api_browser_and_escpos(self):
        self.client.force_authenticate(self.owner_a)

        # Mode browser
        res_print_browser = self.client.post(
            f"/api/dashboard/orders/{self.order_a.id}/print/",
            {"slip_type": "invoice", "mode": "browser"},
            format="json",
        )
        self.assertEqual(res_print_browser.status_code, 200)
        self.assertTrue(res_print_browser.data["success"])
        self.assertEqual(res_print_browser.data["print_count"], 1)

        # Verify audit log in database
        log_browser = OrderPrintLog.objects.filter(order=self.order_a).first()
        self.assertIsNotNone(log_browser)
        self.assertEqual(log_browser.print_mode, "browser")
        self.assertEqual(log_browser.slip_type, "invoice")
        self.assertEqual(log_browser.status, "success")
        self.assertEqual(log_browser.printed_by, self.owner_a)

        # Mode escpos_local (runs safely with simulated/local fallback)
        res_print_escpos = self.client.post(
            f"/api/dashboard/orders/{self.order_a.id}/print/",
            {"slip_type": "kot", "mode": "escpos_local"},
            format="json",
        )
        self.assertEqual(res_print_escpos.status_code, 200)
        self.assertEqual(res_print_escpos.data["mode"], "escpos_local")

        # Total logs for this order should now be 2
        self.assertEqual(OrderPrintLog.objects.filter(order=self.order_a).count(), 2)

    def test_receipt_api_tenant_isolation(self):
        # Authenticate as Company B owner
        self.client.force_authenticate(self.owner_b)

        # Try to access Company A's receipt -> 404
        res_get = self.client.get(f"/api/dashboard/orders/{self.order_a.id}/receipt/")
        self.assertEqual(res_get.status_code, 404)

        # Try to trigger print for Company A's order -> 404
        res_post = self.client.post(
            f"/api/dashboard/orders/{self.order_a.id}/print/",
            {"slip_type": "invoice", "mode": "browser"},
            format="json",
        )
        self.assertEqual(res_post.status_code, 404)

    def test_receipt_uses_company_currency_symbol(self):
        from operations.printing import build_receipt_payload, build_invoice_escpos
        # Test default Rs.
        payload = build_receipt_payload(self.order_a, company=self.company_a)
        self.assertEqual(payload["currency_symbol"], "Rs.")
        self.assertEqual(payload["business"]["currency_symbol"], "Rs.")

        raw_bytes = build_invoice_escpos(self.order_a, company=self.company_a)
        decoded = raw_bytes.decode("ascii", errors="replace")
        self.assertIn("Rs. 28.00", decoded)
        self.assertNotIn("$", decoded)

        # Test customized currency symbol (e.g. AED)
        self.company_a.currency_symbol = "AED"
        self.company_a.save()
        payload_custom = build_receipt_payload(self.order_a, company=self.company_a)
        self.assertEqual(payload_custom["currency_symbol"], "AED")

        raw_custom = build_invoice_escpos(self.order_a, company=self.company_a)
        decoded_custom = raw_custom.decode("ascii", errors="replace")
        self.assertIn("AED 28.00", decoded_custom)
        self.assertNotIn("Rs.", decoded_custom)

    @patch("operations.printing.printer_service.dispatch_to_local_printer")
    def test_auto_print_triggers_kot_and_invoice_on_order_create(self, mock_dispatch):
        mock_dispatch.return_value = {"success": True, "printer": "SpeedX SP-200U", "bytes_sent": 450}

        # Create company with both auto-print flags enabled
        auto_company = Company.objects.create(
            name="Auto Print Diner",
            printer_name="SpeedX SP-200U",
            auto_print_kot=True,
            auto_print_invoice=True,
        )

        new_order = Order.objects.create(
            company=auto_company,
            order_number="ORD-AUTO-001",
            customer_name="Alice Smith",
            total=Decimal("45.00"),
            status="confirmed",
        )

        # Both KOT and Invoice should be dispatched and logged
        self.assertEqual(mock_dispatch.call_count, 2)
        print_logs = OrderPrintLog.objects.filter(order=new_order)
        self.assertEqual(print_logs.count(), 2)

        kot_log = print_logs.filter(slip_type="kot").first()
        inv_log = print_logs.filter(slip_type="invoice").first()
        self.assertIsNotNone(kot_log)
        self.assertIsNotNone(inv_log)
        self.assertEqual(kot_log.status, "success")
        self.assertEqual(inv_log.status, "success")
        self.assertEqual(kot_log.print_mode, "escpos_local")

    @patch("operations.printing.printer_service.dispatch_to_local_printer")
    def test_auto_print_failure_does_not_block_order_creation(self, mock_dispatch):
        mock_dispatch.return_value = {"success": False, "error": "Printer offline / cable unplugged"}

        failing_company = Company.objects.create(
            name="Offline Store",
            printer_name="SpeedX SP-200U",
            auto_print_kot=True,
            auto_print_invoice=False,
        )

        # Order creation must NOT fail or throw exception
        order = Order.objects.create(
            company=failing_company,
            order_number="ORD-FAIL-001",
            customer_name="Bob Offline",
            total=Decimal("15.00"),
            status="new",
        )
        self.assertIsNotNone(order.id)

        # A failed print log should be safely recorded without crashing
        log = OrderPrintLog.objects.filter(order=order, slip_type="kot").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "failed")
        self.assertIn("Printer offline", log.error_message)

    @patch("operations.printing.printer_service.dispatch_to_local_printer")
    def test_auto_print_does_not_duplicate_on_status_update(self, mock_dispatch):
        mock_dispatch.return_value = {"success": True, "printer": "SpeedX SP-200U", "bytes_sent": 300}

        company = Company.objects.create(
            name="Status Check Diner",
            auto_print_kot=True,
            auto_print_invoice=False,
        )

        # 1. Order created in 'new' status -> 1 auto-print fired on create
        order = Order.objects.create(
            company=company,
            order_number="ORD-STATUS-001",
            customer_name="Charlie Status",
            status="new",
        )
        self.assertEqual(mock_dispatch.call_count, 1)
        self.assertEqual(OrderPrintLog.objects.filter(order=order).count(), 1)

        # 2. Subsequent status transitions should NOT duplicate prints
        order.status = "preparing"
        order.save()
        self.assertEqual(mock_dispatch.call_count, 1)

        order.status = "ready"
        order.save()
        self.assertEqual(mock_dispatch.call_count, 1)

        order.status = "delivered"
        order.save()
        self.assertEqual(mock_dispatch.call_count, 1)
        self.assertEqual(OrderPrintLog.objects.filter(order=order).count(), 1)







