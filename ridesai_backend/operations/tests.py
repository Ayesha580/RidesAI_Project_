from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import StaffRole, User
from companies.models import Company, CatalogCategory
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
            subscription_status="active",
            is_manual_override=True,
            status="active",
        )
        self.company_b = Company.objects.create(
            name="Pizza Palace",
            business_type="restaurant",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
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
            customer_phone="+923009988771",
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
        self.assertEqual(order.customer_phone, "+923009988771")
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
            customer_phone="+923009988772",
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
            customer_phone="+923009988773",
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
                sender_phone="+923009876543",
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
        conv = AgentConversation.objects.filter(company=self.company_a, customer_phone="+923009876543").first()
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
                sender_phone="+923009876543",
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
        created_order = Order.objects.filter(company=self.company_a, customer_phone="+923009876543").first()
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
            subscription_status="active",
            is_manual_override=True,
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
            subscription_status="active",
            is_manual_override=True,
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


class ClinicPlatformTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.clinic_company = Company.objects.create(
            name="Care Clinic",
            business_type="clinic",
            address="123 Hospital Rd, Faisalabad",
            phone="03001112233",
            status="active",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            whatsapp_instance_name="care_clinic_inst",
        )
        self.other_company = Company.objects.create(
            name="Other Clinic",
            business_type="clinic",
            address="456 Other Rd, Faisalabad",
            phone="03009998877",
            status="active",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            whatsapp_instance_name="care_clinic_inst",
        )
        self.owner = User.objects.create_user(
            username="care_owner@clinic.pk",
            email="care_owner@clinic.pk",
            password="Password123!",
            company=self.clinic_company,
            role="owner",
            email_verified=True,
        )
        self.other_user = User.objects.create_user(
            username="other_owner@clinic.pk",
            email="other_owner@clinic.pk",
            password="Password123!",
            company=self.other_company,
            role="owner",
            email_verified=True,
        )

    def test_doctor_and_patient_crud_and_tenant_isolation(self):
        # 1. Unauthenticated -> 401
        resp = self.client.get("/api/clinic/doctors/")
        self.assertEqual(resp.status_code, 401)

        # 2. Authenticated as Care Clinic
        self.client.force_authenticate(user=self.owner)
        doc_resp = self.client.post("/api/clinic/doctors/", {
            "name": "Dr. Hamza",
            "specialty": "Cardiologist",
            "qualification": "MBBS, FCPS",
            "consultation_fee": "2000.00",
            "available_days": "Mon-Fri",
            "available_hours": "05:00 PM - 09:00 PM",
            "is_active": True,
        }, format="json")
        self.assertEqual(doc_resp.status_code, 201)
        doc_id = doc_resp.data["id"]

        # Create patient
        pat_resp = self.client.post("/api/clinic/patients/", {
            "name": "Ali Hassan",
            "phone": "03001239876",
            "age": 30,
            "gender": "Male",
            "notes": "Chest discomfort",
        }, format="json")
        self.assertEqual(pat_resp.status_code, 201)
        pat_id = pat_resp.data["id"]

        # 3. Other company cannot see or edit
        self.client.force_authenticate(user=self.other_user)
        other_list = self.client.get("/api/clinic/doctors/")
        self.assertEqual(len(other_list.data["doctors"]), 0)

        other_patch = self.client.patch(f"/api/clinic/doctors/{doc_id}/", {"consultation_fee": "1000.00"}, format="json")
        self.assertEqual(other_patch.status_code, 404)

        other_pat_patch = self.client.patch(f"/api/clinic/patients/{pat_id}/", {"name": "Hacked"}, format="json")
        self.assertEqual(other_pat_patch.status_code, 404)

    @patch("operations.evolution_client.send_text_message")
    def test_appointment_lifecycle_and_notifications(self, mock_evo_send):
        from operations.models import Doctor, Patient, Appointment
        mock_evo_send.return_value = {"success": True}
        self.client.force_authenticate(user=self.owner)

        # 1. Register doctor and patient
        doc = Doctor.objects.create(
            company=self.clinic_company,
            name="Dr. Sarah",
            specialty="Dermatologist",
            consultation_fee=Decimal("1800.00"),
        )
        pat = Patient.objects.create(
            company=self.clinic_company,
            name="Hina",
            phone="03090139836",
        )

        # 2. Create appointment
        resp = self.client.post("/api/clinic/appointments/", {
            "patient_name": "Hina",
            "patient_phone": "03090139836",
            "doctor_id": doc.id,
            "appointment_date": "2026-11-25",
            "appointment_time": "03:00 PM",
            "reason": "Skin checkup",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        apt_id = resp.data["id"]
        apt_num = resp.data["appointment_number"]
        self.assertTrue(apt_num.startswith("APT-"))
        self.assertEqual(resp.data["status"], "pending")

        # 3. Confirm appointment -> WhatsApp notification sent
        confirm_resp = self.client.patch(f"/api/clinic/appointments/{apt_id}/status/", {
            "status": "confirmed",
            "staff_notes": "Confirmed slot with Dr. Sarah",
        }, format="json")
        self.assertEqual(confirm_resp.status_code, 200)
        self.assertEqual(confirm_resp.data["status"], "confirmed")
        self.assertEqual(mock_evo_send.call_count, 1)
        args, kwargs = mock_evo_send.call_args
        self.assertEqual(kwargs["to"], "923090139836")
        self.assertIn("Appointment Confirmed", kwargs["text"])

        # 4. Mark checked_in
        checkin_resp = self.client.patch(f"/api/clinic/appointments/{apt_id}/status/", {
            "status": "checked_in",
        }, format="json")
        self.assertEqual(checkin_resp.status_code, 200)

        # 5. Mark completed
        mock_evo_send.reset_mock()
        complete_resp = self.client.patch(f"/api/clinic/appointments/{apt_id}/status/", {
            "status": "completed",
        }, format="json")
        self.assertEqual(complete_resp.status_code, 200)
        self.assertEqual(mock_evo_send.call_count, 1)

        # 6. Invalid backward transition rejected (completed -> pending)
        invalid_resp = self.client.patch(f"/api/clinic/appointments/{apt_id}/status/", {
            "status": "pending",
        }, format="json")
        self.assertEqual(invalid_resp.status_code, 400)
        self.assertIn("Invalid appointment transition", invalid_resp.data["error"])

    def test_clinic_ai_agent_tools(self):
        from operations.models import Doctor, Patient, Appointment
        from operations.whatsapp_agent import (
            get_category_agent_config,
            execute_get_clinic_doctors,
            execute_book_appointment,
            TOOL_GET_CLINIC_DOCTORS,
            TOOL_BOOK_APPOINTMENT,
            TOOL_CREATE_ORDER,
        )

        cfg = get_category_agent_config("clinic")
        self.assertEqual(cfg["key"], "clinic")
        self.assertIn(TOOL_GET_CLINIC_DOCTORS, cfg["tools"])
        self.assertIn(TOOL_BOOK_APPOINTMENT, cfg["tools"])
        self.assertNotIn(TOOL_CREATE_ORDER, cfg["tools"])

        # Test execute_get_clinic_doctors
        Doctor.objects.create(
            company=self.clinic_company,
            name="Dr. Tariq",
            specialty="Pediatrician",
            consultation_fee=Decimal("1200.00"),
            is_active=True,
        )
        res_docs = execute_get_clinic_doctors(self.clinic_company)
        self.assertTrue(res_docs["success"])
        self.assertEqual(res_docs["count"], 1)
        self.assertEqual(res_docs["doctors"][0]["name"], "Dr. Tariq")
        self.assertEqual(res_docs["doctors"][0]["consultation_fee"], "Rs. 1200")

        # Test execute_book_appointment
        res_book = execute_book_appointment(
            company=self.clinic_company,
            sender_phone="03001234567",
            patient_name="Ahmad",
            doctor_name="Dr. Tariq",
            preferred_date="2026-11-26",
            preferred_time="11:00 AM",
            reason="Child fever",
        )
        self.assertTrue(res_book["success"])
        self.assertTrue(res_book["appointment_number"].startswith("APT-"))
        self.assertEqual(res_book["doctor"], "Dr. Tariq")
        self.assertEqual(res_book["consultation_fee"], "Rs. 1200")
        self.assertTrue(Appointment.objects.filter(
            company=self.clinic_company,
            appointment_number=res_book["appointment_number"],
            status="pending",
        ).exists())


from rest_framework import status as drf_status
from django.urls import reverse as django_reverse


class RetailPlatformTests(TestCase):
    """
    Test suite for the Retail / Store Platform:
    - Fulfillment board (packing & dispatch) with forward-only order transitions
    - Returns & exchanges lifecycle (pending -> approved | rejected -> completed)
    - Low stock & out of stock inventory alerts
    - Multi-tenant company isolation
    - Shared AI agent retail tools (submit_return_request)
    """

    def setUp(self):
        self.retail_company_a = Company.objects.create(
            name="Alpha Retail Mart",
            business_type="retail",
            status="active",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            whatsapp_instance_name="alpha_retail_inst",
            whatsapp_connection_status="connected",
            currency_symbol="Rs.",
        )
        self.retail_company_b = Company.objects.create(
            name="Beta Electronics",
            business_type="retail",
            status="active",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            whatsapp_instance_name="beta_elect_inst",
            whatsapp_connection_status="connected",
            currency_symbol="Rs.",
        )

        self.owner_a = User.objects.create_user(
            username="owner_alpha@test.pk",
            email="owner_alpha@test.pk",
            password="Password123!",
            company=self.retail_company_a,
            role=User.ROLE_OWNER,
            email_verified=True,
        )
        self.owner_b = User.objects.create_user(
            username="owner_beta@test.pk",
            email="owner_beta@test.pk",
            password="Password123!",
            company=self.retail_company_b,
            role=User.ROLE_OWNER,
            email_verified=True,
        )

        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.owner_a)

        self.client_b = APIClient()
        self.client_b.force_authenticate(user=self.owner_b)

        # Products & Inventory
        from companies.models import CatalogItem, Inventory
        self.prod_in_stock = CatalogItem.objects.create(
            company=self.retail_company_a,
            name="Wireless Headphones",
            sku="WH-100",
            price=Decimal("3500.00"),
            is_available=True,
        )
        Inventory.objects.create(
            company=self.retail_company_a,
            item=self.prod_in_stock,
            is_unlimited=False,
            quantity=Decimal("50"),
            low_stock_threshold=Decimal("10"),
        )

        self.prod_low_stock = CatalogItem.objects.create(
            company=self.retail_company_a,
            name="Gaming Mouse RGB",
            sku="GM-200",
            price=Decimal("1800.00"),
            is_available=True,
        )
        Inventory.objects.create(
            company=self.retail_company_a,
            item=self.prod_low_stock,
            is_unlimited=False,
            quantity=Decimal("6"),  # Low stock
            low_stock_threshold=Decimal("10"),
        )

        self.prod_out_of_stock = CatalogItem.objects.create(
            company=self.retail_company_a,
            name="Mechanical Keyboard",
            sku="MK-300",
            price=Decimal("5500.00"),
            is_available=False,
        )
        Inventory.objects.create(
            company=self.retail_company_a,
            item=self.prod_out_of_stock,
            is_unlimited=False,
            quantity=Decimal("0"),  # Out of stock
            low_stock_threshold=Decimal("5"),
        )

        # Orders for fulfillment
        self.order_to_pack = Order.objects.create(
            company=self.retail_company_a,
            customer_name="Usman Ali",
            customer_phone="+923001112233",
            delivery_address="Faisalabad D-Ground",
            status=Order.STATUS_NEW,
            subtotal=Decimal("3500.00"),
            delivery_fee=Decimal("150.00"),
            total=Decimal("3650.00"),
        )
        OrderItem.objects.create(
            order=self.order_to_pack,
            item=self.prod_in_stock,
            item_name=self.prod_in_stock.name,
            quantity=Decimal("1"),
            unit_price=self.prod_in_stock.price,
            line_total=self.prod_in_stock.price,
        )

        self.order_ready = Order.objects.create(
            company=self.retail_company_a,
            customer_name="Ayesha Khan",
            customer_phone="+923214445566",
            delivery_address="Faisalabad Kohinoor",
            status=Order.STATUS_READY,
            subtotal=Decimal("1800.00"),
            delivery_fee=Decimal("150.00"),
            total=Decimal("1950.00"),
        )

    def test_retail_fulfillment_listing_and_kpis(self):
        url = django_reverse("retail_fulfillment")
        resp = self.client_a.get(url)
        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        self.assertIn("kpis", resp.data)
        self.assertIn("results", resp.data)
        self.assertEqual(resp.data["kpis"]["total"], 2)
        self.assertEqual(resp.data["kpis"]["to_pack"], 1)
        self.assertEqual(resp.data["kpis"]["ready"], 1)

        # Test filter by stage
        resp_filtered = self.client_a.get(url, {"stage": "to_pack"})
        self.assertEqual(resp_filtered.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(len(resp_filtered.data["results"]), 1)
        self.assertEqual(resp_filtered.data["results"][0]["id"], self.order_to_pack.id)

    @patch("operations.retail_views.send_status_notification")
    def test_retail_fulfillment_forward_status_transition(self, mock_notify):
        mock_notify.return_value = {"ok": True, "provider": "evolution"}
        url = django_reverse("retail_fulfillment_status", kwargs={"order_id": self.order_to_pack.id})

        # Advance to preparing (packing)
        resp = self.client_a.patch(url, {"status": "preparing"})
        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        self.order_to_pack.refresh_from_db()
        self.assertEqual(self.order_to_pack.status, "preparing")
        mock_notify.assert_called_once()

        # Reject backward transition from preparing -> new
        resp_bad = self.client_a.patch(url, {"status": "new"})
        self.assertEqual(resp_bad.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid status transition", resp_bad.data["detail"])

    @patch("operations.retail_views.send_status_notification")
    def test_retail_returns_crud_and_status_transitions(self, mock_notify):
        mock_notify.return_value = {"ok": True, "provider": "evolution"}
        from operations.models import ReturnRequest

        # 1. Create Return Request
        create_url = django_reverse("retail_returns")
        create_payload = {
            "customer_phone": "+923001112233",
            "customer_name": "Usman Ali",
            "order_number": self.order_to_pack.order_number,
            "item_summary": "1x Wireless Headphones",
            "reason": "Faulty left audio driver",
            "request_type": "return",
        }
        resp = self.client_a.post(create_url, create_payload)
        self.assertEqual(resp.status_code, drf_status.HTTP_201_CREATED)
        ret_id = resp.data["return_request"]["id"]
        ret = ReturnRequest.objects.get(pk=ret_id)
        self.assertEqual(ret.status, ReturnRequest.STATUS_PENDING)
        self.assertTrue(ret.return_number.startswith("RET-"))

        # 2. Approve Return Request
        status_url = django_reverse("retail_return_status", kwargs={"pk": ret_id})
        resp_approve = self.client_a.patch(status_url, {
            "status": "approved",
            "staff_notes": "Return approved. Please keep in original packaging.",
        })
        self.assertEqual(resp_approve.status_code, drf_status.HTTP_200_OK)
        ret.refresh_from_db()
        self.assertEqual(ret.status, "approved")
        mock_notify.assert_called_once()

        # 3. Complete Return Request
        resp_comp = self.client_a.patch(status_url, {
            "status": "completed",
            "staff_notes": "Item received and refund processed.",
        })
        self.assertEqual(resp_comp.status_code, drf_status.HTTP_200_OK)
        ret.refresh_from_db()
        self.assertEqual(ret.status, "completed")

        # 4. Reject backward transition from completed -> pending
        resp_inv = self.client_a.patch(status_url, {"status": "pending"})
        self.assertEqual(resp_inv.status_code, drf_status.HTTP_400_BAD_REQUEST)

    @patch("operations.evolution_client.send_text_message")
    def test_retail_return_approval_evolution_notification(self, mock_evolution):
        mock_evolution.return_value = {"status": "SUCCESS"}
        from operations.models import ReturnRequest
        ret = ReturnRequest.objects.create(
            company=self.retail_company_a,
            customer_phone="03001234567",
            customer_name="Usman Ali",
            order_number=self.order_to_pack.order_number,
            item_summary="1x Wireless Headphones",
            reason="Faulty device",
            request_type="return",
            status=ReturnRequest.STATUS_PENDING,
        )
        status_url = django_reverse("retail_return_status", kwargs={"pk": ret.id})
        resp = self.client_a.patch(status_url, {
            "status": "approved",
            "staff_notes": "Return approved by manager.",
        })
        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        self.assertTrue(resp.data["notification_sent"])
        ret.refresh_from_db()
        self.assertEqual(ret.status, "approved")
        mock_evolution.assert_called_once()
        call_kwargs = mock_evolution.call_args[1]
        self.assertEqual(call_kwargs["instance_name"], "alpha_retail_inst")
        self.assertEqual(call_kwargs["phone"], "923001234567")
        self.assertEqual(call_kwargs["to"], "923001234567")
        self.assertIn("Return Request Approved", call_kwargs["text"])

    @patch("operations.evolution_client.send_text_message")
    def test_exchange_approval_creates_replacement_order_and_completes_on_delivery(self, mock_evolution):
        mock_evolution.return_value = {"status": "SUCCESS"}
        from operations.models import ReturnRequest, Order

        # 1. Create an exchange request
        exchange_req = ReturnRequest.objects.create(
            company=self.retail_company_a,
            order=self.order_to_pack,
            order_number=self.order_to_pack.order_number,
            customer_name="Hamza Tariq",
            customer_phone="03009988776",
            item_summary="1x Wireless Headphones",
            reason="Color replacement requested",
            request_type=ReturnRequest.TYPE_EXCHANGE,
            status=ReturnRequest.STATUS_PENDING,
        )

        status_url = django_reverse("retail_return_status", kwargs={"pk": exchange_req.id})

        # 2. Approve the exchange request -> replacement_order MUST be created
        resp_approve = self.client_a.patch(status_url, {
            "status": "approved",
            "staff_notes": "Exchange approved for doorstep replacement swap",
        })
        self.assertEqual(resp_approve.status_code, drf_status.HTTP_200_OK)
        exchange_req.refresh_from_db()
        self.assertEqual(exchange_req.status, ReturnRequest.STATUS_APPROVED)
        self.assertIsNotNone(exchange_req.replacement_order)

        rep_order = exchange_req.replacement_order
        self.assertEqual(rep_order.status, Order.STATUS_CONFIRMED)
        self.assertEqual(rep_order.total, Decimal("0.00"))
        self.assertIn("EXCHANGE SWAP", rep_order.notes)
        self.assertEqual(rep_order.customer_phone, exchange_req.customer_phone)
        self.assertEqual(resp_approve.data["replacement_order_number"], rep_order.order_number)

        # 3. Advance replacement_order through fulfillment: confirmed -> preparing -> ready -> out_for_delivery -> delivered
        fulfillment_status_url = django_reverse("retail_fulfillment_status", kwargs={"order_id": rep_order.id})
        self.client_a.patch(fulfillment_status_url, {"status": "preparing"})
        self.client_a.patch(fulfillment_status_url, {"status": "ready"})
        self.client_a.patch(fulfillment_status_url, {"status": "out_for_delivery"})
        resp_delivered = self.client_a.patch(fulfillment_status_url, {"status": "delivered"})
        self.assertEqual(resp_delivered.status_code, drf_status.HTTP_200_OK)

        # Assert ReturnRequest automatically transitioned to completed upon delivery
        exchange_req.refresh_from_db()
        self.assertEqual(exchange_req.status, ReturnRequest.STATUS_COMPLETED)
        self.assertIn("Auto-completed", exchange_req.staff_notes)

        # 4. Verify that approving a standard return (refund) does NOT create a replacement order
        return_req = ReturnRequest.objects.create(
            company=self.retail_company_a,
            order=self.order_to_pack,
            order_number=self.order_to_pack.order_number,
            customer_name="Ali Khan",
            customer_phone="03001122334",
            item_summary="1x Wireless Headphones",
            reason="Unwanted gift",
            request_type=ReturnRequest.TYPE_RETURN,
            status=ReturnRequest.STATUS_PENDING,
        )
        return_status_url = django_reverse("retail_return_status", kwargs={"pk": return_req.id})
        resp_return_approve = self.client_a.patch(return_status_url, {
            "status": "approved",
            "staff_notes": "Return approved for refund",
        })
        self.assertEqual(resp_return_approve.status_code, drf_status.HTTP_200_OK)
        return_req.refresh_from_db()
        self.assertEqual(return_req.status, ReturnRequest.STATUS_APPROVED)
        self.assertIsNone(return_req.replacement_order)

    def test_retail_inventory_alerts(self):
        url = django_reverse("retail_inventory_alerts")
        resp = self.client_a.get(url)
        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        kpis = resp.data["kpis"]
        self.assertEqual(kpis["low_stock_count"], 1)
        self.assertEqual(kpis["out_of_stock_count"], 1)
        self.assertEqual(kpis["total_alerts"], 2)

        low_skus = [it["sku"] for it in resp.data["low_stock"]]
        self.assertIn("GM-200", low_skus)

        out_skus = [it["sku"] for it in resp.data["out_of_stock"]]
        self.assertIn("MK-300", out_skus)

    def test_retail_multi_tenant_isolation(self):
        # Company B cannot view Company A's fulfillment orders
        url = django_reverse("retail_fulfillment")
        resp_b = self.client_b.get(url)
        self.assertEqual(resp_b.status_code, drf_status.HTTP_200_OK)
        self.assertEqual(resp_b.data["kpis"]["total"], 0)
        self.assertEqual(len(resp_b.data["results"]), 0)

        # Company B cannot modify Company A's order status
        status_url = django_reverse("retail_fulfillment_status", kwargs={"order_id": self.order_to_pack.id})
        resp_patch_b = self.client_b.patch(status_url, {"status": "preparing"})
        self.assertEqual(resp_patch_b.status_code, drf_status.HTTP_404_NOT_FOUND)

    def test_retail_agent_tools_and_return_request(self):
        from operations.whatsapp_agent import (
            get_category_agent_config,
            execute_submit_return_request,
            TOOL_SUBMIT_RETURN_REQUEST,
            TOOL_GET_CATALOG_ITEMS,
            TOOL_CREATE_ORDER,
            TOOL_CHECK_ORDER_STATUS,
        )
        from operations.models import ReturnRequest

        cfg = get_category_agent_config("retail")
        self.assertEqual(cfg["key"], "retail")
        self.assertIn(TOOL_SUBMIT_RETURN_REQUEST, cfg["tools"])
        self.assertIn(TOOL_GET_CATALOG_ITEMS, cfg["tools"])
        self.assertIn(TOOL_CREATE_ORDER, cfg["tools"])
        self.assertIn(TOOL_CHECK_ORDER_STATUS, cfg["tools"])

        # Test execute_submit_return_request
        res = execute_submit_return_request(
            company=self.retail_company_a,
            sender_phone="+923001112233",
            customer_name="Usman Ali",
            order_number=self.order_to_pack.order_number,
            item_summary="1x Wireless Headphones",
            reason="Color mismatch",
            request_type="exchange",
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["return_number"].startswith("RET-"))
        self.assertEqual(res["request_type"], "exchange")
        self.assertTrue(ReturnRequest.objects.filter(
            company=self.retail_company_a,
            return_number=res["return_number"],
            request_type="exchange",
            status="pending",
        ).exists())


class PublicVoiceAgentMultiTurnOrderTests(TestCase):
    def setUp(self):
        import uuid
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Burger King",
            agent_enabled=True,
            agent_public_id=uuid.uuid4(),
            business_type="restaurant",
            is_approved=True,
            status="active",
            subscription_status="active",
            is_manual_override=True,
        )
        self.item_burger = CatalogItem.objects.create(
            company=self.company,
            name="Zinger Burger",
            price=Decimal("650.00"),
            description="Crispy chicken fillet with lettuce and mayo",
            is_available=True,
        )
        self.item_fries = CatalogItem.objects.create(
            company=self.company,
            name="Crispy Fries",
            price=Decimal("250.00"),
            description="Golden salted french fries",
            is_available=True,
        )

    @patch("operations.audio_service.synthesize_speech", return_value=b"MOCK_TTS_BYTES")
    @patch("operations.whatsapp_agent.OpenAI")
    def test_three_turn_voice_agent_order_and_no_menu_spam(self, mock_openai_cls, mock_synth):
        import json
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        url = f"/api/operations/public/agent/{self.company.agent_public_id}/chat/"

        with patch.object(settings, "OPENAI_API_KEY", "sk-mock-valid-key-for-test"):
            # Turn 1: Customer asks for menu
            turn1_resp = MagicMock()
            turn1_msg = MagicMock()
            turn1_msg.tool_calls = None
            turn1_msg.content = "We have Zinger Burger for 650 rupees and Crispy Fries for 250 rupees. What would you like to order?"
            turn1_resp.choices = [MagicMock(message=turn1_msg)]
            mock_client.chat.completions.create.return_value = turn1_resp

            res1 = self.client.post(url, {"message": "What is on the menu?"}, format="json")
            self.assertEqual(res1.status_code, 200)
            self.assertTrue(len(res1.data["menu_items"]) > 0, "Turn 1 menu request should return menu_items")
            conv_id = res1.data["conversation_id"]
            self.assertIsNotNone(conv_id)
            self.assertIsNone(res1.data["order_summary"])

            # Turn 2: Customer specifies items, AI asks for address
            turn2_resp = MagicMock()
            turn2_msg = MagicMock()
            turn2_msg.tool_calls = None
            turn2_msg.content = "Your order is 1 Zinger Burger and 1 Crispy Fries. Total is 900 rupees. Please provide your name, phone number, and delivery address to confirm and place your order."
            turn2_resp.choices = [MagicMock(message=turn2_msg)]
            mock_client.chat.completions.create.return_value = turn2_resp

            res2 = self.client.post(
                url,
                {"message": "I want 1 Crispy Fries and 1 Zinger Burger", "conversation_id": conv_id},
                format="json",
            )
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(res2.data["conversation_id"], conv_id)
            self.assertEqual(res2.data["menu_items"], [], "Turn 2 ordering/address request should return menu_items: []")
            self.assertIsNone(res2.data["order_summary"])

            # Turn 3: Customer provides address, name, phone, and confirms order
            turn3_tool_call = MagicMock()
            turn3_tool_call.id = "call_create_order_turn3"
            turn3_tool_call.function.name = "create_order"
            turn3_tool_call.function.arguments = json.dumps({
                "items": [
                    {"item_name": "Zinger Burger", "quantity": 1},
                    {"item_name": "Crispy Fries", "quantity": 1},
                ],
                "customer_name": "Ali",
                "customer_phone": "03009876543",
                "delivery_address": "133 A New Satellite Town",
            })
            turn3_first_msg = MagicMock()
            turn3_first_msg.tool_calls = [turn3_tool_call]
            turn3_first_msg.content = None

            turn3_second_msg = MagicMock()
            turn3_second_msg.tool_calls = None
            turn3_second_msg.content = "Your order #RA-998877 has been placed! Total is 900 rupees and will be delivered in 30-45 minutes."

            mock_client.chat.completions.create.side_effect = [
                MagicMock(choices=[MagicMock(message=turn3_first_msg)]),
                MagicMock(choices=[MagicMock(message=turn3_second_msg)]),
            ]

            res3 = self.client.post(
                url,
                {
                    "message": "My name is Ali, phone 03009876543, address 133 A New Satellite Town, confirm order",
                    "conversation_id": conv_id,
                },
                format="json",
            )
            self.assertEqual(res3.status_code, 200)
            self.assertEqual(res3.data["conversation_id"], conv_id)
            self.assertEqual(res3.data["menu_items"], [], "Turn 3 confirmation should return menu_items: []")
            self.assertIsNotNone(res3.data["order_summary"])

            # Verify order in DB
            order = Order.objects.filter(company=self.company, customer_phone="03009876543").first()
            self.assertIsNotNone(order, "Order should be created in DB from speech turn")
            self.assertEqual(order.customer_name, "Ali")
            self.assertEqual(order.status, "new")
            self.assertIn("Satellite Town", order.delivery_address)
            self.assertEqual(order.items.count(), 2)
            self.assertEqual(order.total, Decimal("900.00"))

    @patch("openai.OpenAI")
    def test_transcribe_audio_uses_multilingual_conditioning_prompt(self, mock_openai_cls):
        from operations.audio_service import transcribe_audio, DEFAULT_STT_PROMPT

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.text = "menu bhej do"
        mock_client.audio.transcriptions.create.return_value = mock_resp

        with patch.object(settings, "OPENAI_API_KEY", "sk-mock-valid-key-for-test"):
            with patch.object(settings, "GROQ_API_KEY", ""):
                result = transcribe_audio(b"FAKE_AUDIO_BYTES_OVER_100" * 5)

        self.assertEqual(result, "menu bhej do")
        mock_client.audio.transcriptions.create.assert_called_once()
        _, kwargs = mock_client.audio.transcriptions.create.call_args
        self.assertIn("prompt", kwargs)
        self.assertIn("Urdu", kwargs["prompt"])

    def test_dashboard_conversations_voice_indicator(self):
        from operations.models import AgentConversation, AgentMessage
        from django.contrib.auth import get_user_model

        User = get_user_model()
        owner = User.objects.create_user(
            username="voice_owner@bk.pk",
            email="voice_owner@bk.pk",
            password="testpassword",
            company=self.company,
        )
        conv = AgentConversation.objects.create(
            company=self.company,
            customer_phone="03009998877",
            customer_name="Voice Caller",
        )
        AgentMessage.objects.create(
            conversation=conv,
            role="user",
            content="Audio message",
            metadata={"is_voice": True},
        )
        AgentMessage.objects.create(
            conversation=conv,
            role="assistant",
            content="Voice response",
            metadata={"is_voice": True},
        )

        self.client.force_authenticate(user=owner)
        res_list = self.client.get("/api/dashboard/conversations/")
        self.assertEqual(res_list.status_code, 200)
        found = next((c for c in res_list.data["results"] if c["conversation_key"] == str(conv.conversation_key)), None)
        self.assertIsNotNone(found)
        self.assertTrue(found["is_voice"])
        self.assertTrue(found["messages"][0]["is_voice"])

        res_detail = self.client.get(f"/api/dashboard/conversations/{conv.conversation_key}/")
        self.assertEqual(res_detail.status_code, 200)
        self.assertTrue(res_detail.data["is_voice"])
        self.assertTrue(res_detail.data["messages"][0]["is_voice"])

    def test_create_order_rejects_dummy_phone_and_valued_customer_and_updates_conversation(self):
        import json
        from operations.whatsapp_agent import execute_create_order, _generate_agent_reply
        from operations.models import AgentConversation

        items_payload = [{"item_name": "Zinger Burger", "quantity": 1}]

        # 1. Reject 'Valued Customer' placeholder
        res_placeholder = execute_create_order(
            company=self.company,
            customer_name="Valued Customer",
            customer_phone="03009876543",
            items=items_payload,
            delivery_address="Faisalabad Street 1",
        )
        self.assertFalse(res_placeholder["success"])
        self.assertIn("missing real customer name or phone number", res_placeholder["error"])

        # 2. Reject dummy phone number '03001234567'
        res_dummy_phone = execute_create_order(
            company=self.company,
            customer_name="Usman Tariq",
            customer_phone="03001234567",
            items=items_payload,
            delivery_address="Faisalabad Street 1",
        )
        self.assertFalse(res_dummy_phone["success"])
        self.assertIn("missing real customer name or phone number", res_dummy_phone["error"])

        # 3. Reject short phone number '< 10 digits'
        res_short_phone = execute_create_order(
            company=self.company,
            customer_name="Usman Tariq",
            customer_phone="0300123",
            items=items_payload,
            delivery_address="Faisalabad Street 1",
        )
        self.assertFalse(res_short_phone["success"])
        self.assertIn("missing real customer name or phone number", res_short_phone["error"])

        # 4. Succeeds with real details
        res_success = execute_create_order(
            company=self.company,
            customer_name="Usman Tariq",
            customer_phone="03009876543",
            items=items_payload,
            delivery_address="Faisalabad Street 1",
        )
        self.assertTrue(res_success["success"])
        self.assertEqual(res_success["customer_name"], "Usman Tariq")

        # 5. Conversation update when tool succeeds with real details
        conv = AgentConversation.objects.create(
            company=self.company,
            customer_name="Valued Customer",
            customer_phone="",
        )

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_real_contact_tool"
        mock_tool_call.function.name = "create_order"
        mock_tool_call.function.arguments = json.dumps({
            "items": [{"item_name": "Zinger Burger", "quantity": 1}],
            "customer_name": "Usman Tariq",
            "customer_phone": "03009876543",
            "delivery_address": "House 100 Faisalabad",
        })

        mock_first = MagicMock(tool_calls=[mock_tool_call], content=None)
        mock_second = MagicMock(tool_calls=None, content="Order confirmed!")

        with patch("operations.whatsapp_agent.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.chat.completions.create.side_effect = [
                MagicMock(choices=[MagicMock(message=mock_first)]),
                MagicMock(choices=[MagicMock(message=mock_second)]),
            ]

            biz_context = {"company": self.company}
            _generate_agent_reply(
                message_text="My name is Usman Tariq, phone 03009876543, confirm order",
                customer_name="Valued Customer",
                context=biz_context,
                conversation_obj=conv,
                record_turn=False,
            )

        conv.refresh_from_db()
        self.assertEqual(conv.customer_name, "Usman Tariq", "Conversation customer_name must be updated from 'Valued Customer'")
        self.assertEqual(conv.customer_phone, "03009876543", "Conversation customer_phone must be updated from empty")

    @patch("openai.OpenAI")
    def test_transliterate_devanagari_and_urdu_script_to_roman_urdu(self, mock_openai_cls):
        from operations.audio_service import transliterate_to_roman_urdu

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="Menu bhej do"))]
        mock_client.chat.completions.create.return_value = mock_resp

        # 1. Non-latin text (Devanagari) triggers transliteration
        with patch.object(settings, "OPENAI_API_KEY", "sk-mock-valid-key-for-test"):
            with patch.object(settings, "GROQ_API_KEY", ""):
                result = transliterate_to_roman_urdu("मेन्यू भेज दो")

        self.assertEqual(result, "Menu bhej do")
        mock_client.chat.completions.create.assert_called_once()

        # 2. Latin English/Roman Urdu text bypasses transliteration (0 LLM calls)
        mock_client.chat.completions.create.reset_mock()
        clean_result = transliterate_to_roman_urdu("I want 1 Zinger Burger and Fries")
        self.assertEqual(clean_result, "I want 1 Zinger Burger and Fries")
        mock_client.chat.completions.create.assert_not_called()

    @patch("operations.audio_service.transcribe_audio")
    @patch("operations.views.PublicAgentChatAPIView._public_action")
    def test_public_agent_chat_handles_audio_base64_mediarecorder_payload(self, mock_action, mock_transcribe):
        import base64
        mock_transcribe.return_value = "mera phone number 03090139836 hai"

        fake_audio_bytes = b"RIFF....WAVEfmt ....data" + b"\x00" * 100
        encoded_audio = "data:audio/webm;base64," + base64.b64encode(fake_audio_bytes).decode("ascii")

        with patch("operations.whatsapp_agent._generate_agent_reply") as mock_agent_reply:
            mock_agent_reply.return_value = "Ji maine aapka number 03090139836 note kar liya hai."

            res = self.client.post(
                f"/api/operations/public/agent/{self.company.agent_public_id}/chat/",
                {
                    "audio_base64": encoded_audio,
                    "message": "",
                },
                format="json",
            )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["transcript"], "mera phone number 03090139836 hai")
        self.assertIn("03090139836", res.data["reply_text"])
        mock_transcribe.assert_called_once()


