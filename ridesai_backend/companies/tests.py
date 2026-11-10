from django.test import TestCase

# Create your tests here.

from rest_framework.test import APIClient
from accounts.models import User
from .models import Company, BusinessLocation, BusinessHours, ServiceArea, BusinessKnowledge

class BusinessConfigurationIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.a = Company.objects.create(name='Config A', is_approved=True, polar_subscription_id='cfg-a')
        self.b = Company.objects.create(name='Config B', is_approved=True, polar_subscription_id='cfg-b')
        self.owner_a = User.objects.create_user(username='config-owner-a', password='Pass12345!', company=self.a, role=User.ROLE_OWNER)
        self.owner_b = User.objects.create_user(username='config-owner-b', password='Pass12345!', company=self.b, role=User.ROLE_OWNER)

    def test_owner_can_manage_own_location_and_cannot_read_other_tenant(self):
        BusinessLocation.objects.create(company=self.b, name='Private B', address='Private address')
        self.client.force_authenticate(self.owner_a)
        response = self.client.get('/api/companies/locations/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        response = self.client.post('/api/companies/locations/', {'name':'Branch A','address':'Main Road','city':'Wah','country':'Pakistan'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(BusinessLocation.objects.filter(company=self.a).count(), 1)

    def test_service_area_and_knowledge_are_tenant_scoped(self):
        ServiceArea.objects.create(company=self.b, name='B city', area_type='city', city='Wah')
        BusinessKnowledge.objects.create(company=self.b, title='B policy', content='Private')
        self.client.force_authenticate(self.owner_a)
        self.assertEqual(self.client.get('/api/companies/service-areas/').data, [])
        self.assertEqual(self.client.get('/api/companies/knowledge/').data, [])
