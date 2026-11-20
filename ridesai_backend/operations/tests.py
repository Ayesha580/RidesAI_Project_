from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import StaffRole, User
from companies.models import Company
from datetime import date, timedelta
from django.utils import timezone
from .models import (
    Customer, Order, OrderItem, DeliveryAssignment, OrderEvent, AgentConversation, AgentMessage,
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
        self.assertEqual(result["total"], "Rs. 29.00")  # (2 * 12.50) + (1 * 4.00) = 29.00

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

    def test_clean_text_for_tts(self):
        from operations.audio_service import clean_text_for_tts
        raw = "Your order is *1 Zinger Burger* for $800.00 and _Fries_ for Rs. 250! #Order • Fast delivery"
        cleaned = clean_text_for_tts(raw)
        self.assertNotIn("*", cleaned)
        self.assertNotIn("_", cleaned)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("•", cleaned)
        self.assertNotIn("$", cleaned)
        self.assertNotIn("Rs.", cleaned)
        self.assertIn("800.00 rupees", cleaned)
        self.assertIn("250 rupees", cleaned)

    @patch("openai.OpenAI")
    def test_synthesize_speech_defaults_nova_mp3_and_speed(self, mock_openai_cls):
        from operations.audio_service import synthesize_speech

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = b"MP3_SYNTHESIZED_AUDIO_BYTES"
        mock_client.audio.speech.create.return_value = mock_response

        with patch.object(settings, "OPENAI_API_KEY", "sk-mock-valid-key-for-test"):
            audio_bytes = synthesize_speech("Your order is *1 Cheeseburger* for Rs. 850!")

        self.assertEqual(audio_bytes, b"MP3_SYNTHESIZED_AUDIO_BYTES")
        mock_client.audio.speech.create.assert_called_once_with(
            model="tts-1-hd",
            voice="nova",
            input="Your order is 1 Cheeseburger for 850 rupees!",
            response_format="mp3",
            speed=0.92,
        )

    @patch("operations.whatsapp_agent._dispatch_whatsapp_audio")
    @patch("operations.whatsapp_agent._dispatch_whatsapp_text")
    @patch("operations.whatsapp_agent.synthesize_speech")
    @patch("operations.whatsapp_agent.transcribe_audio")
    @patch("operations.whatsapp_agent.OpenAI")
    def test_voice_order_followed_by_hanjee_krden_places_order(
        self, mock_openai_cls, mock_transcribe, mock_synth, mock_dispatch_text, mock_dispatch_audio
    ):
        import json
        from operations.whatsapp_agent import process_incoming_whatsapp_message
        from operations.models import AgentConversation

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_transcribe.return_value = "1 Cheeseburger and 1 French Fries bhej do 777 Market St"
        mock_synth.return_value = b"MOCK_OGG_AUDIO_BYTES"
        mock_dispatch_audio.return_value = {"success": True}
        mock_dispatch_text.return_value = {"success": True}

        self.company_a.whatsapp_instance_name = "test_evo_inst_multiturn"
        self.company_a.save()

        # Turn 1: LLM responds in simple English without markdown confirming the items and asking for confirmation
        turn1_resp = MagicMock()
        turn1_msg = MagicMock()
        turn1_msg.tool_calls = None
        turn1_msg.content = "Your order is 1 Cheeseburger for 12.50 rupees and 1 French Fries for 4.00 rupees. Total is 16.50 rupees for delivery to 777 Market St. Should I confirm your order?"
        turn1_resp.choices = [MagicMock(message=turn1_msg)]
        mock_client.chat.completions.create.return_value = turn1_resp

        with patch.object(settings, "OPENAI_API_KEY", "sk-mock-valid-key-for-test"):
            res1 = process_incoming_whatsapp_message(
                sender_phone="+923001234567",
                message_text="",
                phone_number_id="test_evo_inst_multiturn",
                customer_name="Ali Khan",
                media_id="mock_media_1",
                msg_type="audio",
                company=self.company_a,
                audio_bytes=b"OGG_RAW_BYTES_TEST",
            )

        self.assertTrue(res1["success"])
        self.assertIn("Your order is 1 Cheeseburger", res1["reply_text"])
        self.assertEqual(Order.objects.filter(company=self.company_a).count(), 0)

        # Verify Turn 1 had CRITICAL VOICE RULE instructions in system prompt and before user message
        turn1_call_messages = mock_client.chat.completions.create.call_args_list[0][1]["messages"]
        turn1_sys_content = turn1_call_messages[0]["content"]
        self.assertIn("CRITICAL VOICE RULE", turn1_sys_content)
        self.assertIn("You MUST reply strictly in simple, plain English ONLY", turn1_sys_content)
        self.assertEqual(turn1_call_messages[-2]["content"], (
            "CRITICAL VOICE RULE: Your reply will be spoken aloud by an English TTS engine. "
            "You MUST reply strictly in simple, plain English ONLY (no Urdu script, no Hindi, no Roman Urdu). "
            "Keep it under 2 short sentences."
        ))

        # Verify Turn 1 was recorded in AgentConversation
        conv = AgentConversation.objects.filter(company=self.company_a, customer_phone="+923001234567").first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.messages.count(), 2)

        # Turn 2: Customer replies with Roman Urdu confirmation "Hanjee krden"
        # Mock OpenAI to call create_order tool call on Turn 2
        tool_call = MagicMock()
        tool_call.id = "call_turn2_confirm"
        tool_call.function.name = "create_order"
        tool_call.function.arguments = json.dumps({
            "items": [
                {"item_name": "Cheeseburger", "quantity": 1},
                {"item_name": "French Fries", "quantity": 1},
            ],
            "delivery_address": "777 Market St",
            "customer_name": "Ali Khan",
        })

        turn2_pass1 = MagicMock()
        turn2_pass1_msg = MagicMock()
        turn2_pass1_msg.tool_calls = [tool_call]
        turn2_pass1_msg.content = None
        turn2_pass1.choices = [MagicMock(message=turn2_pass1_msg)]

        turn2_pass2 = MagicMock()
        turn2_pass2_msg = MagicMock()
        turn2_pass2_msg.content = "Order confirm ho gaya hai! Order number is RA-12345. Aapka order 30-45 minutes mein deliver ho jaye ga."
        turn2_pass2.choices = [MagicMock(message=turn2_pass2_msg)]

        mock_client.chat.completions.create.side_effect = [turn2_pass1, turn2_pass2]

        with patch.object(settings, "OPENAI_API_KEY", "sk-mock-valid-key-for-test"):
            res2 = process_incoming_whatsapp_message(
                sender_phone="+923001234567",
                message_text="Hanjee krden",
                phone_number_id="test_evo_inst_multiturn",
                customer_name="Ali Khan",
                msg_type="text",
                company=self.company_a,
            )

        self.assertTrue(res2["success"])
        # Turn 2 must NOT return a welcome greeting
        self.assertNotIn("Welcome to", res2["reply_text"])
        self.assertIn("Order confirm ho gaya", res2["reply_text"])

        # Verify an order was created in the database
        created_order = Order.objects.filter(company=self.company_a, customer_phone="+923001234567").first()
        self.assertIsNotNone(created_order)
        self.assertEqual(created_order.delivery_address, "777 Market St")
        self.assertEqual(created_order.items.count(), 2)

        # Inspect the messages passed to OpenAI in Turn 2 to verify multi-turn memory
        calls = mock_client.chat.completions.create.call_args_list
        turn2_first_call_messages = calls[-2][1]["messages"]
        # History messages should be present
        roles = [m["role"] for m in turn2_first_call_messages if isinstance(m, dict)]
        self.assertIn("system", roles)
        self.assertIn("assistant", roles)
        # Verify Turn 2 user message is present in the conversation
        user_msgs = [m for m in turn2_first_call_messages if isinstance(m, dict) and m.get("role") == "user"]
        self.assertEqual(len(user_msgs), 2)  # Turn 1 user message + Turn 2 user message
        self.assertEqual(user_msgs[1]["content"], "Hanjee krden")
        # System prompt should have ACTIVE CONVERSATION INSTRUCTION
        system_content = turn2_first_call_messages[0]["content"]
        self.assertIn("ACTIVE CONVERSATION INSTRUCTION", system_content)
        self.assertIn("NEVER start your reply with a welcome greeting", system_content)


class DashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Dashboard Foods",
            business_type="restaurant",
            status="active",
            is_approved=True,
        )
        self.user = User.objects.create_user(
            username="dash_owner",
            password="Password123!",
            email="dash_owner@example.com",
            company=self.company,
            role=User.ROLE_OWNER,
        )
        self.client.force_authenticate(user=self.user)

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

    def test_dashboard_endpoints_reject_unauthenticated_requests(self):
        unauth_client = APIClient()
        # 1. Orders list
        resp = unauth_client.get("/api/dashboard/orders/")
        self.assertEqual(resp.status_code, 401)

        # 2. Conversations list
        resp = unauth_client.get("/api/dashboard/conversations/")
        self.assertEqual(resp.status_code, 401)

        # 3. Order status patch
        resp = unauth_client.patch(f"/api/dashboard/orders/{self.order.id}/status/", {"status": "confirmed"})
        self.assertEqual(resp.status_code, 401)

        # 4. Authenticated user without company gets 403 Forbidden
        user_no_co = User.objects.create_user(username="orphan", password="Password123!", company=None)
        client_no_co = APIClient()
        client_no_co.force_authenticate(user=user_no_co)
        resp = client_no_co.get("/api/dashboard/orders/")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("User has no associated company.", resp.data.get("detail", ""))


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


class KitchenAndRiderWorkflowTests(TestCase):
    """
    KDS & Rider Dashboards + Auto-Assignment Tests.
    Verifies load-balanced rider assignment on 'prepared' status transition,
    and role-based API permissions & isolation.
    """

    def setUp(self):
        self.client = APIClient()

        # Company A
        self.company_a = Company.objects.create(
            name="Burger Hub Dispatch",
            phone="+923001234567",
            address="Commercial Area, Block A",
        )
        self.owner_a = User.objects.create_user(
            username="owner_dispatch",
            email="owner_dispatch@burgerhub.com",
            password="testpassword123",
            company=self.company_a,
            role=User.ROLE_OWNER,
        )

        # 2 Riders for Company A
        self.rider_1 = User.objects.create_user(
            username="rider_speedy",
            email="rider1@burgerhub.com",
            password="testpassword123",
            company=self.company_a,
            role=User.ROLE_RIDER,
        )
        self.rider_2 = User.objects.create_user(
            username="rider_flash",
            email="rider2@burgerhub.com",
            password="testpassword123",
            company=self.company_a,
            role=User.ROLE_RIDER,
        )

        # Kitchen Staff for Company A
        self.kitchen_user = User.objects.create_user(
            username="chef_gordon",
            email="chef@burgerhub.com",
            password="testpassword123",
            company=self.company_a,
            role=User.ROLE_KITCHEN,
        )

        # Company B (Isolated tenant)
        self.company_b = Company.objects.create(
            name="Isolated Pizza B",
            phone="+923009999999",
        )
        self.rider_b = User.objects.create_user(
            username="rider_b_tenant",
            email="riderb@pizza.com",
            password="testpassword123",
            company=self.company_b,
            role=User.ROLE_RIDER,
        )

    def test_auto_assign_best_rider(self):
        # 1. Assign 1 active order to Rider 1 so Rider 1 workload = 1, Rider 2 workload = 0
        order_active_1 = Order.objects.create(
            company=self.company_a,
            order_number="ORD-DISP-001",
            customer_name="Customer One",
            customer_phone="+923001111111",
            status="prepared",
            assigned_rider=self.rider_1,
            total=Decimal("20.00"),
        )

        # 2. Create a new order in 'preparing' with no rider assigned
        order_new = Order.objects.create(
            company=self.company_a,
            order_number="ORD-DISP-002",
            customer_name="Customer Two",
            customer_phone="+923002222222",
            status="preparing",
            assigned_rider=None,
            total=Decimal("35.00"),
        )
        self.assertIsNone(order_new.assigned_rider)

        # 3. Kitchen marks order as 'prepared'
        order_new.status = "prepared"
        order_new.save()

        # 4. Assert load balancing: auto-assigned to Rider 2 (workload 0 vs Rider 1's 1)
        order_new.refresh_from_db()
        self.assertIsNotNone(order_new.assigned_rider)
        self.assertEqual(order_new.assigned_rider, self.rider_2)

    def test_kitchen_and_rider_api_permissions(self):
        # Create an order in 'preparing' for kitchen
        order_kitchen = Order.objects.create(
            company=self.company_a,
            order_number="ORD-KITCHEN-001",
            customer_name="Diner Customer",
            status="preparing",
            total=Decimal("18.00"),
        )
        OrderItem.objects.create(
            order=order_kitchen,
            item_name="Spicy Burger",
            quantity=Decimal("2"),
            unit_price=Decimal("9.00"),
            line_total=Decimal("18.00"),
        )

        # Create Order X assigned to Rider 1
        order_rider_1 = Order.objects.create(
            company=self.company_a,
            order_number="ORD-RIDER-1",
            customer_name="Client Alpha",
            status="prepared",
            assigned_rider=self.rider_1,
            total=Decimal("22.00"),
        )

        # Create Order Y assigned to Rider 2
        order_rider_2 = Order.objects.create(
            company=self.company_a,
            order_number="ORD-RIDER-2",
            customer_name="Client Beta",
            status="prepared",
            assigned_rider=self.rider_2,
            total=Decimal("30.00"),
        )

        # 1. Kitchen Staff API Access
        self.client.force_authenticate(self.kitchen_user)
        res_k_get = self.client.get("/api/kitchen/orders/")
        self.assertEqual(res_k_get.status_code, 200)
        self.assertTrue(any(o["id"] == order_kitchen.id for o in res_k_get.data["orders"]))

        # Kitchen marks order_kitchen as prepared
        res_k_patch = self.client.patch(
            f"/api/kitchen/orders/{order_kitchen.id}/status/",
            {"status": "prepared"},
            format="json",
        )
        self.assertEqual(res_k_patch.status_code, 200)
        self.assertEqual(res_k_patch.data["status"], "prepared")
        self.assertIsNotNone(res_k_patch.data["assigned_rider"])

        # 2. Rider 1 API Access & Isolation
        self.client.force_authenticate(self.rider_1)
        res_r_get = self.client.get("/api/rider/orders/")
        self.assertEqual(res_r_get.status_code, 200)
        # Rider 1 sees Order X, but CANNOT see Order Y
        rider_order_ids = [o["id"] for o in res_r_get.data["orders"]]
        self.assertIn(order_rider_1.id, rider_order_ids)
        self.assertNotIn(order_rider_2.id, rider_order_ids)

        # Rider 1 attempts to update Order Y (assigned to Rider 2) -> Must return 404
        res_cross_patch = self.client.patch(
            f"/api/rider/orders/{order_rider_2.id}/status/",
            {"status": "delivered"},
            format="json",
        )
        self.assertEqual(res_cross_patch.status_code, 404)

        # Rider 1 updates their own Order X -> 200 OK
        res_own_patch = self.client.patch(
            f"/api/rider/orders/{order_rider_1.id}/status/",
            {"status": "out_for_delivery"},
            format="json",
        )
        self.assertEqual(res_own_patch.status_code, 200)
        self.assertEqual(res_own_patch.data["status"], "out_for_delivery")

        # Rider 1 completes delivery -> 200 OK
        res_deliv = self.client.patch(
            f"/api/rider/orders/{order_rider_1.id}/status/",
            {"status": "delivered"},
            format="json",
        )
        self.assertEqual(res_deliv.status_code, 200)
        self.assertEqual(res_deliv.data["status"], "delivered")

        # Now Order X is delivered, so it is excluded from Rider 1's active orders
        res_r_after = self.client.get("/api/rider/orders/")
        self.assertEqual(res_r_after.status_code, 200)
        after_ids = [o["id"] for o in res_r_after.data["orders"]]
        self.assertNotIn(order_rider_1.id, after_ids)