class MonthlyVoiceLimitEnforcementTests(TestCase):
    def setUp(self):
        import uuid
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Voice Limit Test Store",
            business_type="restaurant",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            agent_public_id=uuid.uuid4(),
            message_limit=10,
            messages_used=0,
            message_period_started_at=timezone.now(),
        )

    @patch("operations.audio_service.transcribe_audio")
    @patch("operations.whatsapp_agent._generate_agent_reply")
    def test_public_voice_agent_blocks_when_monthly_limit_reached(self, mock_agent_reply, mock_transcribe):
        self.company.messages_used = 10
        self.company.save(update_fields=["messages_used"])

        import base64
        fake_audio = "data:audio/webm;base64," + base64.b64encode(b"audio_bytes").decode("ascii")

        res = self.client.post(
            f"/api/operations/public/agent/{self.company.agent_public_id}/chat/",
            {
                "audio_base64": fake_audio,
                "message": "",
            },
            format="json",
        )

        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.data["error"], "monthly_limit_reached")
        self.assertIn("monthly usage limit", res.data["message"])
        mock_transcribe.assert_not_called()
        mock_agent_reply.assert_not_called()

    def test_public_agent_catalog_reflects_monthly_limit_reached(self):
        self.company.messages_used = 10
        self.company.save(update_fields=["messages_used"])

        res = self.client.get(f"/api/operations/public/agent/{self.company.agent_public_id}/catalog/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["monthly_limit_reached"])
        self.assertEqual(res.data["messages_used"], 10)
        self.assertEqual(res.data["message_limit"], 10)

    @patch("operations.audio_service.transcribe_audio")
    @patch("operations.whatsapp_agent._generate_agent_reply")
    @patch("operations.whatsapp_agent._dispatch_whatsapp_text")
    def test_whatsapp_voice_agent_blocks_when_monthly_limit_reached(self, mock_dispatch, mock_agent_reply, mock_transcribe):
        from operations.whatsapp_agent import process_incoming_whatsapp_message
        self.company.messages_used = 10
        self.company.save(update_fields=["messages_used"])

        result = process_incoming_whatsapp_message(
            sender_phone="923001234567",
            message_text="",
            phone_number_id="test_phone_id",
            msg_type="audio",
            company=self.company,
            audio_bytes=b"dummy_bytes",
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "monthly_limit_reached")
        mock_transcribe.assert_not_called()
        mock_agent_reply.assert_not_called()
        mock_dispatch.assert_called_once()

    @patch("operations.whatsapp_agent._dispatch_whatsapp_text")
    def test_whatsapp_voice_agent_blocks_when_subscription_inactive(self, mock_dispatch):
        from operations.whatsapp_agent import process_incoming_whatsapp_message
        self.company.subscription_status = "inactive"
        self.company.is_manual_override = False
        self.company.trial_ends_at = timezone.now() - timedelta(days=10)
        self.company.grace_ends_at = timezone.now() - timedelta(days=5)
        self.company.payment_status = Company.PAYMENT_SUSPENDED
        self.company.save()

        result = process_incoming_whatsapp_message(
            sender_phone="923001234567",
            message_text="Hello",
            phone_number_id="test_phone_id",
            company=self.company,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "subscription_inactive")
        mock_dispatch.assert_called_once()


class WebsiteVoiceWidgetEmbedTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Burger Haven",
            business_type="restaurant",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            address="Faisalabad, Pakistan",
        )

    def test_widget_script_endpoint_returns_javascript(self):
        url = f"/api/operations/widget/{self.company.agent_public_id}.js"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertEqual(response.get("Access-Control-Allow-Origin"), "*")
        
        js_code = response.content.decode("utf-8")
        self.assertIn(f"/agent/{self.company.agent_public_id}?embed=1", js_code)
        self.assertIn('iframe.allow = "microphone; autoplay";', js_code)
        self.assertIn("#ff77ff", js_code)
        self.assertIn("Burger Haven", js_code)
        self.assertIn("rides-ai-widget-btn", js_code)
        self.assertIn("rides-ai-widget-popup", js_code)


class OwnerAIPauseResumeToggleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Pizza Studio",
            business_type="restaurant",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            is_ai_paused=False,
            message_limit=100,
            messages_used=5,
        )
        self.owner = User.objects.create_user(
            username="pizza_owner",
            password="Pass12345!",
            email="pizza@example.com",
            company=self.company,
            role=User.ROLE_OWNER,
        )
        self.staff = User.objects.create_user(
            username="pizza_staff",
            password="Pass12345!",
            email="staff@example.com",
            company=self.company,
            role=User.ROLE_STAFF,
        )

    def test_owner_can_toggle_ai_pause(self):
        self.client.force_authenticate(self.owner)
        
        # Pause AI
        res = self.client.post("/api/operations/agent/toggle-pause/", {"is_ai_paused": True}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_ai_paused"])
        self.company.refresh_from_db()
        self.assertTrue(self.company.is_ai_paused)

        # Resume AI
        res2 = self.client.post("/api/operations/agent/toggle-pause/", {"is_ai_paused": False}, format="json")
        self.assertEqual(res2.status_code, 200)
        self.assertFalse(res2.data["is_ai_paused"])
        self.company.refresh_from_db()
        self.assertFalse(self.company.is_ai_paused)

    def test_non_owner_cannot_toggle_ai_pause(self):
        self.client.force_authenticate(self.staff)
        res = self.client.post("/api/operations/agent/toggle-pause/", {"is_ai_paused": True}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_public_catalog_reports_ai_paused(self):
        self.company.is_ai_paused = True
        self.company.save(update_fields=["is_ai_paused"])

        url = f"/api/operations/public/agent/{self.company.agent_public_id}/catalog/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("ai_paused"))

    def test_public_chat_blocks_when_ai_paused_and_does_not_consume_quota(self):
        self.company.is_ai_paused = True
        self.company.save(update_fields=["is_ai_paused"])
        initial_used = self.company.messages_used

        url = f"/api/operations/public/agent/{self.company.agent_public_id}/chat/"
        res = self.client.post(url, {"message": "Hello I want to order pizza"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data.get("error"), "ai_paused")

        self.company.refresh_from_db()
        self.assertEqual(self.company.messages_used, initial_used)

    @patch("operations.whatsapp_agent._dispatch_whatsapp_text")
    def test_whatsapp_message_is_saved_as_human_and_not_replied_when_ai_paused(self, mock_dispatch):
        from operations.whatsapp_agent import process_incoming_whatsapp_message
        self.company.is_ai_paused = True
        self.company.save(update_fields=["is_ai_paused"])
        initial_used = self.company.messages_used

        result = process_incoming_whatsapp_message(
            sender_phone="923091112233",
            message_text="Hi is the shop open?",
            phone_number_id="test_phone_id",
            company=self.company,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result.get("ai_paused"))
        self.assertIsNone(result.get("reply_text"))
        mock_dispatch.assert_not_called()

        # Quota not consumed
        self.company.refresh_from_db()
        self.assertEqual(self.company.messages_used, initial_used)

        # Conversation status set to human for staff pickup
        conv = AgentConversation.objects.filter(company=self.company, customer_phone="923091112233").first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.status, "human")
        self.assertEqual(conv.messages.count(), 1)
        self.assertEqual(conv.messages.first().role, "user")


class AutoLocationFallbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Faisalabad Delights",
            business_type="restaurant",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            address="Faisalabad, Punjab, Pakistan",
        )

    def test_fallback_service_areas_uses_company_address_when_no_service_areas(self):
        from operations.whatsapp_agent import get_effective_service_areas
        areas = get_effective_service_areas(self.company)
        self.assertEqual(areas, ["Faisalabad"])

    def test_public_catalog_includes_fallback_location(self):
        url = f"/api/operations/public/agent/{self.company.agent_public_id}/catalog/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        service_areas = res.data.get("service_areas", [])
        self.assertTrue(len(service_areas) > 0)
        self.assertEqual(service_areas[0]["city"], "Faisalabad")


class RestaurantOperationsPolishTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Burger Hub",
            business_type="restaurant",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            address="Peoples Colony, Faisalabad",
        )
        self.company_b = Company.objects.create(
            name="Pizza Hub",
            business_type="restaurant",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            address="Gulberg, Lahore",
        )

        self.owner_a = User.objects.create_user(
            username="owner_burger",
            email="owner_burger@example.com",
            password="password123",
            role=User.ROLE_OWNER,
            company=self.company_a,
        )
        self.owner_b = User.objects.create_user(
            username="owner_pizza",
            email="owner_pizza@example.com",
            password="password123",
            role=User.ROLE_OWNER,
            company=self.company_b,
        )

        self.item_a = CatalogItem.objects.create(
            company=self.company_a,
            name="Zinger Burger",
            price=Decimal("650.00"),
            is_available=True,
        )

        self.order_a = Order.objects.create(
            company=self.company_a,
            order_number="RA-261121-0001",
            customer_name="Ali Khan",
            customer_phone="03001234567",
            delivery_address="Peoples Colony, Faisalabad",
            status=Order.STATUS_CONFIRMED,
            subtotal=Decimal("650.00"),
            total=Decimal("650.00"),
        )
        OrderItem.objects.create(
            order=self.order_a,
            item=self.item_a,
            item_name="Zinger Burger",
            quantity=Decimal("1"),
            unit_price=Decimal("650.00"),
            line_total=Decimal("650.00"),
        )

    def test_execute_create_order_persists_special_instructions_and_notes(self):
        from operations.whatsapp_agent import execute_create_order

        items = [
            {
                "item_name": "Zinger Burger",
                "quantity": 2,
                "special_instructions": "no onions, extra spicy",
            }
        ]
        res = execute_create_order(
            company=self.company_a,
            customer_name="Tariq Jamil",
            customer_phone="03219876543",
            items=items,
            delivery_address="Peoples Colony, Faisalabad",
            notes="Please call upon arrival",
        )
        self.assertTrue(res["success"])
        order = Order.objects.get(order_number=res["order_number"])
        self.assertIn("Please call upon arrival", order.notes)
        self.assertIn("Zinger Burger: no onions, extra spicy", order.notes)

    def test_auto_assign_rider_picks_least_busy_rider(self):
        rider1 = User.objects.create_user(
            username="rider1",
            password="password123",
            role=User.ROLE_RIDER,
            company=self.company_a,
        )
        rider2 = User.objects.create_user(
            username="rider2",
            password="password123",
            role=User.ROLE_RIDER,
            company=self.company_a,
        )

        # Rider 1 already has an active delivery
        Order.objects.create(
            company=self.company_a,
            order_number="RA-BUSY-1",
            customer_name="Busy Customer",
            customer_phone="03009999999",
            delivery_address="Faisalabad",
            status=Order.STATUS_OUT_FOR_DELIVERY,
            assigned_rider=rider1,
        )

        self.client.force_authenticate(user=self.owner_a)
        res = self.client.post(f"/api/operations/orders/{self.order_a.id}/auto-assign-rider/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["rider"]["id"], rider2.id)

        self.order_a.refresh_from_db()
        self.assertEqual(self.order_a.assigned_rider, rider2)
        self.assertEqual(self.order_a.status, Order.STATUS_ASSIGNED)
        self.assertTrue(DeliveryAssignment.objects.filter(order=self.order_a, rider=rider2).exists())

    def test_dashboard_auto_assign_rider_endpoint(self):
        rider = User.objects.create_user(
            username="rider_dash",
            password="password123",
            role=User.ROLE_RIDER,
            company=self.company_a,
        )

        self.client.force_authenticate(user=self.owner_a)
        res = self.client.post(f"/api/dashboard/orders/{self.order_a.id}/auto-assign-rider/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["rider"]["id"], rider.id)

    def test_auto_assign_rider_returns_400_when_no_riders(self):
        # Company A has no riders
        self.client.force_authenticate(user=self.owner_a)
        res = self.client.post(f"/api/operations/orders/{self.order_a.id}/auto-assign-rider/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("No active riders available", res.data["error"])

    def test_auto_assign_rider_enforces_multi_tenant_isolation(self):
        # Rider belongs ONLY to Company B
        User.objects.create_user(
            username="rider_pizza",
            password="password123",
            role=User.ROLE_RIDER,
            company=self.company_b,
        )

        # Company A owner cannot see Company B riders and gets 400 No active riders
        self.client.force_authenticate(user=self.owner_a)
        res_a = self.client.post(f"/api/operations/orders/{self.order_a.id}/auto-assign-rider/")
        self.assertEqual(res_a.status_code, 400)

        # Company B owner cannot auto-assign Company A's order -> 404
        self.client.force_authenticate(user=self.owner_b)
        res_b = self.client.post(f"/api/operations/orders/{self.order_a.id}/auto-assign-rider/")
        self.assertEqual(res_b.status_code, 404)

    def test_receipt_payload_includes_branding_and_assigned_rider(self):
        from operations.printing import build_receipt_payload
        rider = User.objects.create_user(
            username="rider_fast",
            password="password123",
            role=User.ROLE_RIDER,
            company=self.company_a,
        )
        self.order_a.assigned_rider = rider
        self.order_a.notes = "Allergy: nut allergy. Extra spicy."
        self.order_a.save()

        payload = build_receipt_payload(self.order_a, company=self.company_a)
        self.assertIn("Rides Technologies", payload["business"]["header"])
        self.assertIn("Rides Technologies", payload["business"]["footer"])
        self.assertEqual(payload["order"]["assigned_rider_name"], "rider_fast")
        self.assertTrue(payload["order"]["has_notes"])
        self.assertIn("nut allergy", payload["order"]["notes"])


class OwnerBusinessAssistantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Alpha Burgers",
            business_type="restaurant",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            message_limit=100,
            messages_used=25,
            is_ai_paused=False,
            address="Faisalabad, Pakistan",
        )
        self.company_b = Company.objects.create(
            name="Beta Pharmacy",
            business_type="pharmacy",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
            agent_enabled=True,
            message_limit=50,
            messages_used=5,
            is_ai_paused=True,
            address="Lahore, Pakistan",
        )

        self.owner_a = User.objects.create_user(
            username="owner_alpha",
            email="owner_alpha@example.com",
            password="password123",
            role=User.ROLE_OWNER,
            company=self.company_a,
        )
        self.owner_b = User.objects.create_user(
            username="owner_beta",
            email="owner_beta@example.com",
            password="password123",
            role=User.ROLE_OWNER,
            company=self.company_b,
        )

        # Employees for Company A
        self.staff_a1 = User.objects.create_user(
            username="staff_a1",
            first_name="Ahmed",
            password="password123",
            role=User.ROLE_STAFF,
            company=self.company_a,
            is_active=True,
        )
        self.rider_a1 = User.objects.create_user(
            username="rider_a1",
            first_name="Bilal",
            password="password123",
            role=User.ROLE_RIDER,
            company=self.company_a,
            is_active=True,
        )
        self.inactive_a = User.objects.create_user(
            username="inactive_a",
            first_name="Inactive Staff",
            password="password123",
            role=User.ROLE_STAFF,
            company=self.company_a,
            is_active=False,
        )

        # Employees for Company B
        self.staff_b1 = User.objects.create_user(
            username="staff_b1",
            first_name="Hamza",
            password="password123",
            role=User.ROLE_STAFF,
            company=self.company_b,
            is_active=True,
        )

        # Orders for Company A
        self.order_a1 = Order.objects.create(
            company=self.company_a,
            order_number="ORD-A1",
            customer_name="Customer 1",
            customer_phone="03001112233",
            delivery_address="Peoples Colony",
            status=Order.STATUS_CONFIRMED,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        self.order_a2 = Order.objects.create(
            company=self.company_a,
            order_number="ORD-A2",
            customer_name="Customer 2",
            customer_phone="03004445566",
            delivery_address="Peoples Colony",
            status=Order.STATUS_DELIVERED,
            subtotal=Decimal("1500.00"),
            total=Decimal("1500.00"),
            assigned_rider=self.rider_a1,
        )

        # Orders for Company B
        self.order_b1 = Order.objects.create(
            company=self.company_b,
            order_number="ORD-B1",
            customer_name="Customer B",
            customer_phone="03007778899",
            delivery_address="Gulberg",
            status=Order.STATUS_CONFIRMED,
            subtotal=Decimal("5000.00"),
            total=Decimal("5000.00"),
        )

    def test_unauthenticated_request_returns_401(self):
        res = self.client.post("/api/operations/owner/assistant/", {"message": "hello"})
        self.assertEqual(res.status_code, 401)

    def test_get_employees_summary_multi_tenant_isolation(self):
        from operations.owner_assistant import execute_get_employees_summary

        data_a = execute_get_employees_summary(self.company_a)
        self.assertEqual(data_a["total_employees"], 3)
        self.assertEqual(data_a["active_employees"], 2)
        self.assertEqual(data_a["inactive_employees"], 1)
        names_a = [e["name"] for e in data_a["employees"]]
        self.assertIn("Ahmed", names_a)
        self.assertIn("Bilal", names_a)
        self.assertNotIn("Hamza", names_a)  # Belongs to Company B

        data_b = execute_get_employees_summary(self.company_b)
        self.assertEqual(data_b["total_employees"], 1)
        self.assertEqual(data_b["active_employees"], 1)
        names_b = [e["name"] for e in data_b["employees"]]
        self.assertIn("Hamza", names_b)
        self.assertNotIn("Ahmed", names_b)

    def test_get_sales_and_orders_summary_multi_tenant_isolation(self):
        from operations.owner_assistant import execute_get_sales_and_orders_summary

        sales_a = execute_get_sales_and_orders_summary(self.company_a, period="all")
        self.assertEqual(sales_a["total_orders"], 2)
        self.assertEqual(sales_a["total_sales_pkr"], 2500.0)
        self.assertEqual(sales_a["delivered_orders"], 1)
        self.assertEqual(sales_a["pending_orders"], 1)

        sales_b = execute_get_sales_and_orders_summary(self.company_b, period="all")
        self.assertEqual(sales_b["total_orders"], 1)
        self.assertEqual(sales_b["total_sales_pkr"], 5000.0)

    def test_get_inventory_and_catalog_summary(self):
        from operations.owner_assistant import execute_get_inventory_and_catalog_summary

        item = CatalogItem.objects.create(
            company=self.company_a,
            name="Chicken Burger",
            price=Decimal("450.00"),
            is_available=True,
        )
        Inventory.objects.create(
            company=self.company_a,
            item=item,
            quantity=2,
            is_unlimited=False,
            low_stock_threshold=5,
        )

        data = execute_get_inventory_and_catalog_summary(self.company_a)
        self.assertEqual(data["total_catalog_items"], 1)
        self.assertEqual(data["low_stock_count"], 1)
        self.assertEqual(data["low_stock_items"][0]["item_name"], "Chicken Burger")

    def test_get_deliveries_and_riders_status(self):
        from operations.owner_assistant import execute_get_deliveries_and_riders_status

        data = execute_get_deliveries_and_riders_status(self.company_a)
        self.assertEqual(data["total_active_riders"], 1)
        self.assertEqual(data["unassigned_orders_count"], 1)
        self.assertEqual(data["riders"][0]["name"], "Bilal")
        self.assertEqual(data["riders"][0]["delivered_orders"], 1)

    def test_get_billing_and_ai_usage(self):
        from operations.owner_assistant import execute_get_billing_and_ai_usage

        billing_data = execute_get_billing_and_ai_usage(self.company_a)
        self.assertEqual(billing_data["messages_used"], 25)
        self.assertEqual(billing_data["message_limit"], 100)
        self.assertFalse(billing_data["monthly_limit_reached"])
        self.assertFalse(billing_data["is_ai_paused"])

    def test_toggle_customer_ai_agent(self):
        from operations.owner_assistant import execute_toggle_customer_ai_agent

        # Pause
        res_pause = execute_toggle_customer_ai_agent(self.company_a, pause=True)
        self.assertTrue(res_pause["success"])
        self.assertTrue(res_pause["is_ai_paused"])
        self.company_a.refresh_from_db()
        self.assertTrue(self.company_a.is_ai_paused)

        # Resume
        res_resume = execute_toggle_customer_ai_agent(self.company_a, pause=False)
        self.assertTrue(res_resume["success"])
        self.assertFalse(res_resume["is_ai_paused"])
        self.company_a.refresh_from_db()
        self.assertFalse(self.company_a.is_ai_paused)

    def test_owner_assistant_api_endpoint(self):
        self.client.force_authenticate(user=self.owner_a)
        res = self.client.post(
            "/api/operations/owner/assistant/",
            {"message": "Kitne employees hain hamare paas?"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("transcript", res.data)
        self.assertIn("reply", res.data)
        self.assertTrue("3" in res.data["reply"])
        self.assertTrue("Ahmed" in res.data["reply"] or "Bilal" in res.data["reply"] or "Total Staff" in res.data["reply"])


class P0WhatsAppDBAndSecurityTests(TestCase):
    """P0 Verification: PostgreSQL-backed Meta WhatsApp credentials & production security settings."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="P0 Tenant Alpha",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.company_b = Company.objects.create(
            name="P0 Tenant Beta",
            business_type="pharmacy",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_a = User.objects.create_user(
            username="p0_owner_a",
            email="p0_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="p0_owner_b",
            email="p0_owner_b@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_b,
            is_active=True,
        )

    def test_whatsapp_credentials_persist_in_postgres_with_tenant_isolation(self):
        from operations.whatsapp_storage import (
            get_whatsapp_config,
            get_config_by_phone_number_id,
            is_valid_verify_token,
        )

        # Save Tenant A via API
        self.client.force_authenticate(user=self.owner_a)
        res_a = self.client.post(
            "/api/operations/agent/whatsapp-settings/",
            {
                "phone_number_id": "111222333444",
                "access_token": "EAAG_TENANT_A_SECRET",
                "verify_token": "verify_alpha_999",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(res_a.status_code, 200)

        # Save Tenant B via API
        self.client.force_authenticate(user=self.owner_b)
        res_b = self.client.post(
            "/api/operations/agent/whatsapp-settings/",
            {
                "phone_number_id": "555666777888",
                "access_token": "EAAG_TENANT_B_SECRET",
                "verify_token": "verify_beta_888",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(res_b.status_code, 200)

        # Verify persisted directly on PostgreSQL Company rows
        self.company_a.refresh_from_db()
        self.company_b.refresh_from_db()
        self.assertEqual(self.company_a.whatsapp_phone_number_id, "111222333444")
        self.assertEqual(self.company_a.whatsapp_access_token, "EAAG_TENANT_A_SECRET")
        self.assertEqual(self.company_a.whatsapp_verify_token, "verify_alpha_999")
        self.assertTrue(self.company_a.whatsapp_is_active)

        self.assertEqual(self.company_b.whatsapp_phone_number_id, "555666777888")
        self.assertEqual(self.company_b.whatsapp_access_token, "EAAG_TENANT_B_SECRET")

        # Verify multi-tenant lookup and verify_token validation from DB
        cfg_a = get_config_by_phone_number_id("111222333444")
        self.assertIsNotNone(cfg_a)
        self.assertEqual(cfg_a["company_id"], str(self.company_a.id))
        self.assertEqual(cfg_a["access_token"], "EAAG_TENANT_A_SECRET")

        cfg_b = get_config_by_phone_number_id("555666777888")
        self.assertIsNotNone(cfg_b)
        self.assertEqual(cfg_b["company_id"], str(self.company_b.id))
        self.assertEqual(cfg_b["access_token"], "EAAG_TENANT_B_SECRET")

        self.assertIsNone(get_config_by_phone_number_id("nonexistent_pid_000"))
        self.assertTrue(is_valid_verify_token("verify_alpha_999"))
        self.assertTrue(is_valid_verify_token("verify_beta_888"))
        self.assertFalse(is_valid_verify_token("invalid_token_xyz"))

        # Verify GET endpoint returns only Tenant A's credentials for Owner A
        self.client.force_authenticate(user=self.owner_a)
        get_a = self.client.get("/api/operations/agent/whatsapp-settings/")
        self.assertEqual(get_a.status_code, 200)
        self.assertEqual(get_a.data["phone_number_id"], "111222333444")
        self.assertEqual(get_whatsapp_config(company_id=self.company_a.id)["verify_token"], "verify_alpha_999")

    def test_legacy_json_import_does_not_overwrite_populated_db_records(self):
        import json as _json
        import tempfile
        from pathlib import Path
        from operations.whatsapp_storage import import_legacy_whatsapp_config_json

        # Pre-populate Company A in DB; leave Company B blank
        self.company_a.whatsapp_phone_number_id = "db_existing_pid_a"
        self.company_a.whatsapp_access_token = "db_existing_token_a"
        self.company_a.whatsapp_is_active = True
        self.company_a.save()

        legacy_payload = {
            str(self.company_a.id): {
                "phone_number_id": "stale_json_pid_a",
                "access_token": "stale_json_token_a",
                "verify_token": "stale_vt_a",
                "is_active": False,
            },
            str(self.company_b.id): {
                "phone_number_id": "legacy_json_pid_b",
                "access_token": "legacy_json_token_b",
                "verify_token": "legacy_vt_b",
                "is_active": True,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / "whatsapp_config.json"
            tmp_file.write_text(_json.dumps(legacy_payload), encoding="utf-8")
            imported_count = import_legacy_whatsapp_config_json(json_path=tmp_file)

        self.assertEqual(imported_count, 1)
        self.company_a.refresh_from_db()
        self.company_b.refresh_from_db()
        # Company A preserved existing DB values
        self.assertEqual(self.company_a.whatsapp_phone_number_id, "db_existing_pid_a")
        self.assertEqual(self.company_a.whatsapp_access_token, "db_existing_token_a")
        # Company B imported cleanly from legacy JSON
        self.assertEqual(self.company_b.whatsapp_phone_number_id, "legacy_json_pid_b")
        self.assertEqual(self.company_b.whatsapp_access_token, "legacy_json_token_b")
        self.assertEqual(self.company_b.whatsapp_verify_token, "legacy_vt_b")
        self.assertTrue(self.company_b.whatsapp_is_active)

    def test_production_security_settings_when_debug_false(self):
        import importlib
        import os
        from unittest.mock import patch
        import config.settings as settings_mod

        prod_env = {
            "DJANGO_DEBUG": "False",
            "CORS_ALLOWED_ORIGINS": "https://app.ridesai.com,https://admin.ridesai.com",
        }
        try:
            with patch.dict(os.environ, prod_env, clear=False):
                os.environ.pop("CORS_ALLOW_ALL_ORIGINS", None)
                os.environ.pop("SECURE_SSL_REDIRECT", None)
                importlib.reload(settings_mod)
                self.assertFalse(settings_mod.DEBUG)
                self.assertFalse(settings_mod.CORS_ALLOW_ALL_ORIGINS)
                self.assertEqual(
                    settings_mod.CORS_ALLOWED_ORIGINS,
                    ["https://app.ridesai.com", "https://admin.ridesai.com"],
                )
                self.assertTrue(settings_mod.SECURE_SSL_REDIRECT)
                self.assertTrue(settings_mod.SESSION_COOKIE_SECURE)
                self.assertTrue(settings_mod.CSRF_COOKIE_SECURE)
                self.assertEqual(settings_mod.SECURE_HSTS_SECONDS, 31536000)
                self.assertTrue(settings_mod.SECURE_HSTS_INCLUDE_SUBDOMAINS)
                self.assertTrue(settings_mod.SECURE_HSTS_PRELOAD)
                self.assertEqual(
                    settings_mod.SECURE_PROXY_SSL_HEADER,
                    ("HTTP_X_FORWARDED_PROTO", "https"),
                )
                self.assertTrue(settings_mod.SECURE_CONTENT_TYPE_NOSNIFF)
        finally:
            # Restore original dev settings module state
            importlib.reload(settings_mod)


class AIUpsellingSuggestionsTests(TestCase):
    """Tests for Smart Catalog-Grounded AI Upselling & Cross-Selling Suggestions."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Burger House Upsell",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            enable_upselling=True,
        )
        self.company_b = Company.objects.create(
            name="Other Tenant Pizza",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            enable_upselling=True,
        )
        self.owner_a = User.objects.create_user(
            username="upsell_owner_a",
            email="upsell_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_a,
            is_active=True,
        )
        self.cat_mains = CatalogCategory.objects.create(company=self.company_a, name="Burgers")
        self.cat_sides = CatalogCategory.objects.create(company=self.company_a, name="Sides")
        self.cat_drinks = CatalogCategory.objects.create(company=self.company_a, name="Beverages")
        self.cat_desserts = CatalogCategory.objects.create(company=self.company_a, name="Desserts")

        self.burger = CatalogItem.objects.create(
            company=self.company_a, category=self.cat_mains, name="Zinger Burger", price=Decimal("650.00"), is_available=True
        )
        self.fries = CatalogItem.objects.create(
            company=self.company_a, category=self.cat_sides, name="Crispy Fries", price=Decimal("250.00"), is_available=True
        )
        self.drink = CatalogItem.objects.create(
            company=self.company_a, category=self.cat_drinks, name="Cold Drink", price=Decimal("150.00"), is_available=True
        )
        self.brownie = CatalogItem.objects.create(
            company=self.company_a, category=self.cat_desserts, name="Molten Brownie", price=Decimal("350.00"), is_available=True
        )
        # Out-of-stock item in Company A
        self.oos_wings = CatalogItem.objects.create(
            company=self.company_a, category=self.cat_sides, name="Out Of Stock Wings", price=Decimal("400.00"), is_available=True
        )
        Inventory.objects.create(company=self.company_a, item=self.oos_wings, quantity=Decimal("0"), is_unlimited=False)
        # Unavailable item in Company A
        self.unavail_dip = CatalogItem.objects.create(
            company=self.company_a, category=self.cat_sides, name="Hidden Garlic Dip", price=Decimal("90.00"), is_available=False
        )
        # Other company's item
        self.other_company_drink = CatalogItem.objects.create(
            company=self.company_b, name="Tenant B Secret Shake", price=Decimal("299.00"), is_available=True
        )

    def test_get_upsell_suggestions_strict_tenant_and_stock_isolation(self):
        from operations.whatsapp_agent import get_upsell_suggestions

        suggestions = get_upsell_suggestions(self.company_a, ordered_item_names=["Zinger Burger"])
        names = [s["name"] for s in suggestions]

        self.assertGreaterEqual(len(suggestions), 2)
        self.assertLessEqual(len(suggestions), 3)
        self.assertIn("Crispy Fries", names)
        self.assertIn("Cold Drink", names)
        # Excludes already ordered, out-of-stock, unavailable, and other tenant's items
        self.assertNotIn("Zinger Burger", names)
        self.assertNotIn("Out Of Stock Wings", names)
        self.assertNotIn("Hidden Garlic Dip", names)
        self.assertNotIn("Tenant B Secret Shake", names)
        # Exact Rs. price formatting
        fries_entry = next(s for s in suggestions if s["name"] == "Crispy Fries")
        self.assertEqual(fries_entry["price_formatted"], "Rs. 250")

    def test_system_prompt_respects_enable_upselling_toggle(self):
        from operations.whatsapp_agent import (
            _build_system_prompt,
            get_business_context_for_company,
            get_upsell_suggestions,
        )

        # Enabled (default True)
        ctx_on = get_business_context_for_company(self.company_a)
        self.assertTrue(ctx_on["enable_upselling"])
        prompt_on = _build_system_prompt("Ali", ctx_on)
        self.assertIn("SMART UPSELLING & CROSS-SELLING RULES", prompt_on)
        self.assertIn("Crispy Fries", prompt_on)

        # Disabled (False)
        self.company_a.enable_upselling = False
        self.company_a.save(update_fields=["enable_upselling"])
        self.assertEqual(get_upsell_suggestions(self.company_a, ["Zinger Burger"]), [])

        ctx_off = get_business_context_for_company(self.company_a)
        self.assertFalse(ctx_off["enable_upselling"])
        prompt_off = _build_system_prompt("Ali", ctx_off)
        self.assertNotIn("SMART UPSELLING & CROSS-SELLING RULES", prompt_off)

    def test_agent_settings_patch_persists_enable_upselling(self):
        self.client.force_authenticate(user=self.owner_a)

        # GET defaults to True
        res_get = self.client.get("/api/operations/agent/settings/")
        self.assertEqual(res_get.status_code, 200)
        self.assertTrue(res_get.data["enable_upselling"])

        # PATCH to False
        res_patch = self.client.patch(
            "/api/operations/agent/settings/",
            {"enable_upselling": False},
            format="json",
        )
        self.assertEqual(res_patch.status_code, 200)
        self.assertFalse(res_patch.data["enable_upselling"])
        self.company_a.refresh_from_db()
        self.assertFalse(self.company_a.enable_upselling)

        # PATCH back to True
        res_patch2 = self.client.patch(
            "/api/operations/agent/settings/",
            {"enable_upselling": True},
            format="json",
        )
        self.assertEqual(res_patch2.status_code, 200)
        self.assertTrue(res_patch2.data["enable_upselling"])
        self.company_a.refresh_from_db()
        self.assertTrue(self.company_a.enable_upselling)


class HospitalVerticalTests(TestCase):
    """End-to-end tests for the Hospital multi-tenant vertical."""

    def setUp(self):
        self.client = APIClient()
        self.hospital_a = Company.objects.create(
            name="Shifa International Test Hospital",
            business_type="hospital",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            enable_upselling=True,
        )
        self.hospital_b = Company.objects.create(
            name="Other City Memorial Hospital",
            business_type="hospital",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            enable_upselling=True,
        )
        self.owner_a = User.objects.create_user(
            username="hosp_owner_a",
            email="hosp_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.hospital_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="hosp_owner_b",
            email="hosp_owner_b@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.hospital_b,
            is_active=True,
        )

    def test_hospital_module_registration_and_multi_tenant_isolation(self):
        from accounts.modules import business_key, owner_nav_for
        from operations.models import HospitalDepartment

        self.assertEqual(business_key("hospital"), "hospital")
        self.assertEqual(business_key("Hospital"), "hospital")
        nav_keys = [item["key"] for item in owner_nav_for("hospital")]
        self.assertIn("departments", nav_keys)
        self.assertIn("appointments", nav_keys)
        self.assertIn("doctors", nav_keys)
        self.assertIn("lab_tests", nav_keys)

        # Create department in Hospital A
        self.client.force_authenticate(user=self.owner_a)
        res_a = self.client.post(
            "/api/operations/hospital/departments/",
            {
                "name": "Emergency & Trauma",
                "ward_type": "emergency",
                "floor_or_location": "Ground Floor",
                "total_beds": 20,
                "available_beds": 7,
                "is_24_7": True,
            },
            format="json",
        )
        self.assertEqual(res_a.status_code, 201)
        dept_a_id = res_a.data["id"]

        # Create department in Hospital B
        self.client.force_authenticate(user=self.owner_b)
        res_b = self.client.post(
            "/api/operations/hospital/departments/",
            {
                "name": "Hospital B ICU",
                "ward_type": "icu",
                "total_beds": 10,
                "available_beds": 2,
                "is_24_7": True,
            },
            format="json",
        )
        self.assertEqual(res_b.status_code, 201)

        # Tenant B cannot see or patch Tenant A's department
        list_b = self.client.get("/api/operations/hospital/departments/")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual([d["name"] for d in list_b.data], ["Hospital B ICU"])

        patch_cross = self.client.patch(
            f"/api/operations/hospital/departments/{dept_a_id}/",
            {"available_beds": 0},
            format="json",
        )
        self.assertEqual(patch_cross.status_code, 404)
        self.assertEqual(HospitalDepartment.objects.get(pk=dept_a_id).available_beds, 7)

    def test_department_beds_and_lab_booking_workflow(self):
        self.client.force_authenticate(user=self.owner_a)

        # Create ICU ward and update bed count
        dept_res = self.client.post(
            "/api/operations/hospital/departments/",
            {"name": "Cardiac ICU", "ward_type": "icu", "total_beds": 12, "available_beds": 5, "is_24_7": True},
            format="json",
        )
        self.assertEqual(dept_res.status_code, 201)
        dept_id = dept_res.data["id"]

        bed_patch = self.client.patch(
            f"/api/operations/hospital/departments/{dept_id}/",
            {"available_beds": 4},
            format="json",
        )
        self.assertEqual(bed_patch.status_code, 200)
        self.assertEqual(bed_patch.data["available_beds"], 4)
        self.assertEqual(bed_patch.data["occupied_beds"], 8)

        # Create Lab Test Booking & advance statuses
        lab_res = self.client.post(
            "/api/operations/hospital/lab-bookings/",
            {
                "patient_name": "Bilal Tariq",
                "patient_phone": "03001112233",
                "test_name": "Complete Blood Count (CBC)",
                "price": "1200.00",
                "scheduled_time": "09:30 AM",
            },
            format="json",
        )
        self.assertEqual(lab_res.status_code, 201)
        self.assertEqual(lab_res.data["status"], "scheduled")
        booking_id = lab_res.data["id"]

        st1 = self.client.patch(
            f"/api/operations/hospital/lab-bookings/{booking_id}/status/",
            {"status": "checked_in"},
            format="json",
        )
        self.assertEqual(st1.status_code, 200)
        self.assertEqual(st1.data["status"], "checked_in")

        st2 = self.client.patch(
            f"/api/operations/hospital/lab-bookings/{booking_id}/status/",
            {"status": "completed"},
            format="json",
        )
        self.assertEqual(st2.status_code, 200)
        self.assertEqual(st2.data["status"], "completed")

        # Verify summary endpoint
        sum_res = self.client.get("/api/operations/hospital/summary/")
        self.assertEqual(sum_res.status_code, 200)
        self.assertEqual(sum_res.data["total_beds"], 12)
        self.assertEqual(sum_res.data["available_beds"], 4)
        self.assertEqual(sum_res.data["lab_revenue_today"], 1200.0)

    def test_hospital_ai_voice_agent_prompt_tools_upselling_and_owner_assistant(self):
        from operations.models import Doctor, HospitalDepartment
        from operations.owner_assistant import execute_get_hospital_operations_summary
        from operations.whatsapp_agent import (
            _build_system_prompt,
            execute_book_lab_test,
            execute_get_hospital_departments,
            get_business_context_for_company,
            get_category_agent_config,
            get_upsell_suggestions,
        )

        HospitalDepartment.objects.create(
            company=self.hospital_a, name="Cardiology OPD", ward_type="opd", total_beds=0, available_beds=0
        )
        HospitalDepartment.objects.create(
            company=self.hospital_a, name="Emergency Ward", ward_type="emergency", total_beds=15, available_beds=6, is_24_7=True
        )
        Doctor.objects.create(
            company=self.hospital_a, name="Dr. Ayesha Malik", specialty="Cardiology", consultation_fee=Decimal("2500.00")
        )
        cat_opd = CatalogCategory.objects.create(company=self.hospital_a, name="OPD Consultations")
        cat_lab = CatalogCategory.objects.create(company=self.hospital_a, name="Diagnostic Packages")
        CatalogItem.objects.create(
            company=self.hospital_a, category=cat_opd, name="Cardiology Consultation", price=Decimal("2500.00"), is_available=True
        )
        CatalogItem.objects.create(
            company=self.hospital_a, category=cat_lab, name="Executive Full Body Checkup", price=Decimal("5500.00"), is_available=True
        )
        CatalogItem.objects.create(
            company=self.hospital_a, category=cat_lab, name="Lipid Profile Test", price=Decimal("1800.00"), is_available=True
        )

        # Profile resolution
        cfg = get_category_agent_config("hospital")
        self.assertEqual(cfg["key"], "hospital")
        tool_names = [t["function"]["name"] for t in cfg["tools"]]
        self.assertIn("get_hospital_departments", tool_names)
        self.assertIn("book_lab_test", tool_names)
        self.assertIn("get_upsell_suggestions", tool_names)

        # Prompt includes hospital departments, beds, and upselling when enabled
        ctx = get_business_context_for_company(self.hospital_a)
        prompt = _build_system_prompt("Zainab", ctx)
        self.assertIn("HOSPITAL DEPARTMENTS, WARDS & BED AVAILABILITY", prompt)
        self.assertIn("Emergency Ward", prompt)
        self.assertIn("6/15 beds available", prompt)
        self.assertIn("SMART UPSELLING & CROSS-SELLING RULES", prompt)

        # Upsell suggests diagnostic packages when patient books OPD consultation
        upsells = get_upsell_suggestions(self.hospital_a, ["Cardiology Consultation"])
        upsell_names = [u["name"] for u in upsells]
        self.assertIn("Executive Full Body Checkup", upsell_names)
        self.assertNotIn("Cardiology Consultation", upsell_names)

        # Tool executions strictly scoped to hospital_a
        dept_out = execute_get_hospital_departments(self.hospital_a)
        self.assertTrue(dept_out["success"])
        self.assertEqual(dept_out["count"], 2)

        lab_out = execute_book_lab_test(
            company=self.hospital_a,
            sender_phone="03019998877",
            patient_name="Zainab Ali",
            test_name="Lipid Profile Test",
            scheduled_time="11:00 AM",
        )
        self.assertTrue(lab_out["success"])
        self.assertEqual(lab_out["price"], 1800.0)
        self.assertTrue(lab_out["booking_number"].startswith("LAB-"))

        # Owner AI Business Manager live hospital metrics
        owner_summary = execute_get_hospital_operations_summary(self.hospital_a)
        self.assertEqual(owner_summary["departments_count"], 2)
        self.assertEqual(owner_summary["available_beds"], 6)
        self.assertEqual(owner_summary["total_beds"], 15)
        self.assertEqual(owner_summary["doctors_on_duty_count"], 1)
        self.assertEqual(owner_summary["scheduled_lab_bookings"], 1)
        self.assertEqual(owner_summary["daily_hospital_revenue_rs"], 1800.0)


class AdvancedAnalyticsAndReportsTests(TestCase):
    """Tests for P1 Advanced Time-Series Analytics & Exportable CSV Reports (Multi-Tenant Isolated)."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Analytics Burger Hub",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            messages_used=42,
            message_limit=1000,
        )
        self.company_b = Company.objects.create(
            name="Competitor Pizza Palace",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_a = User.objects.create_user(
            username="analytics_owner_a",
            email="analytics_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="analytics_owner_b",
            email="analytics_owner_b@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_b,
            is_active=True,
        )

        # Company A orders (2 active + 1 cancelled)
        o1 = Order.objects.create(
            company=self.company_a,
            customer_name="Ali Raza",
            customer_phone="03001234567",
            status="delivered",
            source="whatsapp",
            total=Decimal("1500.00"),
        )
        OrderItem.objects.create(order=o1, item_name="Zinger Burger", quantity=2, unit_price=Decimal("750.00"), line_total=Decimal("1500.00"))

        o2 = Order.objects.create(
            company=self.company_a,
            customer_name="Sara Khan",
            customer_phone="03009876543",
            status="confirmed",
            source="agent",
            total=Decimal("900.00"),
        )
        OrderItem.objects.create(order=o2, item_name="Crispy Fries", quantity=3, unit_price=Decimal("300.00"), line_total=Decimal("900.00"))

        Order.objects.create(
            company=self.company_a,
            customer_name="Cancelled Order",
            customer_phone="03005555555",
            status="cancelled",
            source="manual",
            total=Decimal("5000.00"),
        )

        conv_a = AgentConversation.objects.create(company=self.company_a, customer_name="Ali Raza", customer_phone="03001234567")
        AgentMessage.objects.create(conversation=conv_a, role="user", content="2 Zinger Burger")
        AgentMessage.objects.create(conversation=conv_a, role="assistant", content="Order confirmed!")

        # Company B order (MUST NEVER LEAK into Company A analytics or CSV)
        o_b = Order.objects.create(
            company=self.company_b,
            customer_name="Secret Tenant B Customer",
            customer_phone="03119999999",
            status="delivered",
            source="whatsapp",
            total=Decimal("99999.00"),
        )
        OrderItem.objects.create(order=o_b, item_name="Secret Tenant B Pizza", quantity=10, unit_price=Decimal("9999.90"), line_total=Decimal("99999.00"))

    def test_analytics_overview_accuracy_and_tenant_isolation(self):
        self.client.force_authenticate(user=self.owner_a)
        res = self.client.get("/api/operations/analytics/overview/?range=7d")
        self.assertEqual(res.status_code, 200)

        kpis = res.data["kpis"]
        # Revenue excludes cancelled 5000 and excludes Tenant B's 99999 -> 1500 + 900 = 2400
        self.assertEqual(kpis["total_revenue"], 2400.0)
        self.assertEqual(kpis["total_orders"], 3)
        self.assertEqual(kpis["completed_count"], 1)
        self.assertEqual(kpis["cancelled_count"], 1)
        self.assertEqual(kpis["average_order_value"], 1200.0)
        self.assertEqual(kpis["active_ai_conversations"], 1)
        self.assertEqual(kpis["ai_voice_turns"], 2)
        self.assertEqual(kpis["messages_used"], 42)
        self.assertEqual(kpis["message_limit"], 1000)

        # Time-series has 7 daily buckets
        self.assertEqual(len(res.data["time_series"]), 7)
        self.assertEqual(res.data["granularity"], "daily")

        # Top items strictly from Company A
        top_names = [it["name"] for it in res.data["top_items"]]
        self.assertIn("Zinger Burger", top_names)
        self.assertIn("Crispy Fries", top_names)
        self.assertNotIn("Secret Tenant B Pizza", top_names)

        # 90d range uses weekly granularity
        res_90 = self.client.get("/api/operations/analytics/overview/?range=90d")
        self.assertEqual(res_90.status_code, 200)
        self.assertEqual(res_90.data["granularity"], "weekly")

    def test_analytics_export_csv_returns_valid_isolated_csv(self):
        self.client.force_authenticate(user=self.owner_a)
        res = self.client.get("/api/operations/analytics/export/csv/?range=30d")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res["Content-Type"])
        self.assertIn("attachment; filename=", res["Content-Disposition"])

        body = res.content.decode("utf-8-sig")
        self.assertIn("Analytics Burger Hub", body)
        self.assertIn("Ali Raza", body)
        self.assertIn("Zinger Burger", body)
        self.assertIn("2400.00", body)
        # Strict multi-tenant isolation: Tenant B data MUST NOT appear
        self.assertNotIn("Secret Tenant B Customer", body)
        self.assertNotIn("Secret Tenant B Pizza", body)
        self.assertNotIn("99999.00", body)


class NotificationTemplatesTests(TestCase):
    """Tests for P1 Owner-Editable Notification Templates & Per-Event Toggles (Multi-Tenant)."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Notify Cafe Alpha",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            whatsapp_instance_name="notify_alpha_evo",
        )
        self.company_b = Company.objects.create(
            name="Notify Store Beta",
            business_type="retail",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            whatsapp_instance_name="notify_beta_evo",
        )
        self.owner_a = User.objects.create_user(
            username="notify_owner_a",
            email="notify_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="notify_owner_b",
            email="notify_owner_b@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_b,
            is_active=True,
        )

    def test_get_patch_reset_templates_and_tenant_isolation(self):
        from operations.models import NotificationTemplate

        # GET returns all 8 default events for Company A
        self.client.force_authenticate(user=self.owner_a)
        res_list = self.client.get("/api/operations/notifications/templates/")
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.data["templates"]), 8)
        self.assertTrue(len(res_list.data["placeholders"]) >= 5)

        # PATCH customizes order_confirmed for Company A only
        res_patch = self.client.patch(
            "/api/operations/notifications/templates/order_confirmed/",
            {
                "is_enabled": True,
                "whatsapp_enabled": True,
                "email_enabled": False,
                "subject_template": "Shukriya {{customer_name}} — {{company_name}}",
                "body_template": "Salam {{customer_name}}! Order {{order_id}} total {{total_amount}} confirmed.",
            },
            format="json",
        )
        self.assertEqual(res_patch.status_code, 200)
        self.assertTrue(res_patch.data["is_customized"])
        self.assertFalse(res_patch.data["email_enabled"])
        self.assertIn("Salam {{customer_name}}", res_patch.data["body_template"])

        # Company B still sees uncustomized defaults (strict multi-tenant isolation)
        self.client.force_authenticate(user=self.owner_b)
        res_b = self.client.get("/api/operations/notifications/templates/")
        self.assertEqual(res_b.status_code, 200)
        b_conf = next(t for t in res_b.data["templates"] if t["event_type"] == "order_confirmed")
        self.assertFalse(b_conf["is_customized"])
        self.assertTrue(b_conf["email_enabled"])
        self.assertNotIn("Salam", b_conf["body_template"])

        # POST reset restores default for Company A
        self.client.force_authenticate(user=self.owner_a)
        res_reset = self.client.post("/api/operations/notifications/templates/order_confirmed/reset/")
        self.assertEqual(res_reset.status_code, 200)
        self.assertFalse(res_reset.data["is_customized"])
        self.assertFalse(NotificationTemplate.objects.filter(company=self.company_a, event_type="order_confirmed").exists())

    @patch("operations.notifications.evolution_client.send_text_message")
    def test_render_notification_template_and_toggle_skip_behavior(self, mock_evo_send):
        from operations.models import NotificationTemplate
        from operations.notifications import render_notification_template, send_status_notification

        # Safe substitution even with missing placeholders (no KeyError)
        NotificationTemplate.objects.create(
            company=self.company_a,
            event_type="order_confirmed",
            is_enabled=True,
            whatsapp_enabled=True,
            email_enabled=False,
            subject_template="Hi {{customer_name}} ({{missing_var}})",
            body_template="Hello {{customer_name}}, order {{order_id}} at {{company_name}} is {{total_amount}}.",
        )
        rendered = render_notification_template(
            self.company_a,
            "order_confirmed",
            {"customer_name": "Usman", "order_id": "RA-1001", "total_amount": "Rs. 950.00"},
        )
        self.assertEqual(rendered["subject"], "Hi Usman ()")
        self.assertEqual(rendered["body"], "Hello Usman, order RA-1001 at Notify Cafe Alpha is Rs. 950.00.")

        # Dispatches custom body via WhatsApp when enabled
        mock_evo_send.return_value = {"status": "SUCCESS"}
        sent = send_status_notification(
            company=self.company_a,
            customer_phone="03001234567",
            entity_type="order",
            reference_id="RA-1001",
            new_status="confirmed",
            customer_name="Usman",
            total_amount="Rs. 950.00",
        )
        self.assertTrue(sent)
        mock_evo_send.assert_called_once()
        self.assertIn("Hello Usman, order RA-1001 at Notify Cafe Alpha", mock_evo_send.call_args.kwargs["text"])

        # Disable WhatsApp toggle -> must skip WhatsApp dispatch cleanly
        mock_evo_send.reset_mock()
        NotificationTemplate.objects.filter(company=self.company_a, event_type="order_confirmed").update(whatsapp_enabled=False)
        skipped_wa = send_status_notification(
            company=self.company_a,
            customer_phone="03001234567",
            entity_type="order",
            reference_id="RA-1002",
            new_status="confirmed",
        )
        self.assertFalse(skipped_wa)
        mock_evo_send.assert_not_called()

        # Disable entire event -> must skip dispatch cleanly
        NotificationTemplate.objects.filter(company=self.company_a, event_type="order_confirmed").update(
            whatsapp_enabled=True, is_enabled=False
        )
        skipped_all = send_status_notification(
            company=self.company_a,
            customer_phone="03001234567",
            entity_type="order",
            reference_id="RA-1003",
            new_status="confirmed",
        )
        self.assertFalse(skipped_all)
        mock_evo_send.assert_not_called()


class AIFAQLearningLoopTests(TestCase):
    """Tests for P1 Automated AI FAQ Suggestions & Continuous Learning Loop (Multi-Tenant)."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Learning Cafe Alpha",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.company_b = Company.objects.create(
            name="Learning Clinic Beta",
            business_type="clinic",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_a = User.objects.create_user(
            username="faq_owner_a",
            email="faq_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="faq_owner_b",
            email="faq_owner_b@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_b,
            is_active=True,
        )

    def test_log_unanswered_question_deduplicates_and_increments_occurrence_count(self):
        from operations.models import SuggestedFAQ
        from operations.whatsapp_agent import log_unanswered_question

        res1 = log_unanswered_question(
            company=self.company_a,
            question="Do you have free customer parking?",
            source_channel="public_web",
        )
        self.assertTrue(res1["success"])
        self.assertFalse(res1["deduplicated"])
        self.assertEqual(res1["occurrence_count"], 1)

        # Asking again with different casing/whitespace increments existing row instead of duplicating
        res2 = log_unanswered_question(
            company=self.company_a,
            question="  do you have   free customer parking? ",
            draft_answer="Yes, valet parking is available outside.",
            source_channel="whatsapp",
        )
        self.assertTrue(res2["success"])
        self.assertTrue(res2["deduplicated"])
        self.assertEqual(res2["occurrence_count"], 2)
        self.assertEqual(res2["suggestion_id"], res1["suggestion_id"])
        self.assertEqual(SuggestedFAQ.objects.filter(company=self.company_a).count(), 1)

    def test_approve_suggestion_teaches_ai_immediately_with_strict_tenant_isolation(self):
        from companies.models import BusinessKnowledge
        from operations.models import SuggestedFAQ
        from operations.whatsapp_agent import (
            _build_system_prompt,
            get_business_context_for_company,
            log_unanswered_question,
        )

        logged = log_unanswered_question(
            company=self.company_a,
            question="Is your chicken 100% Zabiha Halal?",
            source_channel="whatsapp",
        )
        sug_id = logged["suggestion_id"]

        # Company B MUST NOT see, approve, or dismiss Company A's suggestion
        self.client.force_authenticate(user=self.owner_b)
        list_b = self.client.get("/api/operations/faqs/suggestions/?status=pending")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(list_b.data["pending_count"], 0)
        self.assertEqual(list_b.data["suggestions"], [])

        cross_approve = self.client.post(
            f"/api/operations/faqs/suggestions/{sug_id}/approve/",
            {"question": "Hack", "answer": "Hacked"},
            format="json",
        )
        self.assertEqual(cross_approve.status_code, 404)

        cross_dismiss = self.client.post(f"/api/operations/faqs/suggestions/{sug_id}/dismiss/")
        self.assertEqual(cross_dismiss.status_code, 404)

        # Company A approves the suggestion
        self.client.force_authenticate(user=self.owner_a)
        approve_res = self.client.post(
            f"/api/operations/faqs/suggestions/{sug_id}/approve/",
            {
                "question": "Is your chicken 100% Zabiha Halal?",
                "answer": "Yes, all our meat is 100% certified Zabiha Halal.",
            },
            format="json",
        )
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.data["suggestion"]["status"], "approved")
        self.assertTrue(
            BusinessKnowledge.objects.filter(
                company=self.company_a,
                title="Is your chicken 100% Zabiha Halal?",
                is_approved=True,
                is_active=True,
            ).exists()
        )

        # Immediately grounded in Customer AI Voice Agent system prompt for Company A (and NOT Company B)
        ctx_a = get_business_context_for_company(self.company_a)
        prompt_a = _build_system_prompt("Ayesha", ctx_a)
        self.assertIn("Is your chicken 100% Zabiha Halal?", prompt_a)
        self.assertIn("100% certified Zabiha Halal", prompt_a)

        ctx_b = get_business_context_for_company(self.company_b)
        prompt_b = _build_system_prompt("Ayesha", ctx_b)
        self.assertNotIn("100% certified Zabiha Halal", prompt_b)

        # Dismiss workflow verified for Company A
        logged2 = log_unanswered_question(company=self.company_a, question="Random off-topic question?")
        dismiss_res = self.client.post(f"/api/operations/faqs/suggestions/{logged2['suggestion_id']}/dismiss/")
        self.assertEqual(dismiss_res.status_code, 200)
        self.assertEqual(SuggestedFAQ.objects.get(pk=logged2["suggestion_id"]).status, "dismissed")


class MapPinAndFloorPlanTests(TestCase):
    """Tests for Delivery Map-Pin Coordinates & Restaurant Visual Floor-Plan Tables (Multi-Tenant)."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Bistro Map Alpha",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.company_b = Company.objects.create(
            name="Bistro Map Beta",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_a = User.objects.create_user(
            username="map_owner_a",
            email="map_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="map_owner_b",
            email="map_owner_b@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_b,
            is_active=True,
        )
        self.burger_a = CatalogItem.objects.create(
            company=self.company_a,
            name="Classic Smash Burger",
            price=Decimal("700.00"),
            is_available=True,
        )
        from companies.models import ServiceArea
        ServiceArea.objects.create(
            company=self.company_a,
            name="Faisalabad City",
            area_type="city",
            city="Faisalabad",
            delivery_fee=Decimal("100.00"),
            is_active=True,
        )

    def test_order_delivery_lat_lng_persists_with_tenant_isolation(self):
        self.client.force_authenticate(user=self.owner_a)
        res = self.client.post(
            "/api/operations/orders/",
            {
                "customer_name": "Hamza Tariq",
                "customer_phone": "03001234567",
                "fulfillment_type": "delivery",
                "delivery_address": "Peoples Colony, Faisalabad",
                "city": "Faisalabad",
                "delivery_lat": "31.418715",
                "delivery_lng": "73.079109",
                "items": [{"item_id": self.burger_a.id, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertAlmostEqual(res.data["delivery_lat"], 31.418715, places=5)
        self.assertAlmostEqual(res.data["delivery_lng"], 73.079109, places=5)

        # Verify persisted in PostgreSQL and isolated from Company B
        order_obj = Order.objects.get(pk=res.data["id"])
        self.assertEqual(order_obj.company_id, self.company_a.id)
        self.assertAlmostEqual(float(order_obj.delivery_lat), 31.418715, places=5)
        self.assertAlmostEqual(float(order_obj.delivery_lng), 73.079109, places=5)

        self.client.force_authenticate(user=self.owner_b)
        list_b = self.client.get("/api/operations/orders/")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(list_b.data, [])


    def test_restaurant_table_floor_plan_coordinates_and_isolation(self):
        from operations.models import RestaurantTable

        self.client.force_authenticate(user=self.owner_a)
        create_res = self.client.post(
            "/api/operations/tables/",
            {
                "table_number": "VIP-1",
                "capacity": 6,
                "zone": "VIP / Family",
                "shape": "rect",
                "pos_x": 120,
                "pos_y": 80,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        table_id = create_res.data["id"]
        self.assertEqual(create_res.data["zone"], "VIP / Family")
        self.assertEqual(create_res.data["shape"], "rect")
        self.assertEqual(create_res.data["pos_x"], 120)
        self.assertEqual(create_res.data["pos_y"], 80)

        # Reposition via drag/edit & reserve table
        patch_res = self.client.patch(
            f"/api/operations/tables/{table_id}/",
            {
                "pos_x": 280,
                "pos_y": 195,
                "zone": "Outdoor",
                "shape": "round",
                "status": "reserved",
                "guest_name": "Bilal Family",
                "reservation_time": "8:30 PM",
            },
            format="json",
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["pos_x"], 280)
        self.assertEqual(patch_res.data["pos_y"], 195)
        self.assertEqual(patch_res.data["zone"], "Outdoor")
        self.assertEqual(patch_res.data["shape"], "round")
        self.assertEqual(patch_res.data["status"], "reserved")

        # Tenant B cannot list, patch, or delete Tenant A's table
        self.client.force_authenticate(user=self.owner_b)
        list_b = self.client.get("/api/operations/tables/")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(list_b.data, [])


        cross_patch = self.client.patch(f"/api/operations/tables/{table_id}/", {"pos_x": 0}, format="json")
        self.assertEqual(cross_patch.status_code, 404)
        self.assertEqual(RestaurantTable.objects.get(pk=table_id).pos_x, 280)


class DataRetentionAndConsentTests(TestCase):
    """Tests for PRD §12 Data Retention Policy, Consent Ledger, Purge Command & Customer Erasure."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Privacy Cafe Alpha",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.company_b = Company.objects.create(
            name="Privacy Store Beta",
            business_type="retail",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_a = User.objects.create_user(
            username="priv_owner_a",
            email="priv_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="priv_owner_b",
            email="priv_owner_b@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_b,
            is_active=True,
        )

    def test_retention_policy_crud_and_purge_command_preserves_financial_totals(self):
        from django.core.management import call_command

        self.client.force_authenticate(user=self.owner_a)
        res_get = self.client.get("/api/operations/privacy/retention/")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.data["chat_retention_days"], 90)

        res_patch = self.client.patch(
            "/api/operations/privacy/retention/",
            {"chat_retention_days": 30, "order_pii_retention_days": 60, "auto_purge_enabled": True},
            format="json",
        )
        self.assertEqual(res_patch.status_code, 200)
        self.assertTrue(res_patch.data["auto_purge_enabled"])

        # Seed expired vs fresh data in Company A, plus expired data in Company B (auto_purge disabled)
        old_dt = timezone.now() - timedelta(days=120)
        conv_a = AgentConversation.objects.create(company=self.company_a, customer_name="Old User", customer_phone="03001111111")
        old_msg = AgentMessage.objects.create(conversation=conv_a, role="user", content="Expired chat")
        AgentMessage.objects.filter(pk=old_msg.pk).update(created_at=old_dt)
        fresh_msg = AgentMessage.objects.create(conversation=conv_a, role="user", content="Fresh chat")

        old_order_a = Order.objects.create(
            company=self.company_a,
            customer_name="Old Customer",
            customer_phone="03001111111",
            delivery_address="House 12, Old Street",
            status=Order.STATUS_DELIVERED,
            total=Decimal("2450.00"),
        )
        Order.objects.filter(pk=old_order_a.pk).update(created_at=old_dt)

        old_order_b = Order.objects.create(
            company=self.company_b,
            customer_name="Tenant B Customer",
            customer_phone="03002222222",
            delivery_address="Tenant B Street",
            status=Order.STATUS_DELIVERED,
            total=Decimal("3100.00"),
        )
        Order.objects.filter(pk=old_order_b.pk).update(created_at=old_dt)

        # Dry-run leaves data untouched
        call_command("purge_expired_data", "--dry-run")
        self.assertTrue(AgentMessage.objects.filter(pk=old_msg.pk).exists())

        # Real run purges Company A expired data ONLY, keeping financial total intact
        call_command("purge_expired_data")
        self.assertFalse(AgentMessage.objects.filter(pk=old_msg.pk).exists())
        self.assertTrue(AgentMessage.objects.filter(pk=fresh_msg.pk).exists())

        old_order_a.refresh_from_db()
        self.assertEqual(old_order_a.customer_name, "Anonymized")
        self.assertEqual(old_order_a.customer_phone, "")
        self.assertEqual(old_order_a.delivery_address, "")
        self.assertEqual(old_order_a.total, Decimal("2450.00"))  # Financial total preserved!

        # Company B untouched (strict multi-tenant isolation)
        old_order_b.refresh_from_db()
        self.assertEqual(old_order_b.customer_name, "Tenant B Customer")

    def test_consent_ledger_and_right_to_erasure_tenant_isolation(self):
        self.client.force_authenticate(user=self.owner_a)

        # Record consent for Company A
        c_res = self.client.post(
            "/api/operations/privacy/consents/",
            {
                "customer_identifier": "03009998877",
                "consent_type": "voice_ai_recording",
                "channel": "public_web",
                "granted": True,
            },
            format="json",
        )
        self.assertEqual(c_res.status_code, 201)

        # Same customer phone exists in both Company A and Company B
        order_a = Order.objects.create(
            company=self.company_a,
            customer_name="Sana Tariq",
            customer_phone="03009998877",
            delivery_address="Street A",
            total=Decimal("1200.00"),
        )
        order_b = Order.objects.create(
            company=self.company_b,
            customer_name="Sana Tariq",
            customer_phone="03009998877",
            delivery_address="Street B",
            total=Decimal("1500.00"),
        )

        # Erase customer in Company A
        erase_res = self.client.post(
            "/api/operations/privacy/erase-customer/",
            {"customer_phone_or_email": "03009998877"},
            format="json",
        )
        self.assertEqual(erase_res.status_code, 200)
        self.assertEqual(erase_res.data["anonymized_orders"], 1)
        self.assertEqual(erase_res.data["anonymized_consents"], 1)

        order_a.refresh_from_db()
        self.assertEqual(order_a.customer_name, "Anonymized")
        self.assertEqual(order_a.customer_phone, "")
        self.assertEqual(order_a.total, Decimal("1200.00"))

        # Company B's order & consents remain completely untouched
        order_b.refresh_from_db()
        self.assertEqual(order_b.customer_name, "Sana Tariq")
        self.assertEqual(order_b.customer_phone, "03009998877")

        self.client.force_authenticate(user=self.owner_b)
        list_b = self.client.get("/api/operations/privacy/consents/")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(list_b.data, [])


class SuperAdminDashboardTests(TestCase):
    """Tests for PRD §2.1 & §10 Platform Owner / Super Admin Dashboard (is_superuser protected)."""

    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(
            username="platform_superadmin",
            email="superadmin@ridesai.com",
            password="SuperPassword123!",
        )
        self.company_rest = Company.objects.create(
            name="SuperAdmin Grill House",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            is_approved=True,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            messages_used=120,
            message_limit=1000,
        )
        self.company_hosp = Company.objects.create(
            name="SuperAdmin Care Hospital",
            business_type="hospital",
            status=Company.STATUS_ACTIVE,
            is_approved=True,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
            messages_used=45,
            message_limit=1000,
        )
        self.owner_user = User.objects.create_user(
            username="regular_owner_sa",
            email="regular_owner@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_rest,
            is_active=True,
        )
        self.staff_user = User.objects.create_user(
            username="regular_staff_sa",
            email="regular_staff@example.com",
            password="Password123!",
            role=User.ROLE_STAFF,
            company=self.company_rest,
            is_active=True,
        )
        Order.objects.create(
            company=self.company_rest,
            customer_name="Ali",
            customer_phone="03001234567",
            status="delivered",
            total=Decimal("1800.00"),
        )

    def test_non_superusers_receive_403_on_all_superadmin_endpoints(self):
        endpoints = [
            ("get", "/api/superadmin/overview/"),
            ("get", "/api/superadmin/companies/"),
            ("patch", f"/api/superadmin/companies/{self.company_rest.id}/status/"),
            ("get", "/api/superadmin/audit-logs/"),
        ]
        for user in (self.owner_user, self.staff_user):
            self.client.force_authenticate(user=user)
            for method, url in endpoints:
                if method == "get":
                    res = self.client.get(url)
                else:
                    res = self.client.patch(url, {"is_active": False}, format="json")
                self.assertEqual(res.status_code, 403, f"Expected 403 for {user.username} on {method} {url}")

    def test_superuser_overview_companies_status_toggle_and_audit_log(self):
        self.client.force_authenticate(user=self.superuser)

        # 1. Overview
        ov = self.client.get("/api/superadmin/overview/")
        self.assertEqual(ov.status_code, 200)
        self.assertEqual(ov.data["kpis"]["total_businesses"], 2)
        self.assertEqual(ov.data["kpis"]["active_businesses"], 2)
        self.assertEqual(ov.data["kpis"]["suspended_businesses"], 0)
        self.assertEqual(ov.data["kpis"]["platform_gmv_rs"], 1800.0)
        self.assertEqual(ov.data["kpis"]["total_voice_messages_used"], 165)

        # 2. List & filter companies by vertical
        hosp_list = self.client.get("/api/superadmin/companies/?vertical=hospital")
        self.assertEqual(hosp_list.status_code, 200)
        self.assertEqual(len(hosp_list.data), 1)
        self.assertEqual(hosp_list.data[0]["name"], "SuperAdmin Care Hospital")

        # 3. Suspend company -> updates DB & creates PlatformAuditLog
        sus = self.client.patch(
            f"/api/superadmin/companies/{self.company_rest.id}/status/",
            {"is_active": False, "reason": "Manual review"},
            format="json",
        )
        self.assertEqual(sus.status_code, 200)
        self.assertFalse(sus.data["is_active"])
        self.company_rest.refresh_from_db()
        self.assertEqual(self.company_rest.payment_status, Company.PAYMENT_SUSPENDED)

        # 4. Audit logs reflect suspension
        logs = self.client.get("/api/superadmin/audit-logs/")
        self.assertEqual(logs.status_code, 200)
        self.assertEqual(len(logs.data), 1)
        self.assertEqual(logs.data[0]["action"], "company_suspended")
        self.assertEqual(logs.data[0]["actor_email"], "superadmin@ridesai.com")
        self.assertEqual(logs.data[0]["target_company_name"], "SuperAdmin Grill House")

        # 5. Re-activate company -> creates second audit log
        act = self.client.patch(
            f"/api/superadmin/companies/{self.company_rest.id}/status/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(act.status_code, 200)
        self.assertTrue(act.data["is_active"])
        logs2 = self.client.get("/api/superadmin/audit-logs/")
        self.assertEqual(len(logs2.data), 2)
        self.assertEqual(logs2.data[0]["action"], "company_activated")


class StaffAttendanceAndSuppliersTests(TestCase):
    """Tests for PRD §3 / §9 Staff Attendance & Suppliers Management (Multi-Tenant)."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Ops Hub Alpha",
            business_type="restaurant",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.company_b = Company.objects.create(
            name="Ops Hub Beta",
            business_type="pharmacy",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_a = User.objects.create_user(
            username="att_owner_a",
            email="att_owner_a@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_a,
            is_active=True,
        )
        self.staff_a = User.objects.create_user(
            username="att_staff_a",
            email="att_staff_a@example.com",
            password="Password123!",
            first_name="Kashif",
            role=User.ROLE_STAFF,
            company=self.company_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="att_owner_b",
            email="att_owner_b@example.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.company_b,
            is_active=True,
        )

    def test_staff_attendance_mark_update_and_tenant_isolation(self):
        self.client.force_authenticate(user=self.owner_a)

        # Mark staff_a present with check-in/out times
        mark_res = self.client.post(
            "/api/operations/attendance/",
            {
                "staff_user_id": self.staff_a.id,
                "date": "2026-11-24",
                "status": "late",
                "check_in_time": "09:20",
                "check_out_time": "18:00",
                "notes": "Traffic delay",
            },
            format="json",
        )
        self.assertEqual(mark_res.status_code, 200)
        self.assertEqual(mark_res.data["status"], "late")
        self.assertEqual(mark_res.data["check_in_time"], "09:20")

        # GET sheet reflects summary & record
        sheet = self.client.get("/api/operations/attendance/?date=2026-11-24")
        self.assertEqual(sheet.status_code, 200)
        self.assertEqual(sheet.data["summary"]["late"], 1)
        staff_entry = next(r for r in sheet.data["staff"] if r["staff_user_id"] == self.staff_a.id)
        self.assertEqual(staff_entry["status"], "late")

        # Tenant B cannot mark attendance for Tenant A's staff
        self.client.force_authenticate(user=self.owner_b)
        cross_mark = self.client.post(
            "/api/operations/attendance/",
            {"staff_user_id": self.staff_a.id, "date": "2026-11-24", "status": "absent"},
            format="json",
        )
        self.assertEqual(cross_mark.status_code, 404)

    def test_suppliers_crud_and_tenant_isolation(self):
        from operations.models import Supplier

        self.client.force_authenticate(user=self.owner_a)
        create_res = self.client.post(
            "/api/operations/suppliers/",
            {
                "name": "Fresh Valley Produce",
                "contact_person": "Imran Khan",
                "phone": "03001234567",
                "category": "Produce",
                "payment_terms": "Net 15",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        sup_id = create_res.data["id"]

        # Update supplier
        patch_res = self.client.patch(
            f"/api/operations/suppliers/{sup_id}/",
            {"payment_terms": "Net 30", "is_active": False},
            format="json",
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["payment_terms"], "Net 30")
        self.assertFalse(patch_res.data["is_active"])

        # Tenant B cannot see, edit, or delete Tenant A's supplier
        self.client.force_authenticate(user=self.owner_b)
        list_b = self.client.get("/api/operations/suppliers/")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(list_b.data, [])

        cross_del = self.client.delete(f"/api/operations/suppliers/{sup_id}/")
        self.assertEqual(cross_del.status_code, 404)
        self.assertTrue(Supplier.objects.filter(pk=sup_id).exists())

        # Tenant A deletes cleanly
        self.client.force_authenticate(user=self.owner_a)
        del_a = self.client.delete(f"/api/operations/suppliers/{sup_id}/")
        self.assertEqual(del_a.status_code, 204)
        self.assertFalse(Supplier.objects.filter(pk=sup_id).exists())





































class RestaurantDashboardSummaryTests(TestCase):
    """Tests for GET /api/operations/restaurant/dashboard-summary/?period=today|7d|30d"""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Biryani Palace",
            business_type="restaurant",
            status="active",
            is_approved=True,
        )
        self.company_b = Company.objects.create(
            name="Other Bistro",
            business_type="restaurant",
            status="active",
            is_approved=True,
        )
        self.owner_a = User.objects.create_user(
            username="rest_dash_owner_a",
            email="owner_a@biryanipalace.test",
            password="Password123!",
            company=self.company_a,
            role=User.ROLE_OWNER,
            first_name="Ayesha",
        )
        self.owner_b = User.objects.create_user(
            username="rest_dash_owner_b",
            email="owner_b@otherbistro.test",
            password="Password123!",
            company=self.company_b,
            role=User.ROLE_OWNER,
            first_name="Bilal",
        )

    def test_summary_kpis_tables_alerts_trends_and_tenant_isolation(self):
        from companies.models import CatalogItem, Inventory
        from operations.models import (
            AgentConversation,
            Order,
            OrderItem,
            RestaurantTable,
            SuggestedFAQ,
        )

        # --- Company A Orders ---
        o1 = Order.objects.create(
            company=self.company_a,
            customer_name="Ali",
            customer_phone="03001112222",
            status=Order.STATUS_DELIVERED,
            source="whatsapp",
            subtotal=Decimal("1500.00"),
            total=Decimal("1500.00"),
        )
        o2 = Order.objects.create(
            company=self.company_a,
            customer_name="Sara",
            customer_phone="03001113333",
            status=Order.STATUS_NEW,
            source="public_web",
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        o3 = Order.objects.create(
            company=self.company_a,
            customer_name="Usman",
            customer_phone="03001114444",
            status=Order.STATUS_CANCELLED,
            source="dashboard",
            subtotal=Decimal("800.00"),
            total=Decimal("800.00"),
        )
        OrderItem.objects.create(
            order=o1, item_name="Chicken Biryani", quantity=3, unit_price=Decimal("500.00"), line_total=Decimal("1500.00")
        )
        OrderItem.objects.create(
            order=o2, item_name="Seekh Kabab", quantity=2, unit_price=Decimal("500.00"), line_total=Decimal("1000.00")
        )
        OrderItem.objects.create(
            order=o3, item_name="Cancelled Item", quantity=5, unit_price=Decimal("160.00"), line_total=Decimal("800.00")
        )

        # AI Conversations for Company A
        AgentConversation.objects.create(
            company=self.company_a, customer_phone="03001112222", customer_name="Ali"
        )
        AgentConversation.objects.create(
            company=self.company_a, customer_phone="03001113333", customer_name="Sara"
        )

        # Tables for Company A
        RestaurantTable.objects.create(company=self.company_a, table_number="T1", capacity=4, status=RestaurantTable.STATUS_AVAILABLE)
        RestaurantTable.objects.create(company=self.company_a, table_number="T2", capacity=4, status=RestaurantTable.STATUS_OCCUPIED)
        RestaurantTable.objects.create(company=self.company_a, table_number="T3", capacity=6, status=RestaurantTable.STATUS_RESERVED)

        # Low-stock Inventory for Company A
        item_rice = CatalogItem.objects.create(company=self.company_a, name="Basmati Rice", price=Decimal("300.00"))
        item_water = CatalogItem.objects.create(company=self.company_a, name="Water Bottles", price=Decimal("80.00"))
        Inventory.objects.create(
            company=self.company_a,
            item=item_rice,
            quantity=2,
            low_stock_threshold=5,
            is_unlimited=False,
        )
        Inventory.objects.create(
            company=self.company_a,
            item=item_water,
            quantity=50,
            low_stock_threshold=5,
            is_unlimited=False,
        )

        # Pending FAQ Suggestion for Company A
        SuggestedFAQ.objects.create(
            company=self.company_a,
            question="Do you offer family platters?",
            status=SuggestedFAQ.STATUS_PENDING,
        )

        # --- Company B Noise (must NEVER leak to Company A) ---
        ob = Order.objects.create(
            company=self.company_b,
            customer_name="Foreign Guest",
            customer_phone="03009998888",
            status=Order.STATUS_DELIVERED,
            source="whatsapp",
            subtotal=Decimal("9999.00"),
            total=Decimal("9999.00"),
        )
        OrderItem.objects.create(
            order=ob, item_name="Secret Dish B", quantity=10, unit_price=Decimal("999.90"), line_total=Decimal("9999.00")
        )
        RestaurantTable.objects.create(company=self.company_b, table_number="B1", capacity=2, status=RestaurantTable.STATUS_OCCUPIED)
        item_b = CatalogItem.objects.create(company=self.company_b, name="B Secret Ingredient", price=Decimal("500.00"))
        Inventory.objects.create(
            company=self.company_b, item=item_b, quantity=0, low_stock_threshold=10, is_unlimited=False
        )
        SuggestedFAQ.objects.create(
            company=self.company_b, question="Company B secret?", status=SuggestedFAQ.STATUS_PENDING
        )

        # 1. Query as Company A Owner (period=today)
        self.client.force_authenticate(user=self.owner_a)
        res = self.client.get("/api/operations/restaurant/dashboard-summary/?period=today")
        self.assertEqual(res.status_code, 200)
        body = res.data

        self.assertEqual(body["period"], "today")
        self.assertEqual(body["company_name"], "Biryani Palace")

        # KPIs: revenue excludes cancelled o3 => 1500 + 1000 = 2500, AOV = 1250
        self.assertEqual(body["kpis"]["revenue"], 2500.0)
        self.assertEqual(body["kpis"]["avg_order_value"], 1250.0)
        self.assertEqual(body["kpis"]["total_orders"], 3)
        self.assertEqual(body["kpis"]["active_orders"], 1)
        self.assertEqual(body["kpis"]["completed_orders"], 1)
        self.assertEqual(body["kpis"]["cancelled_orders"], 1)
        self.assertEqual(body["kpis"]["ai_conversations_count"], 2)
        self.assertEqual(body["kpis"]["ai_orders_count"], 2)

        # Tables
        self.assertEqual(body["tables"]["tables_total"], 3)
        self.assertEqual(body["tables"]["tables_available"], 1)
        self.assertEqual(body["tables"]["tables_occupied"], 1)
        self.assertEqual(body["tables"]["tables_reserved"], 1)

        # Alerts
        self.assertEqual(body["alerts"]["unassigned_orders_count"], 1)
        self.assertEqual(body["alerts"]["low_stock_items_count"], 1)
        self.assertEqual(body["alerts"]["pending_faq_suggestions_count"], 1)

        # Trend buckets
        self.assertEqual(len(body["trend"]), 24)

        # Top items excludes cancelled and Company B
        top_names = [i["name"] for i in body["top_items"]]
        self.assertEqual(top_names, ["Chicken Biryani", "Seekh Kabab"])

        # Channels
        self.assertEqual(body["channel_breakdown"]["whatsapp"], 1)
        self.assertEqual(body["channel_breakdown"]["public_web"], 1)
        self.assertEqual(body["channel_breakdown"]["dashboard"], 1)

        # Recent orders strictly Company A
        recent_customers = [o["customer_name"] for o in body["recent_orders"]]
        self.assertNotIn("Foreign Guest", recent_customers)
        self.assertEqual(len(body["recent_orders"]), 3)

        # 2. Verify 7d and 30d trend bucket counts
        res_7d = self.client.get("/api/operations/restaurant/dashboard-summary/?period=7d")
        self.assertEqual(res_7d.status_code, 200)
        self.assertEqual(len(res_7d.data["trend"]), 7)

        res_30d = self.client.get("/api/operations/restaurant/dashboard-summary/?period=30d")
        self.assertEqual(res_30d.status_code, 200)
        self.assertEqual(len(res_30d.data["trend"]), 30)

        # 3. Verify Company B sees only its own isolated data
        self.client.force_authenticate(user=self.owner_b)
        res_b = self.client.get("/api/operations/restaurant/dashboard-summary/?period=today")
        self.assertEqual(res_b.status_code, 200)
        self.assertEqual(res_b.data["kpis"]["revenue"], 9999.0)
        self.assertEqual(res_b.data["kpis"]["total_orders"], 1)
        self.assertEqual(res_b.data["tables"]["tables_total"], 1)
        self.assertEqual([i["name"] for i in res_b.data["top_items"]], ["Secret Dish B"])


class WhatsAppSessionSyncAndReconnectTests(TestCase):
    """Tests for live Evolution API session sync, force reconnect/disconnect, voice notes & order notification errors."""

    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Spice Route Restaurant",
            business_type="restaurant",
            status="active",
            is_approved=True,
            whatsapp_instance_name="company_spice_route",
            whatsapp_connection_status="connected",
        )
        self.owner = User.objects.create_user(
            username="wa_sync_owner",
            email="owner@spiceroute.test",
            password="Password123!",
            company=self.company,
            role=User.ROLE_OWNER,
        )
        self.client.force_authenticate(user=self.owner)

    @patch("operations.evolution_views.evolution_client.get_connection_status")
    def test_status_syncs_stale_connected_flag_to_disconnected(self, mock_live_status):
        mock_live_status.return_value = "disconnected"
        res = self.client.get("/api/operations/whatsapp/connect/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "disconnected")
        self.assertTrue(res.data["live_synced"])
        self.company.refresh_from_db()
        self.assertEqual(self.company.whatsapp_connection_status, "disconnected")

    @patch("operations.evolution_views.evolution_client.reconnect_instance")
    def test_force_reconnect_regenerates_qr_even_when_db_says_connected(self, mock_reconnect):
        mock_reconnect.return_value = {
            "instance_name": "company_spice_route",
            "qrcode_base64": "data:image/png;base64,FRESHQR123",
            "status": "disconnected",
        }
        res = self.client.post("/api/operations/whatsapp/reconnect/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "disconnected")
        self.assertEqual(res.data["qrcode_base64"], "data:image/png;base64,FRESHQR123")
        self.company.refresh_from_db()
        self.assertEqual(self.company.whatsapp_connection_status, "disconnected")
        mock_reconnect.assert_called_once()
        args, kwargs = mock_reconnect.call_args
        self.assertEqual(args[0], "company_spice_route")
        self.assertFalse(str(kwargs.get("webhook_url", "")).endswith("/"))

    @patch("operations.evolution_views.evolution_client.delete_instance")
    @patch("operations.evolution_views.evolution_client.logout_instance")
    def test_disconnect_logs_out_and_deletes_instance(self, mock_logout, mock_delete):
        mock_logout.return_value = {"success": True}
        mock_delete.return_value = {"success": True}
        res = self.client.post("/api/operations/whatsapp/disconnect/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "disconnected")
        self.assertTrue(res.data["disconnected"])
        self.company.refresh_from_db()
        self.assertEqual(self.company.whatsapp_connection_status, "disconnected")
        mock_logout.assert_called_once_with("company_spice_route")
        mock_delete.assert_called_once_with("company_spice_route")

    @patch("operations.evolution_views.evolution_client.reconnect_instance")
    @patch("operations.evolution_views.evolution_client.create_instance")
    @patch("operations.evolution_views.evolution_client.get_connection_status")
    def test_connect_falls_back_to_hard_delete_reconnect_when_401_no_qr(
        self, mock_status, mock_create, mock_reconnect
    ):
        mock_status.return_value = "disconnected"
        mock_create.return_value = {"instance_name": "company_spice_route", "qrcode_base64": None, "status": "close"}
        mock_reconnect.return_value = {
            "instance_name": "company_spice_route",
            "qrcode_base64": "data:image/png;base64,HARD_DELETE_QR_OK",
            "status": "disconnected",
        }
        res = self.client.post("/api/operations/whatsapp/connect/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "disconnected")
        self.assertEqual(res.data["qrcode_base64"], "data:image/png;base64,HARD_DELETE_QR_OK")
        mock_reconnect.assert_called_once()

    @patch("operations.evolution_client.time.sleep")
    @patch("operations.evolution_client.configure_instance_settings")
    @patch("operations.evolution_client.requests.get")
    @patch("operations.evolution_client.requests.post")
    @patch("operations.evolution_client.delete_instance")
    @patch("operations.evolution_client.logout_instance")
    def test_reconnect_hard_deletes_strips_webhook_slash_and_polls_qr(
        self, mock_logout, mock_delete, mock_post, mock_get, mock_cfg, mock_sleep
    ):
        from unittest.mock import MagicMock
        from operations import evolution_client

        # create_instance initially returns no QR; 2nd poll returns valid base64 QR
        post_resp = MagicMock(status_code=201)
        post_resp.json.return_value = {"instance": {"status": "connecting"}}
        mock_post.return_value = post_resp

        poll1 = MagicMock(status_code=200)
        poll1.json.return_value = {"count": 0}
        poll2 = MagicMock(status_code=200)
        poll2.json.return_value = {"base64": "data:image/png;base64,POLLED_FRESH_QR_DATA"}
        mock_get.side_effect = [poll1, poll2]

        res = evolution_client.reconnect_instance(
            "company_spice_route",
            webhook_url="http://host.docker.internal:8000/api/operations/whatsapp/evolution-webhook/",
        )
        mock_logout.assert_called_once_with("company_spice_route")
        mock_delete.assert_called_once_with("company_spice_route")
        self.assertEqual(res["qrcode_base64"], "data:image/png;base64,POLLED_FRESH_QR_DATA")
        # Verify webhook URL passed to Evolution API has NO trailing slash
        _, post_kwargs = mock_post.call_args
        registered_url = post_kwargs["json"]["webhook"]["url"]
        self.assertEqual(
            registered_url,
            "http://host.docker.internal:8000/api/operations/whatsapp/evolution-webhook",
        )
        self.assertEqual(mock_get.call_count, 2)

    @patch("operations.evolution_views.process_incoming_whatsapp_message")
    @patch("operations.evolution_views.evolution_client.get_media_base64")
    def test_webhook_unwraps_ephemeral_voice_note_and_resolves_lid_jid(self, mock_media, mock_process):
        mock_media.return_value = b"OggS-fake-voice-bytes"
        mock_process.return_value = {"success": True, "reply_text": "Order received"}

        payload = {
            "event": "messages.upsert",
            "instance": "company_spice_route",
            "data": {
                "key": {
                    "id": "MSG123",
                    "fromMe": False,
                    "remoteJid": "99887766@lid",
                    "remoteJidAlt": "923001234567@s.whatsapp.net",
                },
                "pushName": "Hamza",
                "message": {
                    "ephemeralMessage": {
                        "message": {
                            "audioMessage": {"mimetype": "audio/ogg; codecs=opus", "ptt": True}
                        }
                    }
                },
            },
        }
        res = self.client.post("/api/operations/whatsapp/evolution-webhook/", payload, format="json")
        self.assertEqual(res.status_code, 200)
        mock_process.assert_called_once()
        _, kwargs = mock_process.call_args
        self.assertEqual(kwargs["sender_phone"], "923001234567")
        self.assertEqual(kwargs["msg_type"], "audio")
        self.assertEqual(kwargs["audio_bytes"], b"OggS-fake-voice-bytes")

    @patch("operations.notifications.evolution_client.send_text_message")
    def test_order_notification_returns_false_on_evolution_error(self, mock_send):
        from operations.notifications import send_status_notification

        mock_send.return_value = {"success": False, "error": "Evolution API HTTP 400: Connection Closed"}
        dispatched = send_status_notification(
            company=self.company,
            customer_phone="03001234567",
            entity_type="order",
            reference_id="ORD-99",
            new_status="confirmed",
        )
        self.assertFalse(dispatched)
        mock_send.assert_called_once()


class RestaurantModifiersAndKDSTests(TestCase):
    """Tests for Menu Modifiers/Add-ons, Order Types, AI Modifier Awareness, and Live KDS."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Grill House A",
            business_type="restaurant",
            status="active",
            is_approved=True,
            subscription_status="active",
        )
        self.company_b = Company.objects.create(
            name="Burger Spot B",
            business_type="restaurant",
            status="active",
            is_approved=True,
            subscription_status="active",
        )
        self.owner_a = User.objects.create_user(
            username="kds_owner_a",
            email="owner_a@grillhouse.test",
            password="Password123!",
            company=self.company_a,
            role=User.ROLE_OWNER,
        )
        self.owner_b = User.objects.create_user(
            username="kds_owner_b",
            email="owner_b@burgerspot.test",
            password="Password123!",
            company=self.company_b,
            role=User.ROLE_OWNER,
        )

    def test_modifiers_persistence_order_totals_kds_bump_and_tenant_isolation(self):
        from companies.models import CatalogItem
        from operations.models import Order, RestaurantTable
        from operations.whatsapp_agent import execute_create_order, execute_get_catalog_items

        self.client.force_authenticate(user=self.owner_a)

        # 1. Create menu item with modifiers_schema, kitchen_station, prep_time_minutes
        modifiers_payload = [
            {
                "group": "Size",
                "required": False,
                "options": [
                    {"name": "Regular", "price": 0},
                    {"name": "Large", "price": 150},
                ],
            },
            {
                "group": "Add-ons",
                "required": False,
                "options": [
                    {"name": "Extra Cheese", "price": 100},
                ],
            },
        ]
        burger = CatalogItem.objects.create(
            company=self.company_a,
            name="Zinger Burger",
            price=Decimal("500.00"),
            kitchen_station="grill",
            prep_time_minutes=12,
            modifiers_schema=modifiers_payload,
        )
        cola = CatalogItem.objects.create(
            company=self.company_a,
            name="Mint Margarita",
            price=Decimal("250.00"),
            kitchen_station="drinks",
            prep_time_minutes=5,
        )
        table_t1 = RestaurantTable.objects.create(
            company=self.company_a,
            table_number="T1",
            capacity=4,
            status=RestaurantTable.STATUS_OCCUPIED,
        )

        # Verify modifiers_schema persisted cleanly
        burger.refresh_from_db()
        self.assertEqual(burger.kitchen_station, "grill")
        self.assertEqual(burger.prep_time_minutes, 12)
        self.assertEqual(len(burger.modifiers_schema), 2)

        # 2. Create Dine-In order with modifiers via API:
        # Base 500 + Large (150) + Extra Cheese (100) = 750 * 2 = 1500
        create_res = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "dine_in",
                "table_id": table_t1.id,
                "customer_name": "Table T1 Guest",
                "items": [
                    {
                        "item_id": burger.id,
                        "quantity": 2,
                        "selected_modifiers": [
                            {"group": "Size", "name": "Large", "price": 150},
                            {"group": "Add-ons", "name": "Extra Cheese", "price": 100},
                        ],
                        "item_notes": "Extra spicy, no mayo",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        self.assertEqual(create_res.data["order_type"], "dine_in")
        self.assertEqual(create_res.data["table_number"], "T1")
        self.assertEqual(Decimal(create_res.data["total"]), Decimal("1500.00"))
        self.assertEqual(len(create_res.data["items"][0]["selected_modifiers"]), 2)
        self.assertEqual(create_res.data["items"][0]["item_notes"], "Extra spicy, no mayo")
        dine_in_order_id = create_res.data["id"]

        # 3. Create Takeaway Drinks order
        drink_res = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "takeaway",
                "customer_name": "Zain",
                "items": [{"item_id": cola.id, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(drink_res.status_code, 201)

        # 4. Verify AI Agent catalog & create_order modifier awareness
        ai_cat = execute_get_catalog_items(self.company_a, search_query="Zinger")
        self.assertTrue(ai_cat["success"])
        self.assertEqual(len(ai_cat["items"][0]["modifiers_schema"]), 2)

        ai_order_res = execute_create_order(
            company=self.company_a,
            customer_name="Hassan Ali",
            customer_phone="03015556677",
            delivery_address="Model Town, Lahore",
            items=[
                {
                    "item_name": "Zinger Burger",
                    "quantity": 1,
                    "selected_modifiers": ["Extra Cheese"],
                    "special_instructions": "Less salt",
                }
            ],
        )
        self.assertTrue(ai_order_res["success"])
        # Base 500 + Extra Cheese 100 = 600
        ai_order_obj = Order.objects.get(order_number=ai_order_res["order_number"])
        self.assertEqual(ai_order_obj.total, Decimal("600.00"))
        self.assertEqual(ai_order_obj.items.first().selected_modifiers[0]["name"], "Extra Cheese")

        # 5. KDS Listing & Station Filtering
        kds_all = self.client.get("/api/operations/restaurant/kds/?station=all")
        self.assertEqual(kds_all.status_code, 200)
        self.assertEqual(kds_all.data["station_counts"]["all"], 3)
        self.assertEqual(kds_all.data["station_counts"]["grill"], 2)
        self.assertEqual(kds_all.data["station_counts"]["drinks"], 1)
        # Oldest-first ordering: dine_in_order_id should be first
        self.assertEqual(kds_all.data["tickets"][0]["id"], dine_in_order_id)

        kds_drinks = self.client.get("/api/operations/restaurant/kds/?station=drinks")
        self.assertEqual(kds_drinks.status_code, 200)
        self.assertEqual(len(kds_drinks.data["tickets"]), 1)
        self.assertEqual(kds_drinks.data["tickets"][0]["items"][0]["name"], "Mint Margarita")

        # 6. 1-Click KDS Bump Progression (new -> preparing -> ready -> delivered for dine_in)
        bump1 = self.client.post(f"/api/operations/restaurant/kds/{dine_in_order_id}/bump/")
        self.assertEqual(bump1.status_code, 200)
        self.assertEqual(bump1.data["status"], Order.STATUS_PREPARING)
        self.assertIsNotNone(bump1.data["prep_started_at"])
        self.assertIsNone(bump1.data["ready_at"])

        bump2 = self.client.post(f"/api/operations/restaurant/kds/{dine_in_order_id}/bump/")
        self.assertEqual(bump2.status_code, 200)
        self.assertEqual(bump2.data["status"], Order.STATUS_READY)
        self.assertIsNotNone(bump2.data["ready_at"])

        bump3 = self.client.post(f"/api/operations/restaurant/kds/{dine_in_order_id}/bump/")
        self.assertEqual(bump3.status_code, 200)
        self.assertEqual(bump3.data["status"], Order.STATUS_DELIVERED)

        # 7. Strict Multi-Tenant Isolation: Company B sees 0 tickets and gets 404 on bump
        self.client.force_authenticate(user=self.owner_b)
        kds_b = self.client.get("/api/operations/restaurant/kds/?station=all")
        self.assertEqual(kds_b.status_code, 200)
        self.assertEqual(kds_b.data["tickets"], [])
        self.assertEqual(kds_b.data["station_counts"]["all"], 0)

        cross_bump = self.client.post(f"/api/operations/restaurant/kds/{drink_res.data['id']}/bump/")
        self.assertEqual(cross_bump.status_code, 404)

    def test_ai_create_order_auto_detects_modifiers_from_special_notes(self):
        """
        Verifies deterministic backend fallback: even if the LLM passes 'extra cheese'
        inside special_instructions or order notes instead of selected_modifiers,
        execute_create_order attaches the structured modifier and adds +Rs. 100 to total.
        """
        from companies.models import CatalogItem
        from operations.models import Order
        from operations.whatsapp_agent import execute_create_order

        CatalogItem.objects.create(
            company=self.company_a,
            name="Zinger Burger",
            price=Decimal("650.00"),
            kitchen_station="grill",
            modifiers_schema=[
                {
                    "group": "Add-ons",
                    "required": False,
                    "options": [{"name": "Extra Cheese", "price": 100}],
                }
            ],
        )

        res = execute_create_order(
            company=self.company_a,
            customer_name="Bilal Ahmed",
            customer_phone="03029998877",
            delivery_address="Gulberg, Lahore",
            items=[
                {
                    "item_name": "Zinger Burger",
                    "quantity": 1,
                    "special_instructions": "with extra cheese please",
                }
            ],
            notes="make it fresh",
        )
        self.assertTrue(res["success"])
        order = Order.objects.get(order_number=res["order_number"])
        # Base 650 + Extra Cheese 100 = 750
        self.assertEqual(order.total, Decimal("750.00"))
        oi = order.items.first()
        self.assertEqual(oi.unit_price, Decimal("750.00"))
        self.assertEqual(len(oi.selected_modifiers), 1)
        self.assertEqual(oi.selected_modifiers[0]["name"], "Extra Cheese")
        self.assertEqual(oi.selected_modifiers[0]["price"], 100.0)


class POSCustomerAutoRecallTests(TestCase):
    """Tests for Guest Auto-Upsert on Order Creation & Fast Multi-Tenant Customer Lookup API."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Royal Karahi A",
            business_type="restaurant",
            status="active",
            is_approved=True,
            subscription_status="active",
        )
        self.company_b = Company.objects.create(
            name="Other Cafe B",
            business_type="restaurant",
            status="active",
            is_approved=True,
            subscription_status="active",
        )
        self.owner_a = User.objects.create_user(
            username="pos_recall_owner_a",
            email="owner_a@royalkarahi.test",
            password="Password123!",
            company=self.company_a,
            role=User.ROLE_OWNER,
        )
        self.owner_b = User.objects.create_user(
            username="pos_recall_owner_b",
            email="owner_b@othercafe.test",
            password="Password123!",
            company=self.company_b,
            role=User.ROLE_OWNER,
        )

    def test_pos_order_auto_saves_customer_and_lookup_is_tenant_isolated(self):
        from companies.models import CatalogItem, ServiceArea
        from operations.models import Customer

        item_a = CatalogItem.objects.create(
            company=self.company_a,
            name="Chicken Karahi",
            price=Decimal("1200.00"),
        )
        ServiceArea.objects.create(
            company=self.company_a,
            area_type="city",
            city="Lahore",
            delivery_fee=Decimal("100.00"),
            is_active=True,
        )

        self.client.force_authenticate(user=self.owner_a)

        # 1. Create a POS Delivery order — should auto-upsert Customer record
        res1 = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "delivery",
                "customer_name": "Usman Tariq",
                "customer_phone": "03005554433",
                "delivery_address": "House 22, Block C, Gulberg",
                "city": "Lahore",
                "items": [{"item_id": item_a.id, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(res1.status_code, 201)

        # Verify Customer auto-created with latest name & delivery_address
        cust = Customer.objects.filter(company=self.company_a, phone="03005554433").first()
        self.assertIsNotNone(cust)
        self.assertEqual(cust.name, "Usman Tariq")
        self.assertEqual(cust.delivery_address, "House 22, Block C, Gulberg")

        # 2. Place a second Takeaway order for the same guest to increment total_orders
        res2 = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "takeaway",
                "customer_name": "Usman Tariq",
                "customer_phone": "03005554433",
                "items": [{"item_id": item_a.id, "quantity": 2}],
            },
            format="json",
        )
        self.assertEqual(res2.status_code, 201)

        # 3. Lookup by partial phone
        lookup_phone = self.client.get("/api/operations/customers/lookup/?q=0300555")
        self.assertEqual(lookup_phone.status_code, 200)
        self.assertEqual(len(lookup_phone.data), 1)
        match = lookup_phone.data[0]
        self.assertEqual(match["name"], "Usman Tariq")
        self.assertEqual(match["phone"], "03005554433")
        self.assertEqual(match["delivery_address"], "House 22, Block C, Gulberg")
        self.assertEqual(match["total_orders"], 2)
        self.assertIsNotNone(match["last_order_at"])

        # 4. Lookup by partial name (case-insensitive)
        lookup_name = self.client.get("/api/operations/customers/lookup/?q=usman")
        self.assertEqual(lookup_name.status_code, 200)
        self.assertEqual(len(lookup_name.data), 1)
        self.assertEqual(lookup_name.data[0]["phone"], "03005554433")

        # 5. Strict multi-tenant isolation: Company B gets 0 matches for Company A's guest
        self.client.force_authenticate(user=self.owner_b)
        lookup_b = self.client.get("/api/operations/customers/lookup/?q=0300555")
        self.assertEqual(lookup_b.status_code, 200)
        self.assertEqual(lookup_b.data, [])


class RestaurantTablesAndReservationsTests(TestCase):
    """Tests for Interactive Floor Plan, Conflict-Free Reservations, Seat/Complete, and AI Table Booking."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Saffron Lounge A",
            business_type="restaurant",
            status="active",
            is_approved=True,
            subscription_status="active",
        )
        self.company_b = Company.objects.create(
            name="Other Rooftop B",
            business_type="restaurant",
            status="active",
            is_approved=True,
            subscription_status="active",
        )
        self.owner_a = User.objects.create_user(
            username="floor_owner_a",
            email="owner_a@saffron.test",
            password="Password123!",
            company=self.company_a,
            role=User.ROLE_OWNER,
        )
        self.owner_b = User.objects.create_user(
            username="floor_owner_b",
            email="owner_b@otherrooftop.test",
            password="Password123!",
            company=self.company_b,
            role=User.ROLE_OWNER,
        )

    def test_floor_plan_conflicts_seat_complete_ai_booking_and_tenant_isolation(self):
        from datetime import timedelta
        from django.utils import timezone
        from operations.models import Customer, Order, RestaurantTable, TableReservation
        from operations.whatsapp_agent import execute_book_table_reservation

        self.client.force_authenticate(user=self.owner_a)

        t1 = RestaurantTable.objects.create(
            company=self.company_a,
            table_number="T1",
            capacity=4,
            section="indoor",
            status=RestaurantTable.STATUS_OCCUPIED,
        )
        t2 = RestaurantTable.objects.create(
            company=self.company_a,
            table_number="VIP-1",
            capacity=6,
            section="vip",
            status=RestaurantTable.STATUS_AVAILABLE,
        )

        # Active dine-in order on T1
        active_ord = Order.objects.create(
            company=self.company_a,
            order_type=Order.ORDER_TYPE_DINE_IN,
            table=t1,
            table_number="T1",
            customer_name="Dine In Guest",
            status=Order.STATUS_PREPARING,
            subtotal=Decimal("2400.00"),
            total=Decimal("2400.00"),
        )

        today_str = timezone.localdate().isoformat()
        upcoming_time = (timezone.localtime() + timedelta(hours=1)).strftime("%H:%M")

        # 1. Create reservation on VIP-1 (auto-upserts Customer)
        res_create = self.client.post(
            "/api/operations/restaurant/reservations/",
            {
                "customer_name": "Nadia Malik",
                "customer_phone": "03007778899",
                "party_size": 4,
                "reservation_date": today_str,
                "reservation_time": upcoming_time,
                "table_id": t2.id,
                "special_requests": "Window seat",
            },
            format="json",
        )
        self.assertEqual(res_create.status_code, 201)
        res_id = res_create.data["id"]
        self.assertEqual(res_create.data["table_number"], "VIP-1")
        self.assertTrue(Customer.objects.filter(company=self.company_a, phone="03007778899").exists())

        # 2. Double-booking conflict prevention within 90-minute window -> 409 Conflict
        conflict_time = (timezone.localtime() + timedelta(hours=1, minutes=30)).strftime("%H:%M")
        res_conflict = self.client.post(
            "/api/operations/restaurant/reservations/",
            {
                "customer_name": "Double Booked Guest",
                "customer_phone": "03001112233",
                "party_size": 4,
                "reservation_date": today_str,
                "reservation_time": conflict_time,
                "table_id": t2.id,
            },
            format="json",
        )
        self.assertEqual(res_conflict.status_code, 409)

        # 3. Floor Plan endpoint includes active dine-in order on T1 & upcoming reservation on VIP-1
        fp_res = self.client.get("/api/operations/restaurant/floor-plan/")
        self.assertEqual(fp_res.status_code, 200)
        self.assertEqual(fp_res.data["summary"]["total"], 2)
        self.assertEqual(fp_res.data["summary"]["by_section"]["indoor"], 1)
        self.assertEqual(fp_res.data["summary"]["by_section"]["vip"], 1)

        tables_by_num = {row["table_number"]: row for row in fp_res.data["tables"]}
        self.assertIsNotNone(tables_by_num["T1"]["active_order"])
        self.assertEqual(tables_by_num["T1"]["active_order"]["order_id"], active_ord.id)
        self.assertEqual(tables_by_num["T1"]["active_order"]["total"], 2400.0)
        self.assertIsNotNone(tables_by_num["VIP-1"]["next_reservation"])
        self.assertEqual(tables_by_num["VIP-1"]["next_reservation"]["customer_name"], "Nadia Malik")

        # 4. 1-Click Seat Guest -> reservation 'seated' & table 'occupied'
        seat_res = self.client.post(f"/api/operations/restaurant/reservations/{res_id}/seat/")
        self.assertEqual(seat_res.status_code, 200)
        self.assertEqual(seat_res.data["status"], TableReservation.STATUS_SEATED)
        t2.refresh_from_db()
        self.assertEqual(t2.status, RestaurantTable.STATUS_OCCUPIED)

        # 5. 1-Click Complete -> reservation 'completed' & table 'available'
        comp_res = self.client.post(f"/api/operations/restaurant/reservations/{res_id}/complete/")
        self.assertEqual(comp_res.status_code, 200)
        self.assertEqual(comp_res.data["status"], TableReservation.STATUS_COMPLETED)
        t2.refresh_from_db()
        self.assertEqual(t2.status, RestaurantTable.STATUS_AVAILABLE)

        # 6. 1-Click Table Status transition to 'cleaning'
        clean_res = self.client.post(
            f"/api/operations/restaurant/tables/{t1.id}/status/",
            {"status": "cleaning"},
            format="json",
        )
        self.assertEqual(clean_res.status_code, 200)
        t1.refresh_from_db()
        self.assertEqual(t1.status, RestaurantTable.STATUS_CLEANING)

        # 7. AI Agent Table Reservation Tool (books best-fit available table)
        tomorrow_str = (timezone.localdate() + timedelta(days=1)).isoformat()
        ai_res = execute_book_table_reservation(
            company=self.company_a,
            customer_name="Hamza Raza",
            customer_phone="03009997766",
            party_size=5,
            reservation_date=tomorrow_str,
            reservation_time="20:00",
            special_requests="Anniversary",
        )
        self.assertTrue(ai_res["success"])
        self.assertEqual(ai_res["table_number"], "VIP-1")  # Only table with capacity >= 5
        self.assertEqual(ai_res["status"], TableReservation.STATUS_CONFIRMED)

        # AI double-booking on same slot for party of 5 fails cleanly
        ai_dup = execute_book_table_reservation(
            company=self.company_a,
            customer_name="Another Party",
            customer_phone="03008887766",
            party_size=5,
            reservation_date=tomorrow_str,
            reservation_time="20:30",
        )
        self.assertFalse(ai_dup["success"])

        # 8. Strict Multi-Tenant Isolation: Company B sees 0 tables/reservations and gets 404
        self.client.force_authenticate(user=self.owner_b)
        fp_b = self.client.get("/api/operations/restaurant/floor-plan/")
        self.assertEqual(fp_b.status_code, 200)
        self.assertEqual(fp_b.data["tables"], [])

        res_b = self.client.get("/api/operations/restaurant/reservations/?date=all")
        self.assertEqual(res_b.status_code, 200)
        self.assertEqual(res_b.data, [])

        cross_seat = self.client.post(f"/api/operations/restaurant/reservations/{res_id}/seat/")
        self.assertEqual(cross_seat.status_code, 404)

    def test_dine_in_auto_occupies_blocks_double_booking_and_frees_table_on_completion(self):
        from companies.models import CatalogItem
        from operations.models import Order, RestaurantTable

        self.client.force_authenticate(user=self.owner_a)

        dish = CatalogItem.objects.create(
            company=self.company_a,
            name="Mutton Karahi",
            price=Decimal("1800.00"),
        )
        t1 = RestaurantTable.objects.create(
            company=self.company_a,
            table_number="T1",
            capacity=4,
            section="indoor",
            status=RestaurantTable.STATUS_AVAILABLE,
        )

        # 1. Creating a Dine-In order on T1 automatically sets T1.status = 'occupied'
        res1 = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "dine_in",
                "table_id": t1.id,
                "customer_name": "Salman Khan",
                "customer_phone": "03001112233",
                "items": [{"item_id": dish.id, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(res1.status_code, 201)
        order_id = res1.data["id"]
        t1.refresh_from_db()
        self.assertEqual(t1.status, RestaurantTable.STATUS_OCCUPIED)

        # 2. Creating a second Dine-In order on T1 for a DIFFERENT customer returns 409 Conflict
        res_conflict = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "dine_in",
                "table_id": t1.id,
                "customer_name": "Different Guest",
                "customer_phone": "03009998877",
                "items": [{"item_id": dish.id, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(res_conflict.status_code, 409)
        self.assertIn("currently occupied by Salman Khan", res_conflict.data["detail"])

        # 3. Completing the Dine-In order (via KDS bump: new -> preparing -> ready -> delivered) frees T1 back to 'available'
        self.client.post(f"/api/operations/restaurant/kds/{order_id}/bump/")
        self.client.post(f"/api/operations/restaurant/kds/{order_id}/bump/")
        bump_done = self.client.post(f"/api/operations/restaurant/kds/{order_id}/bump/")
        self.assertEqual(bump_done.status_code, 200)
        self.assertEqual(bump_done.data["status"], Order.STATUS_DELIVERED)

        t1.refresh_from_db()
        self.assertEqual(t1.status, RestaurantTable.STATUS_AVAILABLE)

    def test_ai_table_booking_normalizes_missing_or_past_date_to_today_and_appears_in_today_filter(self):
        """
        Verifies execute_book_table_reservation normalizes missing, relative ('aaj'),
        or outdated past dates (e.g., 2023-05-01) to today's local date so the created
        TableReservation immediately appears under GET /api/operations/restaurant/reservations/?date=today.
        """
        from django.utils import timezone
        from operations.models import RestaurantTable
        from operations.whatsapp_agent import execute_book_table_reservation

        self.client.force_authenticate(user=self.owner_a)

        RestaurantTable.objects.create(
            company=self.company_a,
            table_number="T5",
            capacity=4,
            section="indoor",
            status=RestaurantTable.STATUS_AVAILABLE,
        )
        RestaurantTable.objects.create(
            company=self.company_a,
            table_number="T6",
            capacity=6,
            section="outdoor",
            status=RestaurantTable.STATUS_AVAILABLE,
        )

        today_iso = timezone.localdate().isoformat()

        # Case 1: Relative date ('aaj')
        r1 = execute_book_table_reservation(
            company=self.company_a,
            customer_name="Ayesha Siddiqui",
            customer_phone="03001239876",
            party_size=4,
            reservation_date="aaj",
            reservation_time="20:00",
        )
        self.assertTrue(r1["success"])
        self.assertEqual(r1["reservation_date"], today_iso)
        self.assertIn("reserved_at", r1)

        # Case 2: LLM guesses an outdated past year (2023-10-15)
        r2 = execute_book_table_reservation(
            company=self.company_a,
            customer_name="Zeeshan Ali",
            customer_phone="03009871234",
            party_size=4,
            reservation_date="2023-10-15",
            reservation_time="21:00",
        )
        self.assertTrue(r2["success"])
        self.assertEqual(r2["reservation_date"], today_iso)

        # Both must appear in GET /api/operations/restaurant/reservations/?date=today
        today_list = self.client.get("/api/operations/restaurant/reservations/?date=today")
        self.assertEqual(today_list.status_code, 200)
        names = [row["customer_name"] for row in today_list.data]
        self.assertIn("Ayesha Siddiqui", names)
        self.assertIn("Zeeshan Ali", names)

    @patch("operations.notifications.send_status_notification")
    def test_pos_delivery_creation_order_type_status_guards_notifications_and_waiting_area(self, mock_notify):
        from companies.models import CatalogItem
        from operations.models import Order

        mock_notify.return_value = True
        self.client.force_authenticate(user=self.owner_a)

        dish = CatalogItem.objects.create(
            company=self.company_a,
            name="Club Sandwich",
            price=Decimal("450.00"),
        )

        # 1. POS Delivery order succeeds with delivery_address even without ServiceArea / city
        deliv_res = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "delivery",
                "fulfillment_type": "delivery",
                "customer_name": "Delivery Guest",
                "customer_phone": "03001112244",
                "delivery_address": "House 9, Street 4, DHA Phase 5",
                "items": [{"item_id": dish.id, "quantity": 2}],
            },
            format="json",
        )
        self.assertEqual(deliv_res.status_code, 201)
        self.assertEqual(deliv_res.data["order_type"], "delivery")
        self.assertEqual(deliv_res.data["delivery_address"], "House 9, Street 4, DHA Phase 5")
        self.assertIsNone(deliv_res.data["table_id"])

        # 2. Dine-In order with Waiting Area (No Table) succeeds cleanly
        mock_notify.reset_mock()
        dine_res = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "dine_in",
                "allow_waiting_area": True,
                "customer_name": "Waiting Guest",
                "customer_phone": "03001119988",
                "items": [{"item_id": dish.id, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(dine_res.status_code, 201)
        self.assertEqual(dine_res.data["order_type"], "dine_in")
        self.assertEqual(dine_res.data["table_number"], "Waiting Area")
        dine_order_id = dine_res.data["id"]

        # Intermediate dine_in notifications ('new', 'preparing', 'ready') MUST be suppressed
        mock_notify.assert_not_called()

        # 3. Dine-In order rejects 'out_for_delivery' with 400 Bad Request
        bad_status = self.client.patch(
            f"/api/operations/orders/{dine_order_id}/status/",
            {"status": Order.STATUS_OUT_FOR_DELIVERY},
            format="json",
        )
        self.assertEqual(bad_status.status_code, 400)

        # Advance dine_in: new -> preparing -> ready (still no WhatsApp spam) -> delivered (fires 1 thank-you!)
        self.client.patch(f"/api/operations/orders/{dine_order_id}/status/", {"status": "preparing"}, format="json")
        self.client.patch(f"/api/operations/orders/{dine_order_id}/status/", {"status": "ready"}, format="json")
        mock_notify.assert_not_called()

        done_res = self.client.patch(
            f"/api/operations/orders/{dine_order_id}/status/",
            {"status": "delivered"},
            format="json",
        )
        self.assertEqual(done_res.status_code, 200)
        self.assertEqual(mock_notify.call_count, 1)

    def test_ai_delivery_order_applies_service_area_delivery_fee_and_zero_for_takeaway(self):
        from companies.models import CatalogItem, ServiceArea
        from operations.models import Order
        from operations.whatsapp_agent import (
            _build_system_prompt,
            execute_create_order,
            get_business_context_for_company,
        )

        ServiceArea.objects.create(
            company=self.company_a,
            area_type="city",
            city="Lahore",
            delivery_fee=Decimal("150.00"),
            is_active=True,
        )
        CatalogItem.objects.create(
            company=self.company_a,
            name="Zinger Burger",
            price=Decimal("650.00"),
            is_available=True,
        )

        # 1. System prompt includes the configured Rs. 150 delivery fee
        ctx = get_business_context_for_company(self.company_a)
        self.assertEqual(ctx["delivery_fee"], 150.0)
        prompt = _build_system_prompt("Ali", ctx)
        self.assertIn("Rs. 150", prompt)

        # 2. AI delivery order adds Rs. 150 delivery_fee -> 650 + 150 = 800
        deliv_res = execute_create_order(
            company=self.company_a,
            customer_name="Farhan Ali",
            customer_phone="03017778899",
            delivery_address="Model Town, Lahore",
            items=[{"item_name": "Zinger Burger", "quantity": 1}],
            order_type="delivery",
        )
        self.assertTrue(deliv_res["success"])
        self.assertEqual(deliv_res["delivery_fee"], "Rs. 150.00")
        self.assertEqual(deliv_res["total"], "Rs. 800.00")
        deliv_order = Order.objects.get(order_number=deliv_res["order_number"])
        self.assertEqual(deliv_order.delivery_fee, Decimal("150.00"))
        self.assertEqual(deliv_order.total, Decimal("800.00"))

        # 3. AI takeaway order keeps delivery_fee = 0 -> total = 650
        take_res = execute_create_order(
            company=self.company_a,
            customer_name="Farhan Ali",
            customer_phone="03017778899",
            delivery_address="Counter Pickup",
            items=[{"item_name": "Zinger Burger", "quantity": 1}],
            order_type="takeaway",
        )
        self.assertTrue(take_res["success"])
        self.assertEqual(take_res["delivery_fee"], "Rs. 0.00")
        self.assertEqual(take_res["total"], "Rs. 650.00")
        take_order = Order.objects.get(order_number=take_res["order_number"])
        self.assertEqual(take_order.delivery_fee, Decimal("0.00"))
        self.assertEqual(take_order.total, Decimal("650.00"))


class RestaurantInventoryAndRecipesTests(TestCase):
    """Tests for Restaurant Ingredient Inventory, Dish Recipes, Auto-Deduction, Restore & AI Out-of-Stock."""

    def setUp(self):
        self.client = APIClient()
        self.company_a = Company.objects.create(
            name="Burger Lab A",
            business_type="restaurant",
            status="active",
            is_approved=True,
            subscription_status="active",
        )
        self.company_b = Company.objects.create(
            name="Other Kitchen B",
            business_type="restaurant",
            status="active",
            is_approved=True,
            subscription_status="active",
        )
        self.owner_a = User.objects.create_user(
            username="inv_owner_a",
            email="owner_a@burgerlab.test",
            password="Password123!",
            company=self.company_a,
            role=User.ROLE_OWNER,
        )
        self.owner_b = User.objects.create_user(
            username="inv_owner_b",
            email="owner_b@otherkitchen.test",
            password="Password123!",
            company=self.company_b,
            role=User.ROLE_OWNER,
        )

    def test_ingredients_recipes_auto_deduction_cancel_restore_ai_oos_and_tenant_isolation(self):
        from companies.models import CatalogItem
        from operations.models import IngredientStockMovement, RestaurantIngredient
        from operations.whatsapp_agent import (
            _build_system_prompt,
            execute_get_catalog_items,
            get_business_context_for_company,
        )

        self.client.force_authenticate(user=self.owner_a)

        dish = CatalogItem.objects.create(
            company=self.company_a,
            name="Zinger Burger",
            price=Decimal("650.00"),
            is_available=True,
        )

        # 1. Create ingredients
        ing_res1 = self.client.post(
            "/api/operations/restaurant/inventory/",
            {
                "name": "Chicken Fillet",
                "unit": "pcs",
                "current_stock": 10,
                "low_stock_threshold": 5,
                "cost_per_unit": 180,
                "supplier_name": "Fresh Poultry",
            },
            format="json",
        )
        self.assertEqual(ing_res1.status_code, 201)
        fillet_id = ing_res1.data["id"]

        ing_res2 = self.client.post(
            "/api/operations/restaurant/inventory/",
            {
                "name": "Burger Bun",
                "unit": "pcs",
                "current_stock": 2,
                "low_stock_threshold": 5,
                "cost_per_unit": 40,
            },
            format="json",
        )
        self.assertEqual(ing_res2.status_code, 201)
        bun_id = ing_res2.data["id"]

        # 2. Map dish recipe: 1 Zinger Burger requires 1 Chicken Fillet + 1 Burger Bun
        rec_res = self.client.put(
            f"/api/operations/restaurant/recipes/{dish.id}/",
            {
                "ingredients": [
                    {"ingredient_id": fillet_id, "quantity_required": 1},
                    {"ingredient_id": bun_id, "quantity_required": 1},
                ]
            },
            format="json",
        )
        self.assertEqual(rec_res.status_code, 200)
        self.assertEqual(len(rec_res.data["ingredients"]), 2)

        # 3. Place an order for 2 Zinger Burgers -> auto-deducts 2 Fillets (10->8) and 2 Buns (2->0)
        ord_res = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "takeaway",
                "customer_name": "Bilal",
                "items": [{"item_id": dish.id, "quantity": 2}],
            },
            format="json",
        )
        self.assertEqual(ord_res.status_code, 201)
        order_id = ord_res.data["id"]

        fillet = RestaurantIngredient.objects.get(pk=fillet_id)
        bun = RestaurantIngredient.objects.get(pk=bun_id)
        self.assertEqual(fillet.current_stock, Decimal("8.000"))
        self.assertEqual(bun.current_stock, Decimal("0.000"))
        self.assertEqual(bun.stock_status, "out_of_stock")

        # 4. AI Agent Out-of-Stock awareness: Bun is at 0 -> Zinger Burger marked [OUT OF STOCK]
        ctx = get_business_context_for_company(self.company_a)
        prompt = _build_system_prompt("Guest", ctx)
        self.assertIn("Zinger Burger [OUT OF STOCK]", prompt)

        ai_cat = execute_get_catalog_items(self.company_a, search_query="Zinger")
        self.assertTrue(ai_cat["success"])
        self.assertFalse(ai_cat["items"][0]["in_stock"])
        self.assertIn("[OUT OF STOCK]", ai_cat["items"][0]["name"])

        # Executive dashboard low_stock_items_count picks up out-of-stock Bun
        dash_res = self.client.get("/api/operations/restaurant/dashboard-summary/?period=today")
        self.assertEqual(dash_res.status_code, 200)
        self.assertGreaterEqual(dash_res.data["alerts"]["low_stock_items_count"], 1)

        # 5. Cancel the order -> restores 2 Fillets (8->10) and 2 Buns (0->2)
        cancel_res = self.client.patch(
            f"/api/operations/orders/{order_id}/status/",
            {"status": "cancelled"},
            format="json",
        )
        self.assertEqual(cancel_res.status_code, 200)

        fillet.refresh_from_db()
        bun.refresh_from_db()
        self.assertEqual(fillet.current_stock, Decimal("10.000"))
        self.assertEqual(bun.current_stock, Decimal("2.000"))
        self.assertTrue(
            IngredientStockMovement.objects.filter(
                company=self.company_a,
                order_id=order_id,
                movement_type=IngredientStockMovement.MOVEMENT_ORDER_CANCEL_RESTORE,
            ).exists()
        )

        # 6. Manual restock & waste adjustments + movement history
        restock_res = self.client.post(
            f"/api/operations/restaurant/inventory/{bun_id}/adjust/",
            {"movement_type": "restock", "quantity": 10, "reason": "Morning bakery delivery"},
            format="json",
        )
        self.assertEqual(restock_res.status_code, 200)
        self.assertEqual(restock_res.data["ingredient"]["current_stock"], 12.0)

        waste_res = self.client.post(
            f"/api/operations/restaurant/inventory/{bun_id}/adjust/",
            {"movement_type": "waste", "quantity": 2, "reason": "Crushed buns"},
            format="json",
        )
        self.assertEqual(waste_res.status_code, 200)
        self.assertEqual(waste_res.data["ingredient"]["current_stock"], 10.0)

        mov_res = self.client.get(f"/api/operations/restaurant/inventory/{bun_id}/movements/")
        self.assertEqual(mov_res.status_code, 200)
        self.assertGreaterEqual(len(mov_res.data), 4)

        # 7. Strict Multi-Tenant Isolation
        self.client.force_authenticate(user=self.owner_b)
        list_b = self.client.get("/api/operations/restaurant/inventory/")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(list_b.data["ingredients"], [])

        cross_adj = self.client.post(
            f"/api/operations/restaurant/inventory/{bun_id}/adjust/",
            {"movement_type": "waste", "quantity": 5},
            format="json",
        )
        self.assertEqual(cross_adj.status_code, 404)


class RestaurantDeliveriesAndCODTests(TestCase):
    """Module 5: Restaurant Deliveries, Live Rider Dispatch & COD Reconciliation tests."""

    def setUp(self):
        from companies.models import Company
        from accounts.models import User, StaffRole
        from operations.models import Order, OrderItem

        self.company = Company.objects.create(
            name="Biryani Dispatch Kitchen",
            business_type="restaurant",
            subscription_status="active",
        )
        self.other_company = Company.objects.create(
            name="Other Tenant Bistro",
            business_type="restaurant",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="dispatch_owner",
            email="dispatch_owner@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.company,
            is_active=True,
        )
        self.other_owner = User.objects.create_user(
            username="other_dispatch_owner",
            email="other_dispatch_owner@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.other_company,
            is_active=True,
        )

        rider_role = StaffRole.objects.create(
            company=self.company,
            name="Rider",
            is_active=True,
            permissions=["deliveries.view_assigned", "deliveries.update_status"],
        )
        self.rider_a = User.objects.create_user(
            username="rider_ali",
            first_name="Ali",
            last_name="Rider",
            email="rider_ali@test.com",
            password="pass",
            role=User.ROLE_STAFF,
            company=self.company,
            staff_role=rider_role,
            is_active=True,
        )
        self.rider_b = User.objects.create_user(
            username="rider_bilal",
            first_name="Bilal",
            last_name="Express",
            email="rider_bilal@test.com",
            password="pass",
            role=User.ROLE_STAFF,
            company=self.company,
            staff_role=rider_role,
            is_active=True,
        )

        self.delivery_order_1 = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="Hassan",
            customer_phone="+923001111111",
            delivery_address="House 12, Block B, DHA",
            status=Order.STATUS_CONFIRMED,
            subtotal=Decimal("1200.00"),
            delivery_fee=Decimal("150.00"),
            total=Decimal("1350.00"),
        )
        OrderItem.objects.create(
            order=self.delivery_order_1,
            item_name="Chicken Biryani",
            quantity=2,
            unit_price=Decimal("600.00"),
            line_total=Decimal("1200.00"),
        )

        self.delivery_order_2 = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="Sana",
            customer_phone="+923002222222",
            delivery_address="Flat 4A, Gulberg III",
            status=Order.STATUS_CONFIRMED,
            subtotal=Decimal("850.00"),
            delivery_fee=Decimal("150.00"),
            total=Decimal("1000.00"),
        )

        # Dine-in order should NEVER appear on the delivery dispatch board
        self.dine_in_order = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DINE_IN,
            customer_name="Walk-in Guest",
            status=Order.STATUS_CONFIRMED,
            subtotal=Decimal("500.00"),
            total=Decimal("500.00"),
        )

        # Other tenant's delivery order must remain strictly isolated
        self.other_delivery = Order.objects.create(
            company=self.other_company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="External Customer",
            delivery_address="Other City",
            status=Order.STATUS_READY,
            total=Decimal("999.00"),
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_board_filters_only_tenant_delivery_orders_and_lists_riders(self):
        res = self.client.get("/api/operations/restaurant/deliveries/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        order_ids = {o["id"] for o in data["orders"]}
        self.assertIn(self.delivery_order_1.id, order_ids)
        self.assertIn(self.delivery_order_2.id, order_ids)
        self.assertNotIn(self.dine_in_order.id, order_ids)
        self.assertNotIn(self.other_delivery.id, order_ids)
        self.assertEqual(data["kpis"]["pending_dispatch"], 2)
        rider_ids = {r["id"] for r in data["riders"]}
        self.assertEqual(rider_ids, {self.rider_a.id, self.rider_b.id})

    def test_rider_assign_lifecycle_and_cod_settlement(self):
        from operations.models import DeliveryAssignment, Order

        # 1. Manual assign order 1 to rider_a
        res = self.client.post(
            f"/api/operations/restaurant/deliveries/{self.delivery_order_1.id}/assign/",
            {"rider_id": self.rider_a.id},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.delivery_order_1.refresh_from_db()
        self.assertEqual(self.delivery_order_1.assigned_rider_id, self.rider_a.id)
        self.assertEqual(self.delivery_order_1.status, Order.STATUS_ASSIGNED)
        self.assertTrue(
            DeliveryAssignment.objects.filter(
                order=self.delivery_order_1, rider=self.rider_a
            ).exists()
        )

        # 2. Auto-assign order 2 -> should pick least-busy rider_b
        res_auto = self.client.post(
            f"/api/operations/restaurant/deliveries/{self.delivery_order_2.id}/assign/",
            {"auto": True},
            format="json",
        )
        self.assertEqual(res_auto.status_code, 200)
        self.delivery_order_2.refresh_from_db()
        self.assertEqual(self.delivery_order_2.assigned_rider_id, self.rider_b.id)

        # 3. Transition order 1 to out_for_delivery -> sets dispatched_at
        res_out = self.client.post(
            f"/api/operations/restaurant/deliveries/{self.delivery_order_1.id}/status/",
            {"status": "out_for_delivery"},
            format="json",
        )
        self.assertEqual(res_out.status_code, 200)
        self.delivery_order_1.refresh_from_db()
        self.assertEqual(self.delivery_order_1.status, Order.STATUS_OUT_FOR_DELIVERY)
        self.assertIsNotNone(self.delivery_order_1.dispatched_at)

        # 4. Transition order 1 to delivered -> sets delivered_at & cod_collected=True
        res_del = self.client.post(
            f"/api/operations/restaurant/deliveries/{self.delivery_order_1.id}/status/",
            {"status": "delivered"},
            format="json",
        )
        self.assertEqual(res_del.status_code, 200)
        self.delivery_order_1.refresh_from_db()
        self.assertEqual(self.delivery_order_1.status, Order.STATUS_DELIVERED)
        self.assertIsNotNone(self.delivery_order_1.delivered_at)
        self.assertTrue(self.delivery_order_1.cod_collected)
        self.assertFalse(self.delivery_order_1.cod_settled)

        # 5. Board reflects Rs. 1350 unsettled COD for rider_a
        board_before = self.client.get("/api/operations/restaurant/deliveries/").json()
        self.assertEqual(board_before["kpis"]["unsettled_cod_total"], 1350.0)
        rider_a_row = next(r for r in board_before["riders"] if r["id"] == self.rider_a.id)
        self.assertEqual(rider_a_row["unsettled_cod_count"], 1)
        self.assertEqual(rider_a_row["unsettled_cod_total"], 1350.0)

        # 6. Settle COD for rider_a -> clears balance & sets cod_settled_at
        res_settle = self.client.post(
            "/api/operations/restaurant/deliveries/settle-cod/",
            {"rider_id": self.rider_a.id},
            format="json",
        )
        self.assertEqual(res_settle.status_code, 200)
        self.assertEqual(res_settle.json()["settled_count"], 1)
        self.assertEqual(res_settle.json()["settled_amount"], 1350.0)

        self.delivery_order_1.refresh_from_db()
        self.assertTrue(self.delivery_order_1.cod_settled)
        self.assertIsNotNone(self.delivery_order_1.cod_settled_at)

        board_after = self.client.get("/api/operations/restaurant/deliveries/").json()
        self.assertEqual(board_after["kpis"]["unsettled_cod_total"], 0.0)

    def test_multi_tenant_isolation_blocks_cross_company_mutations(self):
        # Other company cannot assign or update our delivery order
        other_client = APIClient()
        other_client.force_authenticate(user=self.other_owner)

        res_assign = other_client.post(
            f"/api/operations/restaurant/deliveries/{self.delivery_order_1.id}/assign/",
            {"auto": True},
            format="json",
        )
        self.assertEqual(res_assign.status_code, 404)

        res_status = other_client.post(
            f"/api/operations/restaurant/deliveries/{self.delivery_order_1.id}/status/",
            {"status": "delivered"},
            format="json",
        )
        self.assertEqual(res_status.status_code, 404)

        res_settle = other_client.post(
            "/api/operations/restaurant/deliveries/settle-cod/",
            {"rider_id": self.rider_a.id},
            format="json",
        )
        self.assertEqual(res_settle.status_code, 404)

    def test_manual_rider_reassignment_overwrites_previous_rider(self):
        from operations.models import DeliveryAssignment

        # Assign order 1 to rider_a first
        res1 = self.client.post(
            f"/api/operations/restaurant/deliveries/{self.delivery_order_1.id}/assign/",
            {"rider_id": self.rider_a.id, "auto": False},
            format="json",
        )
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["assigned_rider_id"], self.rider_a.id)

        # Reassign order 1 to rider_b
        res2 = self.client.post(
            f"/api/operations/restaurant/deliveries/{self.delivery_order_1.id}/assign/",
            {"rider_id": self.rider_b.id, "auto": False},
            format="json",
        )
        self.assertEqual(res2.status_code, 200)
        payload = res2.json()
        self.assertEqual(payload["assigned_rider_id"], self.rider_b.id)
        self.assertEqual(payload["assigned_rider_name"], "Bilal Express")
        self.assertEqual(payload["order"]["assigned_rider_id"], self.rider_b.id)

        # Verify DB & DeliveryAssignment overwritten
        self.delivery_order_1.refresh_from_db()
        self.assertEqual(self.delivery_order_1.assigned_rider_id, self.rider_b.id)
        assignment = DeliveryAssignment.objects.get(order=self.delivery_order_1)
        self.assertEqual(assignment.rider_id, self.rider_b.id)

        # Confirm GET /api/operations/restaurant/deliveries/ returns rider_b
        board = self.client.get("/api/operations/restaurant/deliveries/").json()
        order_row = next(o for o in board["orders"] if o["id"] == self.delivery_order_1.id)
        self.assertEqual(order_row["assigned_rider_id"], self.rider_b.id)
        self.assertEqual(order_row["assigned_rider_name"], "Bilal Express")

    def test_smart_fairness_tie_breaker_picks_rider_with_fewer_daily_deliveries(self):
        from django.utils import timezone
        from operations.models import Order
        from operations.restaurant_delivery_views import select_best_available_rider

        # Both rider_a and rider_b have 0 active orders,
        # but rider_a has 2 completed (delivered) orders today and rider_b has 0.
        now_ts = timezone.now()
        for idx in range(2):
            Order.objects.create(
                company=self.company,
                order_type=Order.ORDER_TYPE_DELIVERY,
                customer_name=f"Delivered Guest {idx}",
                delivery_address="DHA Phase 5",
                status=Order.STATUS_DELIVERED,
                assigned_rider=self.rider_a,
                delivered_at=now_ts,
                cod_collected=True,
                total=Decimal("900.00"),
            )

        chosen = select_best_available_rider(self.company)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.id, self.rider_b.id)

    def test_auto_dispatch_toggle_on_pos_and_ai_delivery_order_creation(self):
        from companies.models import CatalogCategory, CatalogItem
        from operations.models import Order
        from operations.views import _create_order
        from operations.whatsapp_agent import execute_create_order

        cat = CatalogCategory.objects.create(company=self.company, name="Burgers")
        burger = CatalogItem.objects.create(
            company=self.company,
            category=cat,
            name="Zinger Burger",
            price=Decimal("650.00"),
            is_available=True,
        )

        # 1. Verify board returns auto_dispatch_enabled=True by default
        board = self.client.get("/api/operations/restaurant/deliveries/").json()
        self.assertTrue(board["auto_dispatch_enabled"])

        # 2. POS delivery order with auto_dispatch_enabled=True -> auto-assigns rider_a
        pos_order_on = _create_order(
            self.company,
            {
                "order_type": "delivery",
                "customer_name": "POS Customer On",
                "customer_phone": "+923009990001",
                "delivery_address": "Model Town, Lahore",
                "items": [{"item_id": burger.id, "quantity": 1}],
            },
            actor=self.owner,
            source="dashboard",
        )
        pos_order_on.refresh_from_db()
        self.assertEqual(pos_order_on.assigned_rider_id, self.rider_a.id)

        # 3. AI delivery order with auto_dispatch_enabled=True -> auto-assigns least-busy rider_b
        ai_res_on = execute_create_order(
            company=self.company,
            customer_name="AI Customer On",
            customer_phone="+923009990002",
            delivery_address="Johar Town, Lahore",
            items=[{"item_name": "Zinger Burger", "quantity": 1}],
            order_type="delivery",
        )
        self.assertTrue(ai_res_on["success"])
        self.assertEqual(ai_res_on.get("assigned_rider_name"), "Bilal Express")
        ai_order_on = Order.objects.get(order_number=ai_res_on["order_number"])
        self.assertEqual(ai_order_on.assigned_rider_id, self.rider_b.id)

        # 4. Toggle Smart Auto-Dispatch OFF via PATCH /api/operations/restaurant/deliveries/settings/
        toggle_res = self.client.patch(
            "/api/operations/restaurant/deliveries/settings/",
            {"auto_dispatch_enabled": False},
            format="json",
        )
        self.assertEqual(toggle_res.status_code, 200)
        self.assertFalse(toggle_res.json()["auto_dispatch_enabled"])
        self.company.refresh_from_db()
        self.assertFalse(self.company.auto_dispatch_enabled)

        # 5. POS delivery order with auto_dispatch_enabled=False -> remains unassigned
        pos_order_off = _create_order(
            self.company,
            {
                "order_type": "delivery",
                "customer_name": "POS Customer Off",
                "customer_phone": "+923009990003",
                "delivery_address": "Gulberg II, Lahore",
                "items": [{"item_id": burger.id, "quantity": 1}],
            },
            actor=self.owner,
            source="dashboard",
        )
        pos_order_off.refresh_from_db()
        self.assertIsNone(pos_order_off.assigned_rider_id)

        # 6. AI delivery order with auto_dispatch_enabled=False -> remains unassigned
        ai_res_off = execute_create_order(
            company=self.company,
            customer_name="AI Customer Off",
            customer_phone="+923009990004",
            delivery_address="Bahria Town, Lahore",
            items=[{"item_name": "Zinger Burger", "quantity": 1}],
            order_type="delivery",
        )
        self.assertTrue(ai_res_off["success"])
        self.assertNotIn("assigned_rider_name", ai_res_off)
        ai_order_off = Order.objects.get(order_number=ai_res_off["order_number"])
        self.assertIsNone(ai_order_off.assigned_rider_id)


class RestaurantCustomersCRMTests(TestCase):
    """Module 6: Restaurant Customers CRM, Guest Profiles, Segmentation & AI Personalization."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from companies.models import Company
        from accounts.models import User
        from operations.models import Order, OrderItem, TableReservation

        self.company = Company.objects.create(
            name="Spice Route Grill",
            business_type="restaurant",
            subscription_status="active",
        )
        self.other_company = Company.objects.create(
            name="Other Bistro",
            business_type="restaurant",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="crm_owner",
            email="crm_owner@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.company,
            is_active=True,
        )
        self.other_owner = User.objects.create_user(
            username="crm_other_owner",
            email="crm_other_owner@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.other_company,
            is_active=True,
        )

        # 1. VIP guest (spend >= 5000 across 2 orders, favorite dish: Mutton Karahi)
        o_vip_1 = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="Zainab Khan",
            customer_phone="+923001112222",
            status=Order.STATUS_DELIVERED,
            total=Decimal("3200.00"),
        )
        OrderItem.objects.create(
            order=o_vip_1, item_name="Mutton Karahi", quantity=2,
            unit_price=Decimal("1600.00"), line_total=Decimal("3200.00"),
        )
        o_vip_2 = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="Zainab Khan",
            customer_phone="03001112222",  # variant format normalizes to same guest
            status=Order.STATUS_DELIVERED,
            total=Decimal("2400.00"),
        )
        OrderItem.objects.create(
            order=o_vip_2, item_name="Mutton Karahi", quantity=1,
            unit_price=Decimal("1600.00"), line_total=Decimal("1600.00"),
        )
        OrderItem.objects.create(
            order=o_vip_2, item_name="Garlic Naan", quantity=2,
            unit_price=Decimal("400.00"), line_total=Decimal("800.00"),
        )

        # 2. Repeat guest (2 orders, spend < 5000, recent)
        for _ in range(2):
            o_rep = Order.objects.create(
                company=self.company,
                order_type=Order.ORDER_TYPE_TAKEAWAY,
                customer_name="Usman Tariq",
                customer_phone="+923003334444",
                status=Order.STATUS_DELIVERED,
                total=Decimal("900.00"),
            )
            OrderItem.objects.create(
                order=o_rep, item_name="Zinger Burger", quantity=1,
                unit_price=Decimal("900.00"), line_total=Decimal("900.00"),
            )

        # 3. New guest (1 recent order)
        o_new = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DINE_IN,
            customer_name="Ayesha Ali",
            customer_phone="+923005556666",
            status=Order.STATUS_DELIVERED,
            total=Decimal("1200.00"),
        )
        OrderItem.objects.create(
            order=o_new, item_name="Chicken Tikka", quantity=1,
            unit_price=Decimal("1200.00"), line_total=Decimal("1200.00"),
        )

        # 4. At-Risk guest (1 order older than 30 days)
        o_risk = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="Hamza Raza",
            customer_phone="+923007778888",
            status=Order.STATUS_DELIVERED,
            total=Decimal("1500.00"),
        )
        old_ts = timezone.now() - timedelta(days=45)
        Order.objects.filter(pk=o_risk.pk).update(created_at=old_ts)
        OrderItem.objects.create(
            order=o_risk, item_name="Beef Pulao", quantity=1,
            unit_price=Decimal("1500.00"), line_total=Decimal("1500.00"),
        )

        # Reservation for VIP guest
        now_dt = timezone.now()
        TableReservation.objects.create(
            company=self.company,
            customer_name="Zainab Khan",
            customer_phone="+923001112222",
            party_size=4,
            reservation_date=now_dt.date(),
            reservation_time=now_dt.time(),
            reserved_at=now_dt,
            status=TableReservation.STATUS_CONFIRMED,
        )

        # Other tenant guest (must stay strictly isolated)
        Order.objects.create(
            company=self.other_company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="External Guest",
            customer_phone="+923009999999",
            status=Order.STATUS_DELIVERED,
            total=Decimal("9999.00"),
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_customers_list_aggregates_spend_favorite_dish_and_segments(self):
        res = self.client.get("/api/operations/restaurant/customers/")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["kpis"]["total_guests"], 4)
        self.assertEqual(data["kpis"]["vip_count"], 1)
        self.assertEqual(data["kpis"]["repeat_count"], 1)
        self.assertEqual(data["kpis"]["new_count"], 1)
        self.assertEqual(data["kpis"]["at_risk_count"], 1)

        by_phone = {c["phone"]: c for c in data["customers"]}
        self.assertNotIn("923009999999", by_phone)

        vip = by_phone["923001112222"]
        self.assertEqual(vip["segment"], "vip")
        self.assertEqual(vip["total_orders"], 2)
        self.assertEqual(vip["total_spend"], 5600.0)
        self.assertEqual(vip["favorite_dish"], "Mutton Karahi")
        self.assertEqual(vip["reservations_count"], 1)

        self.assertEqual(by_phone["923003334444"]["segment"], "repeat")
        self.assertEqual(by_phone["923005556666"]["segment"], "new")
        self.assertEqual(by_phone["923007778888"]["segment"], "at_risk")

        # Filter by segment=at_risk
        risk_res = self.client.get("/api/operations/restaurant/customers/?segment=at_risk").json()
        self.assertEqual(len(risk_res["customers"]), 1)
        self.assertEqual(risk_res["customers"][0]["name"], "Hamza Raza")

    def test_patch_profile_and_whatsapp_ai_returning_guest_prompt(self):
        from operations.whatsapp_agent import _build_system_prompt, get_business_context_for_company

        # Save dietary notes & VIP override for Ayesha (currently 'new')
        patch_res = self.client.patch(
            "/api/operations/restaurant/customers/923005556666/",
            {
                "dietary_notes": "No onions, extra spicy",
                "is_vip_override": True,
                "tags": ["Spice Lover"],
            },
            format="json",
        )
        self.assertEqual(patch_res.status_code, 200)
        detail = patch_res.json()
        self.assertEqual(detail["dietary_notes"], "No onions, extra spicy")
        self.assertTrue(detail["is_vip_override"])
        self.assertEqual(detail["segment"], "vip")

        # Verify WhatsApp AI system prompt injects favorite dish & saved dietary notes
        ctx = get_business_context_for_company(self.company)
        prompt = _build_system_prompt(
            customer_name="Ayesha Ali",
            context=ctx,
            sender_phone="+923005556666",
        )
        self.assertIn("RETURNING GUEST CONTEXT", prompt)
        self.assertIn("Chicken Tikka", prompt)
        self.assertIn("No onions, extra spicy", prompt)
        self.assertIn("VIP Guest", prompt)

    def test_multi_tenant_isolation_on_customer_detail(self):
        other_client = APIClient()
        other_client.force_authenticate(user=self.other_owner)

        # Other tenant cannot view Spice Route Grill's VIP guest
        res = other_client.get("/api/operations/restaurant/customers/923001112222/")
        self.assertEqual(res.status_code, 404)

        # Other tenant's list only contains its own guest
        list_res = other_client.get("/api/operations/restaurant/customers/").json()
        self.assertEqual(list_res["kpis"]["total_guests"], 1)
        self.assertEqual(list_res["customers"][0]["phone"], "923009999999")

    def test_execute_lookup_guest_profile_tool_and_tenant_isolation(self):
        from operations.whatsapp_agent import (
            CATEGORY_AGENT_PROFILES,
            _build_system_prompt,
            execute_lookup_guest_profile,
            get_business_context_for_company,
        )

        # Tool is registered for restaurant vertical
        rest_tool_names = [
            t["function"]["name"] for t in CATEGORY_AGENT_PROFILES["restaurant"]["tools"]
        ]
        self.assertIn("lookup_guest_profile", rest_tool_names)

        # Save dietary notes for VIP guest Zainab
        self.client.patch(
            "/api/operations/restaurant/customers/923001112222/",
            {"dietary_notes": "Less oil, extra raita"},
            format="json",
        )

        # Lookup with variant local format (0300...) returns full profile
        res = execute_lookup_guest_profile(self.company, "03001112222")
        self.assertTrue(res["found"])
        self.assertEqual(res["name"], "Zainab Khan")
        self.assertTrue(res["is_vip"])
        self.assertEqual(res["total_orders"], 2)
        self.assertEqual(res["favorite_dish"], "Mutton Karahi")
        self.assertEqual(res["dietary_notes"], "Less oil, extra raita")
        self.assertEqual(res["preferred_order_type"], "delivery")

        # Lookup for another tenant's guest returns found=False (strict isolation)
        cross = execute_lookup_guest_profile(self.company, "+923009999999")
        self.assertFalse(cross["found"])
        self.assertEqual(cross["total_orders"], 0)

        # Anonymous website voice prompt includes lookup_guest_profile instruction
        ctx = get_business_context_for_company(self.company)
        anon_prompt = _build_system_prompt(
            customer_name="Valued Customer",
            context=ctx,
            sender_phone="",
        )
        self.assertIn("lookup_guest_profile(phone)", anon_prompt)

    def test_prefilled_public_voice_customer_details_and_crm_context_in_prompt(self):
        from operations.whatsapp_agent import _build_system_prompt, get_business_context_for_company

        # Save dietary notes for returning guest Zainab
        self.client.patch(
            "/api/operations/restaurant/customers/923001112222/",
            {"dietary_notes": "No onions, extra mint chutney"},
            format="json",
        )

        ctx = get_business_context_for_company(self.company)
        ctx["customer_phone"] = "+923001112222"
        ctx["customer_address"] = "House 14, Block C, Model Town, Lahore"

        prompt = _build_system_prompt(
            customer_name="Zainab Khan",
            context=ctx,
            is_voice_note=True,
            sender_phone="+923001112222",
            customer_address="House 14, Block C, Model Town, Lahore",
        )

        # Pre-filled details block & explicit DO NOT re-ask instruction
        self.assertIn("PRE-FILLED CUSTOMER DETAILS (ALREADY VERIFIED)", prompt)
        self.assertIn("Customer Name: Zainab Khan", prompt)
        self.assertIn("Customer Phone: +923001112222", prompt)
        self.assertIn("Delivery Address: House 14, Block C, Model Town, Lahore", prompt)
        self.assertIn("DO NOT ask again for their name, phone number, or address", prompt)

        # Returning guest CRM context automatically injected on turn 1
        self.assertIn("RETURNING GUEST CONTEXT (PERSONALIZATION)", prompt)
        self.assertIn("Mutton Karahi", prompt)
        self.assertIn("No onions, extra mint chutney", prompt)

    def test_auto_attach_guest_dietary_notes_to_order_kitchen_notes(self):
        from companies.models import CatalogCategory, CatalogItem
        from operations.models import Order
        from operations.views import _create_order
        from operations.whatsapp_agent import execute_create_order
        from operations.printing.receipt_formatter import build_receipt_payload

        cat = CatalogCategory.objects.create(company=self.company, name="Mains")
        dish = CatalogItem.objects.create(
            company=self.company,
            category=cat,
            name="Chicken Handi",
            price=Decimal("1100.00"),
            is_available=True,
        )

        # Save dietary notes on guest profile
        self.client.patch(
            "/api/operations/restaurant/customers/923001112222/",
            {"dietary_notes": "Extra spicy, no onions"},
            format="json",
        )

        # 1. AI order created WITHOUT explicit notes -> auto-attaches dietary_notes
        ai_res = execute_create_order(
            company=self.company,
            customer_name="Zainab Khan",
            customer_phone="03001112222",
            delivery_address="DHA Phase 5, Lahore",
            items=[{"item_name": "Chicken Handi", "quantity": 1}],
            notes="",
            order_type="delivery",
        )
        self.assertTrue(ai_res["success"])
        ai_order = Order.objects.get(order_number=ai_res["order_number"])
        self.assertIn("Extra spicy, no onions", ai_order.notes)

        # Verify KOT receipt payload renders the attached notes
        kot_payload = build_receipt_payload(ai_order, slip_type="kot")
        self.assertTrue(kot_payload["order"]["has_notes"])
        self.assertIn("Extra spicy, no onions", kot_payload["order"]["notes"])

        # 2. POS order created with separate delivery note -> merges cleanly without losing either
        pos_order = _create_order(
            self.company,
            {
                "order_type": "delivery",
                "customer_name": "Zainab Khan",
                "customer_phone": "+923001112222",
                "delivery_address": "DHA Phase 5, Lahore",
                "notes": "Ring bell twice",
                "items": [{"item_id": dish.id, "quantity": 1}],
            },
            actor=self.owner,
            source="dashboard",
        )
        self.assertIn("Ring bell twice", pos_order.notes)
        self.assertIn("Extra spicy, no onions", pos_order.notes)


class RestaurantReportsAnalyticsTests(TestCase):
    """Module 7: Restaurant Reports, Recipe-Based Profitability & CSV Export tests."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from companies.models import CatalogCategory, CatalogItem, Company
        from accounts.models import User
        from operations.models import MenuItemRecipe, Order, OrderItem, RestaurantIngredient

        self.company = Company.objects.create(
            name="Royal Karahi House",
            business_type="restaurant",
            subscription_status="active",
        )
        self.other_company = Company.objects.create(
            name="Other Cafe",
            business_type="restaurant",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="reports_owner",
            email="reports_owner@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.company,
            is_active=True,
        )
        self.other_owner = User.objects.create_user(
            username="reports_other_owner",
            email="reports_other_owner@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.other_company,
            is_active=True,
        )

        # Menu items + Ingredient + Recipe (Zinger Burger COGS = 2 * 100 = Rs. 200 per unit)
        cat = CatalogCategory.objects.create(company=self.company, name="Burgers")
        self.burger = CatalogItem.objects.create(
            company=self.company,
            category=cat,
            name="Zinger Burger",
            price=Decimal("600.00"),
            is_available=True,
        )
        self.drink = CatalogItem.objects.create(
            company=self.company,
            category=cat,
            name="Mint Margarita",
            price=Decimal("250.00"),
            is_available=True,
        )
        chicken = RestaurantIngredient.objects.create(
            company=self.company,
            name="Chicken Fillet",
            unit="pcs",
            current_stock=Decimal("50"),
            cost_per_unit=Decimal("100.00"),
        )
        MenuItemRecipe.objects.create(
            company=self.company,
            catalog_item=self.burger,
            ingredient=chicken,
            quantity_required=Decimal("2.000"),
        )

        # 1. Today POS Delivery order: 2 Burgers (1200) + 150 delivery fee = 1350; COGS = 400
        self.order_today_pos = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="Ali",
            status=Order.STATUS_DELIVERED,
            source="dashboard",
            subtotal=Decimal("1200.00"),
            delivery_fee=Decimal("150.00"),
            total=Decimal("1350.00"),
            cod_collected=True,
            cod_settled=False,
        )
        OrderItem.objects.create(
            order=self.order_today_pos,
            item=self.burger,
            item_name="Zinger Burger",
            quantity=Decimal("2"),
            unit_price=Decimal("600.00"),
            line_total=Decimal("1200.00"),
        )

        # 2. Today WhatsApp AI Dine-in order: 2 Mint Margaritas (no recipe -> COGS 0) = 500
        self.order_today_ai = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DINE_IN,
            customer_name="Sara",
            status=Order.STATUS_CONFIRMED,
            source="agent",
            subtotal=Decimal("500.00"),
            delivery_fee=Decimal("0.00"),
            total=Decimal("500.00"),
        )
        OrderItem.objects.create(
            order=self.order_today_ai,
            item=self.drink,
            item_name="Mint Margarita",
            quantity=Decimal("2"),
            unit_price=Decimal("250.00"),
            line_total=Decimal("500.00"),
        )

        # 3. Cancelled order today -> must be EXCLUDED from net_revenue & COGS
        self.order_cancelled = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="Cancelled Guest",
            status=Order.STATUS_CANCELLED,
            source="dashboard",
            subtotal=Decimal("600.00"),
            total=Decimal("600.00"),
        )
        OrderItem.objects.create(
            order=self.order_cancelled,
            item=self.burger,
            item_name="Zinger Burger",
            quantity=Decimal("1"),
            unit_price=Decimal("600.00"),
            line_total=Decimal("600.00"),
        )

        # 4. Historical order (20 days ago, takeaway, Website Voice AI)
        self.order_old = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_TAKEAWAY,
            customer_name="Old Guest",
            status=Order.STATUS_DELIVERED,
            source="api",
            subtotal=Decimal("600.00"),
            total=Decimal("600.00"),
        )
        Order.objects.filter(pk=self.order_old.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )
        OrderItem.objects.create(
            order=self.order_old,
            item=self.burger,
            item_name="Zinger Burger",
            quantity=Decimal("1"),
            unit_price=Decimal("600.00"),
            line_total=Decimal("600.00"),
        )

        # 5. Other tenant's order (must remain isolated)
        Order.objects.create(
            company=self.other_company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="External",
            status=Order.STATUS_DELIVERED,
            total=Decimal("9999.00"),
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_reports_revenue_cogs_profit_and_breakdowns(self):
        # All-time report
        res = self.client.get("/api/operations/restaurant/reports/?range=all")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        kpis = data["kpis"]

        # Net revenue = 1350 + 500 + 600 = 2450 (excludes 600 cancelled & 9999 other company)
        self.assertEqual(kpis["net_revenue"], 2450.0)
        self.assertEqual(kpis["total_orders"], 3)
        self.assertEqual(kpis["cancelled_orders"], 1)
        self.assertEqual(kpis["delivery_fees_total"], 150.0)
        # COGS = 2 burgers (400) + 1 old burger (200) + 2 drinks (0) = 600
        self.assertEqual(kpis["estimated_cogs"], 600.0)
        self.assertEqual(kpis["gross_profit"], 1850.0)
        self.assertEqual(kpis["unsettled_cod_total"], 1350.0)

        # Order type split
        ot_map = {r["key"]: r for r in data["order_type_breakdown"]}
        self.assertEqual(ot_map["delivery"]["orders"], 1)
        self.assertEqual(ot_map["dine_in"]["orders"], 1)
        self.assertEqual(ot_map["takeaway"]["orders"], 1)

        # Channel split
        ch_map = {r["channel"]: r for r in data["channel_breakdown"]}
        self.assertEqual(ch_map["POS"]["orders"], 1)
        self.assertEqual(ch_map["WhatsApp AI"]["orders"], 1)
        self.assertEqual(ch_map["Website Voice AI"]["orders"], 1)

        # Top dishes margin table
        burger_row = next(d for d in data["top_dishes"] if d["dish_name"] == "Zinger Burger")
        self.assertEqual(burger_row["qty_sold"], 3.0)
        self.assertEqual(burger_row["revenue"], 1800.0)
        self.assertEqual(burger_row["estimated_cogs"], 600.0)
        self.assertEqual(burger_row["gross_profit"], 1200.0)

    def test_date_range_today_and_csv_export(self):
        # Today filter excludes the 20-day-old order
        res_today = self.client.get("/api/operations/restaurant/reports/?range=today")
        self.assertEqual(res_today.status_code, 200)
        self.assertEqual(res_today.json()["kpis"]["total_orders"], 2)
        self.assertEqual(res_today.json()["kpis"]["net_revenue"], 1850.0)

        # CSV export returns valid text/csv with expected headers & rows
        csv_res = self.client.get("/api/operations/restaurant/reports/export/?range=all")
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("text/csv", csv_res["Content-Type"])
        body = csv_res.content.decode("utf-8")
        self.assertIn("Order Ref,Date/Time,Customer,Order Type,Channel,Status,Subtotal,Delivery Fee,Total,Est. COGS,Est. Profit,COD Settled", body)
        self.assertIn(self.order_today_pos.order_number, body)
        self.assertNotIn("External", body)

    def test_multi_tenant_isolation_on_reports(self):
        other_client = APIClient()
        other_client.force_authenticate(user=self.other_owner)
        res = other_client.get("/api/operations/restaurant/reports/?range=all")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["kpis"]["total_orders"], 1)
        self.assertEqual(res.json()["kpis"]["net_revenue"], 9999.0)


class RestaurantProductionHardeningTests(TestCase):
    """Production Hardening: Suppliers, Expenses & True Net Profit, Safe Public Recall, Min Rs. 500 Delivery, Rider Contact."""

    def setUp(self):
        from companies.models import CatalogCategory, CatalogItem, Company
        from accounts.models import StaffRole, User
        from operations.models import Order, OrderItem, RestaurantGuestProfile

        self.company = Company.objects.create(
            name="Lahore Tandoor Grill",
            business_type="restaurant",
            subscription_status="active",
            agent_enabled=True,
            min_delivery_order_amount=Decimal("500.00"),
        )
        self.other_company = Company.objects.create(
            name="Other Kitchen",
            business_type="restaurant",
            subscription_status="active",
            agent_enabled=True,
        )
        self.owner = User.objects.create_user(
            username="hardening_owner",
            email="hardening_owner@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.company,
            is_active=True,
        )
        self.other_owner = User.objects.create_user(
            username="hardening_other",
            email="hardening_other@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.other_company,
            is_active=True,
        )

        rider_role = StaffRole.objects.create(
            company=self.company,
            name="Rider",
            is_active=True,
            permissions=["deliveries.view_assigned", "deliveries.update_status"],
        )
        self.rider = User.objects.create_user(
            username="hardening_rider",
            first_name="Kamran",
            last_name="Khan",
            email="kamran@test.com",
            phone="+923009876543",
            password="pass",
            role=User.ROLE_STAFF,
            company=self.company,
            staff_role=rider_role,
            is_active=True,
        )

        cat = CatalogCategory.objects.create(company=self.company, name="Menu")
        self.cheap_item = CatalogItem.objects.create(
            company=self.company,
            category=cat,
            name="Garlic Naan",
            price=Decimal("150.00"),
            is_available=True,
        )
        self.main_item = CatalogItem.objects.create(
            company=self.company,
            category=cat,
            name="Chicken Karahi",
            price=Decimal("1200.00"),
            is_available=True,
        )

        # Returning guest for safe public recall
        RestaurantGuestProfile.objects.create(
            company=self.company,
            phone="923001234567",
            display_phone="+923001234567",
            name="Rubaisha Munir",
            dietary_notes="Extra spicy",
        )
        self.existing_order = Order.objects.create(
            company=self.company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            customer_name="Rubaisha Munir",
            customer_phone="+923001234567",
            delivery_address="House 9, Block C, Gulberg",
            status=Order.STATUS_ASSIGNED,
            assigned_rider=self.rider,
            subtotal=Decimal("1200.00"),
            total=Decimal("1200.00"),
        )
        OrderItem.objects.create(
            order=self.existing_order,
            item=self.main_item,
            item_name="Chicken Karahi",
            quantity=Decimal("1"),
            unit_price=Decimal("1200.00"),
            line_total=Decimal("1200.00"),
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_supplier_crud_and_restock_auto_logs_expense(self):
        from operations.models import RestaurantExpense

        # 1. Create supplier
        s_res = self.client.post(
            "/api/operations/restaurant/suppliers/",
            {
                "name": "Fresh Poultry Farms",
                "contact_person": "Tariq",
                "phone": "+923001110000",
                "category": "Meat",
            },
            format="json",
        )
        self.assertEqual(s_res.status_code, 201)
        sup_id = s_res.json()["id"]

        # 2. Create ingredient linked to supplier
        i_res = self.client.post(
            "/api/operations/restaurant/inventory/",
            {
                "name": "Chicken Breast",
                "unit": "kg",
                "current_stock": "5",
                "cost_per_unit": "600",
                "supplier_id": sup_id,
            },
            format="json",
        )
        self.assertEqual(i_res.status_code, 201)
        ing_id = i_res.json()["id"]
        self.assertEqual(i_res.json()["supplier_id"], sup_id)

        # 3. Restock with purchase_cost=3000 & log_as_expense=True -> auto-creates RestaurantExpense
        adj_res = self.client.post(
            f"/api/operations/restaurant/inventory/{ing_id}/adjust/",
            {
                "movement_type": "stock_in",
                "quantity": 5,
                "supplier_id": sup_id,
                "purchase_cost": 3000,
                "log_as_expense": True,
                "reason": "Morning chicken delivery",
            },
            format="json",
        )
        self.assertEqual(adj_res.status_code, 200)
        exp_id = adj_res.json()["expense_id"]
        self.assertIsNotNone(exp_id)
        exp = RestaurantExpense.objects.get(pk=exp_id, company=self.company)
        self.assertEqual(exp.category, RestaurantExpense.CAT_INVENTORY)
        self.assertEqual(exp.amount, Decimal("3000.00"))
        self.assertEqual(exp.supplier_id, sup_id)

    def test_operating_expenses_and_true_net_profit_in_reports(self):
        # Record Rs. 400 cleaning expense
        exp_res = self.client.post(
            "/api/operations/restaurant/expenses/",
            {
                "title": "Kitchen Cleaning Supplies",
                "category": "cleaning_maintenance",
                "amount": 400,
                "notes": "Soap & sanitizer",
            },
            format="json",
        )
        self.assertEqual(exp_res.status_code, 201)
        exp_id = exp_res.json()["id"]

        # Reports summary: net_revenue=1200, cogs=0, gross_profit=1200, total_expenses=400 -> net_profit=800
        rep = self.client.get("/api/operations/restaurant/reports/?range=all").json()
        self.assertEqual(rep["kpis"]["net_revenue"], 1200.0)
        self.assertEqual(rep["kpis"]["gross_profit"], 1200.0)
        self.assertEqual(rep["kpis"]["total_expenses"], 400.0)
        self.assertEqual(rep["kpis"]["net_profit"], 800.0)

        # Delete expense -> net_profit returns to 1200
        del_res = self.client.delete(f"/api/operations/restaurant/expenses/{exp_id}/")
        self.assertEqual(del_res.status_code, 204)
        rep_after = self.client.get("/api/operations/restaurant/reports/?range=all").json()
        self.assertEqual(rep_after["kpis"]["total_expenses"], 0.0)
        self.assertEqual(rep_after["kpis"]["net_profit"], 1200.0)

    def test_safe_public_phone_recall_and_tenant_isolation(self):
        anon = APIClient()
        url = f"/api/operations/public/agent/{self.company.agent_public_id}/recall/"

        # Exact full phone match -> returns name & address
        res_ok = anon.post(url, {"phone": "03001234567"}, format="json")
        self.assertEqual(res_ok.status_code, 200)
        self.assertTrue(res_ok.json()["found"])
        self.assertEqual(res_ok.json()["name"], "Rubaisha Munir")
        self.assertEqual(res_ok.json()["address"], "House 9, Block C, Gulberg")

        # Partial phone (< 10 digits) -> strictly returns found=False (no PII leak)
        res_partial = anon.post(url, {"phone": "030012"}, format="json")
        self.assertEqual(res_partial.status_code, 200)
        self.assertFalse(res_partial.json()["found"])

        # Cross-tenant agent URL -> cannot recall Company A's guest
        other_url = f"/api/operations/public/agent/{self.other_company.agent_public_id}/recall/"
        res_cross = anon.post(other_url, {"phone": "03001234567"}, format="json")
        self.assertEqual(res_cross.status_code, 200)
        self.assertFalse(res_cross.json()["found"])

    def test_min_delivery_order_amount_500_pos_and_ai(self):
        from operations.whatsapp_agent import execute_create_order

        # 1. POS delivery under Rs. 500 -> HTTP 400
        pos_low = self.client.post(
            "/api/operations/orders/",
            {
                "order_type": "delivery",
                "customer_name": "Test",
                "customer_phone": "+923001112233",
                "delivery_address": "DHA Lahore",
                "items": [{"item_id": self.cheap_item.id, "quantity": 2}],  # Rs. 300
            },
            format="json",
        )
        self.assertEqual(pos_low.status_code, 400)

        # 2. AI delivery under Rs. 500 -> blocked with clear error
        ai_low = execute_create_order(
            company=self.company,
            customer_name="Test",
            customer_phone="+923001112233",
            delivery_address="DHA Lahore",
            items=[{"item_name": "Garlic Naan", "quantity": 2}],  # Rs. 300
            order_type="delivery",
        )
        self.assertFalse(ai_low["success"])
        self.assertIn("500", ai_low["error"])

        # 3. AI delivery >= Rs. 500 -> succeeds
        ai_ok = execute_create_order(
            company=self.company,
            customer_name="Test",
            customer_phone="+923001112233",
            delivery_address="DHA Lahore",
            items=[{"item_name": "Chicken Karahi", "quantity": 1}],  # Rs. 1200
            order_type="delivery",
        )
        self.assertTrue(ai_ok["success"])

        # 4. AI takeaway < Rs. 500 -> allowed (minimum applies to delivery only)
        ai_takeaway = execute_create_order(
            company=self.company,
            customer_name="Test",
            customer_phone="+923001112233",
            delivery_address="",
            items=[{"item_name": "Garlic Naan", "quantity": 1}],  # Rs. 150
            order_type="takeaway",
        )
        self.assertTrue(ai_takeaway["success"])

    def test_delivery_dispatch_returns_rider_and_customer_phones(self):
        res = self.client.get("/api/operations/restaurant/deliveries/")
        self.assertEqual(res.status_code, 200)
        order_row = next(o for o in res.json()["orders"] if o["id"] == self.existing_order.id)
        self.assertEqual(order_row["assigned_rider_phone"], "+923009876543")
        self.assertEqual(order_row["customer_phone"], "+923001234567")

    def test_decimal_kg_ingredient_deduction_and_exact_cogs(self):
        from operations.models import MenuItemRecipe, Order, RestaurantIngredient
        from operations.views import _create_order

        # 5.00 kg Chicken at Rs. 800/kg; recipe uses 0.25 kg per Chicken Karahi -> COGS = Rs. 200.00
        chicken = RestaurantIngredient.objects.create(
            company=self.company,
            name="Boneless Chicken",
            unit="kg",
            current_stock=Decimal("5.000"),
            low_stock_threshold=Decimal("1.000"),
            cost_per_unit=Decimal("800.00"),
        )
        MenuItemRecipe.objects.create(
            company=self.company,
            catalog_item=self.main_item,
            ingredient=chicken,
            quantity_required=Decimal("0.250"),
        )

        # Place order for 1 Chicken Karahi -> deducts exactly 0.25 kg (leaving 4.75 kg)
        new_order = _create_order(
            self.company,
            {
                "order_type": "takeaway",
                "customer_name": "Weight Test",
                "customer_phone": "+923001119999",
                "items": [{"item_id": self.main_item.id, "quantity": 1}],
            },
            actor=self.owner,
            source="dashboard",
        )
        chicken.refresh_from_db()
        self.assertEqual(chicken.current_stock, Decimal("4.750"))

        # Reports COGS includes exact 0.25 * 800 = 200 for both existing_order and new_order (2 x 200 = 400)
        rep = self.client.get("/api/operations/restaurant/reports/?range=all").json()
        self.assertEqual(rep["kpis"]["estimated_cogs"], 400.0)

    def test_customer_to_rider_whatsapp_notification_and_ai_order_tracking(self):
        from unittest.mock import patch
        from operations.notifications import send_order_status_notification
        from operations.whatsapp_agent import execute_check_order_status

        # 1. Verify out_for_delivery WhatsApp notification includes rider name, phone & wa.me link
        self.company.whatsapp_instance_name = "test_inst"
        self.company.save(update_fields=["whatsapp_instance_name"])
        captured_messages = []

        def fake_send_wa(instance_name, phone, to, text, **kwargs):
            captured_messages.append(text)
            return {"success": True}

        with patch("operations.notifications.evolution_client.send_text_message", side_effect=fake_send_wa):
            send_order_status_notification(
                order=self.existing_order,
                previous_status="assigned",
                new_status="out_for_delivery",
            )

        self.assertEqual(len(captured_messages), 1)
        wa_body = captured_messages[0]
        self.assertIn("Kamran Khan", wa_body)
        self.assertIn("+923009876543", wa_body)
        self.assertIn("https://wa.me/923009876543?text=", wa_body)
        self.assertIn(self.existing_order.order_number, wa_body)

        # 2. Verify AI execute_check_order_status returns rider contact + WhatsApp URL
        track = execute_check_order_status(
            company=self.company,
            customer_phone="+923001234567",
            order_number=self.existing_order.order_number,
        )
        self.assertTrue(track["found"])
        latest = track["latest_order"]
        self.assertEqual(latest["assigned_rider_name"], "Kamran Khan")
        self.assertEqual(latest["assigned_rider_phone"], "+923009876543")
        self.assertIn("https://wa.me/923009876543?text=", latest["rider_whatsapp_url"])

    def test_initial_stock_auto_logs_operating_expense_and_updates_net_profit(self):
        from operations.models import RestaurantExpense

        # POST /api/operations/restaurant/inventory/ with 20 kg @ Rs. 350 -> Rs. 7,000 expense
        res = self.client.post(
            "/api/operations/restaurant/inventory/",
            {
                "name": "Mutton Leg",
                "unit": "kg",
                "current_stock": "20",
                "low_stock_threshold": "3",
                "cost_per_unit": "350",
                "log_as_expense": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIsNotNone(data["expense_id"])
        self.assertEqual(data["expense_amount"], 7000.0)

        exp = RestaurantExpense.objects.get(pk=data["expense_id"], company=self.company)
        self.assertEqual(exp.category, RestaurantExpense.CAT_INVENTORY)
        self.assertEqual(exp.amount, Decimal("7000.00"))
        self.assertIn("Initial Stock: Mutton Leg", exp.title)

        # Verify reports deducts Rs. 7,000 from net_profit (gross_profit=1200 - 7000 = -5800)
        rep = self.client.get("/api/operations/restaurant/reports/?range=all").json()
        self.assertEqual(rep["kpis"]["total_expenses"], 7000.0)
        self.assertEqual(rep["kpis"]["net_profit"], -5800.0)


class HospitalModule1Tests(TestCase):
    """Hospital Module 1: Executive Dashboard, Departments, Wards, Live Bed Map & Atomic IPD Admissions."""

    def setUp(self):
        from companies.models import Company
        from accounts.models import User

        self.hospital_a = Company.objects.create(
            name="City Care Hospital",
            business_type="hospital",
            subscription_status="active",
        )
        self.hospital_b = Company.objects.create(
            name="Other Medical Center",
            business_type="hospital",
            subscription_status="active",
        )
        self.owner_a = User.objects.create_user(
            username="hosp_owner_a",
            email="hosp_a@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.hospital_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="hosp_owner_b",
            email="hosp_b@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.hospital_b,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner_a)

    def test_department_ward_auto_beds_atomic_admit_discharge_and_dashboard_kpis(self):
        from operations.models import HospitalAdmission, HospitalBed

        # 1. Create Department
        dept_res = self.client.post(
            "/api/operations/hospital/departments/",
            {
                "name": "Cardiology",
                "code": "CARD",
                "head_of_department": "Dr. Salman",
                "floor_location": "3rd Floor",
                "phone_ext": "301",
                "is_24_7": True,
            },
            format="json",
        )
        self.assertEqual(dept_res.status_code, 201)
        dept_id = dept_res.json()["id"]
        self.assertEqual(dept_res.json()["code"], "CARD")

        # 2. Create Ward with auto_create_beds=4
        ward_res = self.client.post(
            "/api/operations/hospital/wards/",
            {
                "name": "ICU Ward A",
                "department_id": dept_id,
                "ward_type": "icu",
                "daily_bed_rate": "5000.00",
                "floor": "3rd Floor",
                "auto_create_beds": 4,
                "bed_prefix": "ICU",
            },
            format="json",
        )
        self.assertEqual(ward_res.status_code, 201)
        ward_data = ward_res.json()
        self.assertEqual(ward_data["total_beds"], 4)
        self.assertEqual(ward_data["available_beds"], 4)
        bed_numbers = [b["bed_number"] for b in ward_data["beds"]]
        self.assertEqual(bed_numbers, ["ICU-01", "ICU-02", "ICU-03", "ICU-04"])
        bed_1_id = ward_data["beds"][0]["id"]

        # 3. Atomic Bed Admission (available -> occupied)
        adm_res = self.client.post(
            f"/api/operations/hospital/beds/{bed_1_id}/admit/",
            {
                "patient_name": "Bilal Ahmed",
                "patient_phone": "+923001112222",
                "attending_doctor": "Dr. Salman",
                "diagnosis": "Chest Pain Observation",
            },
            format="json",
        )
        self.assertEqual(adm_res.status_code, 201)
        self.assertEqual(adm_res.json()["bed"]["status"], HospitalBed.STATUS_OCCUPIED)
        self.assertEqual(adm_res.json()["admission"]["status"], HospitalAdmission.STATUS_ADMITTED)

        # 4. Double-admission guard returns 409 Conflict
        dup_res = self.client.post(
            f"/api/operations/hospital/beds/{bed_1_id}/admit/",
            {"patient_name": "Another Patient"},
            format="json",
        )
        self.assertEqual(dup_res.status_code, 409)

        # 5. Dashboard KPI accuracy while 1/4 beds occupied
        dash = self.client.get("/api/operations/hospital/dashboard/").json()
        self.assertEqual(dash["kpis"]["total_departments"], 1)
        self.assertEqual(dash["kpis"]["total_wards"], 1)
        self.assertEqual(dash["kpis"]["total_beds"], 4)
        self.assertEqual(dash["kpis"]["occupied_beds"], 1)
        self.assertEqual(dash["kpis"]["available_beds"], 3)
        self.assertEqual(dash["kpis"]["bed_occupancy_pct"], 25.0)
        self.assertEqual(dash["kpis"]["active_admissions_count"], 1)
        self.assertEqual(dash["kpis"]["admissions_today"], 1)

        # 6. Discharge calculates total_bed_charges (>= 1 day * 5000 = 5000) & moves bed to cleaning
        dis_res = self.client.post(
            f"/api/operations/hospital/beds/{bed_1_id}/discharge/",
            {"notes": "Stable, discharged with medication"},
            format="json",
        )
        self.assertEqual(dis_res.status_code, 200)
        self.assertEqual(dis_res.json()["bed"]["status"], HospitalBed.STATUS_CLEANING)
        self.assertEqual(dis_res.json()["stay_days"], 1)
        self.assertEqual(dis_res.json()["total_bed_charges"], 5000.0)
        self.assertEqual(dis_res.json()["admission"]["status"], HospitalAdmission.STATUS_DISCHARGED)

        # 7. Mark cleaning bed back to available
        ready_res = self.client.patch(
            f"/api/operations/hospital/beds/{bed_1_id}/",
            {"status": "available"},
            format="json",
        )
        self.assertEqual(ready_res.status_code, 200)
        self.assertEqual(ready_res.json()["status"], HospitalBed.STATUS_AVAILABLE)

    def test_multi_tenant_isolation_between_hospitals(self):
        # Create ward + beds in Hospital A
        w_res = self.client.post(
            "/api/operations/hospital/wards/",
            {"name": "Private Wing", "ward_type": "private", "auto_create_beds": 2, "bed_prefix": "PVT"},
            format="json",
        )
        self.assertEqual(w_res.status_code, 201)
        bed_id = w_res.json()["beds"][0]["id"]

        # Hospital B cannot see Hospital A's wards/beds or admit into Hospital A's bed
        client_b = APIClient()
        client_b.force_authenticate(user=self.owner_b)

        dash_b = client_b.get("/api/operations/hospital/dashboard/").json()
        self.assertEqual(dash_b["kpis"]["total_wards"], 0)
        self.assertEqual(dash_b["kpis"]["total_beds"], 0)

        wards_b = client_b.get("/api/operations/hospital/wards/").json()
        self.assertEqual(len(wards_b), 0)

        admit_cross = client_b.post(
            f"/api/operations/hospital/beds/{bed_id}/admit/",
            {"patient_name": "Unauthorized"},
            format="json",
        )
        self.assertEqual(admit_cross.status_code, 404)


class HospitalModule2Tests(TestCase):
    """Hospital Module 2: Doctors Directory, Weekly OPD Schedules & Live AI Sync."""

    def setUp(self):
        from companies.models import Company
        from accounts.models import User
        from operations.models import HospitalDepartment

        self.hospital_a = Company.objects.create(
            name="Shifa City Hospital",
            business_type="hospital",
            subscription_status="active",
        )
        self.hospital_b = Company.objects.create(
            name="Other General Hospital",
            business_type="hospital",
            subscription_status="active",
        )
        self.owner_a = User.objects.create_user(
            username="doc_owner_a",
            email="doc_a@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.hospital_a,
            is_active=True,
        )
        self.owner_b = User.objects.create_user(
            username="doc_owner_b",
            email="doc_b@test.com",
            password="pass",
            role=User.ROLE_OWNER,
            company=self.hospital_b,
            is_active=True,
        )
        self.cardio_dept = HospitalDepartment.objects.create(
            company=self.hospital_a,
            name="Cardiology",
            code="CARD",
            is_24_7=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner_a)

    def test_doctor_crud_weekly_schedules_status_toggle_and_ai_sync(self):
        from operations.whatsapp_agent import (
            _build_system_prompt,
            build_hospital_doctors_ai_context,
            get_business_context_for_company,
        )

        # 1. Create doctor with department & mon/wed/fri OPD schedules
        res = self.client.post(
            "/api/operations/hospital/doctors/",
            {
                "full_name": "Dr. Ayesha Khan",
                "department_id": self.cardio_dept.id,
                "specialization": "Cardiologist",
                "qualification": "MBBS, FCPS",
                "consultation_fee": "3000.00",
                "room_number": "OPD Room 4",
                "schedules": [
                    {"day_of_week": "mon", "start_time": "09:00", "end_time": "14:00", "max_patients": 20},
                    {"day_of_week": "wed", "start_time": "09:00", "end_time": "14:00", "max_patients": 20},
                    {"day_of_week": "fri", "start_time": "10:00", "end_time": "13:00", "max_patients": 15},
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        doc_data = res.json()
        doc_id = doc_data["id"]
        self.assertEqual(doc_data["department_name"], "Cardiology")
        self.assertEqual(doc_data["consultation_fee"], 3000.0)
        self.assertEqual(len(doc_data["schedules"]), 3)

        # Dashboard KPIs include total_doctors & doctors_available_today
        dash = self.client.get("/api/operations/hospital/dashboard/").json()
        self.assertEqual(dash["kpis"]["total_doctors"], 1)
        self.assertEqual(dash["kpis"]["doctors_available_today"], 1)

        # 2. Live AI context & system prompt contain doctor details & timings
        ai_block = build_hospital_doctors_ai_context(self.hospital_a)
        self.assertIn("Dr. Ayesha Khan", ai_block)
        self.assertIn("Cardiologist", ai_block)
        self.assertIn("Rs. 3000", ai_block)
        self.assertIn("Mon 09:00-14:00", ai_block)

        ctx = get_business_context_for_company(self.hospital_a)
        prompt = _build_system_prompt(customer_name="Patient", context=ctx)
        self.assertIn("HOSPITAL DOCTORS & OPD SCHEDULE", prompt)
        self.assertIn("Dr. Ayesha Khan", prompt)

        # 3. Quick status toggle: available -> on_leave
        st_res = self.client.post(
            f"/api/operations/hospital/doctors/{doc_id}/status/",
            {"availability_status": "on_leave"},
            format="json",
        )
        self.assertEqual(st_res.status_code, 200)
        self.assertEqual(st_res.json()["availability_status"], "on_leave")

        # AI context now flags [ON LEAVE]
        ai_block_leave = build_hospital_doctors_ai_context(self.hospital_a)
        self.assertIn("[ON LEAVE]", ai_block_leave)

        # 4. Multi-tenant isolation: Hospital B cannot see or edit Hospital A's doctor
        client_b = APIClient()
        client_b.force_authenticate(user=self.owner_b)
        self.assertEqual(len(client_b.get("/api/operations/hospital/doctors/").json()), 0)
        self.assertEqual(
            client_b.patch(f"/api/operations/hospital/doctors/{doc_id}/", {"consultation_fee": 100}, format="json").status_code,
            404,
        )


class HospitalModule3Tests(TestCase):
    """PostgreSQL 16 tests for Hospital Module 3: OPD Appointments, Live Token Queue & AI Booking."""

    def setUp(self):
        from operations.models import HospitalDepartment, HospitalDoctor
        self.client = APIClient()
        self.hospital_a = Company.objects.create(
            name="HospitalCare OPD Alpha",
            business_type="hospital",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_a = User.objects.create_user(
            username="hosp_m3_owner_a",
            email="hosp_m3_a@test.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.hospital_a,
        )
        self.hospital_b = Company.objects.create(
            name="HospitalCare OPD Beta",
            business_type="hospital",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_b = User.objects.create_user(
            username="hosp_m3_owner_b",
            email="hosp_m3_b@test.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.hospital_b,
        )
        self.dept_cardio = HospitalDepartment.objects.create(
            company=self.hospital_a,
            name="Cardiology",
            code="CARD",
            is_active=True,
        )
        self.doc_1 = HospitalDoctor.objects.create(
            company=self.hospital_a,
            department=self.dept_cardio,
            full_name="Dr. Ayesha Khan",
            specialization="Cardiologist",
            consultation_fee=Decimal("2500.00"),
            follow_up_fee=Decimal("1200.00"),
            room_number="OPD Room 4",
            is_active=True,
        )
        self.doc_2 = HospitalDoctor.objects.create(
            company=self.hospital_a,
            department=self.dept_cardio,
            full_name="Dr. Bilal Tariq",
            specialization="Pediatrician",
            consultation_fee=Decimal("1800.00"),
            follow_up_fee=Decimal("900.00"),
            room_number="OPD Room 7",
            is_active=True,
        )
        self.client.force_authenticate(user=self.owner_a)

    def test_atomic_tokens_queue_status_revenue_ai_booking_and_isolation(self):
        from datetime import timedelta
        from operations.models import HospitalAppointment
        from operations.whatsapp_agent import book_hospital_appointment

        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)

        # 1. Atomic sequential token assignment (#1, #2) for doc_1 today
        r1 = self.client.post(
            "/api/operations/hospital/appointments/",
            {
                "doctor_id": self.doc_1.id,
                "patient_name": "Ali Raza",
                "patient_phone": "03001112233",
                "appointment_date": today.isoformat(),
                "visit_type": "new",
                "chief_complaint": "Chest discomfort",
            },
            format="json",
        )
        self.assertEqual(r1.status_code, 201)
        a1 = r1.json()
        self.assertEqual(a1["token_number"], 1)
        self.assertEqual(a1["consultation_fee"], 2500.0)
        self.assertEqual(a1["department_name"], "Cardiology")

        r2 = self.client.post(
            "/api/operations/hospital/appointments/",
            {
                "doctor_id": self.doc_1.id,
                "patient_name": "Sara Ahmed",
                "patient_phone": "03004445566",
                "appointment_date": today.isoformat(),
                "visit_type": "follow_up",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 201)
        a2 = r2.json()
        self.assertEqual(a2["token_number"], 2)
        self.assertEqual(a2["consultation_fee"], 1200.0)  # auto follow_up_fee

        # Token resets to #1 for a different doctor on the same date
        r_doc2 = self.client.post(
            "/api/operations/hospital/appointments/",
            {
                "doctor_id": self.doc_2.id,
                "patient_name": "Hamza Kid",
                "patient_phone": "03112223344",
                "appointment_date": today.isoformat(),
            },
            format="json",
        )
        self.assertEqual(r_doc2.status_code, 201)
        self.assertEqual(r_doc2.json()["token_number"], 1)

        # Token resets to #1 for doc_1 on a different date (tomorrow)
        r_tom = self.client.post(
            "/api/operations/hospital/appointments/",
            {
                "doctor_id": self.doc_1.id,
                "patient_name": "Zainab Tomorrow",
                "patient_phone": "03219998877",
                "appointment_date": tomorrow.isoformat(),
            },
            format="json",
        )
        self.assertEqual(r_tom.status_code, 201)
        self.assertEqual(r_tom.json()["token_number"], 1)

        # 2. Workflow transitions + payment_status='paid' reflected in dashboard today_opd_revenue
        s1 = self.client.post(
            f"/api/operations/hospital/appointments/{a1['id']}/status/",
            {"status": "checked_in", "payment_status": "paid"},
            format="json",
        )
        self.assertEqual(s1.status_code, 200)
        self.assertEqual(s1.json()["status"], "checked_in")
        self.assertEqual(s1.json()["payment_status"], "paid")

        s2 = self.client.post(
            f"/api/operations/hospital/appointments/{a1['id']}/status/",
            {"status": "in_consultation"},
            format="json",
        )
        self.assertEqual(s2.status_code, 200)
        self.assertEqual(s2.json()["status"], "in_consultation")

        # 3. Live OPD Queue shows current_token=1, next_token=2 for doc_1
        q_res = self.client.get(f"/api/operations/hospital/opd-queue/?date={today.isoformat()}")
        self.assertEqual(q_res.status_code, 200)
        q_data = q_res.json()
        doc1_queue = next(q for q in q_data["queues"] if q["doctor_id"] == self.doc_1.id)
        self.assertEqual(doc1_queue["current_token"], 1)
        self.assertEqual(doc1_queue["next_token"], 2)
        self.assertEqual(doc1_queue["waiting_count"], 1)

        # Complete token 1 -> completed_count becomes 1
        s3 = self.client.post(
            f"/api/operations/hospital/appointments/{a1['id']}/status/",
            {"status": "completed"},
            format="json",
        )
        self.assertEqual(s3.status_code, 200)
        self.assertEqual(s3.json()["status"], "completed")

        # Dashboard KPIs include today_appointments, waiting_in_opd, today_opd_revenue
        dash = self.client.get("/api/operations/hospital/dashboard/").json()
        self.assertEqual(dash["kpis"]["today_appointments"], 3)
        self.assertEqual(dash["kpis"]["waiting_in_opd"], 2)
        self.assertEqual(dash["kpis"]["today_opd_revenue"], 2500.0)

        # 4. AI booking helper creates HospitalAppointment with booking_source='whatsapp_ai' & plain text
        ai_res = book_hospital_appointment(
            company=self.hospital_a,
            doctor_name="Cardiology",
            patient_name="Usman Tariq",
            patient_phone="03335556677",
            appointment_date=today.isoformat(),
            visit_type="new",
            chief_complaint="Routine heart check",
            booking_source="whatsapp_ai",
        )
        self.assertTrue(ai_res["success"])
        self.assertEqual(ai_res["token_number"], 3)
        self.assertEqual(ai_res["booking_source"], "whatsapp_ai")
        msg = ai_res["confirmation_message"]
        self.assertIn("Token Number is 3", msg)
        self.assertIn("Dr. Ayesha Khan", msg)
        self.assertNotIn("*", msg)
        self.assertNotIn("_", msg)
        self.assertTrue(
            HospitalAppointment.objects.filter(
                company=self.hospital_a, pk=ai_res["appointment_id"], booking_source="whatsapp_ai"
            ).exists()
        )

        # 5. Multi-tenant isolation: Hospital B cannot view or modify Hospital A's appointments
        client_b = APIClient()
        client_b.force_authenticate(user=self.owner_b)
        b_list = client_b.get("/api/operations/hospital/appointments/").json()
        self.assertEqual(b_list["count"], 0)
        self.assertEqual(
            client_b.patch(f"/api/operations/hospital/appointments/{a1['id']}/", {"payment_status": "unpaid"}, format="json").status_code,
            404,
        )
        self.assertEqual(
            client_b.post(f"/api/operations/hospital/appointments/{a1['id']}/status/", {"status": "cancelled"}, format="json").status_code,
            404,
        )


class HospitalModule4Tests(TestCase):
    """PostgreSQL 16 tests for Hospital Module 4: Patients Directory (EMR) & Digital Prescriptions."""

    def setUp(self):
        from operations.models import HospitalDepartment, HospitalDoctor
        self.client = APIClient()
        self.hospital_a = Company.objects.create(
            name="HospitalCare EMR Alpha",
            business_type="hospital",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_a = User.objects.create_user(
            username="hosp_m4_owner_a",
            email="hosp_m4_a@test.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.hospital_a,
        )
        self.hospital_b = Company.objects.create(
            name="HospitalCare EMR Beta",
            business_type="hospital",
            status=Company.STATUS_ACTIVE,
            payment_status=Company.PAYMENT_OK,
            subscription_status=Company.SUBSCRIPTION_ACTIVE,
        )
        self.owner_b = User.objects.create_user(
            username="hosp_m4_owner_b",
            email="hosp_m4_b@test.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            company=self.hospital_b,
        )
        self.dept = HospitalDepartment.objects.create(
            company=self.hospital_a,
            name="Cardiology",
            code="CARD",
            is_active=True,
        )
        self.doc = HospitalDoctor.objects.create(
            company=self.hospital_a,
            department=self.dept,
            full_name="Dr. Ayesha Khan",
            specialization="Cardiologist",
            qualification="MBBS, FCPS",
            consultation_fee=Decimal("2500.00"),
            room_number="OPD Room 4",
            is_active=True,
        )
        self.client.force_authenticate(user=self.owner_a)

    def test_mrn_generation_patient_360_prescriptions_kpis_and_isolation(self):
        # 1. Sequential atomic MRN generation: MRN-0001, MRN-0002
        p1_res = self.client.post(
            "/api/operations/hospital/patients/",
            {
                "full_name": "Ali Raza",
                "phone": "03001112233",
                "age": 42,
                "gender": "male",
                "blood_group": "B+",
                "allergies": "Penicillin",
                "chronic_conditions": "Hypertension",
            },
            format="json",
        )
        self.assertEqual(p1_res.status_code, 201)
        p1 = p1_res.json()
        self.assertEqual(p1["mrn"], "MRN-0001")
        self.assertEqual(p1["blood_group"], "B+")

        p2_res = self.client.post(
            "/api/operations/hospital/patients/",
            {
                "full_name": "Fatima Noor",
                "phone": "03009998877",
                "age": 31,
                "gender": "female",
                "blood_group": "O+",
            },
            format="json",
        )
        self.assertEqual(p2_res.status_code, 201)
        self.assertEqual(p2_res.json()["mrn"], "MRN-0002")

        # 2. Create OPD appointment matching patient 1's phone so Patient 360° picks it up
        appt_res = self.client.post(
            "/api/operations/hospital/appointments/",
            {
                "doctor_id": self.doc.id,
                "patient_name": "Ali Raza",
                "patient_phone": "03001112233",
                "chief_complaint": "Elevated BP",
            },
            format="json",
        )
        self.assertEqual(appt_res.status_code, 201)

        # 3. Prescription creation with RX-0001, vitals, and structured medications
        rx_res = self.client.post(
            "/api/operations/hospital/prescriptions/",
            {
                "patient_id": p1["id"],
                "doctor_id": self.doc.id,
                "appointment_id": appt_res.json()["id"],
                "vitals": {"bp": "140/90", "pulse": "78", "temp": "98.6 F", "weight": "74 kg"},
                "diagnosis": "Stage 1 Essential Hypertension",
                "medications": [
                    {
                        "name": "Amlodipine 5mg",
                        "dosage": "1 tab",
                        "frequency": "1+0+0",
                        "duration": "30 days",
                        "instructions": "Morning after breakfast",
                    },
                    {
                        "name": "Panadol 500mg",
                        "dosage": "1 tab",
                        "frequency": "1+0+1",
                        "duration": "5 days",
                        "instructions": "If headache",
                    },
                ],
                "lab_tests_advised": "ECG, Lipid Profile",
                "clinical_notes": "Low sodium diet and daily walk.",
            },
            format="json",
        )
        self.assertEqual(rx_res.status_code, 201)
        rx = rx_res.json()
        self.assertEqual(rx["rx_number"], "RX-0001")
        self.assertEqual(rx["vitals"]["bp"], "140/90")
        self.assertEqual(len(rx["medications"]), 2)
        self.assertEqual(rx["hospital"]["name"], "HospitalCare EMR Alpha")

        # Patient 360° EMR detail includes prescriptions + matched appointments
        emr_res = self.client.get(f"/api/operations/hospital/patients/{p1['id']}/")
        self.assertEqual(emr_res.status_code, 200)
        emr = emr_res.json()
        self.assertEqual(emr["mrn"], "MRN-0001")
        self.assertEqual(len(emr["prescriptions"]), 1)
        self.assertEqual(emr["prescriptions"][0]["rx_number"], "RX-0001")
        self.assertEqual(len(emr["appointments"]), 1)

        # 4. Dashboard KPIs reflect total_patients and today_prescriptions
        dash = self.client.get("/api/operations/hospital/dashboard/").json()
        self.assertEqual(dash["kpis"]["total_patients"], 2)
        self.assertEqual(dash["kpis"]["today_prescriptions"], 1)

        # 5. Strict multi-tenant isolation: Hospital B cannot access Hospital A's patients or prescriptions
        client_b = APIClient()
        client_b.force_authenticate(user=self.owner_b)
        self.assertEqual(client_b.get("/api/operations/hospital/patients/").json()["count"], 0)
        self.assertEqual(client_b.get(f"/api/operations/hospital/patients/{p1['id']}/").status_code, 404)
        self.assertEqual(client_b.get("/api/operations/hospital/prescriptions/").json()["count"], 0)
        self.assertEqual(client_b.get(f"/api/operations/hospital/prescriptions/{rx['id']}/").status_code, 404)