from .whatsapp_agent import (
    check_and_enforce_voice_limit,
    check_and_enforce_text_limit,
    process_incoming_whatsapp_message,
    _build_system_prompt,
    _generate_agent_reply,
)
from .calling_views import check_and_enforce_call_limit


class VoiceCostOptimizationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Pizza King Cost Test",
            business_type="restaurant",
            is_approved=True,
            max_daily_voice_notes=2,
        )
        self.phone_number_id = "phone_id_cost_test_123"
        self.customer_phone = "+923001234567"

    @patch("operations.whatsapp_agent._get_business_context")
    @patch("operations.whatsapp_agent.WhatsAppService")
    @patch("operations.whatsapp_agent.transcribe_audio")
    @patch("operations.whatsapp_agent.synthesize_speech")
    @patch("operations.whatsapp_agent._generate_agent_reply")
    def test_voice_rate_limit_enforced(
        self,
        mock_generate_reply,
        mock_synthesize,
        mock_transcribe,
        mock_service_cls,
        mock_get_context,
    ):
        mock_get_context.return_value = {
            "is_configured": True,
            "company": self.company,
            "business_name": self.company.name,
            "catalog": [],
            "knowledge": [],
            "hours": [],
        }
        mock_service = MagicMock()
        mock_service.send_text_message.return_value = {"success": True}
        mock_service.download_media_file.return_value = b"fake_ogg_data"
        mock_service.upload_media.return_value = "outbound_media_999"
        mock_service.send_audio_message.return_value = {"success": True}
        mock_service_cls.return_value = mock_service

        mock_transcribe.return_value = "I want a small pizza"
        mock_generate_reply.return_value = "Order placed!"
        mock_synthesize.return_value = b"fake_tts_audio"

        # 1. First voice note - should succeed
        res1 = process_incoming_whatsapp_message(
            sender_phone=self.customer_phone,
            message_text="",
            phone_number_id=self.phone_number_id,
            media_id="media_1",
            msg_type="audio",
        )
        self.assertTrue(res1["success"])
        self.assertFalse(res1.get("rate_limited", False))
        self.assertEqual(mock_transcribe.call_count, 1)

        customer = Customer.objects.get(company=self.company, phone=self.customer_phone)
        self.assertEqual(customer.daily_voice_count, 1)

        # 2. Second voice note - reaches the limit of 2
        res2 = process_incoming_whatsapp_message(
            sender_phone=self.customer_phone,
            message_text="",
            phone_number_id=self.phone_number_id,
            media_id="media_2",
            msg_type="audio",
        )
        self.assertTrue(res2["success"])
        self.assertFalse(res2.get("rate_limited", False))
        self.assertEqual(mock_transcribe.call_count, 2)

        customer.refresh_from_db()
        self.assertEqual(customer.daily_voice_count, 2)

        # Reset call counts before 3rd attempt
        mock_transcribe.reset_mock()
        mock_synthesize.reset_mock()
        mock_generate_reply.reset_mock()
        mock_service.send_text_message.reset_mock()

        # 3. Third voice note - exceeds the limit of 2
        res3 = process_incoming_whatsapp_message(
            sender_phone=self.customer_phone,
            message_text="",
            phone_number_id=self.phone_number_id,
            media_id="media_3",
            msg_type="audio",
        )
        self.assertTrue(res3.get("rate_limited", False))
        warning_text = "⏳ You have reached the daily limit for voice messages. Please type your order or continue via text."
        self.assertEqual(res3["reply_text"], warning_text)

        # Verify external STT, TTS, and LLM APIs were NEVER called
        mock_transcribe.assert_not_called()
        mock_synthesize.assert_not_called()
        mock_generate_reply.assert_not_called()

        # Verify static warning text was dispatched to user
        mock_service.send_text_message.assert_called_once_with(
            to=self.customer_phone,
            text=warning_text,
        )

        # Ensure counter is not incremented past the limit
        customer.refresh_from_db()
        self.assertEqual(customer.daily_voice_count, 2)

    def test_voice_count_resets_next_day(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        customer = Customer.objects.create(
            company=self.company,
            phone="+923009999999",
            daily_voice_count=15,
            last_voice_date=yesterday,
        )

        allowed, limit_msg, updated_customer = check_and_enforce_voice_limit(
            company=self.company,
            phone="+923009999999",
        )

        self.assertTrue(allowed)
        self.assertIsNone(limit_msg)
        self.assertEqual(updated_customer.daily_voice_count, 1)
        self.assertEqual(updated_customer.last_voice_date, timezone.now().date())

    def test_system_prompt_brevity_rules(self):
        prompt = _build_system_prompt(
            customer_name="John",
            context={"business_name": "Fast Bites", "catalog": [], "knowledge": [], "hours": []},
        )
        self.assertIn("CRITICAL COST-SAVING RULES:", prompt)
        self.assertIn("Answer in strictly 1 to 2 short sentences. Maximum 20 words per response.", prompt)
        self.assertIn("NEVER use filler words, introductory pleasantries, or formatting like markdown/bullet points.", prompt)

    @patch("operations.whatsapp_agent._get_business_context")
    @patch("operations.whatsapp_agent.WhatsAppService")
    @patch("operations.whatsapp_agent._generate_agent_reply")
    def test_text_rate_limit_enforced(
        self,
        mock_generate_reply,
        mock_service_cls,
        mock_get_context,
    ):
        mock_get_context.return_value = {
            "is_configured": True,
            "company": self.company,
            "business_name": self.company.name,
            "catalog": [],
            "knowledge": [],
            "hours": [],
        }
        mock_service = MagicMock()
        mock_service.send_text_message.return_value = {"success": True}
        mock_service_cls.return_value = mock_service

        # 1. Simulate customer hitting 50 texts today
        customer = Customer.objects.create(
            company=self.company,
            phone=self.customer_phone,
            daily_text_count=50,
            last_text_date=timezone.now().date(),
        )
        conv = AgentConversation.objects.create(
            company=self.company,
            customer_phone=self.customer_phone,
            status="bot",
        )

        # 2. Customer sends the 51st text
        res = process_incoming_whatsapp_message(
            sender_phone=self.customer_phone,
            message_text="Hello what is your menu?",
            phone_number_id=self.phone_number_id,
            msg_type="text",
        )

        # 3. Verify rate limit response and LLM skip
        self.assertTrue(res.get("rate_limited", False))
        warning_msg = (
            "⏳ You have reached the maximum message limit for today. "
            "A human agent will assist you shortly."
        )
        self.assertEqual(res["reply_text"], warning_msg)

        # LLM must NEVER be called
        mock_generate_reply.assert_not_called()

        # Static fallback dispatched to WhatsApp user
        mock_service.send_text_message.assert_called_once_with(
            to=self.customer_phone,
            text=warning_msg,
        )

        # Conversation status transitioned to human handover
        conv.refresh_from_db()
        self.assertEqual(conv.status, "human")

    def test_call_rate_limit_rejected(self):
        # 1. Customer who already used their 3 calls today
        Customer.objects.create(
            company=self.company,
            phone=self.customer_phone,
            daily_call_count=3,
            last_call_date=timezone.now().date(),
        )

        # 2. Simulate incoming call webhook hitting limit
        response = self.client.post(
            "/api/operations/calls/incoming/",
            {
                "From": self.customer_phone,
                "CallSid": "call_quota_test_rejected_01",
                "company_id": self.company.id,
            },
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # Verify static audio rejection without AI stream
        self.assertIn("<Say>Our AI lines are currently busy. Please text your order on WhatsApp.</Say>", content)
        self.assertIn("<Hangup/>", content)
        self.assertNotIn("<Stream", content)

        # Verify VoiceCall was recorded as rejected
        vcall = VoiceCall.objects.filter(call_id="call_quota_test_rejected_01").first()
        self.assertIsNotNone(vcall)
        self.assertEqual(vcall.status, "rejected")

    def test_call_duration_limit_injected(self):
        # Customer within quota (0 calls today)
        response = self.client.post(
            "/api/operations/calls/incoming/",
            {
                "From": "+923007777777",
                "CallSid": "call_quota_test_allowed_01",
                "company_id": self.company.id,
            },
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # 3 minutes * 60 seconds = 180 seconds dynamically injected
        self.assertIn("<Stream", content)
        self.assertIn('timeLimit="180"', content)

        # Verify customer's call count incremented
        cust = Customer.objects.get(company=self.company, phone="+923007777777")
        self.assertEqual(cust.daily_call_count, 1)


from .whatsapp_agent import _dispatch_whatsapp_text, _dispatch_whatsapp_audio


class EvolutionAPIIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Evolution QR Pizza",
            business_type="restaurant",
            is_approved=True,
            whatsapp_connection_status="disconnected",
        )
        self.owner = User.objects.create_user(
            username="owner_evo_test",
            password="Password123!",
            email="owner_evo@example.com",
            company=self.company,
            role=User.ROLE_OWNER,
        )

    @patch("operations.evolution_client.requests.post")
    def test_connect_whatsapp_generates_qr(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "instance": {"instanceName": f"company_{self.company.id}", "status": "created"},
            "qrcode": {"base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."},
        }
        mock_post.return_value = mock_resp

        self.client.force_authenticate(self.owner)
        response = self.client.post("/api/operations/whatsapp/connect/")
        self.assertEqual(response.status_code, 200)

        # Verify instance name assigned
        self.company.refresh_from_db()
        expected_inst = f"company_{self.company.id}"
        self.assertEqual(self.company.whatsapp_instance_name, expected_inst)
        self.assertEqual(response.data["instance_name"], expected_inst)
        self.assertEqual(response.data["qrcode_base64"], "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...")

    @patch("operations.evolution_views.process_incoming_whatsapp_message")
    def test_evolution_webhook_routes_text_to_agent(self, mock_process_agent):
        mock_process_agent.return_value = {"success": True, "reply_text": "Agent reply text"}
        self.company.whatsapp_instance_name = "test_evo_inst_42"
        self.company.save()

        # 1. Ignore bot's own message
        res_from_me = self.client.post(
            "/api/operations/whatsapp/evolution-webhook/",
            {
                "event": "messages.upsert",
                "instance": "test_evo_inst_42",
                "data": {
                    "key": {"fromMe": True, "remoteJid": "923001234567@s.whatsapp.net"},
                    "message": {"conversation": "My own bot message"},
                },
            },
            format="json",
        )
        self.assertEqual(res_from_me.status_code, 200)
        self.assertEqual(res_from_me.data.get("ignored"), "from_me")
        mock_process_agent.assert_not_called()

        # 2. Ignore group chats
        res_group = self.client.post(
            "/api/operations/whatsapp/evolution-webhook/",
            {
                "event": "messages.upsert",
                "instance": "test_evo_inst_42",
                "data": {
                    "key": {"fromMe": False, "remoteJid": "123456789-987654@g.us"},
                    "message": {"conversation": "Group chatter"},
                },
            },
            format="json",
        )
        self.assertEqual(res_group.status_code, 200)
        self.assertEqual(res_group.data.get("ignored"), "group_message")
        mock_process_agent.assert_not_called()

        # 3. Valid customer incoming text message
        res_customer = self.client.post(
            "/api/operations/whatsapp/evolution-webhook/",
            {
                "event": "messages.upsert",
                "instance": "test_evo_inst_42",
                "data": {
                    "key": {"fromMe": False, "remoteJid": "923001234567@s.whatsapp.net"},
                    "pushName": "John Doe",
                    "message": {"conversation": "Can I order 1 large pizza?"},
                },
            },
            format="json",
        )
        self.assertEqual(res_customer.status_code, 200)
        self.assertEqual(res_customer.data.get("status"), "processed")
        mock_process_agent.assert_called_once_with(
            sender_phone="923001234567",
            message_text="Can I order 1 large pizza?",
            phone_number_id="test_evo_inst_42",
            customer_name="John Doe",
            media_id=None,
            msg_type="text",
            company=self.company,
            audio_bytes=None,
        )

    def test_evolution_webhook_updates_connection_status(self):
        self.company.whatsapp_instance_name = "test_evo_conn_inst"
        self.company.whatsapp_connection_status = "disconnected"
        self.company.save()

        response = self.client.post(
            "/api/operations/whatsapp/evolution-webhook/",
            {
                "event": "connection.update",
                "instance": "test_evo_conn_inst",
                "data": {"state": "open"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("connection_status"), "connected")

        self.company.refresh_from_db()
        self.assertEqual(self.company.whatsapp_connection_status, "connected")

    @patch("operations.evolution_client.send_text_message")
    def test_outbound_reply_uses_evolution_when_instance_set(self, mock_evo_send):
        mock_evo_send.return_value = {"key": {"id": "evo_msg_123"}, "status": "PENDING"}

        company_evo = Company.objects.create(
            name="Evo Tenant",
            whatsapp_instance_name="company_evo_inst",
        )
        company_meta = Company.objects.create(
            name="Meta Tenant",
            whatsapp_instance_name="",
        )

        mock_meta_service = MagicMock()
        mock_meta_service.send_text_message.return_value = {"success": True, "messages": [{"id": "meta_wamid_99"}]}

        # 1. Company with Evolution instance uses Evolution API
        res_evo = _dispatch_whatsapp_text(
            company=company_evo,
            phone="923009998877",
            text="Hello from Evolution!",
            service=mock_meta_service,
        )
        self.assertTrue(res_evo["success"])
        self.assertEqual(res_evo["provider"], "evolution")
        mock_evo_send.assert_called_once_with(
            instance_name="company_evo_inst",
            phone="923009998877",
            text="Hello from Evolution!",
        )
        mock_meta_service.send_text_message.assert_not_called()

        # 2. Company without Evolution instance falls back to Meta WhatsAppService
        res_meta = _dispatch_whatsapp_text(
            company=company_meta,
            phone="923009998877",
            text="Hello from Meta Cloud API!",
            service=mock_meta_service,
        )
        self.assertTrue(res_meta["success"])
        mock_meta_service.send_text_message.assert_called_once_with(
            to="923009998877",
            text="Hello from Meta Cloud API!",
        )

    @patch("operations.evolution_client.requests.post")
    def test_configure_instance_settings_rejects_calls(self, mock_post):
        from operations.evolution_client import configure_instance_settings
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "SUCCESS"}
        mock_post.return_value = mock_resp

        res = configure_instance_settings("test_instance_reject", msg_call="Custom busy message")
        self.assertEqual(res, {"status": "SUCCESS"})

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("/settings/set/test_instance_reject", args[0])
        payload = kwargs.get("json", {})
        self.assertTrue(payload.get("rejectCall"))
        self.assertEqual(payload.get("msgCall"), "Custom busy message")
        self.assertTrue(payload.get("groupsIgnore"))
        self.assertFalse(payload.get("alwaysOnline"))

    @patch("operations.evolution_client.requests.post")
    def test_get_media_base64_success(self, mock_post):
        import base64
        from operations.evolution_client import get_media_base64
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        raw_bytes = b"TEST_OGG_AUDIO_STREAM_123"
        mock_resp.json.return_value = {
            "base64": f"data:audio/ogg;base64,{base64.b64encode(raw_bytes).decode('utf-8')}"
        }
        mock_post.return_value = mock_resp

        result = get_media_base64("test_instance_media", {"key": {"id": "msg_abc"}})
        self.assertEqual(result, raw_bytes)

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("/chat/getBase64FromMediaMessage/test_instance_media", args[0])
        payload = kwargs.get("json", {})
        self.assertEqual(payload.get("message"), {"key": {"id": "msg_abc"}})
        self.assertFalse(payload.get("convertToMp4"))

    @patch("operations.evolution_client.requests.post")
    def test_get_media_base64_accepts_201_created(self, mock_post):
        import base64
        from operations.evolution_client import get_media_base64
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        raw_bytes = b"EVO_V2_201_CREATED_AUDIO"
        mock_resp.json.return_value = {
            "base64": base64.b64encode(raw_bytes).decode("utf-8"),
            "buffer": None,
        }
        mock_post.return_value = mock_resp

        result = get_media_base64("test_instance_201", {"key": {"id": "msg_201"}})
        self.assertEqual(result, raw_bytes)

    @patch("operations.evolution_client.get_media_base64")
    @patch("operations.evolution_views.process_incoming_whatsapp_message")
    def test_evolution_webhook_routes_audio_message(self, mock_process_agent, mock_get_media):
        mock_get_media.return_value = b"MOCK_DECRYPTED_AUDIO"
        mock_process_agent.return_value = {"success": True}

        self.company.whatsapp_instance_name = "test_evo_audio_inst"
        self.company.save()

        response = self.client.post(
            "/api/operations/whatsapp/evolution-webhook/",
            {
                "event": "messages.upsert",
                "instance": "test_evo_audio_inst",
                "data": {
                    "key": {"fromMe": False, "remoteJid": "923112233445@s.whatsapp.net"},
                    "pushName": "Jane Voice",
                    "message": {
                        "audioMessage": {
                            "url": "https://mmg.whatsapp.net/v/t62.7114-24/audio.enc",
                            "mimetype": "audio/ogg; codecs=opus",
                        }
                    },
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("status"), "processed")
        mock_get_media.assert_called_once()
        mock_process_agent.assert_called_once_with(
            sender_phone="923112233445",
            message_text="",
            phone_number_id="test_evo_audio_inst",
            customer_name="Jane Voice",
            media_id="evolution_voice_note",
            msg_type="audio",
            company=self.company,
            audio_bytes=b"MOCK_DECRYPTED_AUDIO",
        )

    @patch("operations.evolution_client.get_media_base64")
    @patch("operations.evolution_views.process_incoming_whatsapp_message")
    def test_evolution_webhook_reads_message_base64_inline(self, mock_process_agent, mock_get_media):
        import base64
        mock_process_agent.return_value = {"success": True}
        raw_audio = b"INLINE_AUDIO_DECRYPTED"
        b64_audio = base64.b64encode(raw_audio).decode("utf-8")

        self.company.whatsapp_instance_name = "test_evo_inline_inst"
        self.company.save()

        # Evolution API v2 with WEBHOOK_BASE64=true puts base64 in data["message"]["base64"]
        response = self.client.post(
            "/api/operations/whatsapp/evolution-webhook/",
            {
                "event": "messages.upsert",
                "instance": "test_evo_inline_inst",
                "data": {
                    "key": {"fromMe": False, "remoteJid": "923112233445@s.whatsapp.net"},
                    "pushName": "Inline Tester",
                    "message": {
                        "base64": f"data:audio/ogg;base64,{b64_audio}",
                        "audioMessage": {
                            "url": "https://mmg.whatsapp.net/v/t62.7114-24/audio.enc",
                        },
                    },
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("status"), "processed")
        # Should NOT make extra HTTP call since base64 was inline
        mock_get_media.assert_not_called()
        mock_process_agent.assert_called_once_with(
            sender_phone="923112233445",
            message_text="",
            phone_number_id="test_evo_inline_inst",
            customer_name="Inline Tester",
            media_id="evolution_voice_note",
            msg_type="audio",
            company=self.company,
            audio_bytes=raw_audio,
        )

    @patch("operations.evolution_client.get_media_base64")
    @patch("operations.evolution_views.process_incoming_whatsapp_message")
    def test_evolution_webhook_failed_audio_does_not_pass_meta_url(self, mock_process_agent, mock_get_media):
        mock_get_media.return_value = None
        mock_process_agent.return_value = {"success": True}

        self.company.whatsapp_instance_name = "test_evo_failed_audio_inst"
        self.company.save()

        response = self.client.post(
            "/api/operations/whatsapp/evolution-webhook/",
            {
                "event": "messages.upsert",
                "instance": "test_evo_failed_audio_inst",
                "data": {
                    "key": {"fromMe": False, "remoteJid": "923112233445@s.whatsapp.net"},
                    "pushName": "Failed Audio",
                    "message": {
                        "audioMessage": {
                            "url": "https://mmg.whatsapp.net/v/t62.7114-24/audio.enc",
                        },
                    },
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        mock_get_media.assert_called_once()
        # media_id MUST be None, NOT the encrypted https://mmg.whatsapp.net URL
        mock_process_agent.assert_called_once_with(
            sender_phone="923112233445",
            message_text="",
            phone_number_id="test_evo_failed_audio_inst",
            customer_name="Failed Audio",
            media_id=None,
            msg_type="audio",
            company=self.company,
            audio_bytes=None,
        )

    @patch("operations.whatsapp_agent._dispatch_whatsapp_text")
    @patch("operations.whatsapp_agent.transcribe_audio")
    @patch("operations.whatsapp_agent._generate_agent_reply")
    def test_whatsapp_agent_processes_raw_audio_bytes(self, mock_reply, mock_transcribe, mock_dispatch):
        from operations.whatsapp_agent import process_incoming_whatsapp_message
        mock_transcribe.return_value = "Mujhe 2 Zinger burger bhej do"
        mock_reply.return_value = "Order placed successfully!"
        mock_dispatch.return_value = {"success": True}

        self.company.whatsapp_instance_name = "test_evo_audio_agent_inst"
        self.company.save()

        result = process_incoming_whatsapp_message(
            sender_phone="923001239999",
            message_text="",
            phone_number_id="test_evo_audio_agent_inst",
            customer_name="Audio Tester",
            media_id="mock_media_id",
            msg_type="audio",
            company=self.company,
            audio_bytes=b"OGG_RAW_BYTES_TEST",
        )
        self.assertTrue(result["success"])
        mock_transcribe.assert_called_once_with(b"OGG_RAW_BYTES_TEST", filename="audio.ogg")
        mock_reply.assert_called_once()


class Sprint1SharedCoreTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_restaurant = Company.objects.create(
            name="Sprint1 Gourmet",
            business_type="restaurant",
            status="active",
            is_approved=True,
            whatsapp_instance_name="sprint1_rest_evo",
        )
        self.company_pharmacy = Company.objects.create(
            name="Sprint1 Pharmacy",
            business_type="pharmacy",
            status="active",
            is_approved=True,
            whatsapp_instance_name="sprint1_pharma_evo",
        )
        self.company_clinic = Company.objects.create(
            name="Sprint1 Clinic",
            business_type="clinic",
            status="active",
            is_approved=True,
            whatsapp_instance_name="sprint1_clinic_evo",
        )
        self.company_retail = Company.objects.create(
            name="Sprint1 Mart",
            business_type="retail",
            status="active",
            is_approved=True,
            whatsapp_instance_name="sprint1_retail_evo",
        )

        self.owner = User.objects.create_user(
            username="sprint1_owner",
            password="Password123!",
            company=self.company_restaurant,
            role=User.ROLE_OWNER,
        )

    def test_category_aware_system_prompt_and_tools(self):
        from operations.whatsapp_agent import (
            _build_system_prompt,
            get_category_agent_config,
            TOOL_CREATE_ORDER,
            TOOL_GET_CATALOG_ITEMS,
            TOOL_CHECK_ORDER_STATUS,
        )

        # 1. Restaurant config & prompt
        rest_cfg = get_category_agent_config("restaurant")
        self.assertIn(TOOL_CREATE_ORDER, rest_cfg["tools"])
        prompt_rest = _build_system_prompt("Ali", {"business_name": "Sprint1 Gourmet", "business_type": "restaurant"})
        self.assertIn("food ordering", prompt_rest.lower())
        self.assertIn("FOOD MENU & AVAILABLE DISHES", prompt_rest)
        self.assertIn("GLOBAL HEALTH & DIETARY GUARDRAILS", prompt_rest)
        self.assertIn("Never diagnose medical conditions", prompt_rest)

        # 2. Pharmacy config & prompt
        pharma_cfg = get_category_agent_config("pharmacy")
        self.assertIn(TOOL_CREATE_ORDER, pharma_cfg["tools"])
        prompt_pharma = _build_system_prompt("Sarah", {"business_name": "Sprint1 Pharmacy", "business_type": "pharmacy"})
        self.assertIn("pharmacy assistant", prompt_pharma.lower())
        self.assertIn("MEDICINES & HEALTHCARE PRODUCTS", prompt_pharma)
        self.assertIn("prescription", prompt_pharma.lower())
        self.assertIn("GLOBAL HEALTH & DIETARY GUARDRAILS", prompt_pharma)

        # 3. Clinic config & prompt (create_order must NOT be in active tools)
        clinic_cfg = get_category_agent_config("clinic")
        self.assertNotIn(TOOL_CREATE_ORDER, clinic_cfg["tools"])
        self.assertIn(TOOL_GET_CATALOG_ITEMS, clinic_cfg["tools"])
        self.assertIn(TOOL_CHECK_ORDER_STATUS, clinic_cfg["tools"])
        prompt_clinic = _build_system_prompt("Dr. Patient", {"business_name": "Sprint1 Clinic", "business_type": "clinic"})
        self.assertIn("clinic appointment desk", prompt_clinic.lower())
        self.assertIn("CLINICAL SERVICES & SPECIALTIES", prompt_clinic)
        self.assertIn("GLOBAL HEALTH & DIETARY GUARDRAILS", prompt_clinic)

        # 4. Retail config & prompt
        retail_cfg = get_category_agent_config("retail")
        self.assertIn(TOOL_CREATE_ORDER, retail_cfg["tools"])
        prompt_retail = _build_system_prompt("Usman", {"business_name": "Sprint1 Mart", "business_type": "retail"})
        self.assertIn("retail store assistant", prompt_retail.lower())
        self.assertIn("STORE CATALOG & INVENTORY", prompt_retail)

    @patch("operations.evolution_client.send_text_message")
    def test_order_status_change_dispatches_whatsapp_notification(self, mock_evo_send):
        mock_evo_send.return_value = {"status": "SUCCESS"}

        order = Order.objects.create(
            company=self.company_restaurant,
            customer_name="Kamran",
            customer_phone="+923001112233",
            delivery_address="D-Ground, Faisalabad",
            status=Order.STATUS_NEW,
            subtotal=Decimal("850.00"),
            total=Decimal("850.00"),
            source="agent",
        )

        self.client.force_authenticate(user=self.owner)

        # 1. Update from Dashboard: NEW -> CONFIRMED
        resp = self.client.patch(
            f"/api/dashboard/orders/{order.id}/status/",
            {"status": "confirmed", "note": "Kitchen accepted"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_evo_send.call_count, 1)
        args, kwargs = mock_evo_send.call_args
        self.assertEqual(kwargs["instance_name"], "sprint1_rest_evo")
        self.assertIn("923001112233", kwargs["to"])
        self.assertIn("Order Confirmed", kwargs["text"])

        # 2. Idempotent check: same status does NOT dispatch duplicate message
        mock_evo_send.reset_mock()
        from operations.notifications import send_order_status_notification
        order.refresh_from_db()
        dispatched = send_order_status_notification(order, previous_status="confirmed", new_status="confirmed")
        self.assertFalse(dispatched)
        mock_evo_send.assert_not_called()

        # 3. Advance status: CONFIRMED -> PREPARING
        dispatched = send_order_status_notification(order, previous_status="confirmed", new_status="preparing")
        self.assertTrue(dispatched)
        self.assertEqual(mock_evo_send.call_count, 1)
        args, kwargs = mock_evo_send.call_args
        self.assertIn("Order In Preparation", kwargs["text"])

        # 4. Advance status: PREPARING -> DELIVERED
        mock_evo_send.reset_mock()
        dispatched = send_order_status_notification(order, previous_status="preparing", new_status="delivered")
        self.assertTrue(dispatched)
        self.assertEqual(mock_evo_send.call_count, 1)
        args, kwargs = mock_evo_send.call_args
        self.assertIn("Order Delivered", kwargs["text"])

    @patch("operations.evolution_client.send_text_message")
    def test_order_status_rejects_backward_transitions(self, mock_evo_send):
        """
        Verify backward transitions (ready -> new, delivered -> preparing) return 400 Bad Request
        and trigger zero WhatsApp notifications.
        """
        order = Order.objects.create(
            company=self.company_restaurant,
            customer_name="Backward Test",
            customer_phone="03090139836",
            delivery_address="Faisalabad",
            status=Order.STATUS_READY,
            subtotal=Decimal("500.00"),
            total=Decimal("500.00"),
        )
        self.client.force_authenticate(user=self.owner)

        # 1. Attempt invalid backward transition from Dashboard: ready -> new
        resp = self.client.patch(
            f"/api/dashboard/orders/{order.id}/status/",
            {"status": "new"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid status transition", resp.data.get("error", ""))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_READY)
        mock_evo_send.assert_not_called()

        # 2. Advance to terminal state 'delivered'
        resp = self.client.patch(
            f"/api/dashboard/orders/{order.id}/status/",
            {"status": "delivered"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_DELIVERED)
        self.assertEqual(mock_evo_send.call_count, 1)

        # 3. Attempt invalid transition from terminal state: delivered -> preparing
        mock_evo_send.reset_mock()
        resp = self.client.patch(
            f"/api/dashboard/orders/{order.id}/status/",
            {"status": "preparing"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid status transition", resp.data.get("error", ""))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_DELIVERED)
        mock_evo_send.assert_not_called()

    @patch("operations.evolution_client.send_text_message")
    def test_notification_normalizes_local_phone_and_handles_ready_prepared(self, mock_evo_send):
        """
        Verify local 03xx phone numbers are normalized to 923xxxxxxxxx and ready/prepared
        statuses produce proper customer WhatsApp messages.
        """
        mock_evo_send.return_value = {"status": "SUCCESS"}
        from operations.notifications import normalize_pakistan_phone, send_order_status_notification

        # Phone normalization unit tests
        self.assertEqual(normalize_pakistan_phone("03090139836"), "923090139836")
        self.assertEqual(normalize_pakistan_phone("+923090139836"), "923090139836")
        self.assertEqual(normalize_pakistan_phone("+92 309 0139836"), "923090139836")
        self.assertEqual(normalize_pakistan_phone("00923090139836"), "923090139836")
        self.assertEqual(normalize_pakistan_phone("3090139836"), "923090139836")

        order = Order.objects.create(
            company=self.company_restaurant,
            customer_name="Local Phone Test",
            customer_phone="03090139836",
            delivery_address="Faisalabad",
            status=Order.STATUS_CONFIRMED,
            subtotal=Decimal("600.00"),
            total=Decimal("600.00"),
        )

        # Dispatch 'ready' notification
        dispatched = send_order_status_notification(order, previous_status="preparing", new_status="ready")
        self.assertTrue(dispatched)
        self.assertEqual(mock_evo_send.call_count, 1)
        args, kwargs = mock_evo_send.call_args
        self.assertEqual(kwargs["to"], "923090139836")
        self.assertIn("Order Ready", kwargs["text"])

        # Dispatch 'prepared' notification
        mock_evo_send.reset_mock()
        dispatched = send_order_status_notification(order, previous_status="preparing", new_status="prepared")
        self.assertTrue(dispatched)
        self.assertEqual(mock_evo_send.call_count, 1)
        args, kwargs = mock_evo_send.call_args
        self.assertEqual(kwargs["to"], "923090139836")
        self.assertIn("Order Ready", kwargs["text"])


class PharmacyPlatformTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_pharmacy = Company.objects.create(
            name="CarePlus Pharmacy",
            business_type="pharmacy",
            status="active",
            is_approved=True,
            whatsapp_instance_name="careplus_pharma_inst",
        )
        self.company_other = Company.objects.create(
            name="Other Shop",
            business_type="retail",
            status="active",
            is_approved=True,
        )

        self.pharmacist = User.objects.create_user(
            username="pharmacist_ali",
            password="Password123!",
            company=self.company_pharmacy,
            role=User.ROLE_OWNER,
        )
        self.other_user = User.objects.create_user(
            username="other_owner",
            password="Password123!",
            company=self.company_other,
            role=User.ROLE_OWNER,
        )

        from companies.models import CatalogItem
        self.medicine = CatalogItem.objects.create(
            company=self.company_pharmacy,
            name="Augmentin 625mg",
            generic_name="Amoxicillin + Clavulanate",
            price=Decimal("450.00"),
            requires_prescription=True,
            is_available=True,
        )

    def test_medicine_batch_expiry_status_and_isolation(self):
        from operations.models import MedicineBatch
        from datetime import date, timedelta

        today = date.today()

        # 1. Safe batch (expiry in 60 days)
        b_safe = MedicineBatch.objects.create(
            company=self.company_pharmacy,
            item=self.medicine,
            batch_number="AUG-SAFE-01",
            expiry_date=today + timedelta(days=60),
            quantity=100,
        )
        self.assertEqual(b_safe.status, "safe")

        # 2. Expiring soon batch (expiry in 15 days)
        b_soon = MedicineBatch.objects.create(
            company=self.company_pharmacy,
            item=self.medicine,
            batch_number="AUG-SOON-02",
            expiry_date=today + timedelta(days=15),
            quantity=20,
        )
        self.assertEqual(b_soon.status, "expiring_soon")

        # 3. Expired batch (expiry 5 days ago)
        b_expired = MedicineBatch.objects.create(
            company=self.company_pharmacy,
            item=self.medicine,
            batch_number="AUG-EXP-03",
            expiry_date=today - timedelta(days=5),
            quantity=10,
        )
        self.assertEqual(b_expired.status, "expired")

        # 4. Unauthenticated access rejected with 401
        resp = self.client.get("/api/pharmacy/batches/")
        self.assertEqual(resp.status_code, 401)

        # 5. Pharmacist access returns all batches & summary counts
        self.client.force_authenticate(user=self.pharmacist)
        resp = self.client.get("/api/pharmacy/batches/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["summary"]["total_batches"], 3)
        self.assertEqual(resp.data["summary"]["expired_count"], 1)
        self.assertEqual(resp.data["summary"]["expiring_soon_count"], 1)
        self.assertEqual(resp.data["count"], 3)

        # 6. Tenant isolation: Other tenant sees 0 batches
        self.client.force_authenticate(user=self.other_user)
        resp = self.client.get("/api/pharmacy/batches/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["summary"]["total_batches"], 0)
        self.assertEqual(resp.data["count"], 0)

    @patch("operations.evolution_client.send_text_message")
    def test_prescription_lifecycle_and_whatsapp_notification(self, mock_evo_send):
        mock_evo_send.return_value = {"status": "SUCCESS"}
        from operations.models import Prescription

        self.client.force_authenticate(user=self.pharmacist)

        # 1. Create prescription request
        resp = self.client.post("/api/pharmacy/prescriptions/", {
            "customer_name": "Hamza Tariq",
            "customer_phone": "03090139836",
            "requested_items_text": "2x Augmentin 625mg, 1x Panadol",
            "notes": "Prescribed by Dr. Asim at DHQ Faisalabad",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        rx_id = resp.data["id"]
        rx_number = resp.data["prescription_number"]
        self.assertTrue(rx_number.startswith("RX-"))
        self.assertEqual(resp.data["status"], "pending")

        # 2. Approve prescription -> triggers WhatsApp notification
        resp = self.client.patch(f"/api/pharmacy/prescriptions/{rx_id}/status/", {
            "status": "approved",
            "pharmacist_notes": "Prescription verified and approved by pharmacist Ali",
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "approved")
        self.assertEqual(mock_evo_send.call_count, 1)
        args, kwargs = mock_evo_send.call_args
        self.assertEqual(kwargs["to"], "923090139836")
        self.assertIn("Approved", kwargs["text"])

        # 3. Invalid backward transition rejected (approved -> pending)
        resp = self.client.patch(f"/api/pharmacy/prescriptions/{rx_id}/status/", {
            "status": "pending",
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid prescription transition", resp.data["error"])

        # 4. Mark Dispensed
        mock_evo_send.reset_mock()
        resp = self.client.patch(f"/api/pharmacy/prescriptions/{rx_id}/status/", {
            "status": "dispensed",
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "dispensed")
        self.assertEqual(mock_evo_send.call_count, 1)

    def test_pharmacy_ai_agent_prescription_submission_tool(self):
        from operations.whatsapp_agent import (
            get_category_agent_config,
            execute_submit_prescription_request,
            TOOL_SUBMIT_PRESCRIPTION_REQUEST,
            execute_get_catalog_items,
        )
        from operations.models import Prescription

        # 1. Config includes submit_prescription_request tool for pharmacy
        cfg = get_category_agent_config("pharmacy")
        self.assertIn(TOOL_SUBMIT_PRESCRIPTION_REQUEST, cfg["tools"])

        # 2. Catalog includes requires_prescription flag
        cat_result = execute_get_catalog_items(self.company_pharmacy)
        self.assertTrue(cat_result["success"])
        items = cat_result["items"]
        augmentin = next((it for it in items if it["id"] == self.medicine.id), None)
        self.assertIsNotNone(augmentin)
        self.assertTrue(augmentin["requires_prescription"])
        self.assertEqual(augmentin["generic_name"], "Amoxicillin + Clavulanate")

        # 3. Execute tool: submit_prescription_request creates Prescription record
        res = execute_submit_prescription_request(
            company=self.company_pharmacy,
            customer_phone="03001234567",
            customer_name="Zainab",
            requested_items="Augmentin 625mg 1 strip",
            notes="Doctor advised 5 days course",
        )
        self.assertTrue(res["success"])
        self.assertIn("RX-", res["prescription_number"])
        self.assertTrue(Prescription.objects.filter(
            company=self.company_pharmacy,
            prescription_number=res["prescription_number"],
            status="pending",
        ).exists())
















